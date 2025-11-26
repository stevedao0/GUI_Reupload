"""Main processing pipeline that orchestrates all components"""
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Callable, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..downloader import YouTubeDownloader, DownloadResult
from ..analysis import AudioAnalyzer, VideoAnalyzer, KaraokeDetector
from ..detection import ReuploadDetector
from ..utils.logger import setup_logger
from ..utils.time_parser import get_segment_info

logger = setup_logger(__name__)


class ProcessingPipeline:
    """Main pipeline for processing videos and detecting reuploads"""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize components
        logger.info("Initializing pipeline components...")
        
        self.downloader = YouTubeDownloader(config)
        self.audio_analyzer = AudioAnalyzer(config)
        self.video_analyzer = VideoAnalyzer(config)
        self.karaoke_detector = KaraokeDetector(config)
        self.reupload_detector = ReuploadDetector(config)
        
        logger.info("Pipeline initialized successfully")
    
    def process(self,
               urls: List[str],
               metadata: List[Dict],
               progress_callback: Optional[Callable] = None,
               log_callback: Optional[Callable] = None,
               is_cancelled: Optional[Callable[[], bool]] = None) -> Dict:
        """
        Main processing pipeline
        
        Args:
            urls: List of YouTube URLs
            metadata: List of metadata dicts for each URL
            progress_callback: Callback for progress updates (current, total, status)
            log_callback: Callback for log messages
            is_cancelled: Optional callback returning True if processing should stop early
        
        Returns:
            Dict with results including clusters, statistics, etc.
        """
        
        def update_progress(current, total, status):
            if progress_callback:
                progress_callback(current, total, status)
        
        def log(message):
            if log_callback:
                log_callback(message)
            logger.info(message)

        def should_cancel() -> bool:
            return bool(is_cancelled and is_cancelled())
        
        try:
            if should_cancel():
                log("Processing cancelled before start of pipeline")
                raise RuntimeError("Processing cancelled by user")

            total_steps = 6
            current_step = 0
            
            # Step 1: Prepare segments and download videos
            current_step += 1
            update_progress(current_step, total_steps, "Downloading videos...")
            log(f"Step {current_step}/{total_steps}: Downloading {len(urls)} videos...")
            
            # Parse time ranges from metadata
            download_tasks = []
            for url, meta in zip(urls, metadata):
                if should_cancel():
                    log("Cancellation requested while preparing download tasks - stopping early")
                    raise RuntimeError("Processing cancelled by user")
                # Extract time range from metadata
                time_range = meta.get('Thoi gian') or meta.get('Thời gian') or meta.get('Time Range')
                
                # Get segment info
                start, end, duration = get_segment_info(url, time_range)

                # Safe string for URL logging (handles non-string/NaN values from Excel)
                url_str = url if isinstance(url, str) else str(url)
                url_preview = url_str[:20]

                if end is not None:
                    log(f"  Segment: {meta.get('ID Video', url_preview)} - {start}s to {end}s ({duration}s)")
                else:
                    log(f"  Full video: {meta.get('ID Video', url_preview)}")
                
                download_tasks.append({
                    'url': url,
                    'start_time': start if end is not None else None,
                    'end_time': end,
                    'metadata': meta
                })
            
            # Download with segments
            if should_cancel():
                log("Processing cancelled before download step")
                raise RuntimeError("Processing cancelled by user")

            download_results = self.downloader.download_batch_with_segments(download_tasks, is_cancelled=is_cancelled)
            successful_downloads = [r for r in download_results if r.success]
            
            log(f"✓ Downloaded {len(successful_downloads)}/{len(urls)} videos successfully")
            
            if not successful_downloads:
                raise ValueError("No videos downloaded successfully")
            
            # Prepare paths and metadata
            # Map back to original metadata from download_tasks
            url_to_task = {task['url']: task for task in download_tasks}
            
            # IMPORTANT: Preserve original order from Excel by mapping downloads back to original order
            # Create a mapping: url -> (download_result, original_index)
            url_to_result = {r.url: (r, i) for i, r in enumerate(successful_downloads)}
            
            # Reconstruct in original Excel order
            video_paths = []
            audio_paths = []
            video_urls = []
            video_metadata = []
            
            # Sort by original order (use STT if available, otherwise by index in download_tasks)
            for original_idx, task in enumerate(download_tasks):
                url = task['url']
                if url in url_to_result:
                    r, _ = url_to_result[url]
                    video_paths.append(r.video_path)
                    audio_paths.append(r.audio_path)
                    video_urls.append(r.url)
                    
                    # Get original metadata from Excel (preserve order)
                    original_meta = task['metadata'].copy()
                    # Merge with YouTube metadata
                    if r.metadata:
                        original_meta.update(r.metadata)
                    # Ensure STT is preserved
                    if 'STT' not in original_meta and 'ST' in original_meta:
                        original_meta['STT'] = original_meta['ST']
                    elif 'STT' not in original_meta:
                        original_meta['STT'] = original_idx + 1
                    video_metadata.append(original_meta)
            
            # Step 2: Group by Code FIRST (before similarity matrix calculation for optimization)
            current_step += 1
            update_progress(current_step, total_steps, "Grouping by Code...")
            log(f"Step {current_step}/{total_steps}: Grouping videos by Code for optimized processing...")
            
            # Group by Code - only compare reuploads within the same Code
            code_groups = {}
            
            for idx, meta in enumerate(video_metadata):
                code = str(meta.get('Code', '')).strip()
                if not code:
                    code = 'UNKNOWN'  # Default code if missing
                
                if code not in code_groups:
                    code_groups[code] = []
                
                code_groups[code].append(idx)
            
            log(f"✓ Found {len(code_groups)} Code groups: {list(code_groups.keys())}")
            total_comparisons = 0
            for code, indices in code_groups.items():
                n = len(indices)
                comparisons = n * (n - 1) // 2 if n > 1 else 0
                total_comparisons += comparisons
                log(f"  Code {code}: {n} videos → {comparisons} comparisons")
            log(f"  Total comparisons: {total_comparisons} (vs {len(video_paths) * (len(video_paths) - 1) // 2} if not grouped)")
            
            # Determine types EARLY to skip unnecessary video extraction for Audio rows
            early_types = []
            for meta in video_metadata:
                t = str(meta.get('Type') or meta.get('type') or '').strip().lower()
                early_types.append(t)
            non_audio_indices = [i for i, t in enumerate(early_types) if t not in ['audio', 'âm thanh']]
            non_audio_video_paths = [video_paths[i] for i in non_audio_indices]

            # Step 3: Extract features (skip video features for Audio items)
            current_step += 1
            update_progress(current_step, total_steps, "Extracting features...")
            log(f"Step {current_step}/{total_steps}: Extracting audio and video features (skip video for Audio types)...")

            if should_cancel():
                log("Processing cancelled before feature extraction")
                raise RuntimeError("Processing cancelled by user")
            
            audio_features = self.audio_analyzer.batch_extract_features(audio_paths, is_cancelled=is_cancelled)
            if should_cancel():
                log("Processing cancelled during audio feature extraction")
                raise RuntimeError("Processing cancelled by user")

            video_features = {}
            if len(non_audio_video_paths) > 0:
                video_features = self.video_analyzer.batch_extract_features(non_audio_video_paths, is_cancelled=is_cancelled)
                if should_cancel():
                    log("Processing cancelled during video feature extraction")
                    raise RuntimeError("Processing cancelled by user")
                log(f"✓ Extracted video features for {len(non_audio_video_paths)}/{len(video_paths)} non-Audio videos")
            else:
                log("✓ Skipped video feature extraction (all rows are Audio)")
            
            log(f"✓ Audio features extracted for all videos")
            
            # Step 4: Get video types from Excel metadata (user-provided)
            current_step += 1
            update_progress(current_step, total_steps, "Loading video types...")
            log(f"Step {current_step}/{total_steps}: Reading video types from metadata...")
            
            # Extract video types from metadata (user has already classified)
            video_types = []
            for meta in video_metadata:
                # Check multiple possible column names
                vtype = (meta.get('Type') or 
                        meta.get('type') or 
                        meta.get('Hình thức sử dụng') or
                        meta.get('Loại') or
                        meta.get('Category') or
                        'Unknown')
                video_types.append(str(vtype).strip())
            
            log(f"✓ Video types loaded from metadata")
            
            # Log video type distribution
            type_counts = {}
            for vtype in video_types:
                type_counts[vtype] = type_counts.get(vtype, 0) + 1
            log(f"Video type distribution: {type_counts}")
            
            # Step 5: Calculate similarity matrices ONLY for each Code group (optimized + parallel)
            current_step += 1
            update_progress(current_step, total_steps, "Calculating similarities...")
            log(f"Step {current_step}/{total_steps}: Calculating similarity matrices per Code group (parallel)...")

            if should_cancel():
                log("Processing cancelled before similarity calculation")
                raise RuntimeError("Processing cancelled by user")
            
            # Get max workers for parallel processing (limit to avoid overhead)
            max_workers = self.config.get('processing.max_code_group_workers', 8)
            # Limit max workers to reasonable number (too many threads = overhead)
            max_workers = min(max_workers, len(code_groups), 16)  # Max 16 threads
            
            log(f"Using {max_workers} parallel workers for {len(code_groups)} Code groups")
            
            # Helper function to process a single Code group
            def process_code_group(code: str, indices: List[int]) -> tuple:
                """Process a single Code group and return (code, clusters)"""
                try:
                    if should_cancel():
                        raise RuntimeError("Processing cancelled by user")

                    if len(indices) < 2:
                        return (code, [])
                    
                    # Extract paths, URLs, metadata, types for this Code group
                    code_audio_paths = [audio_paths[i] for i in indices]
                    code_video_paths = [video_paths[i] for i in indices]
                    code_urls = [video_urls[i] for i in indices]
                    code_metadata = [video_metadata[i] for i in indices]
                    code_types = [video_types[i] for i in indices]
                    
                    # Extract features for this Code group only
                    code_audio_features = {}
                    code_video_features = {}
                    for path in code_audio_paths:
                        if path in audio_features:
                            code_audio_features[path] = audio_features[path]
                    # Only include video features for non-Audio rows in this group
                    for path, vtype in zip(code_video_paths, code_types):
                        if str(vtype).strip().lower() in ['audio', 'âm thanh']:
                            continue
                        if path in video_features:
                            code_video_features[path] = video_features[path]
                    
                    if len(code_audio_features) < 2:
                        return (code, [])
                    
                    # Calculate similarity matrices ONLY for this Code group (much faster!)
                    code_audio_matrix, code_audio_paths_ordered = self.audio_analyzer.create_similarity_matrix(code_audio_features)
                    # Build video matrix only if we have >= 2 non-audio videos in this code group
                    if len(code_video_features) >= 2:
                        code_video_matrix, code_video_paths_ordered = self.video_analyzer.create_similarity_matrix(code_video_features)
                    else:
                        import numpy as np
                        code_video_matrix = np.zeros((0, 0))
                        code_video_paths_ordered = []
                    
                    # Derive singer count per video (AFTER ordering, to match audio_paths_ordered)
                    code_singer_counts = []
                    for path in code_audio_paths_ordered:
                        features = audio_features.get(path)
                        if features is not None and hasattr(features, 'num_singers_estimate'):
                            try:
                                count = int(getattr(features, 'num_singers_estimate', 0))
                                code_singer_counts.append(count)
                            except Exception:
                                code_singer_counts.append(0)
                        else:
                            code_singer_counts.append(0)
                    
                    # Log singer counts for debugging
                    if code_singer_counts and any(c > 0 for c in code_singer_counts):
                        logger.info(f"🎤 Code {code}: Singer counts = {code_singer_counts} (matched to {len(code_audio_paths_ordered)} audio paths)")
                    else:
                        logger.warning(f"⚠️ Code {code}: No singer count data available (all zeros)")
                    
                    # Detect reuploads within this Code group
                    code_clusters = self.reupload_detector.detect_reuploads(
                        code_audio_matrix,
                        code_video_matrix,
                        code_urls,
                        code_metadata,
                        code_types,
                        audio_paths_ordered=code_audio_paths_ordered,
                        video_paths_ordered=code_video_paths_ordered,
                        audio_paths=code_audio_paths,
                        video_paths=code_video_paths,
                        video_features_dict=code_video_features,
                        singer_counts=code_singer_counts,
                    )
                    
                    return (code, code_clusters)
                except Exception as e:
                    logger.error(f"Error processing Code group {code}: {e}", exc_info=True)
                    return (code, [])
            
            # Process Code groups in parallel (with limited workers)
            all_clusters = []
            processed_count = 0
            total_groups = len([g for g in code_groups.values() if len(g) >= 2])
            
            if max_workers > 1 and total_groups > 1:
                # Parallel processing for multiple Code groups
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all Code groups
                    futures = {
                        executor.submit(process_code_group, code, indices): code
                        for code, indices in code_groups.items()
                        if len(indices) >= 2
                    }
                    
                    # Collect results as they complete
                    for future in as_completed(futures):
                        if should_cancel():
                            log("Processing cancelled - stopping code group processing")
                            # Cancel all remaining futures
                            for f in futures:
                                f.cancel()
                            raise RuntimeError("Processing cancelled by user")

                        code = futures[future]
                        try:
                            result_code, code_clusters = future.result()
                            all_clusters.extend(code_clusters)
                            processed_count += 1
                            if len(code_clusters) > 0:
                                log(f"  Code {result_code}: Found {len(code_clusters)} clusters ({processed_count}/{total_groups})")
                            else:
                                log(f"  Code {result_code}: No clusters ({processed_count}/{total_groups})")
                        except Exception as e:
                            logger.error(f"Error getting result for Code group {code}: {e}", exc_info=True)
                            processed_count += 1
            else:
                # Sequential processing (if only 1 worker or 1 group)
                for code, indices in code_groups.items():
                    if len(indices) < 2:
                        continue
                    result_code, code_clusters = process_code_group(code, indices)
                    all_clusters.extend(code_clusters)
                    processed_count += 1
                    if len(code_clusters) > 0:
                        log(f"  Code {result_code}: Found {len(code_clusters)} clusters ({processed_count}/{total_groups})")
            
            clusters = all_clusters
            log(f"✓ Total: Found {len(clusters)} reupload clusters across {processed_count} Code groups")
            
            # Step 6: Generate statistics
            current_step += 1
            update_progress(current_step, total_steps, "Generating report...")
            log(f"Step {current_step}/{total_steps}: Generating statistics...")

            if should_cancel():
                log("Processing cancelled before statistics step")
                raise RuntimeError("Processing cancelled by user")
            
            statistics = self.reupload_detector.get_statistics(clusters, len(video_urls))
            
            log(f"✓ Statistics generated")
            log(f"Total reuploads: {statistics['total_reuploads']}")
            log(f"Reupload percentage: {statistics['reupload_percentage']:.1f}%")
            
            # Cleanup
            if not self.config.get('download.keep_files', False):
                log("Cleaning up temporary files...")
                self.downloader.cleanup()
                log("✓ Cleanup complete")
            
            # Prepare results
            # IMPORTANT: Store ALL download tasks (including failed ones) for export
            # Map failed downloads to error messages
            failed_downloads_map = {}
            for task in download_tasks:
                url = task['url']
                if url not in {r.url for r in successful_downloads}:
                    # Find error message from download results
                    for result in download_results:
                        if result.url == url and not result.success:
                            failed_downloads_map[url] = result.error or "Unknown error"
                            break
            
            # Calculate full matrices for export (if needed for similarity matrix sheet)
            # Note: This is optional - can be computed on-demand in export_results if needed
            full_audio_matrix = None
            full_video_matrix = None
            try:
                # Create full matrices for export (all videos, not just Code groups)
                full_audio_matrix, _ = self.audio_analyzer.create_similarity_matrix(audio_features)
                # Only create video matrix if we actually extracted any video features
                if len(video_features) >= 2:
                    full_video_matrix, _ = self.video_analyzer.create_similarity_matrix(video_features)
                else:
                    import numpy as np
                    full_video_matrix = np.array([])
                log("✓ Full similarity matrices created for export")
            except Exception as e:
                log(f"⚠ Warning: Could not create full matrices for export: {e}")
                # Continue without full matrices - export will skip similarity matrix sheets
            
            results = {
                'clusters': clusters,
                'statistics': statistics,
                'video_types': video_types,
                'metadata': video_metadata,
                'urls': video_urls,
                'audio_paths': audio_paths,
                'video_paths': video_paths,
                'audio_matrix': full_audio_matrix if full_audio_matrix is not None else np.array([]),
                'video_matrix': full_video_matrix if full_video_matrix is not None else np.array([]),
                'audio_features': audio_features,  # Store features for on-demand matrix calculation
                'video_features': video_features,  # Store features for on-demand matrix calculation
                'timestamp': datetime.now().isoformat(),
                # Store all original input for export (including failed downloads)
                'all_download_tasks': download_tasks,
                'all_original_metadata': metadata,  # Original input metadata
                'all_original_urls': urls,  # Original input URLs
                'successful_urls': set(video_urls),  # Track which URLs succeeded
                'failed_downloads_map': failed_downloads_map  # Map URL -> error message
            }
            
            update_progress(total_steps, total_steps, "Complete!")
            log("✓ Processing pipeline complete!")
            
            return results
            
        except RuntimeError as e:
            # Propagate cancellation upwards without treating it as an internal error
            log(str(e))
            raise
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            raise
    
    def export_results(self, results: Dict, output_path: str):
        """Export results to Excel file"""
        try:
            logger.info(f"Exporting results to {output_path}")
            
            clusters = results['clusters']
            statistics = results['statistics']
            urls = results.get('urls', [])
            metadata = results.get('metadata', [])
            video_types = results.get('video_types', [])
            audio_paths = results.get('audio_paths', [])
            audio_matrix = results.get('audio_matrix', np.array([]))
            video_matrix = results.get('video_matrix', np.array([]))
            audio_features = results.get('audio_features', {})
            
            # Map URL -> audio_path for singer lookup
            url_to_audio_path = {url: apath for url, apath in zip(urls, audio_paths)}
            
            # Create Excel writer
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                
                # Sheet 1: All Videos Processed (including failed downloads)
                logger.info("Creating 'All Videos' sheet...")
                
                # Get all original input data (including failed downloads)
                all_download_tasks = results.get('all_download_tasks', [])
                all_original_metadata = results.get('all_original_metadata', metadata)
                all_original_urls = results.get('all_original_urls', urls)
                successful_urls = results.get('successful_urls', set(urls))
                failed_downloads_map = results.get('failed_downloads_map', {})
                
                # Build URL to processed data mapping
                url_to_processed = {}
                for url, meta, vtype in zip(urls, metadata, video_types):
                    url_to_processed[url] = {'meta': meta, 'vtype': vtype}
                
                # Build reupload map
                reupload_map = {}  # url -> (is_reupload, original_url, similarity)
                for cluster in clusters:
                    # Mark original as not reupload
                    reupload_map[cluster.original_url] = (False, None, None)
                    # Mark reuploads
                    for reup_url, similarity in zip(cluster.reupload_urls, cluster.similarities):
                        reupload_map[reup_url] = (True, cluster.original_url, similarity)
                
                all_videos_data = []
                # Export ALL rows from original input (including failed downloads)
                for original_idx, (url, meta) in enumerate(zip(all_original_urls, all_original_metadata)):
                    # Check if this URL was successfully downloaded and processed
                    if url not in successful_urls:
                        # Failed download - mark with error status and include error message
                        error_msg = failed_downloads_map.get(url, "Unknown error")
                        # Extract short error description
                        if "Private video" in error_msg:
                            error_desc = "Private"
                        elif "Sign in" in error_msg or "cookies" in error_msg.lower():
                            error_desc = "Cần đăng nhập"
                        elif "unavailable" in error_msg.lower() or "removed" in error_msg.lower():
                            error_desc = "Video không khả dụng"
                        elif "timeout" in error_msg.lower():
                            error_desc = "Timeout"
                        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                            error_desc = "Lỗi mạng"
                        else:
                            error_desc = "Lỗi khác"
                        reupload_status = f"Lỗi - Không tải được video ({error_desc})"
                        vtype = meta.get('Type') or meta.get('type', 'Unknown')
                        duration = ''
                    else:
                        # Successfully processed - get processed data
                        processed_data = url_to_processed.get(url, {})
                        processed_meta = processed_data.get('meta', meta)
                        vtype = processed_data.get('vtype', meta.get('Type') or meta.get('type', 'Unknown'))
                        duration = processed_meta.get('duration', '')
                        
                        # Determine reupload status
                        if url in reupload_map:
                            is_reupload, orig_url, similarity = reupload_map[url]
                            if is_reupload:
                                # Find original video ID from processed metadata
                                orig_idx = urls.index(orig_url) if orig_url in urls else -1
                                if orig_idx >= 0 and orig_idx < len(metadata):
                                    orig_id = metadata[orig_idx].get('ID Video', 'video gốc')
                                else:
                                    orig_id = 'video gốc'
                                reupload_status = f"Yes - Reupload của {orig_id} ({similarity:.1%})"
                            else:
                                reupload_status = "No - Video gốc"
                        else:
                            reupload_status = "No - Video độc nhất"
                    
                    # Get STT from original metadata (preserve Excel order)
                    stt = meta.get('STT') or meta.get('ST') or (original_idx + 1)
                    # Ensure STT is numeric for sorting
                    try:
                        stt = int(stt)
                    except (ValueError, TypeError):
                        stt = original_idx + 1
                    
                    # Extract singer count from audio features if available
                    singer_count = ''
                    if url in successful_urls and url_to_audio_path:
                        apath = url_to_audio_path.get(url)
                        if apath and apath in audio_features:
                            feat = audio_features[apath]
                            if hasattr(feat, 'num_singers_estimate'):
                                try:
                                    singer_count = str(int(getattr(feat, 'num_singers_estimate', 0)))
                                except Exception:
                                    singer_count = str(getattr(feat, 'num_singers_estimate', ''))
                    
                    all_videos_data.append({
                        'STT': stt,
                        'Code': meta.get('Code', ''),
                        'ID Video': meta.get('ID Video', ''),
                        'Link YouTube': url,
                        'Thoi gian': meta.get('Thoi gian') or meta.get('Thời gian', ''),
                        'Type': vtype,
                        'Duration (s)': duration,
                        'Singers': singer_count,
                        'Is Reupload': reupload_status
                    })
                
                df_all_videos = pd.DataFrame(all_videos_data)
                # Sort by Code first, then STT to group by Code and preserve original Excel order
                if 'Code' in df_all_videos.columns and 'STT' in df_all_videos.columns:
                    df_all_videos = df_all_videos.sort_values(['Code', 'STT'], ascending=[True, True])
                elif 'STT' in df_all_videos.columns:
                    df_all_videos = df_all_videos.sort_values('STT', ascending=True)
                df_all_videos.to_excel(writer, sheet_name='All Videos', index=False)
                
                # Sheet 2: Reupload Clusters (if any found)
                if clusters:
                    logger.info(f"Creating 'Reupload Clusters' sheet with {len(clusters)} clusters...")
                    clusters_data = []
                    for cluster in clusters:
                        # Find Code from metadata
                        code = ''
                        for url in urls:
                            if url == cluster.original_url:
                                idx = urls.index(url)
                                if idx < len(metadata):
                                    code = metadata[idx].get('Code', '')
                                break
                        
                        for i, (reupload_url, reupload_title, similarity) in enumerate(
                            zip(cluster.reupload_urls, cluster.reupload_titles, cluster.similarities)
                        ):
                            clusters_data.append({
                                'Code': code,
                                'Link Gốc (Original)': cluster.original_url,
                                'Tiêu đề Gốc': cluster.original_title,
                                'Ngày Upload Gốc': cluster.original_date,
                                'Link Reupload': reupload_url,
                                'Tiêu đề Reupload': reupload_title,
                                'Độ giống (Similarity)': f"{similarity:.2%}",
                                'Loại Video': cluster.video_type,
                                'Kết luận': f'Reupload từ link gốc'
                            })
                    
                    df_clusters = pd.DataFrame(clusters_data)
                    # Sort by Code for easier filtering
                    if 'Code' in df_clusters.columns:
                        df_clusters = df_clusters.sort_values('Code', ascending=True)
                    df_clusters.to_excel(writer, sheet_name='Reupload Clusters', index=False)
                else:
                    logger.info("No clusters found - creating empty 'Reupload Clusters' sheet")
                    # Create empty sheet with headers
                    df_empty = pd.DataFrame(columns=[
                        'Link Gốc (Original)', 'Tiêu đề Gốc', 'Ngày Upload Gốc',
                        'Link Reupload', 'Tiêu đề Reupload', 'Độ giống (Similarity)',
                        'Loại Video', 'Kết luận'
                    ])
                    df_empty.to_excel(writer, sheet_name='Reupload Clusters', index=False)
                
                # Sheet 3: Summary by Video
                logger.info("Creating 'Summary' sheet...")
                if clusters:
                    summary_data = []
                    for cluster in clusters:
                        # Find Code from metadata
                        code = ''
                        for url in urls:
                            if url == cluster.original_url:
                                idx = urls.index(url)
                                if idx < len(metadata):
                                    code = metadata[idx].get('Code', '')
                                break
                        
                        avg_similarity = sum(cluster.similarities) / len(cluster.similarities) if cluster.similarities else 0
                        summary_data.append({
                            'Code': code,
                            'Link Gốc': cluster.original_url,
                            'Tiêu đề': cluster.original_title,
                            'Số lượng Reupload': len(cluster.reupload_urls),
                            'Độ giống TB': f"{avg_similarity:.2%}",
                            'Loại Video': cluster.video_type,
                            'Ngày Upload': cluster.original_date
                        })
                    
                    df_summary = pd.DataFrame(summary_data)
                    # Sort by Code for easier filtering
                    if 'Code' in df_summary.columns:
                        df_summary = df_summary.sort_values('Code', ascending=True)
                    df_summary.to_excel(writer, sheet_name='Summary', index=False)
                else:
                    # No clusters - show all videos as unique
                    summary_data = []
                    for url, meta, vtype in zip(urls, metadata, video_types):
                        summary_data.append({
                            'Link': url,
                            'Tiêu đề': meta.get('title', ''),
                            'Số lượng Reupload': 0,
                            'Độ giống TB': 'N/A',
                            'Loại Video': vtype,
                            'Ngày Upload': meta.get('upload_date', ''),
                            'Trạng thái': 'Video độc nhất (không tìm thấy reupload)'
                        })
                    
                    df_summary = pd.DataFrame(summary_data)
                    df_summary.to_excel(writer, sheet_name='Summary', index=False)
                
                # Sheet 4: Similarity Matrix
                logger.info("Creating 'Similarity Matrix' sheet...")
                if video_matrix.size > 0:
                    # Create matrix with appropriate headers matching matrix size
                    video_ids_all = [meta.get('ID Video', f'Video_{i+1}') for i, meta in enumerate(metadata)]
                    n = video_matrix.shape[0]
                    headers = []
                    if n == len(video_ids_all):
                        headers = video_ids_all
                    else:
                        # Try non-audio IDs (since we may have skipped audio rows in video matrix)
                        non_audio_ids = [meta.get('ID Video', f'Video_{idx+1}')
                                         for idx, (meta, t) in enumerate(zip(metadata, video_types))
                                         if str(t).strip().lower() not in ['audio', 'âm thanh']]
                        if len(non_audio_ids) == n:
                            headers = non_audio_ids
                        else:
                            # Fallback: generate generic headers
                            headers = [f'Video_{i+1}' for i in range(n)]
                            logger.warning(f"Similarity Matrix: header count mismatch (matrix={n}, meta_all={len(video_ids_all)}, non_audio={len(non_audio_ids)}). Using generic headers.")
                    
                    df_similarity = pd.DataFrame(
                        video_matrix,
                        columns=headers,
                        index=headers
                    )
                    # Format as percentages
                    df_similarity = df_similarity.map(lambda x: f"{x:.2%}" if isinstance(x, (int, float)) else x)
                    df_similarity.to_excel(writer, sheet_name='Similarity Matrix')
                
                # Sheet 5: Detailed Comparisons (All Pairs)
                logger.info("Creating 'Detailed Comparisons' sheet...")
                if video_matrix.size > 0:
                    # Build filtered lists to match video_matrix size
                    n = video_matrix.shape[0]
                    meta_non_audio = [m for m, t in zip(metadata, video_types) if str(t).strip().lower() not in ['audio', 'âm thanh']]
                    urls_non_audio = [u for u, t in zip(urls, video_types) if str(t).strip().lower() not in ['audio', 'âm thanh']]
                    types_non_audio = [t for t in video_types if str(t).strip().lower() not in ['audio', 'âm thanh']]
                    if len(meta_non_audio) == n and len(urls_non_audio) == n:
                        comparison_data = []
                        for i in range(n):
                            for j in range(i + 1, n):
                                similarity = video_matrix[i, j]
                                comparison_data.append({
                                    'Video 1 ID': meta_non_audio[i].get('ID Video', f'Video_{i+1}'),
                                    'Video 1 Link': urls_non_audio[i],
                                    'Video 1 Title': meta_non_audio[i].get('title', ''),
                                    'Video 2 ID': meta_non_audio[j].get('ID Video', f'Video_{j+1}'),
                                    'Video 2 Link': urls_non_audio[j],
                                    'Video 2 Title': meta_non_audio[j].get('title', ''),
                                    'Similarity': f"{similarity:.2%}",
                                    'Is Reupload?': 'Yes' if similarity >= 0.80 else 'No',
                                    'Type 1': types_non_audio[i],
                                    'Type 2': types_non_audio[j]
                                })
                        df_comparison = pd.DataFrame(comparison_data)
                        # Sort by similarity descending
                        if not df_comparison.empty:
                            df_comparison['Similarity_Value'] = df_comparison['Similarity'].str.rstrip('%').astype(float) / 100
                            df_comparison = df_comparison.sort_values('Similarity_Value', ascending=False)
                            df_comparison = df_comparison.drop('Similarity_Value', axis=1)
                        df_comparison.to_excel(writer, sheet_name='Detailed Comparisons', index=False)
                    else:
                        logger.warning("Detailed Comparisons: skipped due to size mismatch with filtered non-audio lists.")
                
                # Sheet 6: Statistics
                stats_data = [
                    {'Metric': 'Total Videos Processed', 'Value': statistics['total_videos']},
                    {'Metric': 'Original Videos', 'Value': statistics['total_originals']},
                    {'Metric': 'Reupload Videos', 'Value': statistics['total_reuploads']},
                    {'Metric': 'Reupload Percentage', 'Value': f"{statistics['reupload_percentage']:.1f}%"},
                    {'Metric': 'Average Similarity', 'Value': f"{statistics['average_similarity']:.2%}"},
                    {'Metric': 'Number of Clusters', 'Value': statistics['clusters']},
                ]
                
                # Add type distribution
                for vtype, count in statistics['type_distribution'].items():
                    stats_data.append({
                        'Metric': f'Reuploads - {vtype}',
                        'Value': count
                    })
                
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='Statistics', index=False)
            
            logger.info(f"✓ Results exported successfully to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export results: {e}", exc_info=True)
            raise

