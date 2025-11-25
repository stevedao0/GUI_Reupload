"""Karaoke detection using OCR and optical flow analysis"""
import cv2
import os
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import easyocr
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

# Suppress OpenCV/FFmpeg warnings (AAC decoder warnings)
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'  # Suppress all FFmpeg logs
cv2.setLogLevel(0)  # Suppress OpenCV INFO/WARN logs


@dataclass
class KaraokeFeatures:
    """Karaoke detection features"""
    path: str
    has_text: bool
    text_confidence: float
    text_regions: List[Tuple[int, int, int, int]]  # Bounding boxes
    is_bottom_region: bool  # Text in bottom region
    optical_flow: float  # From video analyzer
    video_type: str  # Audio, Video, Midi Karaoke, MV Karaoke


class KaraokeDetector:
    """Detect and classify karaoke videos"""
    
    def __init__(self, config):
        self.config = config
        self.ocr_engine = config.get('karaoke.ocr_engine', 'easyocr')
        self.languages = config.get('karaoke.languages', ['en', 'vi'])
        self.text_region = config.get('karaoke.text_region', [0.6, 1.0])
        self.flow_threshold = config.get('thresholds.optical_flow_threshold', 5.0)
        
        # Initialize OCR
        self.reader = None
        self._init_ocr()
        
        logger.info(f"KaraokeDetector initialized: engine={self.ocr_engine}, languages={self.languages}")
    
    def _init_ocr(self):
        """Initialize OCR engine"""
        try:
            if self.ocr_engine == 'easyocr':
                logger.info("Initializing EasyOCR...")
                self.reader = easyocr.Reader(self.languages, gpu=True)
                logger.info("EasyOCR initialized")
            elif self.ocr_engine == 'paddleocr':
                from paddleocr import PaddleOCR
                logger.info("Initializing PaddleOCR...")
                self.reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True)
                logger.info("PaddleOCR initialized")
            else:
                raise ValueError(f"Unknown OCR engine: {self.ocr_engine}")
        except Exception as e:
            logger.error(f"Failed to initialize OCR: {e}")
            logger.warning("OCR disabled - karaoke detection will be limited")
    
    def detect_text_in_frame(self, frame: np.ndarray) -> Tuple[bool, float, List]:
        """Detect text in a single frame"""
        try:
            if self.reader is None:
                return False, 0.0, []
            
            if self.ocr_engine == 'easyocr':
                results = self.reader.readtext(frame)
                
                if not results:
                    return False, 0.0, []
                
                # Extract bounding boxes and confidences
                boxes = []
                confidences = []
                
                for (bbox, text, conf) in results:
                    # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    
                    x1, y1 = int(min(x_coords)), int(min(y_coords))
                    x2, y2 = int(max(x_coords)), int(max(y_coords))
                    
                    boxes.append((x1, y1, x2, y2))
                    confidences.append(conf)
                
                avg_confidence = np.mean(confidences) if confidences else 0.0
                has_text = avg_confidence > self.config.get('thresholds.karaoke_text_confidence', 0.5)
                
                return has_text, avg_confidence, boxes
                
            elif self.ocr_engine == 'paddleocr':
                result = self.reader.ocr(frame, cls=True)
                
                if not result or not result[0]:
                    return False, 0.0, []
                
                boxes = []
                confidences = []
                
                for line in result[0]:
                    bbox, (text, conf) = line
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    
                    x1, y1 = int(min(x_coords)), int(min(y_coords))
                    x2, y2 = int(max(x_coords)), int(max(y_coords))
                    
                    boxes.append((x1, y1, x2, y2))
                    confidences.append(conf)
                
                avg_confidence = np.mean(confidences) if confidences else 0.0
                has_text = avg_confidence > self.config.get('thresholds.karaoke_text_confidence', 0.5)
                
                return has_text, avg_confidence, boxes
            
        except Exception as e:
            logger.error(f"Error detecting text in frame: {e}")
            return False, 0.0, []
    
    def is_text_in_bottom_region(self, boxes: List[Tuple], frame_height: int) -> bool:
        """Check if text is in bottom region of frame (typical for karaoke)"""
        if not boxes:
            return False
        
        bottom_threshold = frame_height * self.text_region[0]
        
        # Check if majority of text boxes are in bottom region
        bottom_count = 0
        for (x1, y1, x2, y2) in boxes:
            box_center_y = (y1 + y2) / 2
            if box_center_y >= bottom_threshold:
                bottom_count += 1
        
        return bottom_count / len(boxes) > 0.5  # More than 50% in bottom
    
    def detect_karaoke(self, video_path: str, optical_flow: float, sample_frames: int = 10) -> KaraokeFeatures:
        """Detect if video is karaoke and classify type"""
        try:
            logger.info(f"Detecting karaoke features: {Path(video_path).name}")
            
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Sample frames evenly across video
            frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)
            
            text_detections = []
            all_boxes = []
            
            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                
                if not ret:
                    continue
                
                # Detect text
                has_text, confidence, boxes = self.detect_text_in_frame(frame)
                text_detections.append((has_text, confidence))
                all_boxes.extend(boxes)
            
            cap.release()
            
            # Aggregate results
            has_text_count = sum(1 for (has, _) in text_detections if has)
            avg_confidence = np.mean([conf for (_, conf) in text_detections])
            
            has_karaoke_text = has_text_count >= sample_frames * 0.3  # 30% of frames have text
            is_bottom = self.is_text_in_bottom_region(all_boxes, frame_height) if all_boxes else False
            
            # Classify video type
            video_type = self._classify_video_type(
                has_karaoke_text, 
                is_bottom, 
                optical_flow
            )
            
            features = KaraokeFeatures(
                path=video_path,
                has_text=has_karaoke_text,
                text_confidence=float(avg_confidence),
                text_regions=all_boxes,
                is_bottom_region=is_bottom,
                optical_flow=optical_flow,
                video_type=video_type
            )
            
            logger.info(f"Karaoke detection: type={video_type}, text={has_karaoke_text}, flow={optical_flow:.2f}")
            return features
            
        except Exception as e:
            logger.error(f"Failed to detect karaoke for {video_path}: {e}")
            # Return default features
            return KaraokeFeatures(
                path=video_path,
                has_text=False,
                text_confidence=0.0,
                text_regions=[],
                is_bottom_region=False,
                optical_flow=optical_flow,
                video_type="Audio"
            )
    
    def _classify_video_type(self, has_text: bool, is_bottom: bool, optical_flow: float) -> str:
        """Classify video type based on text and motion features"""
        
        # Decision tree for classification
        if has_text and is_bottom:
            # Has karaoke text in bottom region
            if optical_flow > self.flow_threshold:
                return "MV Karaoke"  # Dynamic video with karaoke text
            else:
                return "Midi Karaoke"  # Static/minimal motion with karaoke text
        else:
            # No karaoke text detected
            if optical_flow > self.flow_threshold / 2:  # Lower threshold for non-karaoke
                return "Video"  # Dynamic video without karaoke
            else:
                return "Audio"  # Static image (lyric video, audio visualizer)
    
    def batch_detect(self, video_paths: List[str], optical_flows: Dict[str, float]) -> Dict[str, KaraokeFeatures]:
        """Detect karaoke for multiple videos"""
        logger.info(f"Detecting karaoke for {len(video_paths)} videos")
        
        features_dict = {}
        for i, path in enumerate(video_paths, 1):
            try:
                logger.info(f"Processing video {i}/{len(video_paths)}")
                optical_flow = optical_flows.get(path, 0.0)
                features = self.detect_karaoke(path, optical_flow)
                features_dict[path] = features
            except Exception as e:
                logger.error(f"Skipping {path} due to error: {e}")
                continue
        
        logger.info(f"Successfully detected karaoke for {len(features_dict)} videos")
        return features_dict

