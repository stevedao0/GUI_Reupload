"""YouTube downloader using yt-dlp with parallel download support"""
import yt_dlp
import subprocess
import time
import signal
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from dataclasses import dataclass
import json
from ..utils.logger import setup_logger
from ..utils.time_parser import seconds_to_timestamp
from ..utils.ffmpeg_helper import get_ffmpeg_path, get_ffprobe_path

logger = setup_logger(__name__)


@dataclass
class DownloadResult:
    """Result of a download operation"""
    url: str
    success: bool
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    merged_path: Optional[str] = None
    metadata: Optional[Dict] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    duration: Optional[int] = None
    error: Optional[str] = None


class YouTubeDownloader:
    """Download YouTube videos with yt-dlp"""
    
    def __init__(self, config):
        self.config = config
        self.temp_dir = Path(config.get('download.temp_dir', 'temp_downloads'))
        self.temp_dir.mkdir(exist_ok=True)

        # Create subdirectories
        self.video_dir = self.temp_dir / "videos"
        self.audio_dir = self.temp_dir / "audios"
        self.video_dir.mkdir(exist_ok=True)
        self.audio_dir.mkdir(exist_ok=True)

        self.max_parallel = config.get('download.max_parallel', 8)
        self.video_quality = config.get('download.video_quality', '480p')
        self.audio_quality = config.get('download.audio_quality', '128')
        self.concurrent_fragments = config.get('download.concurrent_fragments', 8)
        self.retries = config.get('download.retries', 10)
        self.fragment_retries = config.get('download.fragment_retries', 10)
        self.max_retry_attempts = config.get('download.max_retry_attempts', 3)  # Number of wrapper-level retries
        self.retry_delay_base = config.get('download.retry_delay_base', 2)  # Base delay in seconds (exponential backoff)

        # Cache settings
        self.enable_cache = config.get('download.enable_cache', True)  # Enable file cache/resume
        self.verify_file_size = config.get('download.verify_file_size', True)  # Check file integrity
        self.min_file_size = config.get('download.min_file_size', 1024)  # Minimum valid file size (1KB)

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.corrupted_files = 0
    
    def _verify_file_integrity(self, file_path: Path, file_type: str = "file") -> bool:
        """
        Verify that a downloaded file is valid and not corrupted

        Simple file integrity check - only checks file existence and size
        Does NOT perform deep analysis (ffprobe, audio analysis, etc) to keep cache check
        fast and independent from video/audio processing pipeline

        Args:
            file_path: Path to the file to check
            file_type: Type of file (for logging)

        Returns:
            True if file passes basic integrity checks, False otherwise
        """
        if not file_path.exists():
            return False

        try:
            # Check file size
            file_size = file_path.stat().st_size

            # Minimum file size check
            if file_size < self.min_file_size:
                logger.warning(f"⚠️  {file_type} file too small ({file_size} bytes): {file_path.name}")
                return False

            # Check if file is readable
            with open(file_path, 'rb') as f:
                # Try to read first few bytes to ensure file is not corrupted
                header = f.read(16)
                if len(header) < 16:
                    logger.warning(f"⚠️  {file_type} file appears corrupted (cannot read header): {file_path.name}")
                    return False

            # File type specific minimum size checks (based on typical file sizes)
            if file_type == "video":
                # Video files should be at least 100KB for even a short clip
                if file_size < 100 * 1024:
                    logger.warning(f"⚠️  Video file suspiciously small ({file_size / 1024:.1f} KB): {file_path.name}")
                    return False

            elif file_type == "audio":
                # Audio files should be at least 10KB for even a short clip
                if file_size < 10 * 1024:
                    logger.warning(f"⚠️  Audio file suspiciously small ({file_size / 1024:.1f} KB): {file_path.name}")
                    return False

            # All checks passed
            return True

        except Exception as e:
            logger.warning(f"⚠️  Failed to verify {file_type} file integrity: {e}")
            # On verification error, assume file might be valid (don't delete unnecessarily)
            return True

    def _is_network_error(self, error: Exception) -> bool:
        """Check if error is network-related and can be retried"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        network_keywords = [
            'timeout', 'connection', 'network', 'unreachable',
            'refused', 'reset', 'broken pipe', 'errno', 'socket',
            'http error', '503', '502', '504', '500', '429',
            'temporary failure', 'name resolution', 'dns',
            'ssl', 'certificate', 'handshake'
        ]

        return any(keyword in error_str or keyword in error_type for keyword in network_keywords)
    
    def _get_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info['id']
        except Exception as e:
            logger.error(f"Failed to extract video ID from {url}: {e}")
            # Fallback: extract from URL
            if 'v=' in url:
                return url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                return url.split('youtu.be/')[1].split('?')[0]
            return str(hash(url))[:10]
    
    def _get_format_string(self) -> str:
        """Get format string for yt-dlp based on quality setting"""
        quality_map = {
            '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
            '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
            '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        }
        return quality_map.get(self.video_quality, quality_map['480p'])
    
    def _trim_media(self, input_path: Path, output_path: Path, start_time: int, end_time: int) -> bool:
        """
        Trim media file using ffmpeg
        
        Args:
            input_path: Input file path
            output_path: Output file path
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            start_ts = seconds_to_timestamp(start_time)
            duration = end_time - start_time

            cmd = [
                get_ffmpeg_path(),  # Use bundled or system ffmpeg
                '-loglevel', 'error',  # Only show errors, suppress warnings
                '-i', str(input_path),
                '-ss', start_ts,
                '-t', str(duration),
                '-c', 'copy',  # Copy codec (fast, no re-encoding)
                '-y',  # Overwrite output file
                str(output_path)
            ]
            
            logger.debug(f"Trimming command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully trimmed: {output_path.name}")
                return True
            else:
                # Filter out common non-critical AAC warnings
                stderr_output = result.stderr.decode(errors='ignore')
                # Filter out AAC decoder warnings (these are usually harmless)
                filtered_lines = [
                    line for line in stderr_output.split('\n')
                    if line.strip() and not any(warning in line for warning in [
                        '[aac @', 'Reserved bit set', 'Number of bands', 'exceeds limit'
                    ])
                ]
                filtered_error = '\n'.join(filtered_lines)
                
                if filtered_error.strip():
                    logger.error(f"ffmpeg error: {filtered_error}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to trim media: {e}")
            return False

    def merge_video_audio(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        """
        Merge video and audio files into a single file using ffmpeg

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Path to output merged file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not video_path.exists():
                logger.error(f"Video file not found: {video_path}")
                return False
            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            cmd = [
                get_ffmpeg_path(),
                '-loglevel', 'error',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                str(output_path)
            ]

            logger.info(f"🔧 Merging video + audio: {output_path.name}")

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600
            )

            if result.returncode == 0 and output_path.exists():
                logger.info(f"✅ Successfully merged: {output_path.name}")
                return True
            else:
                stderr_output = result.stderr.decode(errors='ignore')
                logger.error(f"ffmpeg merge error: {stderr_output}")
                return False

        except Exception as e:
            logger.error(f"Failed to merge video+audio: {e}")
            return False

    def download_video(self, url: str, 
                      start_time: Optional[int] = None,
                      end_time: Optional[int] = None,
                      progress_callback: Optional[Callable] = None,
                      retry_attempt: int = 0) -> DownloadResult:
        """
        Download a single video (or segment) with automatic retry for network errors
        
        Args:
            url: YouTube URL
            start_time: Start time in seconds (optional, for segments)
            end_time: End time in seconds (optional, for segments)
            progress_callback: Progress callback function
            retry_attempt: Current retry attempt number (internal use)
            
        Returns:
            DownloadResult with paths and metadata
        """
        video_id = self._get_video_id(url)
        
        # Determine if we need to trim
        is_segment = start_time is not None and end_time is not None
        
        # Create unique identifier for this download to avoid conflicts
        # Use hash of URL to ensure uniqueness even if video_id is the same
        url_hash = str(abs(hash(url)))[:8]
        
        # File paths
        if is_segment:
            video_path = self.video_dir / f"{video_id}_{start_time}_{end_time}.mp4"
            audio_path = self.audio_dir / f"{video_id}_{start_time}_{end_time}.mp3"
            # Use unique temp files to avoid conflicts when same video_id downloaded in parallel
            temp_video_path = self.video_dir / f"{video_id}_{url_hash}_temp.mp4"
            temp_audio_path = self.audio_dir / f"{video_id}_{url_hash}_temp.mp3"
            # Metadata path should match file paths for consistency
            metadata_path = self.temp_dir / f"{video_id}_{start_time}_{end_time}_metadata.json"
        else:
            video_path = self.video_dir / f"{video_id}.mp4"
            audio_path = self.audio_dir / f"{video_id}.mp3"
            # Use unique temp files to avoid conflicts
            temp_video_path = self.video_dir / f"{video_id}_{url_hash}_temp.mp4"
            temp_audio_path = self.audio_dir / f"{video_id}_{url_hash}_temp.mp3"
            # Metadata path should match file paths for consistency
            metadata_path = self.temp_dir / f"{video_id}_metadata.json"
        
        # Check if files already exist (skip download if found and valid)
        if self.enable_cache:
            video_exists = video_path.exists()
            audio_exists = audio_path.exists()
            metadata_exists = metadata_path.exists()

            logger.info(f"🔍 Cache check for {video_id} (segment: {is_segment}):")
            logger.info(f"   Video: {video_path.name} - {'✓ EXISTS' if video_exists else '✗ MISSING'}")
            logger.info(f"   Audio: {audio_path.name} - {'✓ EXISTS' if audio_exists else '✗ MISSING'}")
            logger.info(f"   Metadata: {metadata_path.name} - {'✓ EXISTS' if metadata_exists else '✗ MISSING'}")

            # Verify file integrity if enabled
            video_valid = True
            audio_valid = True

            if self.verify_file_size and video_exists:
                video_valid = self._verify_file_integrity(video_path, "video")
                if not video_valid:
                    logger.warning(f"   ⚠️  Cached video file is corrupted, will re-download")
                    self.corrupted_files += 1
                    # Delete corrupted file
                    try:
                        video_path.unlink()
                        video_exists = False
                    except Exception as e:
                        logger.error(f"   Failed to delete corrupted video: {e}")

            if self.verify_file_size and audio_exists:
                audio_valid = self._verify_file_integrity(audio_path, "audio")
                if not audio_valid:
                    logger.warning(f"   ⚠️  Cached audio file is corrupted, will re-download")
                    self.corrupted_files += 1
                    # Delete corrupted file
                    try:
                        audio_path.unlink()
                        audio_exists = False
                    except Exception as e:
                        logger.error(f"   Failed to delete corrupted audio: {e}")

            if video_exists and audio_exists and video_valid and audio_valid:
                # Cache hit! Files are valid and ready to use
                self.cache_hits += 1

                # If both files exist, we can skip download even without metadata
                # Try to load metadata if available, otherwise create minimal metadata
                existing_metadata = None
                if metadata_exists:
                    try:
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            existing_metadata = json.load(f)
                        logger.info(f"✅ CACHE HIT! Using cached files with metadata for {video_id}")
                        logger.info(f"   📂 Video: {video_path.name} ({video_path.stat().st_size / 1024 / 1024:.2f} MB)")
                        logger.info(f"   🎵 Audio: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.2f} MB)")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to load cached metadata: {e}")
                        logger.info(f"   Will create minimal metadata from existing files")
                else:
                    logger.info(f"✅ CACHE HIT! Files exist, creating metadata for {video_id}")

                # Create minimal metadata if not available
                if not existing_metadata:
                    # Extract basic info from yt-dlp without downloading
                    try:
                        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                            info = ydl.extract_info(url, download=False)
                            existing_metadata = {
                                'id': info.get('id', video_id),
                                'title': info.get('title', ''),
                                'uploader': info.get('uploader', ''),
                                'upload_date': info.get('upload_date', ''),
                                'duration': end_time - start_time if is_segment else info.get('duration', 0),
                                'url': url
                            }
                        # Save metadata for next time
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(existing_metadata, f, ensure_ascii=False, indent=2)
                        logger.info(f"   ✓ Created and saved metadata")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to extract metadata: {e}")
                        # Use minimal fallback metadata
                        existing_metadata = {
                            'id': video_id,
                            'title': '',
                            'uploader': '',
                            'upload_date': '',
                            'duration': end_time - start_time if is_segment else 0,
                            'url': url
                        }

                return DownloadResult(
                    url=url,
                    success=True,
                    video_path=str(video_path),
                    audio_path=str(audio_path),
                    metadata=existing_metadata,
                    start_time=start_time,
                    end_time=end_time,
                    duration=existing_metadata.get('duration', None)
                )
            else:
                # Cache miss - need to download
                self.cache_misses += 1
                logger.info(f"⬇️  CACHE MISS - Downloading {video_id}...")
        
        try:
            # Progress hook
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # Extract progress info
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    # Format speed
                    if speed:
                        speed_mb = speed / 1024 / 1024
                        speed_str = f"{speed_mb:.2f} MB/s"
                    else:
                        speed_str = "N/A"
                    
                    # Format percentage
                    if total > 0:
                        percent = (downloaded / total) * 100
                        percent_str = f"{percent:.1f}%"
                    else:
                        percent_str = "N/A"
                    
                    # Format ETA
                    if eta:
                        eta_min = eta // 60
                        eta_sec = eta % 60
                        eta_str = f"{eta_min:02d}:{eta_sec:02d}"
                    else:
                        eta_str = "N/A"
                    
                    # Log progress
                    logger.info(f"📥 {video_id}: {percent_str} | Speed: {speed_str} | ETA: {eta_str}")
                    
                    # Call external callback if provided
                    if progress_callback:
                        progress_callback({
                            'video_id': video_id,
                            'percent': percent if total > 0 else 0,
                            'speed': speed,
                            'eta': eta,
                            'downloaded': downloaded,
                            'total': total
                        })
                
                elif d['status'] == 'finished':
                    logger.info(f"✓ {video_id}: Download complete, processing...")
            
            # Download video
            video_opts = {
                'format': self._get_format_string(),
                'outtmpl': str(temp_video_path.with_suffix('')),
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [progress_hook],
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ffmpeg_location': get_ffmpeg_path(),
                'concurrent_fragment_downloads': self.concurrent_fragments,
                'retries': self.retries,
                'fragment_retries': self.fragment_retries,
                'http_chunk_size': 10485760,
                'buffersize': 1024 * 1024 * 4,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'postprocessor_args': {
                    'ffmpeg': [
                        '-threads', '4',
                        '-preset', 'ultrafast',
                        '-movflags', '+faststart',
                        '-hide_banner',
                        '-loglevel', 'warning',
                        '-y'
                    ]
                },
            }
            
            if is_segment:
                logger.info(f"Downloading video segment ({start_time}s-{end_time}s): {url}")
            else:
                logger.info(f"Downloading video: {url}")

            # Download with timeout using ThreadPoolExecutor
            download_timeout = 600  # 10 minutes max per video
            executor = ThreadPoolExecutor(max_workers=1)

            def download_video_task():
                with yt_dlp.YoutubeDL(video_opts) as ydl:
                    return ydl.extract_info(url, download=True)

            try:
                logger.info(f"⏱️  Starting video download (timeout: {download_timeout}s)...")
                future = executor.submit(download_video_task)
                info = future.result(timeout=download_timeout)

                metadata = {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'description': info.get('description', '')[:500],
                    'thumbnail': info.get('thumbnail'),
                }
            except TimeoutError:
                logger.error(f"❌ Video download timeout after {download_timeout}s for {video_id}")
                logger.warning(f"⚠️  FFmpeg conversion may be stuck. Skipping this video.")
                raise Exception(f"Download timeout after {download_timeout}s")
            finally:
                executor.shutdown(wait=False)
            
            # Download audio separately
            def audio_progress_hook(d):
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    speed = d.get('speed', 0)
                    
                    if speed:
                        speed_mb = speed / 1024 / 1024
                        speed_str = f"{speed_mb:.2f} MB/s"
                    else:
                        speed_str = "N/A"
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                        logger.info(f"🎵 {video_id} Audio: {percent:.1f}% | Speed: {speed_str}")
                
                elif d['status'] == 'finished':
                    logger.info(f"✓ {video_id}: Audio download complete")
            
            audio_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(temp_audio_path.with_suffix('')),
                'quiet': False,
                'no_warnings': False,  # Allow warnings (they're filtered by logger)
                'progress_hooks': [audio_progress_hook],
                # FFmpeg location (bundled or system)
                'ffmpeg_location': get_ffmpeg_path(),
                # Speed optimization
                'concurrent_fragment_downloads': self.concurrent_fragments,
                'retries': self.retries,
                'fragment_retries': self.fragment_retries,
                'http_chunk_size': 10485760,  # 10MB chunks
                'buffersize': 1024 * 1024 * 4,  # 4MB buffer
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': self.audio_quality,
                }],
            }

            logger.info(f"🎵 Downloading audio...")

            # Audio download with timeout
            audio_executor = ThreadPoolExecutor(max_workers=1)
            audio_timeout = 300  # 5 minutes for audio

            def download_audio_task():
                with yt_dlp.YoutubeDL(audio_opts) as ydl:
                    ydl.download([url])

            try:
                logger.info(f"⏱️  Starting audio download (timeout: {audio_timeout}s)...")
                audio_future = audio_executor.submit(download_audio_task)
                audio_future.result(timeout=audio_timeout)
            except TimeoutError:
                logger.error(f"❌ Audio download timeout after {audio_timeout}s for {video_id}")
                logger.warning(f"⚠️  Skipping this video due to audio timeout.")
                raise Exception(f"Audio download timeout after {audio_timeout}s")
            finally:
                audio_executor.shutdown(wait=False)
            
            # Trim if segment
            if is_segment:
                logger.info(f"Trimming segment: {start_time}s to {end_time}s")
                
                # Trim video
                if not self._trim_media(temp_video_path, video_path, start_time, end_time):
                    raise Exception("Failed to trim video")
                
                # Trim audio
                if not self._trim_media(temp_audio_path, audio_path, start_time, end_time):
                    raise Exception("Failed to trim audio")
                
                # Clean up temp files
                if temp_video_path.exists() and temp_video_path != video_path:
                    temp_video_path.unlink()
                if temp_audio_path.exists() and temp_audio_path != audio_path:
                    temp_audio_path.unlink()
            
            # Save metadata
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            duration = end_time - start_time if is_segment else metadata.get('duration')

            logger.info(f"Successfully downloaded: {metadata.get('title')}")

            # Merge video + audio into single file
            merged_path = None
            if video_path.exists() and audio_path.exists():
                if is_segment:
                    merged_filename = f"{video_id}_{start_time}_{end_time}_merged.mp4"
                else:
                    merged_filename = f"{video_id}_merged.mp4"

                merged_path = self.temp_dir / merged_filename

                logger.info(f"🔧 Merging video + audio into: {merged_filename}")
                if self.merge_video_audio(video_path, audio_path, merged_path):
                    logger.info(f"✅ Merge successful: {merged_filename}")
                else:
                    logger.warning(f"⚠️  Merge failed, keeping separate files")
                    merged_path = None

            return DownloadResult(
                url=url,
                success=True,
                video_path=str(video_path),
                audio_path=str(audio_path),
                merged_path=str(merged_path) if merged_path else None,
                metadata=metadata,
                start_time=start_time,
                end_time=end_time,
                duration=duration
            )
            
        except Exception as e:
            error_str = str(e)
            is_network_error = self._is_network_error(e)
            
            # Retry logic for network errors
            if is_network_error and retry_attempt < self.max_retry_attempts:
                retry_delay = self.retry_delay_base * (2 ** retry_attempt)  # Exponential backoff
                logger.warning(f"⚠ Network error for {url}: {error_str}")
                logger.info(f"🔄 Retrying in {retry_delay}s... (Attempt {retry_attempt + 1}/{self.max_retry_attempts})")
                
                time.sleep(retry_delay)
                
                # Retry download
                return self.download_video(
                    url=url,
                    start_time=start_time,
                    end_time=end_time,
                    progress_callback=progress_callback,
                    retry_attempt=retry_attempt + 1
                )
            else:
                # Max retries reached or non-network error
                if is_network_error:
                    logger.error(f"❌ Failed to download {url} after {retry_attempt + 1} attempts: {error_str}")
                else:
                    logger.error(f"❌ Failed to download {url}: {error_str}")
                
                return DownloadResult(
                    url=url,
                    success=False,
                    error=error_str
                )
    
    def download_batch(self, urls: List[str], 
                      progress_callback: Optional[Callable] = None) -> List[DownloadResult]:
        """Download multiple videos in parallel"""
        logger.info(f"Starting batch download of {len(urls)} videos")
        logger.info(f"Using {self.max_parallel} parallel threads")
        
        results = []
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {
                executor.submit(self.download_video, url, progress_callback): url 
                for url in urls
            }
            
            for future in as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if progress_callback:
                        progress_callback({
                            'status': 'finished',
                            'url': url,
                            'success': result.success
                        })
                        
                except Exception as e:
                    logger.error(f"Exception during download of {url}: {e}")
                    results.append(DownloadResult(
                        url=url,
                        success=False,
                        error=str(e)
                    ))
        
        successful = sum(1 for r in results if r.success)
        logger.info(f"Batch download complete: {successful}/{len(urls)} successful")
        
        return results
    
    def download_batch_with_segments(self,
                                     tasks: List[Dict],
                                     progress_callback: Optional[Callable] = None,
                                     is_cancelled: Optional[Callable[[], bool]] = None) -> List[DownloadResult]:
        """
        Download multiple videos with segment support

        Args:
            tasks: List of dicts with 'url', 'start_time', 'end_time', 'metadata'
            progress_callback: Progress callback function
            is_cancelled: Callback returning True if processing should stop

        Returns:
            List of DownloadResults
        """
        logger.info(f"Starting batch download of {len(tasks)} videos/segments")
        logger.info(f"Using {self.max_parallel} parallel threads")
        logger.info(f"Retry settings: max_attempts={self.max_retry_attempts}, retries={self.retries}, fragment_retries={self.fragment_retries}")

        results = []
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {}
            for task in tasks:
                if is_cancelled and is_cancelled():
                    logger.warning("Download cancelled before starting all tasks")
                    break

                future = executor.submit(
                    self.download_video,
                    task['url'],
                    task.get('start_time'),
                    task.get('end_time'),
                    progress_callback,
                    retry_attempt=0  # Start with first attempt
                )
                futures[future] = task

            for future in as_completed(futures):
                if is_cancelled and is_cancelled():
                    logger.warning("Download cancelled - stopping early")
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break
                task = futures[future]
                url = task['url']
                try:
                    result = future.result()
                    results.append(result)
                    
                    if progress_callback:
                        progress_callback({
                            'status': 'finished',
                            'url': url,
                            'success': result.success
                        })
                        
                except Exception as e:
                    logger.error(f"Exception during download of {url}: {e}")
                    results.append(DownloadResult(
                        url=url,
                        success=False,
                        error=str(e)
                    ))
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"Batch download complete: {successful}/{len(tasks)} successful, {failed} failed")
        
        # Log failed downloads for potential manual retry
        if failed > 0:
            failed_urls = [r.url for r in results if not r.success]
            logger.warning(f"⚠ Failed downloads: {failed_urls}")
        
        return results
    
    def retry_failed_downloads(self, 
                             failed_results: List[DownloadResult],
                             progress_callback: Optional[Callable] = None) -> List[DownloadResult]:
        """
        Retry failed downloads (useful for network errors)
        
        Args:
            failed_results: List of failed DownloadResults
            progress_callback: Progress callback function
            
        Returns:
            List of DownloadResults (only retried ones)
        """
        if not failed_results:
            logger.info("No failed downloads to retry")
            return []
        
        # Filter network errors
        network_failures = [
            r for r in failed_results 
            if r.error and self._is_network_error(Exception(r.error))
        ]
        
        if not network_failures:
            logger.info("No network-related failures to retry")
            return []
        
        logger.info(f"🔄 Retrying {len(network_failures)} failed downloads...")
        
        # Convert to tasks
        tasks = []
        for result in network_failures:
            tasks.append({
                'url': result.url,
                'start_time': result.start_time,
                'end_time': result.end_time,
                'metadata': {}
            })
        
        # Retry downloads
        retry_results = self.download_batch_with_segments(tasks, progress_callback)
        
        successful_retries = sum(1 for r in retry_results if r.success)
        logger.info(f"✓ Retry complete: {successful_retries}/{len(network_failures)} successful")
        
        return retry_results
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'corrupted_files': self.corrupted_files,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2)
        }

    def log_cache_stats(self):
        """Log cache statistics"""
        stats = self.get_cache_stats()
        logger.info("=" * 60)
        logger.info("📊 CACHE STATISTICS:")
        logger.info(f"   ✅ Cache Hits:       {stats['cache_hits']}")
        logger.info(f"   ⬇️  Cache Misses:     {stats['cache_misses']}")
        logger.info(f"   ⚠️  Corrupted Files:  {stats['corrupted_files']}")
        logger.info(f"   📈 Cache Hit Rate:   {stats['hit_rate_percent']}%")
        logger.info(f"   🎯 Total Requests:   {stats['total_requests']}")
        logger.info("=" * 60)

    def cleanup(self, keep_files: bool = True):
        """
        Clean up downloaded files

        SAFETY FIRST: Files are kept by default to enable cache/resume functionality
        Only deletes files when explicitly requested (keep_files=False)

        Args:
            keep_files: If True, keep all downloaded files (default: True for resume capability)
                       If False, delete all files in temp directory

        WARNING: Setting keep_files=False will permanently delete ALL cached files!
        """
        if not keep_files:
            if self.temp_dir.exists():
                # Count files before deletion (for logging)
                try:
                    video_count = len(list(self.video_dir.glob('*.mp4'))) if self.video_dir.exists() else 0
                    audio_count = len(list(self.audio_dir.glob('*.mp3'))) if self.audio_dir.exists() else 0
                    total_files = video_count + audio_count

                    logger.warning("=" * 60)
                    logger.warning("⚠️  WARNING: DELETING ALL DOWNLOADED FILES!")
                    logger.warning(f"   📁 Location: {self.temp_dir.absolute()}")
                    logger.warning(f"   📹 Videos: {video_count} files")
                    logger.warning(f"   🎵 Audio: {audio_count} files")
                    logger.warning(f"   📊 Total: {total_files} files")
                    logger.warning("   This action CANNOT be undone!")
                    logger.warning("=" * 60)

                    # Delete the entire temp directory
                    import shutil
                    shutil.rmtree(self.temp_dir)

                    logger.info(f"✓ Cleanup complete - {total_files} files deleted")
                except Exception as e:
                    logger.error(f"❌ Failed to cleanup files: {e}")
            else:
                logger.info("⚠️  Cleanup requested but temp directory doesn't exist")
        else:
            # Keep files - just log the status
            if self.temp_dir.exists():
                try:
                    video_count = len(list(self.video_dir.glob('*.mp4'))) if self.video_dir.exists() else 0
                    audio_count = len(list(self.audio_dir.glob('*.mp3'))) if self.audio_dir.exists() else 0
                    total_files = video_count + audio_count

                    logger.info("=" * 60)
                    logger.info("✅ KEEPING downloaded files for cache/resume")
                    logger.info(f"   📁 Location: {self.temp_dir.absolute()}")
                    logger.info(f"   📹 Videos: {video_count} files")
                    logger.info(f"   🎵 Audio: {audio_count} files")
                    logger.info(f"   📊 Total: {total_files} files cached")
                    logger.info("   💡 Tip: These files will be reused on next run (faster!)")
                    logger.info("=" * 60)
                except Exception as e:
                    logger.warning(f"⚠️  Could not count cached files: {e}")
                    logger.info(f"✅ Keeping downloaded files at: {self.temp_dir.absolute()}")
            else:
                logger.info("✅ Cache enabled - files will be saved to: {self.temp_dir.absolute()}")

