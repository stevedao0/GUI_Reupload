"""Video analysis and comparison using deep learning"""
import cv2
import os
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
import torchvision.models as models
import torchvision.transforms as transforms
from ..utils.logger import setup_logger
from .video_features_enhanced import VideoFeaturesEnhanced

logger = setup_logger(__name__)

# Suppress OpenCV/FFmpeg warnings (AAC decoder warnings)
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'  # Suppress all FFmpeg logs
cv2.setLogLevel(0)  # Suppress OpenCV INFO/WARN logs


@dataclass
class VideoFeatures:
    """Video feature representation"""
    path: str
    embeddings: np.ndarray  # Frame embeddings
    global_embedding: np.ndarray  # Average embedding
    optical_flow_magnitude: float  # Average motion magnitude
    num_frames: int
    fps: float
    duration: float
    enhanced_features: dict = None  # Enhanced features (brightness, color, scene)


class VideoAnalyzer:
    """Analyze and compare video files using deep learning"""
    
    def __init__(self, config):
        self.config = config
        self.device = self._setup_device()
        self.model_type = config.get('video.model', 'clip')
        self.keyframe_interval = config.get('video.keyframe_interval', 1.0)
        self.skip_initial_seconds = config.get('video.skip_initial_seconds', 3)
        self.sampling_mode = config.get('video.sampling_mode', 'interval')  # 'interval' or 'uniform'
        self.max_keyframes = config.get('video.max_keyframes', 64)
        self.batch_size = config.get('gpu.batch_size', 32)
        self.fp16 = config.get('gpu.fp16', True)
        
        # Load model
        self.model, self.processor = self._load_model()
        
        logger.info(f"VideoAnalyzer initialized: device={self.device}, model={self.model_type}, skip_initial={self.skip_initial_seconds}s")
    
    def _setup_device(self) -> torch.device:
        """Setup computing device (GPU/CPU)"""
        if not self.config.get('gpu.enabled', True):
            return torch.device('cpu')
        
        if torch.cuda.is_available():
            device = torch.device('cuda')
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
            logger.info("Using Apple Silicon GPU")
        else:
            device = torch.device('cpu')
            logger.info("Using CPU")
        
        return device
    
    def _load_model(self):
        """Load deep learning model for feature extraction"""
        try:
            if self.model_type == 'clip':
                logger.info("Loading CLIP model...")
                model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                model = model.to(self.device)
                model.eval()
                return model, processor
                
            elif self.model_type == 'resnet50':
                logger.info("Loading ResNet50 model...")
                model = models.resnet50(pretrained=True)
                # Remove final classification layer
                model = torch.nn.Sequential(*list(model.children())[:-1])
                model = model.to(self.device)
                model.eval()
                
                # Standard ImageNet preprocessing
                processor = transforms.Compose([
                    transforms.Resize(256),
                    transforms.CenterCrop(224),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                       std=[0.229, 0.224, 0.225]),
                ])
                return model, processor
                
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")
                
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def extract_keyframes(self, video_path: str) -> List[np.ndarray]:
        """Extract keyframes from video according to sampling mode, skipping initial seconds"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate frame to start from (skip initial seconds)
            skip_frames = int(fps * self.skip_initial_seconds) if fps > 0 else 0
            if skip_frames >= total_frames:
                skip_frames = 0  # Fallback if metadata is weird
            
            keyframes: List[np.ndarray] = []
            
            if self.sampling_mode == 'uniform' and total_frames > 0:
                # Uniform sampling across the whole video (after skip)
                available_frames = max(1, total_frames - skip_frames)
                num_samples = min(self.max_keyframes, available_frames)
                frame_indices = np.linspace(skip_frames, total_frames - 1, num_samples, dtype=int)
                
                logger.info(
                    f"Extracting keyframes (uniform): fps={fps:.1f}, total={total_frames}, "
                    f"skip={skip_frames} frames ({self.skip_initial_seconds}s), samples={num_samples}"
                )
                
                for idx in frame_indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    keyframes.append(frame_rgb)
            else:
                # Interval-based sampling (current behavior)
                frame_interval = int(fps * self.keyframe_interval) if fps > 0 else 1
                if frame_interval <= 0:
                    frame_interval = 1
                
                frame_idx = 0
                
                logger.info(
                    f"Extracting keyframes (interval): fps={fps:.1f}, total={total_frames}, "
                    f"interval={frame_interval}, skip={skip_frames} frames ({self.skip_initial_seconds}s)"
                )
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Skip initial frames
                    if frame_idx < skip_frames:
                        frame_idx += 1
                        continue
                    
                    # Extract at interval (after skipping initial frames)
                    if (frame_idx - skip_frames) % frame_interval == 0:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        keyframes.append(frame_rgb)
                    
                    frame_idx += 1
            
            cap.release()
            
            logger.info(
                f"Extracted {len(keyframes)} keyframes from {Path(video_path).name} "
                f"(mode={self.sampling_mode}, skipped first {self.skip_initial_seconds}s)"
            )
            return keyframes
            
        except Exception as e:
            logger.error(f"Failed to extract keyframes from {video_path}: {e}")
            raise
    
    def calculate_optical_flow(self, video_path: str, sample_frames: int = 30) -> float:
        """Calculate average optical flow magnitude to detect motion, skipping initial seconds"""
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate frame to start from (skip initial seconds)
            skip_frames = int(fps * self.skip_initial_seconds) if fps > 0 else 0
            available_frames = max(1, total_frames - skip_frames)
            
            # Sample frames evenly across video (after skipping initial frames)
            frame_indices = np.linspace(skip_frames, total_frames - 1, sample_frames, dtype=int)
            
            # Read first frame (after skip)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_indices[0])
            ret, prev_frame = cap.read()
            if not ret:
                return 0.0
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            
            flow_magnitudes = []
            
            for target_idx in frame_indices[1:]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calculate optical flow
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                )
                
                # Calculate magnitude
                magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                avg_magnitude = np.mean(magnitude)
                flow_magnitudes.append(avg_magnitude)
                
                prev_gray = gray
            
            cap.release()
            
            avg_flow = np.mean(flow_magnitudes)
            logger.info(f"Optical flow magnitude: {avg_flow:.2f}")
            
            return float(avg_flow)
            
        except Exception as e:
            logger.error(f"Failed to calculate optical flow for {video_path}: {e}")
            return 0.0
    
    def extract_features(self, video_path: str) -> VideoFeatures:
        """Extract deep features from video"""
        try:
            logger.info(f"Extracting video features: {Path(video_path).name}")
            
            # Get video info
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            
            # Extract keyframes
            keyframes = self.extract_keyframes(video_path)
            
            # Extract embeddings
            embeddings = []
            
            for i in range(0, len(keyframes), self.batch_size):
                batch = keyframes[i:i + self.batch_size]
                batch_embeddings = self._extract_batch_embeddings(batch)
                embeddings.extend(batch_embeddings)
            
            embeddings = np.array(embeddings)
            global_embedding = np.mean(embeddings, axis=0)
            
            # Calculate optical flow
            optical_flow = self.calculate_optical_flow(video_path)
            
            # Extract enhanced features (brightness, color, scene)
            enhanced_features = VideoFeaturesEnhanced.extract_all_enhanced_features(keyframes)
            
            features = VideoFeatures(
                path=video_path,
                embeddings=embeddings,
                global_embedding=global_embedding,
                optical_flow_magnitude=optical_flow,
                num_frames=len(keyframes),
                fps=fps,
                duration=duration,
                enhanced_features=enhanced_features
            )
            
            logger.info(f"Video features extracted: {len(keyframes)} frames, flow={optical_flow:.2f}")
            logger.info(f"Enhanced: {enhanced_features['brightness']['brightness_category']}, "
                       f"{enhanced_features['performance']['performance_type']}")
            return features
            
        except Exception as e:
            logger.error(f"Failed to extract video features from {video_path}: {e}")
            raise
    
    def _extract_batch_embeddings(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        """Extract embeddings for a batch of frames"""
        try:
            if self.model_type == 'clip':
                # Process with CLIP
                images = [Image.fromarray(frame) for frame in frames]
                inputs = self.processor(images=images, return_tensors="pt", padding=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    if self.fp16 and self.device.type == 'cuda':
                        with torch.cuda.amp.autocast():
                            image_features = self.model.get_image_features(**inputs)
                    else:
                        image_features = self.model.get_image_features(**inputs)
                    
                    # Normalize features
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                    embeddings = image_features.cpu().numpy()
                
            else:  # ResNet or other
                # Process with torchvision transforms
                batch_tensors = []
                for frame in frames:
                    pil_image = Image.fromarray(frame)
                    tensor = self.processor(pil_image)
                    batch_tensors.append(tensor)
                
                batch_tensor = torch.stack(batch_tensors).to(self.device)
                
                with torch.no_grad():
                    if self.fp16 and self.device.type == 'cuda':
                        with torch.cuda.amp.autocast():
                            features = self.model(batch_tensor)
                    else:
                        features = self.model(batch_tensor)
                    
                    embeddings = features.squeeze().cpu().numpy()
                    
                    # Ensure 2D array
                    if len(embeddings.shape) == 1:
                        embeddings = embeddings.reshape(1, -1)
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Failed to extract batch embeddings: {e}")
            raise
    
    def compare_features(self, features1: VideoFeatures, features2: VideoFeatures) -> float:
        """Compare two video features and return similarity score"""
        try:
            # 1. CLIP semantic similarity (visual content)
            cos_sim = np.dot(features1.global_embedding, features2.global_embedding) / (
                np.linalg.norm(features1.global_embedding) * np.linalg.norm(features2.global_embedding)
            )
            # Ensure in [0, 1] range
            clip_similarity = (cos_sim + 1) / 2
            
            # 2. Enhanced features similarity (scene matching)
            if features1.enhanced_features and features2.enhanced_features:
                enhanced_sim = VideoFeaturesEnhanced.compare_enhanced_features(
                    features1.enhanced_features,
                    features2.enhanced_features
                )
                
                # Get combined enhanced score
                enhanced_score = enhanced_sim['combined_enhanced_score']
                
                # If CLIP similarity is very high (>0.95), trust CLIP more
                # This handles cases where content is identical but lighting/scene differs slightly
                if clip_similarity > 0.95:
                    # High CLIP = same content, so trust it more (80% CLIP, 20% Enhanced)
                    clip_weight = 0.8
                    enhanced_weight = 0.2
                elif clip_similarity > 0.85:
                    # Medium-high CLIP (70% CLIP, 30% Enhanced)
                    clip_weight = 0.7
                    enhanced_weight = 0.3
                else:
                    # Lower CLIP, balance both (60% CLIP, 40% Enhanced)
                    clip_weight = 0.6
                    enhanced_weight = 0.4
                
                # Combine CLIP + Enhanced with adaptive weights
                # CLIP for content/person, Enhanced for scene/lighting/location
                final_similarity = clip_weight * clip_similarity + enhanced_weight * enhanced_score
                
                logger.info(f"Video similarity: CLIP={clip_similarity:.3f}, "
                           f"Enhanced={enhanced_score:.3f}, "
                           f"Final={final_similarity:.3f} "
                           f"(weights: CLIP={clip_weight:.1f}, Enhanced={enhanced_weight:.1f})")
                logger.info(f"  → {enhanced_sim['explanation']}")
                
                return float(max(0.0, min(1.0, final_similarity)))
            else:
                # Fall back to CLIP only if enhanced features not available
                logger.info(f"Video similarity (CLIP only): {clip_similarity:.3f}")
                return float(max(0.0, min(1.0, clip_similarity)))
            
        except Exception as e:
            logger.error(f"Failed to compare video features: {e}")
            return 0.0
    
    def batch_extract_features(self, video_paths: List[str], is_cancelled=None) -> Dict[str, VideoFeatures]:
        """Extract features from multiple videos.
        If is_cancelled callback is provided and returns True, stops early.
        """
        logger.info(f"Extracting features from {len(video_paths)} videos")
        
        features_dict = {}
        for i, path in enumerate(video_paths, 1):
            if is_cancelled and is_cancelled():
                logger.info("Cancellation requested during video feature extraction - stopping early")
                break
            try:
                logger.info(f"Processing video {i}/{len(video_paths)}")
                features = self.extract_features(path)
                features_dict[path] = features
            except Exception as e:
                logger.error(f"Skipping {path} due to error: {e}")
                continue
        
        logger.info(f"Successfully extracted features from {len(features_dict)} videos")
        if is_cancelled and is_cancelled():
            logger.warning("Video feature extraction was cancelled by user")
        return features_dict
    
    def create_similarity_matrix(self, features_dict: Dict[str, VideoFeatures]) -> Tuple[np.ndarray, List[str]]:
        """Create pairwise similarity matrix for all videos"""
        paths = list(features_dict.keys())
        n = len(paths)
        
        logger.info(f"Creating {n}x{n} video similarity matrix")
        
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            similarity_matrix[i, i] = 1.0
            
            for j in range(i + 1, n):
                sim = self.compare_features(
                    features_dict[paths[i]],
                    features_dict[paths[j]]
                )
                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim
        
        logger.info("Video similarity matrix created")
        return similarity_matrix, paths

