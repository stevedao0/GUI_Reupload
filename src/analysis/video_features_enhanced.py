"""Enhanced video feature extraction for detailed comparison"""
import cv2
import numpy as np
from typing import List, Tuple
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class VideoFeaturesEnhanced:
    """Enhanced video features for detailed comparison"""
    
    @staticmethod
    def analyze_brightness(frames: List[np.ndarray]) -> dict:
        """
        Analyze brightness to detect night performance
        
        Returns:
            dict with brightness stats and night detection
        """
        brightness_values = []
        
        for frame in frames:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            # Calculate mean brightness
            brightness = np.mean(gray)
            brightness_values.append(brightness)
        
        avg_brightness = np.mean(brightness_values)
        std_brightness = np.std(brightness_values)
        
        # Night detection (low brightness)
        # Typical values: Day=100-200, Indoor=50-100, Night/Stage=20-60
        is_night = avg_brightness < 70
        is_very_dark = avg_brightness < 40
        
        return {
            'average_brightness': avg_brightness,
            'std_brightness': std_brightness,
            'min_brightness': np.min(brightness_values),
            'max_brightness': np.max(brightness_values),
            'is_night_performance': is_night,
            'is_very_dark_stage': is_very_dark,
            'brightness_category': VideoFeaturesEnhanced._categorize_brightness(avg_brightness)
        }
    
    @staticmethod
    def _categorize_brightness(brightness: float) -> str:
        """Categorize brightness level"""
        if brightness < 30:
            return "Very Dark (Night stage/club)"
        elif brightness < 50:
            return "Dark (Indoor performance)"
        elif brightness < 70:
            return "Dim (Stage with lights)"
        elif brightness < 100:
            return "Indoor (Normal lighting)"
        elif brightness < 150:
            return "Bright (Well-lit indoor)"
        else:
            return "Very Bright (Outdoor/Studio)"
    
    @staticmethod
    def analyze_color_distribution(frames: List[np.ndarray], sample_size: int = 10) -> dict:
        """
        Analyze color distribution for matching stage/scene
        
        Args:
            frames: List of frames
            sample_size: Number of frames to sample
        
        Returns:
            dict with color statistics
        """
        # Sample frames evenly
        indices = np.linspace(0, len(frames)-1, min(sample_size, len(frames)), dtype=int)
        sampled_frames = [frames[i] for i in indices]
        
        color_histograms = []
        dominant_colors = []
        
        for frame in sampled_frames:
            # Calculate color histogram for each channel
            hist_r = cv2.calcHist([frame], [0], None, [32], [0, 256])
            hist_g = cv2.calcHist([frame], [1], None, [32], [0, 256])
            hist_b = cv2.calcHist([frame], [2], None, [32], [0, 256])
            
            # Normalize
            hist_r = hist_r.flatten() / hist_r.sum()
            hist_g = hist_g.flatten() / hist_g.sum()
            hist_b = hist_b.flatten() / hist_b.sum()
            
            color_histograms.append(np.concatenate([hist_r, hist_g, hist_b]))
            
            # Get dominant color
            avg_color = np.mean(frame.reshape(-1, 3), axis=0)
            dominant_colors.append(avg_color)
        
        # Average histogram
        avg_histogram = np.mean(color_histograms, axis=0)
        
        # Average dominant color
        avg_dominant = np.mean(dominant_colors, axis=0)
        
        # Color temperature (warm vs cool)
        r, g, b = avg_dominant
        color_temp = 'warm' if r > b else 'cool'
        
        return {
            'color_histogram': avg_histogram,
            'dominant_color_rgb': avg_dominant,
            'color_temperature': color_temp,
            'red_dominance': float(r / (r + g + b + 1e-6)),
            'green_dominance': float(g / (r + g + b + 1e-6)),
            'blue_dominance': float(b / (r + g + b + 1e-6))
        }
    
    @staticmethod
    def compare_color_histograms(hist1: np.ndarray, hist2: np.ndarray) -> float:
        """
        Compare two color histograms
        
        Returns:
            Similarity score 0-1
        """
        # Correlation method
        correlation = cv2.compareHist(
            hist1.astype(np.float32),
            hist2.astype(np.float32),
            cv2.HISTCMP_CORREL
        )
        return float(max(0, correlation))
    
    @staticmethod
    def analyze_scene_consistency(frames: List[np.ndarray], sample_size: int = 20) -> dict:
        """
        Analyze scene consistency (same location/stage)
        
        Returns:
            dict with scene consistency metrics
        """
        # Sample frames
        indices = np.linspace(0, len(frames)-1, min(sample_size, len(frames)), dtype=int)
        sampled_frames = [frames[i] for i in indices]
        
        # Calculate frame-to-frame differences
        differences = []
        for i in range(len(sampled_frames) - 1):
            frame1 = cv2.cvtColor(sampled_frames[i], cv2.COLOR_RGB2GRAY)
            frame2 = cv2.cvtColor(sampled_frames[i+1], cv2.COLOR_RGB2GRAY)
            
            # Resize for faster computation
            frame1 = cv2.resize(frame1, (64, 64))
            frame2 = cv2.resize(frame2, (64, 64))
            
            # Calculate difference
            diff = np.mean(np.abs(frame1.astype(float) - frame2.astype(float)))
            differences.append(diff)
        
        avg_diff = np.mean(differences)
        std_diff = np.std(differences)
        
        # Low difference = consistent scene (same stage/location)
        # High difference = many scene changes (different locations)
        is_consistent_scene = avg_diff < 30  # Threshold tuned for stage performances
        
        return {
            'average_scene_change': avg_diff,
            'std_scene_change': std_diff,
            'is_consistent_scene': is_consistent_scene,
            'scene_stability': 'Stable (Same location)' if is_consistent_scene else 'Dynamic (Multiple scenes)'
        }
    
    @staticmethod
    def detect_stage_performance(frames: List[np.ndarray]) -> dict:
        """
        Detect characteristics of stage performance
        
        Returns:
            dict with stage performance indicators
        """
        # Sample frames
        sample_size = min(10, len(frames))
        indices = np.linspace(0, len(frames)-1, sample_size, dtype=int)
        sampled_frames = [frames[i] for i in indices]
        
        # Indicators
        dark_frame_count = 0
        bright_spot_count = 0  # Stage lights
        
        for frame in sampled_frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            avg_brightness = np.mean(gray)
            
            # Count dark frames (night performance)
            if avg_brightness < 60:
                dark_frame_count += 1
            
            # Detect bright spots (stage lights)
            bright_pixels = np.sum(gray > 200)
            total_pixels = gray.size
            if bright_pixels / total_pixels > 0.05:  # >5% very bright pixels
                bright_spot_count += 1
        
        has_stage_lights = bright_spot_count > sample_size * 0.3
        is_night_performance = dark_frame_count > sample_size * 0.5
        
        return {
            'has_stage_lighting': has_stage_lights,
            'is_night_performance': is_night_performance,
            'dark_frame_ratio': dark_frame_count / sample_size,
            'performance_type': VideoFeaturesEnhanced._classify_performance_type(
                is_night_performance,
                has_stage_lights
            )
        }
    
    @staticmethod
    def _classify_performance_type(is_night: bool, has_lights: bool) -> str:
        """Classify performance type"""
        if is_night and has_lights:
            return "Night Stage Performance (Concert/Show)"
        elif is_night and not has_lights:
            return "Indoor Dark Performance (Club/Bar)"
        elif not is_night and has_lights:
            return "Indoor Stage (Studio/Theater)"
        else:
            return "Outdoor/Bright Indoor"
    
    @staticmethod
    def extract_all_enhanced_features(frames: List[np.ndarray]) -> dict:
        """
        Extract all enhanced features at once
        
        Args:
            frames: List of RGB frames
        
        Returns:
            dict with all enhanced features
        """
        logger.info("Extracting enhanced video features...")
        
        features = {}
        
        # Brightness analysis
        features['brightness'] = VideoFeaturesEnhanced.analyze_brightness(frames)
        
        # Color distribution
        features['color'] = VideoFeaturesEnhanced.analyze_color_distribution(frames)
        
        # Scene consistency
        features['scene'] = VideoFeaturesEnhanced.analyze_scene_consistency(frames)
        
        # Stage performance detection
        features['performance'] = VideoFeaturesEnhanced.detect_stage_performance(frames)
        
        logger.info(f"Enhanced features: {features['brightness']['brightness_category']}, "
                   f"{features['performance']['performance_type']}, "
                   f"{features['scene']['scene_stability']}")
        
        return features
    
    @staticmethod
    def compare_enhanced_features(features1: dict, features2: dict) -> dict:
        """
        Compare two sets of enhanced features
        
        Returns:
            dict with similarity scores and explanations
        """
        similarities = {}
        
        # 1. Brightness similarity
        bright1 = features1['brightness']['average_brightness']
        bright2 = features2['brightness']['average_brightness']
        bright_diff = abs(bright1 - bright2)
        bright_sim = max(0, 1 - bright_diff / 100)  # Normalize by 100
        similarities['brightness_similarity'] = bright_sim
        
        # 2. Same night performance?
        same_night = (features1['brightness']['is_night_performance'] == 
                     features2['brightness']['is_night_performance'])
        similarities['same_time_of_day'] = same_night
        
        # 3. Color histogram similarity
        color_sim = VideoFeaturesEnhanced.compare_color_histograms(
            features1['color']['color_histogram'],
            features2['color']['color_histogram']
        )
        similarities['color_similarity'] = color_sim
        
        # 4. Same performance type? (CRITICAL: indoor vs outdoor)
        same_perf_type = (features1['performance']['performance_type'] == 
                         features2['performance']['performance_type'])
        similarities['same_performance_type'] = same_perf_type
        
        # If different performance type (indoor vs outdoor), apply severe penalty
        perf_type_penalty = 1.0 if same_perf_type else 0.2  # 80% penalty if different
        
        # 5. Scene consistency match
        scene_sim = 1.0 if (features1['scene']['is_consistent_scene'] == 
                           features2['scene']['is_consistent_scene']) else 0.5
        similarities['scene_consistency_match'] = scene_sim
        
        # Combined score
        # Weight: brightness=0.2, color=0.3, performance_type=0.3, scene=0.2
        # Apply penalty if different performance type
        base_score = (
            0.2 * bright_sim +
            0.3 * color_sim +
            0.3 * (1.0 if same_perf_type else 0.0) +
            0.2 * scene_sim
        )
        
        # Apply severe penalty if different performance type (indoor vs outdoor)
        combined_score = base_score * perf_type_penalty
        
        similarities['combined_enhanced_score'] = combined_score
        
        # Explanation
        if combined_score > 0.7:
            explanation = "Likely same performance/location"
        elif combined_score > 0.5:
            explanation = "Similar performance conditions"
        else:
            explanation = "Different performance/location"
        
        similarities['explanation'] = explanation
        
        return similarities

