"""Reupload detection using clustering and graph analysis"""
import numpy as np
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ReuploadCluster:
    """A cluster of similar videos (potential reuploads)"""
    original_url: str
    original_title: str
    original_date: str
    reupload_urls: List[str]
    reupload_titles: List[str]
    similarities: List[float]  # Similarity scores
    video_type: str


class ReuploadDetector:
    """Detect reupload videos using similarity clustering"""
    
    def __init__(self, config):
        self.config = config
        self.audio_threshold = config.get('thresholds.audio_similarity', 0.75)
        self.video_threshold = config.get('thresholds.video_similarity', 0.85)
        self.combined_threshold = config.get('thresholds.combined_similarity', 0.75)
        self.optical_flow_threshold = config.get('thresholds.optical_flow_threshold', 5.0)
        self.compare_within_same_type_only = config.get('thresholds.compare_within_same_type_only', True)
        
        # Weights for combined score
        self.audio_weight = config.get('weights.audio', 0.4)
        self.video_weight = config.get('weights.video', 0.4)
        self.scene_weight = config.get('weights.scene', 0.2)
        
        logger.info("ReuploadDetector initialized")
    
    def calculate_combined_similarity(self, 
                                     audio_sim: float, 
                                     video_sim: float, 
                                     scene_sim: float = 0.0) -> float:
        """Calculate weighted combined similarity score"""
        combined = (
            self.audio_weight * audio_sim +
            self.video_weight * video_sim +
            self.scene_weight * scene_sim
        )
        return combined
    
    def create_combined_similarity_matrix(self,
                                         audio_matrix: np.ndarray,
                                         video_matrix: np.ndarray,
                                         optical_flows: Dict[str, float] = None,
                                         video_paths: List[str] = None,
                                         optical_flow_threshold: float = 5.0) -> np.ndarray:
        """Create combined similarity matrix from audio and video matrices
        
        For static images (low optical flow), use audio-only similarity instead of combined
        """
        logger.info("Creating combined similarity matrix")
        
        # Handle different matrix shapes (when some analysis failed)
        audio_size = audio_matrix.shape[0] if len(audio_matrix.shape) > 0 else 0
        video_size = video_matrix.shape[0] if len(video_matrix.shape) > 0 else 0
        
        # Case 1: Both have features and same shape
        if audio_size > 0 and video_size > 0 and audio_size == video_size:
            logger.info(f"Combining audio ({audio_size}x{audio_size}) and video ({video_size}x{video_size}) matrices")
            
            # Create base combined matrix
            combined = (
                self.audio_weight * audio_matrix +
                self.video_weight * video_matrix
            )
            
            # If optical flows are available, adjust for static images
            if optical_flows is not None and video_paths is not None and len(video_paths) == audio_size:
                static_count = 0
                for i in range(audio_size):
                    for j in range(i + 1, audio_size):
                        path_i = video_paths[i] if i < len(video_paths) else None
                        path_j = video_paths[j] if j < len(video_paths) else None
                        
                        if path_i and path_j:
                            flow_i = optical_flows.get(path_i, float('inf'))
                            flow_j = optical_flows.get(path_j, float('inf'))
                            
                            # If both are static images (low optical flow), use VIDEO-only similarity (rule #2)
                            if flow_i < optical_flow_threshold and flow_j < optical_flow_threshold:
                                video_sim = float(video_matrix[i, j])
                                # Rule #2 threshold: require reasonable visual match for static content (relaxed from 0.88)
                                if video_sim < 0.80:
                                    # Push below threshold so it won't cluster
                                    combined[i, j] = 0.0
                                    combined[j, i] = 0.0
                                else:
                                    combined[i, j] = video_sim
                                    combined[j, i] = video_sim
                                static_count += 1
                                logger.debug(
                                    f"📷 Static image pair [{i}↔{j}]: flow_i={flow_i:.2f}, flow_j={flow_j:.2f}, video_sim={video_sim:.3f} → video-only"
                                )
                            else:
                                # Non-static pair: use combined similarity without aggressive gating
                                audio_sim_gate = float(audio_matrix[i, j])
                                # Only apply gentle gating for very low audio similarity (< 0.60)
                                if audio_sim_gate < 0.60:
                                    # Reduce combined similarity but don't force below threshold
                                    reduction_factor = 0.85  # Reduce by 15%
                                    combined[i, j] *= reduction_factor
                                    combined[j, i] *= reduction_factor
                                    logger.debug(
                                        f"🔊 Gentle audio gate applied [{i}↔{j}]: audio_sim={audio_sim_gate:.3f} < 0.60 → reduced by 15%"
                                    )
                
                if static_count > 0:
                    logger.info(f"📷 Adjusted {static_count} static pairs (using video-only similarity)")
            
            logger.info(f"Combined matrix created: shape={combined.shape}")
            return combined
        
        # Case 2: Only audio features available
        elif audio_size > 0 and video_size == 0:
            logger.warning("No video features available, using audio only")
            logger.info(f"Using audio matrix: shape={audio_matrix.shape}")
            return audio_matrix
        
        # Case 3: Only video features available
        elif video_size > 0 and audio_size == 0:
            logger.warning("No audio features available, using video only")
            logger.info(f"Using video matrix: shape={video_matrix.shape}")
            return video_matrix
        
        # Case 4: Sizes don't match (some videos failed in one analysis but not the other)
        elif audio_size > 0 and video_size > 0 and audio_size != video_size:
            logger.error(f"Matrix size mismatch: audio={audio_size}x{audio_size}, video={video_size}x{video_size}")
            logger.warning("Using video matrix only (larger set)")
            # Use the larger matrix (more data available)
            if video_size >= audio_size:
                return video_matrix
            else:
                return audio_matrix
        
        # Case 5: No features at all
        else:
            raise ValueError("No features available for comparison (both audio and video analysis failed)")
    
    def find_connected_components(self, similarity_matrix: np.ndarray, 
                                 threshold: float) -> List[Set[int]]:
        """Find connected components in similarity graph using threshold"""
        n = len(similarity_matrix)
        
        # Debug: Find max similarity and count high-similarity pairs
        if n > 1:
            # Get upper triangle (without diagonal)
            upper_tri = []
            for i in range(n):
                for j in range(i + 1, n):
                    upper_tri.append(similarity_matrix[i, j])
            
            max_sim = np.max(upper_tri)
            min_sim = np.min(upper_tri)
            avg_sim = np.mean(upper_tri)
            
            # Count pairs above various thresholds
            above_threshold = sum(1 for s in upper_tri if s >= threshold)
            above_70 = sum(1 for s in upper_tri if s >= 0.70)
            above_75 = sum(1 for s in upper_tri if s >= 0.75)
            above_80 = sum(1 for s in upper_tri if s >= 0.80)
            above_85 = sum(1 for s in upper_tri if s >= 0.85)
            
            logger.info(f"Similarity statistics:")
            logger.info(f"  Max: {max_sim:.3f}, Min: {min_sim:.3f}, Avg: {avg_sim:.3f}")
            logger.info(f"  Pairs above thresholds:")
            logger.info(f"    ≥70%: {above_70}/{len(upper_tri)}")
            logger.info(f"    ≥75%: {above_75}/{len(upper_tri)}")
            logger.info(f"    ≥80%: {above_80}/{len(upper_tri)}")
            logger.info(f"    ≥85%: {above_85}/{len(upper_tri)}")
            logger.info(f"    ≥{threshold:.0%}: {above_threshold}/{len(upper_tri)} ← Current threshold")
            
            if above_threshold == 0:
                logger.warning(f"⚠ No pairs found above threshold {threshold:.1%}")
                logger.warning(f"⚠ Highest similarity found: {max_sim:.1%}")
                if max_sim >= 0.70:
                    logger.warning(f"💡 Consider lowering threshold to ~{max_sim - 0.05:.1%} to detect these pairs")
        
        # Build adjacency list
        graph = defaultdict(set)
        edges_added = 0
        for i in range(n):
            for j in range(i + 1, n):
                if similarity_matrix[i, j] >= threshold:
                    graph[i].add(j)
                    graph[j].add(i)
                    edges_added += 1
                    logger.debug(f"Edge added: {i} ↔ {j} (similarity: {similarity_matrix[i, j]:.3f})")
        
        logger.info(f"Graph built: {edges_added} edges added (pairs ≥ {threshold:.1%})")
        
        # Find connected components using DFS
        visited = set()
        components = []
        
        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        for i in range(n):
            if i not in visited:
                component = set()
                dfs(i, component)
                if len(component) > 1:  # Only clusters with 2+ videos
                    components.append(component)
                    logger.info(f"Cluster found: {len(component)} videos - indices {sorted(component)}")
        
        logger.info(f"Found {len(components)} clusters with threshold={threshold:.1%}")
        return components
    
    def identify_original(self, 
                         indices: Set[int], 
                         metadata_list: List[Dict]) -> int:
        """Identify the original video in a cluster (earliest upload)"""
        
        earliest_idx = None
        earliest_date = None
        
        for idx in indices:
            metadata = metadata_list[idx]
            upload_date = metadata.get('upload_date', '99999999')
            
            # Parse upload_date (format: YYYYMMDD)
            try:
                date_obj = datetime.strptime(upload_date, '%Y%m%d')
            except:
                # If parsing fails, use string comparison
                date_obj = upload_date
            
            if earliest_date is None or date_obj < earliest_date:
                earliest_date = date_obj
                earliest_idx = idx
        
        return earliest_idx if earliest_idx is not None else min(indices)
    
    def create_clusters(self,
                       similarity_matrix: np.ndarray,
                       urls: List[str],
                       metadata_list: List[Dict],
                       video_types: List[str],
                       threshold: float = None) -> List[ReuploadCluster]:
        """Create reupload clusters from similarity matrix
        
        Args:
            similarity_matrix: NxN similarity matrix
            urls: List of video URLs
            metadata_list: List of metadata dicts
            video_types: List of video types
            threshold: Similarity threshold (default: combined_threshold)
        """
        
        if threshold is None:
            threshold = self.combined_threshold
        
        logger.info(f"Creating reupload clusters with threshold={threshold:.1%}")
        
        # Find connected components
        components = self.find_connected_components(
            similarity_matrix, 
            threshold
        )
        
        clusters = []
        
        for component in components:
            # Identify original
            original_idx = self.identify_original(component, metadata_list)
            
            # Get reupload indices
            reupload_indices = component - {original_idx}
            
            if not reupload_indices:
                continue
            
            # Get metadata
            original_meta = metadata_list[original_idx]
            
            # Get similarities
            similarities = [
                similarity_matrix[original_idx, idx] 
                for idx in reupload_indices
            ]
            
            # Create cluster
            cluster = ReuploadCluster(
                original_url=urls[original_idx],
                original_title=original_meta.get('title', 'Unknown'),
                original_date=original_meta.get('upload_date', 'Unknown'),
                reupload_urls=[urls[idx] for idx in reupload_indices],
                reupload_titles=[
                    metadata_list[idx].get('title', 'Unknown') 
                    for idx in reupload_indices
                ],
                similarities=similarities,
                video_type=video_types[original_idx]
            )
            
            clusters.append(cluster)
        
        logger.info(f"Created {len(clusters)} reupload clusters")
        
        # Sort by number of reuploads (descending)
        clusters.sort(key=lambda c: len(c.reupload_urls), reverse=True)
        
        return clusters
    
    def detect_reuploads(self,
                        audio_matrix: np.ndarray,
                        video_matrix: np.ndarray,
                        urls: List[str],
                        metadata_list: List[Dict],
                        video_types: List[str],
                        audio_paths_ordered: List[str] = None,
                        video_paths_ordered: List[str] = None,
                        audio_paths: List[str] = None,
                        video_paths: List[str] = None,
                        video_features_dict: Dict[str, any] = None,
                        singer_counts: List[int] = None) -> List[ReuploadCluster]:
        """Main method to detect reuploads
        
        Important: audio_paths_ordered and video_paths_ordered must match the order of audio_matrix and video_matrix
        
        For Audio type videos: Use audio-only comparison with audio_similarity threshold
        For Video/Karaoke type videos: Use combined (audio+video) with combined_similarity threshold
        """
        
        logger.info("Starting reupload detection")
        logger.info(f"Processing {len(urls)} videos")
        
        # Group videos by type (Audio vs non-Audio)
        audio_indices = [i for i, vtype in enumerate(video_types) 
                        if str(vtype).strip().lower() in ['audio', 'âm thanh']]
        video_indices = [i for i, vtype in enumerate(video_types) 
                        if str(vtype).strip().lower() not in ['audio', 'âm thanh']]
        
        logger.info(f"Video type breakdown: {len(audio_indices)} Audio, {len(video_indices)} Video/Karaoke")
        
        all_clusters = []
        
        # Process Audio type videos separately (audio-only)
        if audio_indices and audio_matrix.size > 0:
            logger.info(f"🎵 Processing {len(audio_indices)} Audio type videos (audio-only comparison)...")
            
            # Create sub-matrix for audio videos only
            audio_submatrix = np.zeros((len(audio_indices), len(audio_indices)))
            for idx_i, i in enumerate(audio_indices):
                for idx_j, j in enumerate(audio_indices):
                    if i < audio_matrix.shape[0] and j < audio_matrix.shape[0]:
                        audio_submatrix[idx_i, idx_j] = audio_matrix[i, j]
            
            logger.info(f"Created audio sub-matrix: {audio_submatrix.shape}")
            
            # Apply singer penalty for Audio type videos
            if singer_counts is not None and len(singer_counts) > 0:
                for idx_i, i in enumerate(audio_indices):
                    for idx_j, j in enumerate(audio_indices):
                        if idx_i >= idx_j:  # Only process upper triangle
                            continue
                        
                        # Get singer counts for these audio indices
                        if i < len(singer_counts) and j < len(singer_counts):
                            si = singer_counts[i] or 0
                            sj = singer_counts[j] or 0
                            
                            if si > 0 and sj > 0 and si != sj:
                                old_val = audio_submatrix[idx_i, idx_j]
                                # Use config value or default to 0.5
                                penalty = float(self.config.get('thresholds.singer_mismatch_penalty', 0.5))
                                audio_submatrix[idx_i, idx_j] *= penalty
                                audio_submatrix[idx_j, idx_i] *= penalty
                                new_val = audio_submatrix[idx_i, idx_j]
                                logger.warning(f"🎙️ Singer penalty (Audio) [{idx_i}↔{idx_j}]: {si} vs {sj} singers, similarity {old_val:.3f}→{new_val:.3f} (×{penalty})")
            
            # Log audio similarity statistics
            if len(audio_indices) > 1:
                upper_tri = []
                for idx_i in range(len(audio_indices)):
                    for idx_j in range(idx_i + 1, len(audio_indices)):
                        upper_tri.append(audio_submatrix[idx_i, idx_j])
                
                if upper_tri:
                    max_sim = np.max(upper_tri)
                    avg_sim = np.mean(upper_tri)
                    min_sim = np.min(upper_tri)
                    above_threshold = sum(1 for s in upper_tri if s >= self.audio_threshold)
                    logger.info(f"🎵 Audio similarity statistics:")
                    logger.info(f"  Max: {max_sim:.3f}, Avg: {avg_sim:.3f}, Min: {min_sim:.3f}")
                    logger.info(f"  Pairs ≥{self.audio_threshold:.1%}: {above_threshold}/{len(upper_tri)}")
                    
                    # Log top similarities for debugging
                    sorted_sims = sorted(upper_tri, reverse=True)[:5]
                    if sorted_sims:
                        logger.info(f"  Top similarities: {[f'{s:.1%}' for s in sorted_sims]}")
                    
                    # Log pairs close to threshold (for debugging false negatives like link 12-13)
                    near_threshold = [(s, i, j) for idx_i, i in enumerate(audio_indices) 
                                     for idx_j, j in enumerate(audio_indices) 
                                     if idx_j > idx_i and (s := audio_submatrix[idx_i, idx_j]) >= 0.65 and s < self.audio_threshold]
                    if near_threshold:
                        near_threshold.sort(reverse=True)
                        logger.info(f"  Near threshold ({self.audio_threshold:.1%}): {len(near_threshold)} pairs")
                        for s, i, j in near_threshold[:3]:  # Top 3
                            logger.info(f"    [{i}↔{j}]: {s:.1%} (below threshold by {self.audio_threshold - s:.1%})")
            
            # Use audio_similarity threshold for audio videos
            audio_urls = [urls[i] for i in audio_indices]
            audio_metadata = [metadata_list[i] for i in audio_indices]
            audio_types = [video_types[i] for i in audio_indices]
            
            audio_clusters = self.create_clusters(
                audio_submatrix,
                audio_urls,
                audio_metadata,
                audio_types,
                threshold=self.audio_threshold  # Use audio threshold
            )
            
            logger.info(f"🎵 Found {len(audio_clusters)} audio clusters with threshold={self.audio_threshold:.1%}")
            
            # Log audio cluster details
            for cluster in audio_clusters:
                logger.info(f"  Audio cluster: {len(cluster.reupload_urls)} reuploads")
                for reup_url, sim in zip(cluster.reupload_urls, cluster.similarities):
                    logger.info(f"    - {reup_url[:30]}... : {sim:.1%}")
            
            all_clusters.extend(audio_clusters)
        
        # Process Video/Karaoke type videos (combined audio+video)
        if video_indices:
            logger.info(f"🎬 Processing {len(video_indices)} Video/Karaoke type videos (combined comparison)...")
            
            paths_for_matrix = video_paths_ordered if video_paths_ordered is not None else video_paths
            
            # Extract optical flows from video_features_dict if available (LOCAL order)
            optical_flows = {}
            if video_features_dict is not None and paths_for_matrix is not None:
                from ..analysis.video_analyzer import VideoFeatures
                for path in paths_for_matrix:
                    if path in video_features_dict:
                        features = video_features_dict[path]
                        if isinstance(features, VideoFeatures):
                            optical_flows[path] = features.optical_flow_magnitude
            
            # Build mappings between global video order and local matrix order
            path_to_local_idx = {path: idx for idx, path in enumerate(paths_for_matrix)} if paths_for_matrix else {}
            path_to_global_idx = {path: idx for idx, path in enumerate(video_paths)} if video_paths is not None else {}
            global_to_local_idx = {}
            if video_paths is not None:
                for g_idx, path in enumerate(video_paths):
                    local_idx = path_to_local_idx.get(path)
                    if local_idx is not None:
                        global_to_local_idx[g_idx] = local_idx
            
            # Start from audio similarities so we always have a global-sized matrix
            if audio_matrix.size > 0:
                combined_matrix = audio_matrix.copy()
            else:
                matrix_size = len(urls)
                combined_matrix = np.zeros((matrix_size, matrix_size))
            
            local_combined = None
            if video_matrix.size > 0 and paths_for_matrix:
                # Build an audio sub-matrix that matches the local video order
                if audio_matrix.size > 0 and audio_paths_ordered:
                    audio_subset = np.zeros((len(paths_for_matrix), len(paths_for_matrix)))
                    # Normalize paths by extracting filename without extension
                    # (audio files are in audios/ folder, video files are in videos/ folder)
                    from pathlib import Path
                    def normalize_path(p):
                        return Path(p).stem  # Get filename without extension

                    # Debug: Log paths being compared
                    logger.debug(f"🔍 Audio paths (first 3): {audio_paths_ordered[:3]}")
                    logger.debug(f"🔍 Video paths (first 3): {paths_for_matrix[:3]}")
                    logger.debug(f"🔍 Audio normalized: {[normalize_path(p) for p in audio_paths_ordered[:3]]}")
                    logger.debug(f"🔍 Video normalized: {[normalize_path(p) for p in paths_for_matrix[:3]]}")

                    path_to_audio_idx = {normalize_path(path): idx for idx, path in enumerate(audio_paths_ordered)}
                    missing_audio_paths = set()
                    for i, path_i in enumerate(paths_for_matrix):
                        normalized_video = normalize_path(path_i)
                        ai = path_to_audio_idx.get(normalized_video)
                        if ai is None:
                            missing_audio_paths.add(path_i)
                            logger.debug(f"   Cannot find audio for video: {Path(path_i).name} (normalized: {normalized_video})")
                            continue
                        for j, path_j in enumerate(paths_for_matrix):
                            aj = path_to_audio_idx.get(normalize_path(path_j))
                            if aj is None:
                                missing_audio_paths.add(path_j)
                                continue
                            audio_subset[i, j] = audio_matrix[ai, aj]
                    if missing_audio_paths:
                        logger.warning(
                            f"⚠️ Unable to align audio rows for {len(missing_audio_paths)} video(s); "
                            "those pairs will use audio-only zeros in the combined matrix."
                        )
                else:
                    audio_subset = np.zeros_like(video_matrix)
                
                local_combined = self.create_combined_similarity_matrix(
                    audio_subset,
                    video_matrix,
                    optical_flows=optical_flows if optical_flows else None,
                    video_paths=paths_for_matrix,
                    optical_flow_threshold=self.optical_flow_threshold
                )
                
                # Project the local combined scores back into global order
                for local_i, path_i in enumerate(paths_for_matrix):
                    gi = path_to_global_idx.get(path_i)
                    if gi is None or gi >= combined_matrix.shape[0]:
                        continue
                    for local_j, path_j in enumerate(paths_for_matrix):
                        gj = path_to_global_idx.get(path_j)
                        if gj is None or gj >= combined_matrix.shape[0]:
                            continue
                        combined_matrix[gi, gj] = local_combined[local_i, local_j]
            else:
                logger.warning("⚠️ No video similarity matrix available; falling back to audio-only similarities for video comparisons.")

            # Additional gating for Video/Karaoke pairs using local video indices where possible
            if audio_matrix.size > 0:
                for idx_i in video_indices:
                    for idx_j in video_indices:
                        if idx_j <= idx_i:
                            continue
 
                        if idx_i >= combined_matrix.shape[0] or idx_j >= combined_matrix.shape[0]:
                            continue
 
                        a_sim = float(audio_matrix[idx_i, idx_j]) if (
                            idx_i < audio_matrix.shape[0] and idx_j < audio_matrix.shape[0]
                        ) else 0.0
                        local_i = global_to_local_idx.get(idx_i)
                        local_j = global_to_local_idx.get(idx_j)
                        v_sim = float(video_matrix[local_i, local_j]) if (
                            local_i is not None and local_j is not None and video_matrix.size > 0
                        ) else 0.0
 
                        vtype_i = str(video_types[idx_i]).strip().lower()
                        vtype_j = str(video_types[idx_j]).strip().lower()
                        is_karaoke_pair = any(k in vtype_i for k in ['karaoke', 'lyric']) and \
                                          any(k in vtype_j for k in ['karaoke', 'lyric'])

                        if is_karaoke_pair:
                            # FORCE DEBUG: Log everything for Karaoke pairs to diagnose issues
                            logger.info(f"🔍 KARAOKE CHECK [{idx_i}↔{idx_j}]: Audio={a_sim:.3f}, Video={v_sim:.3f}")
                            
                            # Rule dành riêng cho Karaoke (SIẾT LẠI)
                            # 1) Video cực giống (>= 0.92) thì mới tin hoàn toàn (tăng từ 0.90)
                            if v_sim >= 0.92:
                                logger.info(
                                    f"  ✅ Karaoke ACCEPTED (High Video) [{idx_i}↔{idx_j}]: "
                                    f"audio={a_sim:.3f}, video={v_sim:.3f}≥0.92"
                                )
                            else:
                                # 2) Nếu video chỉ khá (>= 0.85) thì audio phải ổn hơn (>= 0.65, tăng từ 0.60)
                                if v_sim < 0.85 or a_sim < 0.65:
                                    combined_matrix[idx_i, idx_j] = 0.0
                                    combined_matrix[idx_j, idx_i] = 0.0
                                    logger.info(
                                        f"  ❌ Karaoke REJECTED [{idx_i}↔{idx_j}]: "
                                        f"audio={a_sim:.3f} (need≥0.65) hoặc video={v_sim:.3f} (need≥0.85)"
                                    )
                                    continue

                                logger.info(
                                    f"  ✅ Karaoke ACCEPTED (Moderate) [{idx_i}↔{idx_j}]: "
                                    f"audio={a_sim:.3f}≥0.65 AND video={v_sim:.3f}≥0.85"
                                )
                        else:
                            # Rule cho Video thường (NỚI LỎNG NHẸ)
                            # Hạ ngưỡng audio xuống 0.65 (thay vì 0.70-0.75 mặc định) để bắt cặp 23-25
                            # Vẫn giữ video threshold >= 0.85 để tránh false positive
                            if a_sim < 0.65 or v_sim < self.video_threshold:
                                combined_matrix[idx_i, idx_j] = 0.0
                                combined_matrix[idx_j, idx_i] = 0.0
                                logger.debug(
                                    f"  ⛔ Rejected [{idx_i}↔{idx_j}]: "
                                    f"audio={a_sim:.3f} (need≥0.65) "
                                    f"hoặc video={v_sim:.3f} (need≥{self.video_threshold:.2f})"
                                )
                                continue

                            logger.debug(
                                f"  ✓ Passed [{idx_i}↔{idx_j}]: "
                                f"audio={a_sim:.3f}≥0.65 "
                                f"AND video={v_sim:.3f}≥{self.video_threshold:.2f}"
                            )
 
                        # Boost combined similarity for near-identical pairs so they reliably pass threshold
                        if a_sim >= 0.96 and v_sim >= 0.85:
                            old_val = combined_matrix[idx_i, idx_j]
                            boosted = max(old_val, 0.85)
                            combined_matrix[idx_i, idx_j] = boosted
                            combined_matrix[idx_j, idx_i] = boosted
                            logger.info(
                                f"🎤 Boost applied [{idx_i}↔{idx_j}]: audio={a_sim:.3f}, video={v_sim:.3f}, "
                                f"combined {old_val:.3f}→{boosted:.3f}"
                            )
 
                        # Optional singer-count penalty: if singer counts differ, heavily reduce similarity
                        if singer_counts is not None:
                            if idx_i < len(singer_counts) and idx_j < len(singer_counts):
                                si = singer_counts[idx_i] or 0
                                sj = singer_counts[idx_j] or 0
                                if si > 0 and sj > 0 and si != sj:
                                    old_val = combined_matrix[idx_i, idx_j]
                                    penalty = float(self.config.get('thresholds.singer_mismatch_penalty', 0.5))
                                    combined_matrix[idx_i, idx_j] *= penalty
                                    combined_matrix[idx_j, idx_i] *= penalty
                                    new_val = combined_matrix[idx_i, idx_j]
                                    logger.warning(
                                        f"🎙️ Singer penalty [{idx_i}↔{idx_j}]: {si} vs {sj} singers, "
                                        f"combined {old_val:.3f}→{new_val:.3f} (×{penalty})"
                                    )
            
            # Create sub-matrix for all non-audio videos (for statistics and static detection)
            video_submatrix = np.zeros((len(video_indices), len(video_indices)))
            for idx_i, i in enumerate(video_indices):
                for idx_j, j in enumerate(video_indices):
                    if i < combined_matrix.shape[0] and j < combined_matrix.shape[0]:
                        video_submatrix[idx_i, idx_j] = combined_matrix[i, j]
            
            logger.info(f"Created video sub-matrix: {video_submatrix.shape}")
            
            # Adjust threshold for static images by examining local optical flows
            effective_threshold = self.combined_threshold
            if optical_flows and paths_for_matrix:
                static_pair_count = 0
                for i in range(len(paths_for_matrix)):
                    flow_i = optical_flows.get(paths_for_matrix[i], float('inf'))
                    if flow_i >= self.optical_flow_threshold:
                        continue
                    for j in range(i + 1, len(paths_for_matrix)):
                        flow_j = optical_flows.get(paths_for_matrix[j], float('inf'))
                        if flow_j < self.optical_flow_threshold:
                            static_pair_count += 1
                
                if static_pair_count > 0:
                    logger.info(f"📷 Found {static_pair_count} static image pairs - using threshold 0.70 for static pairs")
                    effective_threshold = 0.70
                else:
                    logger.debug(
                        f"📷 No static image pairs found in this cluster (threshold: {self.optical_flow_threshold})"
                    )
            
            # Log overall video similarity statistics
            if len(video_indices) > 1:
                upper_tri = []
                for idx_i in range(len(video_indices)):
                    for idx_j in range(idx_i + 1, len(video_indices)):
                        upper_tri.append(video_submatrix[idx_i, idx_j])
                
                if upper_tri:
                    max_sim = np.max(upper_tri)
                    avg_sim = np.mean(upper_tri)
                    min_sim = np.min(upper_tri)
                    above_threshold = sum(1 for s in upper_tri if s >= effective_threshold)
                    logger.info(f"🎬 Video similarity statistics (all non-audio):")
                    logger.info(f"  Max: {max_sim:.3f}, Avg: {avg_sim:.3f}, Min: {min_sim:.3f}")
                    logger.info(f"  Pairs ≥{effective_threshold:.1%}: {above_threshold}/{len(upper_tri)}")
            
            # ------------------------------------------------------------------
            # Optional restriction: only compare within the same Type group
            # ------------------------------------------------------------------
            type_groups = {'video': [], 'karaoke': [], 'other': []}
            for idx in video_indices:
                vtype_str = str(video_types[idx]).strip().lower()
                if any(k in vtype_str for k in ['karaoke', 'lyric']):
                    key = 'karaoke'
                elif any(k in vtype_str for k in ['video', 'mv']):
                    key = 'video'
                else:
                    key = 'other'
                type_groups[key].append(idx)
            
            video_clusters: List[ReuploadCluster] = []
            
            for group_name, indices_in_group in type_groups.items():
                if not indices_in_group:
                    continue
                
                if self.compare_within_same_type_only and len(indices_in_group) < 2:
                    logger.info(
                        f"Skipping reupload detection for Type group '{group_name}' with only 1 video "
                        f"(indices={indices_in_group})"
                    )
                    continue
                
                group_urls = [urls[i] for i in indices_in_group]
                group_metadata = [metadata_list[i] for i in indices_in_group]
                group_types = [video_types[i] for i in indices_in_group]
                
                group_matrix = np.zeros((len(indices_in_group), len(indices_in_group)))
                for gi, i in enumerate(indices_in_group):
                    for gj, j in enumerate(indices_in_group):
                        if i < combined_matrix.shape[0] and j < combined_matrix.shape[0]:
                            group_matrix[gi, gj] = combined_matrix[i, j]
                
                logger.info(
                    f"Creating clusters for Type group '{group_name}' with {len(indices_in_group)} videos "
                    f"(effective_threshold={effective_threshold:.1%})"
                )
                
                group_clusters = self.create_clusters(
                    group_matrix,
                    group_urls,
                    group_metadata,
                    group_types,
                    threshold=effective_threshold,
                )
                video_clusters.extend(group_clusters)
            
            logger.info(f"🎬 Found {len(video_clusters)} video clusters with threshold={effective_threshold:.1%}")
            all_clusters.extend(video_clusters)
        
        # Statistics
        total_reuploads = sum(len(c.reupload_urls) for c in all_clusters)
        logger.info(f"Detection complete: {len(all_clusters)} clusters total, {total_reuploads} reuploads found")
        
        return all_clusters
    
    def get_statistics(self, clusters: List[ReuploadCluster], total_videos_processed: int = None) -> Dict:
        """Get statistics about detected reuploads"""
        
        # If total not provided, calculate from clusters
        if total_videos_processed is None:
            total_videos = len(clusters) + sum(len(c.reupload_urls) for c in clusters)
        else:
            total_videos = total_videos_processed
            
        total_originals = len(clusters)
        total_reuploads = sum(len(c.reupload_urls) for c in clusters)
        
        # Group by video type
        type_stats = defaultdict(int)
        for cluster in clusters:
            type_stats[cluster.video_type] += len(cluster.reupload_urls)
        
        # Average similarity per cluster
        avg_similarities = [
            np.mean(c.similarities) if c.similarities else 0.0
            for c in clusters
        ]
        overall_avg_similarity = np.mean(avg_similarities) if avg_similarities else 0.0
        
        stats = {
            'total_videos': total_videos,
            'total_originals': total_originals,
            'total_reuploads': total_reuploads,
            'reupload_percentage': (total_reuploads / total_videos * 100) if total_videos > 0 else 0,
            'type_distribution': dict(type_stats),
            'average_similarity': overall_avg_similarity,
            'clusters': len(clusters)
        }
        
        return stats

