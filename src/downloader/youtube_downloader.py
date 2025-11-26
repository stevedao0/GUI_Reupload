"""YouTube downloader using yt-dlp with parallel download support"""
import yt_dlp
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        
        # Check if files already exist (skip download if found)
        # Log file existence check for debugging
        video_exists = video_path.exists()
        audio_exists = audio_path.exists()
        metadata_exists = metadata_path.exists()
        
        logger.info(f"🔍 Checking existing files for {video_id} (segment: {is_segment}):")
        logger.info(f"   Video: {video_path.name} - {'✓ EXISTS' if video_exists else '✗ MISSING'}")
        logger.info(f"   Audio: {audio_path.name} - {'✓ EXISTS' if audio_exists else '✗ MISSING'}")
        logger.info(f"   Metadata: {metadata_path.name} - {'✓ EXISTS' if metadata_exists else '✗ MISSING'}")
        
        if video_exists and audio_exists:
            # If both files exist, we can skip download even without metadata
            # Try to load metadata if available, otherwise create minimal metadata
            existing_metadata = None
            if metadata_exists:
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        existing_metadata = json.load(f)
                    logger.info(f"⏭️  Skipping download for {video_id}: all files exist (with metadata)")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to load existing metadata for {video_id}: {e}")
                    logger.info(f"   Will create minimal metadata from existing files")
            else:
                logger.info(f"⏭️  Skipping download for {video_id}: files exist (no metadata, will create)")
            
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
            
            logger.info(f"   Video: {video_path.name}, Audio: {audio_path.name}")
            
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
                'quiet': False,  # Show progress
                'no_warnings': False,  # Allow warnings (they're filtered by logger)
                'progress_hooks': [progress_hook],
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                # FFmpeg location (bundled or system)
                'ffmpeg_location': get_ffmpeg_path(),
                # Speed optimization
                'concurrent_fragment_downloads': self.concurrent_fragments,
                'retries': self.retries,
                'fragment_retries': self.fragment_retries,
                'http_chunk_size': 10485760,  # 10MB chunks
                'buffersize': 1024 * 1024 * 4,  # 4MB buffer
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            }
            
            if is_segment:
                logger.info(f"Downloading video segment ({start_time}s-{end_time}s): {url}")
            else:
                logger.info(f"Downloading video: {url}")
                
            with yt_dlp.YoutubeDL(video_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                metadata = {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'description': info.get('description', '')[:500],  # First 500 chars
                    'thumbnail': info.get('thumbnail'),
                }
            
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
            with yt_dlp.YoutubeDL(audio_opts) as ydl:
                ydl.download([url])
            
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
            
            return DownloadResult(
                url=url,
                success=True,
                video_path=str(video_path),
                audio_path=str(audio_path),
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
    
    def cleanup(self, keep_files: bool = False):
        """Clean up downloaded files"""
        if not keep_files and self.temp_dir.exists():
            logger.info("Cleaning up temporary files...")
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info("Cleanup complete")

