"""Audio analysis and comparison using audio fingerprinting"""
import numpy as np
import librosa
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from scipy.spatial.distance import cosine
from sklearn.cluster import KMeans
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class AudioFeatures:
    """Audio feature representation"""
    path: str
    mfcc: np.ndarray  # Mel-frequency cepstral coefficients
    chroma: np.ndarray  # Chromagram
    spectral_contrast: np.ndarray
    tempo: float
    duration: float
    # Remix detection features
    spectral_rolloff_mean: float = 0.0
    spectral_rolloff_std: float = 0.0
    zcr_mean: float = 0.0
    zcr_std: float = 0.0
    spectral_bandwidth_mean: float = 0.0
    spectral_bandwidth_std: float = 0.0
    # Estimated number of main singers (approximate voice count)
    num_singers_estimate: int = 1


class AudioAnalyzer:
    """Analyze and compare audio files"""
    
    def __init__(self, config):
        self.config = config
        self.sample_rate = config.get('audio.sample_rate', 22050)
        self.duration_limit = config.get('audio.duration_limit', 180)
        self.skip_initial_seconds = config.get('audio.skip_initial_seconds', 3)
        self.num_segments = config.get('audio.num_segments', 5)  # Extract from multiple segments
        self.cache = {}
    
    def extract_features(self, audio_path: str) -> AudioFeatures:
        """Extract audio features from file, skipping initial seconds and using multiple segments"""
        try:
            logger.info(f"Extracting audio features: {Path(audio_path).name}")
            
            # Get full audio duration
            full_duration = librosa.get_duration(path=audio_path)
            
            # Calculate segment duration (divide available time after skip)
            skip_seconds = self.skip_initial_seconds
            available_duration = min(self.duration_limit, full_duration - skip_seconds)
            if available_duration <= 0:
                available_duration = min(self.duration_limit, full_duration)
                skip_seconds = 0
            
            segment_duration = available_duration / self.num_segments if self.num_segments > 1 else available_duration
            
            # Extract features from multiple segments
            all_mfcc = []
            all_chroma = []
            all_spectral = []
            all_rolloff = []
            all_zcr = []
            all_bandwidth = []
            tempo_list = []
            
            for i in range(self.num_segments):
                # Calculate segment start time (skip initial + offset for this segment)
                segment_start = skip_seconds + (i * segment_duration)
                
                # Load segment
                y_segment, sr = librosa.load(
                    audio_path,
                    sr=self.sample_rate,
                    offset=segment_start,
                    duration=segment_duration
                )
                
                if len(y_segment) == 0:
                    continue
                
                # Extract features from this segment
                mfcc_seg = librosa.feature.mfcc(y=y_segment, sr=sr, n_mfcc=20)
                all_mfcc.append(np.mean(mfcc_seg, axis=1))
                
                chroma_seg = librosa.feature.chroma_stft(y=y_segment, sr=sr)
                all_chroma.append(np.mean(chroma_seg, axis=1))
                
                spectral_seg = librosa.feature.spectral_contrast(y=y_segment, sr=sr)
                all_spectral.append(np.mean(spectral_seg, axis=1))
                
                # Tempo (only for first segment to avoid overhead)
                if i == 0:
                    tempo, _ = librosa.beat.beat_track(y=y_segment, sr=sr)
                    tempo_list.append(tempo)
                
                # Remix detection features
                rolloff_seg = librosa.feature.spectral_rolloff(y=y_segment, sr=sr)[0]
                all_rolloff.extend(rolloff_seg)
                
                zcr_seg = librosa.feature.zero_crossing_rate(y_segment)[0]
                all_zcr.extend(zcr_seg)
                
                bandwidth_seg = librosa.feature.spectral_bandwidth(y=y_segment, sr=sr)[0]
                all_bandwidth.extend(bandwidth_seg)
            
            # Average features across all segments
            mfcc_mean = np.mean(all_mfcc, axis=0) if all_mfcc else np.zeros(20)
            chroma_mean = np.mean(all_chroma, axis=0) if all_chroma else np.zeros(12)
            spectral_mean = np.mean(all_spectral, axis=0) if all_spectral else np.zeros(7)
            tempo = np.mean(tempo_list) if tempo_list else 120.0
            
            rolloff_mean = np.mean(all_rolloff) if all_rolloff else 0.0
            rolloff_std = np.std(all_rolloff) if all_rolloff else 0.0
            zcr_mean = np.mean(all_zcr) if all_zcr else 0.0
            zcr_std = np.std(all_zcr) if all_zcr else 0.0
            bandwidth_mean = np.mean(all_bandwidth) if all_bandwidth else 0.0
            bandwidth_std = np.std(all_bandwidth) if all_bandwidth else 0.0

            # ------------------------------------------------------------------
            # Singer count estimation (approximate number of main voices)
            # ------------------------------------------------------------------
            num_singers_estimate = 1
            try:
                # Use per-segment MFCC means as features for clustering.
                # Each element in all_mfcc corresponds roughly to an equal-duration segment.
                if len(all_mfcc) >= 2:
                    X = np.vstack(all_mfcc)
                    max_clusters = int(self.config.get('audio.singer_max_clusters', 3))
                    max_clusters = max(1, min(max_clusters, len(all_mfcc)))

                    # Run KMeans with a small number of clusters (up to 3)
                    kmeans = KMeans(n_clusters=max_clusters, n_init=10, random_state=42)
                    labels = kmeans.fit_predict(X)

                    # Compute share of segments per cluster (≈ time share per voice)
                    total_segments = len(labels)
                    shares = []
                    for cid in range(max_clusters):
                        count = int(np.sum(labels == cid))
                        share = count / total_segments if total_segments > 0 else 0.0
                        shares.append(share)

                    # Sort shares descending to reason about dominant voices
                    shares.sort(reverse=True)

                    # Check if shares are too uniform (indicates insufficient samples or single voice)
                    # If all shares are nearly equal, likely a single singer with noise/backing
                    variance = np.var(shares) if len(shares) > 0 else 0.0
                    if max_clusters >= 2 and variance < 0.01:  # Very low variance = uniform distribution
                        num_singers_estimate = 1
                        logger.info(
                            "Estimated singers: %d (uniform distribution detected: variance=%.4f, shares=%s)",
                            num_singers_estimate,
                            variance,
                            ", ".join(f"{s:.2f}" for s in shares),
                        )
                    else:
                        # Heuristics to avoid over-counting backing vocals/short noises
                        p1 = shares[0] if len(shares) > 0 else 1.0
                        p2 = shares[1] if len(shares) > 1 else 0.0
                        p3 = shares[2] if len(shares) > 2 else 0.0

                        # Thresholds can be tuned from config if needed
                        solo_dom_threshold = float(self.config.get('audio.singer_solo_threshold', 0.80))
                        duo_main_threshold = float(self.config.get('audio.singer_duo_main_threshold', 0.60))
                        duo_second_threshold = float(self.config.get('audio.singer_duo_second_threshold', 0.20))
                        trio_min_share = float(self.config.get('audio.singer_trio_min_share', 0.15))

                        # Case 1: clearly solo – one very dominant cluster, others tiny
                        if p1 >= solo_dom_threshold and p2 < trio_min_share:
                            # One dominant voice, others are likely backing/short
                            num_singers_estimate = 1
                        # Case 2: at least two strong clusters → likely duo/trio
                        elif p1 >= duo_main_threshold and p2 >= duo_second_threshold:
                            # Two relatively strong voices
                            # If the third cluster is tiny, still count as 2
                            if (p1 + p2) >= 0.80 and p3 < 0.10:
                                num_singers_estimate = 2
                            else:
                                # Three noticeable clusters only if each has enough share
                                if max_clusters >= 3 and p3 >= trio_min_share:
                                    num_singers_estimate = 3
                                else:
                                    num_singers_estimate = 2
                        else:
                            # More balanced distribution; cap at 3 and ignore very small clusters
                            effective_clusters = sum(1 for s in shares if s >= trio_min_share)
                            if effective_clusters <= 1:
                                num_singers_estimate = 1
                            elif effective_clusters == 2:
                                num_singers_estimate = 2
                            else:
                                num_singers_estimate = 3

                        logger.info(
                            "Estimated singers: %d (segment shares: %s)",
                            num_singers_estimate,
                            ", ".join(f"{s:.2f}" for s in shares),
                        )
            except Exception as e:
                # Singer estimation is best-effort; log and fall back to 1 singer on failure
                logger.warning(f"Singer count estimation failed for {audio_path}: {e}")
                num_singers_estimate = 1
            
            features = AudioFeatures(
                path=audio_path,
                mfcc=mfcc_mean,
                chroma=chroma_mean,
                spectral_contrast=spectral_mean,
                tempo=float(tempo),
                duration=full_duration,
                spectral_rolloff_mean=float(rolloff_mean),
                spectral_rolloff_std=float(rolloff_std),
                zcr_mean=float(zcr_mean),
                zcr_std=float(zcr_std),
                spectral_bandwidth_mean=float(bandwidth_mean),
                spectral_bandwidth_std=float(bandwidth_std),
                num_singers_estimate=int(num_singers_estimate),
            )
            
            logger.info(
                "Audio features extracted: %d segments, skip=%ss, duration=%.1fs, tempo=%.1f, singers≈%d",
                self.num_segments,
                skip_seconds,
                full_duration,
                features.tempo,
                features.num_singers_estimate,
            )
            return features
            
        except Exception as e:
            logger.error(f"Failed to extract audio features from {audio_path}: {e}")
            raise
    
    def compare_features(self, features1: AudioFeatures, features2: AudioFeatures) -> float:
        """Compare two audio features and return similarity score (0-1)"""
        try:
            # Compare MFCC (most important for audio fingerprinting)
            mfcc_sim = 1 - cosine(features1.mfcc, features2.mfcc)
            
            # Compare chroma (pitch content)
            chroma_sim = 1 - cosine(features1.chroma, features2.chroma)
            
            # Compare spectral contrast
            spectral_sim = 1 - cosine(features1.spectral_contrast, features2.spectral_contrast)
            
            # Compare tempo
            tempo_diff = abs(features1.tempo - features2.tempo)
            tempo_sim = max(0, 1 - tempo_diff / 100)  # Normalize by 100 BPM
            
            # Compare remix features (detect effects/processing differences)
            # Remix typically has different spectral characteristics
            rolloff_diff = abs(features1.spectral_rolloff_mean - features2.spectral_rolloff_mean)
            rolloff_sim = max(0, 1 - rolloff_diff / 2000)  # Stricter normalization - remix has higher rolloff
            
            zcr_diff = abs(features1.zcr_mean - features2.zcr_mean)
            zcr_sim = max(0, 1 - zcr_diff / 0.05)  # Stricter - remix often has different ZCR
            
            bandwidth_diff = abs(features1.spectral_bandwidth_mean - features2.spectral_bandwidth_mean)
            bandwidth_sim = max(0, 1 - bandwidth_diff / 1000)  # Stricter - remix has wider bandwidth
            
            # Average remix features similarity
            remix_features_sim = (rolloff_sim + zcr_sim + bandwidth_sim) / 3
            
            # Log remix features comparison (for debugging)
            logger.debug(f"Remix features comparison:")
            logger.debug(f"  Rolloff: {rolloff_sim:.3f} (diff={rolloff_diff:.1f})")
            logger.debug(f"  ZCR: {zcr_sim:.3f} (diff={zcr_diff:.4f})")
            logger.debug(f"  Bandwidth: {bandwidth_sim:.3f} (diff={bandwidth_diff:.1f})")
            logger.debug(f"  Average remix similarity: {remix_features_sim:.3f}")
            
            # Weighted combination (original features)
            base_similarity = (
                0.50 * mfcc_sim +        # MFCC is most important
                0.25 * chroma_sim +       # Pitch content
                0.15 * spectral_sim +     # Timbre
                0.10 * tempo_sim          # Tempo
            )
            
            # If remix features are very different, apply penalty
            # BUT: If base_similarity is very high (>0.80), significantly reduce penalty
            # This allows remixes of the same audio to be grouped together
            if remix_features_sim > 0.85:
                remix_penalty = 1.0  # Same type (both original or both remix)
            elif remix_features_sim > 0.60:
                remix_penalty = 0.80  # Somewhat different (20% penalty, reduced from 25%)
            elif remix_features_sim > 0.40:
                # If base similarity is very high (>0.85), likely both are remixes of same audio
                if base_similarity > 0.85:
                    remix_penalty = 0.90  # Very reduced penalty for very high base similarity (increased from 0.85)
                elif base_similarity > 0.80:
                    remix_penalty = 0.80  # Reduced penalty for high base similarity (increased from 0.7)
                elif base_similarity > 0.75:
                    remix_penalty = 0.70  # Moderate penalty for medium-high base similarity
                else:
                    remix_penalty = 0.5  # Moderate penalty (50% penalty)
            else:
                # Extremely different remix features
                if base_similarity > 0.85:
                    remix_penalty = 0.80  # Significant reduction for very high base similarity (increased from 0.75)
                elif base_similarity > 0.80:
                    remix_penalty = 0.70  # Reduced penalty for high base similarity (increased from 0.6)
                elif base_similarity > 0.75:
                    remix_penalty = 0.60  # Moderate penalty for medium-high base similarity
                else:
                    remix_penalty = 0.35  # Severe penalty (65% penalty)
            
            if remix_penalty < 1.0:
                logger.info(f"⚠ Remix penalty applied: {remix_penalty:.2f} (remix_features_sim={remix_features_sim:.3f}, base_sim={base_similarity:.3f})")
            
            # Apply remix penalty (if effects are very different, reduce similarity)
            similarity = base_similarity * remix_penalty

            # Rule #3: Additional remix penalty boost for tempo/chroma discrepancies
            # DISABLED: Tempo detection can be inaccurate (double/half tempo mistakes)
            # Only apply penalty for VERY obvious remixes (tempo > 40% different)
            try:
                rel_tempo_diff = 0.0
                if max(features1.tempo, features2.tempo, 1e-6) > 0:
                    rel_tempo_diff = abs(features1.tempo - features2.tempo) / max(features1.tempo, features2.tempo, 1e-6)

                # Only penalize if tempo is VERY different (>40%) AND chroma is also low
                if rel_tempo_diff > 0.40 and chroma_sim < 0.50:
                    similarity *= 0.85
                    logger.info(
                        f"💡 Remix penalty applied (very different): rel_tempo_diff={rel_tempo_diff:.3f}, chroma_sim={chroma_sim:.3f} → sim={similarity:.3f}"
                    )
            except Exception:
                pass
            
            # Debug logging (only log if penalty is significant)
            if remix_penalty < 1.0:
                logger.debug(f"Audio comparison breakdown (REMIX DETECTED):")
                logger.debug(f"  MFCC: {mfcc_sim:.3f} (weight 50%)")
                logger.debug(f"  Chroma: {chroma_sim:.3f} (weight 25%)")
                logger.debug(f"  Spectral: {spectral_sim:.3f} (weight 15%)")
                logger.debug(f"  Tempo: {tempo_sim:.3f} (weight 10%)")
                logger.debug(f"  Base similarity: {base_similarity:.3f}")
                logger.debug(f"  Remix features: {remix_features_sim:.3f} (penalty={remix_penalty:.2f})")
                logger.debug(f"  → Final (after penalty): {similarity:.3f}")
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Failed to compare audio features: {e}")
            logger.exception(e)
            return 0.0
    
    def compare_audio_files(self, path1: str, path2: str) -> float:
        """Compare two audio files and return similarity score"""
        try:
            # Extract features
            features1 = self.extract_features(path1)
            features2 = self.extract_features(path2)
            
            # Compare
            similarity = self.compare_features(features1, features2)
            
            logger.info(f"Audio similarity: {similarity:.3f}")
            return similarity
            
        except Exception as e:
            logger.error(f"Failed to compare audio files: {e}")
            return 0.0
    
    def batch_extract_features(self, audio_paths: List[str], is_cancelled=None) -> Dict[str, AudioFeatures]:
        """Extract features from multiple audio files.
        If is_cancelled callback is provided and returns True, stops early.
        """
        logger.info(f"🎵 Extracting AUDIO features from {len(audio_paths)} files...")
        
        features_dict = {}
        for i, path in enumerate(audio_paths, 1):
            if is_cancelled and is_cancelled():
                logger.info("Cancellation requested during audio feature extraction - stopping early")
                break
            try:
                filename = Path(path).name
                logger.info(f"  [{i}/{len(audio_paths)}] Processing: {filename}")
                features = self.extract_features(path)
                features_dict[path] = features
                logger.info(f"  ✓ Success: MFCC shape={features.mfcc.shape}, Tempo={features.tempo:.1f} BPM")
            except Exception as e:
                logger.error(f"  ✗ Failed: {Path(path).name} - {e}")
                logger.exception(e)
                continue
        
        success_rate = len(features_dict) / len(audio_paths) * 100 if audio_paths else 0
        logger.info(f"🎵 Audio extraction: {len(features_dict)}/{len(audio_paths)} files ({success_rate:.0f}%)")
        
        if is_cancelled and is_cancelled():
            logger.warning("Audio feature extraction was cancelled by user")
        
        if len(features_dict) == 0:
            logger.error("⚠ NO AUDIO FEATURES EXTRACTED - Audio comparison will fail!")
        elif len(features_dict) < len(audio_paths):
            logger.warning(f"⚠ Some audio files failed: {len(audio_paths) - len(features_dict)} failures")
        
        return features_dict
    
    def create_similarity_matrix(self, features_dict: Dict[str, AudioFeatures]) -> Tuple[np.ndarray, List[str]]:
        """Create pairwise similarity matrix for all audio files"""
        paths = list(features_dict.keys())
        n = len(paths)
        
        logger.info(f"🎵 Creating {n}x{n} AUDIO similarity matrix ({n*(n-1)//2} comparisons)...")
        
        similarity_matrix = np.zeros((n, n))
        comparisons = []
        
        for i in range(n):
            similarity_matrix[i, i] = 1.0  # Self-similarity
            
            for j in range(i + 1, n):
                sim = self.compare_features(
                    features_dict[paths[i]], 
                    features_dict[paths[j]]
                )
                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim
                
                # Store for stats
                comparisons.append(sim)
                
                # Log individual comparisons
                file_i = Path(paths[i]).stem
                file_j = Path(paths[j]).stem
                logger.info(f"  [{i}↔{j}] {file_i} vs {file_j}: {sim:.3f}")
        
        # Statistics
        if comparisons:
            max_sim = max(comparisons)
            min_sim = min(comparisons)
            avg_sim = sum(comparisons) / len(comparisons)
            
            logger.info(f"🎵 AUDIO similarity matrix complete:")
            logger.info(f"  Max: {max_sim:.3f}, Min: {min_sim:.3f}, Avg: {avg_sim:.3f}")
            
            # Count above thresholds
            above_60 = sum(1 for s in comparisons if s >= 0.60)
            above_70 = sum(1 for s in comparisons if s >= 0.70)
            above_75 = sum(1 for s in comparisons if s >= 0.75)
            above_80 = sum(1 for s in comparisons if s >= 0.80)
            
            logger.info(f"  Pairs ≥60%: {above_60}/{len(comparisons)}")
            logger.info(f"  Pairs ≥70%: {above_70}/{len(comparisons)}")
            logger.info(f"  Pairs ≥75%: {above_75}/{len(comparisons)} ← Audio threshold")
            logger.info(f"  Pairs ≥80%: {above_80}/{len(comparisons)}")
            
            if above_75 == 0 and max_sim >= 0.60:
                logger.warning(f"⚠ No audio pairs above 75% threshold (max={max_sim:.1%})")
                logger.warning(f"💡 Consider lowering audio_similarity threshold to ~{max(0.55, max_sim - 0.05):.2f}")
        
        return similarity_matrix, paths

