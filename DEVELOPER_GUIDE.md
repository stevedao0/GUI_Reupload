# 💻 Developer Guide

**YouTube Reupload Detector - Technical Documentation**

---

## 📑 **Table of Contents**

1. [System Architecture](#system-architecture)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Adding Features](#adding-features)
6. [Testing](#testing)
7. [Contributing](#contributing)

---

## 🏗️ **System Architecture**

### **Overview**

```
┌─────────────────┐
│   GUI (PyQt6)   │
└────────┬────────┘
         │
    ┌────▼────────────────┐
    │ Processing Pipeline │
    └────┬────────────────┘
         │
    ┌────▼────┐     ┌──────────┐
    │Download │────▶│ Analysis │
    └─────────┘     └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐
         │ Audio  │ │ Video  │ │Karaoke │
         │Analyzer│ │Analyzer│ │Detector│
         └────┬───┘ └───┬────┘ └───┬────┘
              │         │          │
              └─────────┼──────────┘
                        │
                   ┌────▼─────────┐
                   │   Detection  │
                   │  (Clustering)│
                   └──────┬───────┘
                          │
                     ┌────▼────┐
                     │ Export  │
                     └─────────┘
```

### **Components:**

1. **GUI Layer** - User interface (PyQt6)
2. **Pipeline** - Orchestration & workflow
3. **Downloader** - YouTube video download (yt-dlp)
4. **Analyzers** - Feature extraction (audio/video/karaoke)
5. **Detector** - Similarity & clustering
6. **Utils** - Shared utilities (config, logging, time parsing)

---

## 📁 **Project Structure**

```
Reupload/
├── main.py                      # Entry point
├── config.yaml                  # Configuration
├── requirements.txt             # Dependencies
│
├── src/
│   ├── __init__.py
│   │
│   ├── gui/                     # GUI components
│   │   ├── __init__.py
│   │   ├── main_window.py       # Main window (PyQt6)
│   │   └── professional_theme.py # Dark theme
│   │
│   ├── downloader/              # Download module
│   │   ├── __init__.py
│   │   └── youtube_downloader.py # yt-dlp wrapper
│   │
│   ├── analysis/                # Analysis modules
│   │   ├── __init__.py
│   │   ├── audio_analyzer.py    # Audio features (MFCC, etc.)
│   │   ├── video_analyzer.py    # Video features (CLIP, etc.)
│   │   ├── video_features_enhanced.py # Enhanced features
│   │   └── karaoke_detector.py  # OCR detection
│   │
│   ├── detection/               # Detection module
│   │   ├── __init__.py
│   │   └── reupload_detector.py # Clustering algorithm
│   │
│   ├── pipeline/                # Processing pipeline
│   │   ├── __init__.py
│   │   └── processing_pipeline.py # Workflow orchestration
│   │
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── logger.py            # Logging setup
│       ├── config.py            # Config loader
│       └── time_parser.py       # Time parsing
│
├── docs/                        # Documentation
│   ├── USER_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   └── DEVELOPER_GUIDE.md (this file)
│
├── temp_downloads/              # Temporary files (gitignored)
│   ├── videos/
│   └── audios/
│
└── tests/                       # Test scripts
    ├── test_gpu.py
    ├── test_audio_only.py
    └── debug_similarity.py
```

---

## 🔧 **Core Components**

### **1. YouTube Downloader**

**File:** `src/downloader/youtube_downloader.py`

**Class:** `YouTubeDownloader`

**Key Methods:**
```python
def download_video(url, start_time=None, end_time=None, progress_callback=None)
    # Download single video with optional segment

def download_batch_with_segments(urls_metadata, progress_callback=None)
    # Batch download with parallel processing

def _trim_media(input_path, output_path, start_time, end_time)
    # Trim video/audio using ffmpeg
```

**Features:**
- Parallel downloads (ThreadPoolExecutor)
- Concurrent fragment downloads (yt-dlp)
- Progress callbacks
- Automatic trimming for segments
- Separate video + audio extraction

**Dependencies:**
- yt-dlp: Video download
- ffmpeg: Media processing

---

### **2. Audio Analyzer**

**File:** `src/analysis/audio_analyzer.py`

**Class:** `AudioAnalyzer`

**Features Extracted:**
```python
@dataclass
class AudioFeatures:
    mfcc: np.ndarray              # Mel-frequency cepstral coefficients
    chroma: np.ndarray            # Chromagram (pitch content)
    spectral_contrast: np.ndarray # Spectral contrast
    tempo: float                  # Beats per minute
    duration: float               # Audio duration
```

**Key Methods:**
```python
def extract_features(audio_path) -> AudioFeatures
    # Extract all audio features from file

def compare_features(features1, features2) -> float
    # Compare two AudioFeatures, return similarity (0-1)
    # Weighted: 50% MFCC, 25% Chroma, 15% Spectral, 10% Tempo

def create_similarity_matrix(features_dict) -> (np.ndarray, List[str])
    # Create NxN similarity matrix for all audio files
```

**Algorithm:**
```python
similarity = (
    0.50 * (1 - cosine(mfcc1, mfcc2)) +
    0.25 * (1 - cosine(chroma1, chroma2)) +
    0.15 * (1 - cosine(spectral1, spectral2)) +
    0.10 * tempo_similarity
)
```

**Dependencies:**
- librosa: Audio processing
- numpy: Arrays & computation

---

### **3. Video Analyzer**

**File:** `src/analysis/video_analyzer.py`

**Class:** `VideoAnalyzer`

**Features Extracted:**
```python
@dataclass
class VideoFeatures:
    clip_embeddings: np.ndarray  # CLIP semantic embeddings
    optical_flow: float          # Motion score
    keyframe_count: int          # Number of keyframes
    is_static: bool              # Static vs dynamic
    enhanced_features: dict      # Brightness, color, scene, performance
```

**Enhanced Features** (from `video_features_enhanced.py`):
```python
{
    'brightness': {
        'average': float,        # 0-255
        'category': str,         # dark/dim/normal/bright
    },
    'color': {
        'average_hue': float,    # 0-180 (HSV)
        'average_sat': float,    # 0-255
        'color_variance': float, # Color diversity
    },
    'scene_complexity': {
        'edge_density': float,   # Edge pixel count
        'texture_std': float,    # Texture variation
    },
    'performance': {
        'type': str,             # indoor/outdoor
        'lighting': str,         # day/night
    }
}
```

**Key Methods:**
```python
def extract_features(video_path) -> VideoFeatures
    # Extract frames → CLIP embeddings + enhanced features

def compare_features(features1, features2) -> float
    # Combined: 60% CLIP + 40% Enhanced
```

**Algorithm:**
```python
clip_sim = 1 - cosine(clip1, clip2)

enhanced_sim = average(
    brightness_similarity,
    color_similarity,
    scene_similarity,
    performance_match
)

final = 0.6 * clip_sim + 0.4 * enhanced_sim
```

**Dependencies:**
- transformers: CLIP model
- opencv-python: Video processing
- torch: Deep learning
- PIL: Image processing

---

### **4. Karaoke Detector**

**File:** `src/analysis/karaoke_detector.py`

**Class:** `KaraokeDetector`

**Key Methods:**
```python
def detect_text(video_path, num_frames=30) -> bool
    # Sample frames, run OCR, detect running text

def has_running_text(video_path) -> bool
    # Detect if text changes across frames (karaoke)
```

**Algorithm:**
1. Extract N evenly-spaced frames
2. Run OCR on each frame
3. Compare text across frames
4. If text changes → Karaoke detected

**Dependencies:**
- easyocr or paddleocr: OCR

---

### **5. Reupload Detector**

**File:** `src/detection/reupload_detector.py`

**Class:** `ReuploadDetector`

**Key Methods:**
```python
def detect_reuploads(audio_matrix, video_matrix, metadata_list) -> Dict
    # Main detection algorithm

def create_combined_similarity_matrix(audio_matrix, video_matrix) -> np.ndarray
    # Combine audio + video matrices with weights

def find_connected_components(similarity_matrix, threshold) -> List[Set[int]]
    # Graph-based clustering using DFS

def identify_original(indices, metadata_list) -> int
    # Find earliest upload in cluster (= original)
```

**Algorithm:**

1. **Combine Matrices:**
   ```python
   combined = (
       weights['audio'] * audio_matrix +
       weights['video'] * video_matrix
   )
   ```

2. **Build Graph:**
   ```python
   for each pair (i, j):
       if combined[i, j] >= threshold:
           add_edge(i, j)
   ```

3. **Find Connected Components (DFS):**
   ```python
   clusters = []
   for each node:
       if not visited:
           cluster = dfs(node)
           if len(cluster) > 1:
               clusters.append(cluster)
   ```

4. **Identify Originals:**
   ```python
   for each cluster:
       original = earliest_upload_date(cluster)
       reuploads = cluster - {original}
   ```

**Dependencies:**
- numpy: Matrix operations
- collections: defaultdict for graphs

---

### **6. Processing Pipeline**

**File:** `src/pipeline/processing_pipeline.py`

**Class:** `ProcessingPipeline`

**Workflow:**
```python
def process(urls, metadata, progress_callback, log_callback) -> Dict:
    1. Download all videos (parallel)
    2. Extract audio features (batch)
    3. Extract video features (batch)
    4. Create similarity matrices
    5. Detect reuploads (clustering)
    6. Return results
```

**Progress Callbacks:**
```python
progress_callback(current, total, status)
log_callback(message)
```

**Error Handling:**
- Graceful degradation (continue if some fail)
- Detailed logging
- Return partial results

---

## 🔄 **Data Flow**

### **Complete Flow:**

```
1. User loads Excel file
   ↓
2. GUI extracts URLs + metadata
   ↓
3. Pipeline.process(urls, metadata)
   ↓
4. Downloader.download_batch()
   │  - Parallel download
   │  - Extract video + audio
   │  - Trim segments (if specified)
   ↓
5. Audio Analyzer
   │  - Extract MFCC, Chroma, Spectral, Tempo
   │  - Create similarity matrix (NxN)
   ↓
6. Video Analyzer
   │  - Extract frames
   │  - CLIP embeddings
   │  - Enhanced features (brightness, color, scene)
   │  - Create similarity matrix (NxN)
   ↓
7. Reupload Detector
   │  - Combine audio + video matrices
   │  - Build similarity graph
   │  - Find connected components (clusters)
   │  - Identify originals (earliest upload)
   ↓
8. Pipeline.export_results()
   │  - Create Excel with multiple sheets
   │  - All Videos, Clusters, Matrix, Comparisons, Summary
   ↓
9. GUI displays results
```

### **Data Structures:**

#### **Video Metadata:**
```python
{
    'url': str,
    'id': str,
    'title': str,
    'upload_date': str,         # YYYY-MM-DD
    'duration': int,            # seconds
    'type': str,                # Video/Audio/Karaoke
    'start_time': int,          # seconds (if segment)
    'end_time': int,            # seconds (if segment)
    'video_path': str,
    'audio_path': str,
}
```

#### **Results:**
```python
{
    'clusters': [
        {
            'original_id': str,
            'original_index': int,
            'reupload_indices': [int, ...],
            'similarities': [float, ...],
        },
        ...
    ],
    'metadata': [dict, ...],          # All video metadata
    'audio_matrix': np.ndarray,       # NxN similarities
    'video_matrix': np.ndarray,       # NxN similarities
    'combined_matrix': np.ndarray,    # NxN combined
}
```

---

## ➕ **Adding Features**

### **Add New Analysis Feature**

#### **Example: Add "Audio Loudness" feature**

1. **Update AudioFeatures dataclass:**
   ```python
   # src/analysis/audio_analyzer.py
   @dataclass
   class AudioFeatures:
       # ... existing fields ...
       loudness: float  # NEW
   ```

2. **Extract feature:**
   ```python
   def extract_features(self, audio_path):
       # ... existing code ...
       
       # NEW: Extract loudness
       loudness = librosa.feature.rms(y=y)[0].mean()
       
       return AudioFeatures(
           # ... existing fields ...
           loudness=loudness
       )
   ```

3. **Update comparison:**
   ```python
   def compare_features(self, f1, f2):
       # ... existing code ...
       
       # NEW: Compare loudness
       loudness_diff = abs(f1.loudness - f2.loudness)
       loudness_sim = max(0, 1 - loudness_diff / 10)  # Normalize
       
       # Update weighted combination
       similarity = (
           0.45 * mfcc_sim +      # Reduced
           0.25 * chroma_sim +
           0.15 * spectral_sim +
           0.10 * tempo_sim +
           0.05 * loudness_sim    # NEW
       )
   ```

4. **Test:**
   ```bash
   python test_audio_only.py
   ```

---

### **Add New Analyzer**

#### **Example: Add "Thumbnail Analyzer"**

1. **Create new file:**
   ```python
   # src/analysis/thumbnail_analyzer.py
   from dataclasses import dataclass
   import numpy as np
   
   @dataclass
   class ThumbnailFeatures:
       color_hist: np.ndarray
       edge_hist: np.ndarray
   
   class ThumbnailAnalyzer:
       def extract_features(self, thumbnail_url):
           # Download thumbnail
           # Extract features
           return ThumbnailFeatures(...)
       
       def compare_features(self, f1, f2):
           # Compare histograms
           return similarity
   ```

2. **Integrate into pipeline:**
   ```python
   # src/pipeline/processing_pipeline.py
   from ..analysis.thumbnail_analyzer import ThumbnailAnalyzer
   
   def __init__(self, config):
       # ... existing ...
       self.thumbnail_analyzer = ThumbnailAnalyzer(config)
   
   def process(self, urls, metadata):
       # ... after video analysis ...
       
       # Extract thumbnail features
       thumb_features = {}
       for meta in metadata:
           features = self.thumbnail_analyzer.extract_features(
               meta['thumbnail']
           )
           thumb_features[meta['id']] = features
       
       # Create thumbnail matrix
       thumb_matrix, _ = self.thumbnail_analyzer.create_similarity_matrix(
           thumb_features
       )
       
       # Update detection to include thumbnail matrix
       results = self.reupload_detector.detect_reuploads(
           audio_matrix,
           video_matrix,
           thumb_matrix,  # NEW
           metadata_list
       )
   ```

3. **Update detector:**
   ```python
   # src/detection/reupload_detector.py
   def detect_reuploads(self, audio_matrix, video_matrix, 
                        thumb_matrix=None, metadata_list=None):
       
       # Update combined matrix
       if thumb_matrix is not None:
           combined = (
               weights['audio'] * audio_matrix +
               weights['video'] * video_matrix +
               weights['thumbnail'] * thumb_matrix
           )
   ```

4. **Update config:**
   ```yaml
   # config.yaml
   weights:
     audio: 0.35
     video: 0.35
     thumbnail: 0.10  # NEW
     karaoke: 0.20
   ```

---

## 🧪 **Testing**

### **Unit Tests**

**Create:** `tests/test_audio_analyzer.py`

```python
import unittest
from src.analysis.audio_analyzer import AudioAnalyzer
from src.utils.config import Config

class TestAudioAnalyzer(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.analyzer = AudioAnalyzer(self.config)
    
    def test_extract_features(self):
        features = self.analyzer.extract_features("test_audio.mp3")
        self.assertIsNotNone(features.mfcc)
        self.assertEqual(features.mfcc.shape[0], 20)
    
    def test_compare_features(self):
        f1 = self.analyzer.extract_features("audio1.mp3")
        f2 = self.analyzer.extract_features("audio2.mp3")
        similarity = self.analyzer.compare_features(f1, f2)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)

if __name__ == '__main__':
    unittest.main()
```

**Run:**
```bash
python -m unittest tests/test_audio_analyzer.py
```

---

### **Integration Tests**

**Test full pipeline:**

```python
# tests/test_integration.py
def test_full_pipeline():
    # Prepare test data
    urls = [
        "https://youtube.com/watch?v=test1",
        "https://youtube.com/watch?v=test2",
    ]
    metadata = [
        {'url': urls[0], 'type': 'Video'},
        {'url': urls[1], 'type': 'Video'},
    ]
    
    # Run pipeline
    pipeline = ProcessingPipeline(config)
    results = pipeline.process(urls, metadata)
    
    # Verify results
    assert 'clusters' in results
    assert 'metadata' in results
    assert len(results['metadata']) == 2
```

---

## 🤝 **Contributing**

### **Code Style**

- **PEP 8** compliance
- Type hints where possible
- Docstrings for classes/methods
- Comments for complex logic

**Example:**
```python
def compare_features(self, features1: AudioFeatures, 
                     features2: AudioFeatures) -> float:
    """
    Compare two audio features and return similarity score.
    
    Args:
        features1: First audio features
        features2: Second audio features
    
    Returns:
        Similarity score (0.0-1.0), where 1.0 is identical
    
    Raises:
        ValueError: If features have incompatible shapes
    """
    pass
```

---

### **Git Workflow**

1. **Fork repository**
2. **Create feature branch:**
   ```bash
   git checkout -b feature/new-feature
   ```

3. **Make changes, commit:**
   ```bash
   git add .
   git commit -m "Add new feature: ..."
   ```

4. **Push:**
   ```bash
   git push origin feature/new-feature
   ```

5. **Create Pull Request**

---

### **Commit Message Format**

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Formatting
- refactor: Code restructuring
- test: Tests
- chore: Maintenance

**Example:**
```
feat: Add thumbnail similarity analysis

- Created ThumbnailAnalyzer class
- Integrated into pipeline
- Added tests
- Updated config with thumbnail weights

Closes #42
```

---

## 📚 **Additional Resources**

### **Dependencies:**

- **yt-dlp:** https://github.com/yt-dlp/yt-dlp
- **librosa:** https://librosa.org/doc/latest/
- **transformers:** https://huggingface.co/docs/transformers/
- **opencv-python:** https://docs.opencv.org/
- **PyQt6:** https://www.riverbankcomputing.com/static/Docs/PyQt6/

### **Algorithms:**

- **CLIP:** https://arxiv.org/abs/2103.00020
- **MFCC:** Mel-frequency cepstral coefficients
- **Graph Clustering:** Connected components via DFS

---

## 💾 **File Cache & Resume System**

### **Overview**

The downloader implements a smart file cache system that prevents re-downloading files that already exist. This dramatically improves performance on re-runs and enables resume functionality after errors.

### **How It Works**

```
┌─────────────────────────────────────┐
│  Download Request: video.mp4        │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  Cache Check (< 1ms)                │
│  • File exists?                     │
│  • Readable?                        │
│  • Size > minimum?                  │
└─────────────────────────────────────┘
              ↓
        ✅ Valid?
              │
    ┌─────────┴─────────┐
   YES                  NO
    │                    │
    ↓                    ↓
┌───────────┐    ┌──────────────┐
│ CACHE HIT │    │ CACHE MISS   │
│ Use file  │    │ Download new │
└───────────┘    └──────────────┘
```

### **Configuration**

```yaml
download:
  # File Management
  keep_files: true        # KEEP files by default (RECOMMENDED)

  # Cache Settings
  enable_cache: true      # Enable cache system
  verify_file_size: true  # Check integrity
  min_file_size: 1024     # Minimum valid size (1KB)
```

### **Safety Features**

#### **1. Keep Files By Default**
```python
keep_files: true  # ✅ Default behavior - NEVER auto-delete
```

**Why?**
- Enables cache/resume functionality
- Prevents accidental data loss
- Makes re-runs 75%+ faster
- Saves bandwidth and time

#### **2. Clear Warnings Before Deletion**
```
============================================================
⚠️  WARNING: DELETING ALL DOWNLOADED FILES!
   📁 Location: /path/to/temp_downloads
   📹 Videos: 150 files
   🎵 Audio: 150 files
   📊 Total: 300 files
   This action CANNOT be undone!
============================================================
```

#### **3. Corrupted File Detection**
```python
# Auto-detect and re-download corrupted files
if file_size < 100KB:  # Video too small
    delete_and_redownload()
```

### **File Structure**

```
temp_downloads/
├── videos/
│   ├── abc123.mp4              # Final (kept)
│   ├── xyz789.mp4              # Final (kept)
│   └── temp_12345678.mp4       # Temp (deleted after processing)
├── audios/
│   ├── abc123.mp3              # Final (kept)
│   ├── xyz789.mp3              # Final (kept)
│   └── temp_87654321.mp3       # Temp (deleted after processing)
└── abc123_metadata.json        # Metadata (kept)
```

### **Performance Impact**

**Without Cache:**
```
100 videos × 30 seconds = 3000 seconds (50 minutes)
```

**With Cache (75% hit rate):**
```
25 videos × 30 seconds = 750 seconds (12.5 minutes)
Savings: 37.5 minutes per run! (75% faster)
```

### **Cache Statistics**

The system tracks cache performance:

```python
stats = downloader.get_cache_stats()
# {
#     'cache_hits': 150,
#     'cache_misses': 50,
#     'corrupted_files': 2,
#     'total_requests': 200,
#     'hit_rate_percent': 75.0
# }
```

Console output:
```
============================================================
📊 CACHE STATISTICS:
   ✅ Cache Hits:       150
   ⬇️  Cache Misses:     50
   ⚠️  Corrupted Files:  2
   �� Cache Hit Rate:   75.0%
   🎯 Total Requests:   200
============================================================
```

### **Best Practices**

1. **Always keep `keep_files: true`** unless disk space is critical
2. **Enable cache** for faster re-runs
3. **Monitor cache stats** to optimize performance
4. **Let corrupted files auto-delete** - they're re-downloaded automatically
5. **Never manually delete temp_downloads/** while processing

### **Troubleshooting**

**Q: Files were deleted, how to prevent this?**
```yaml
# Set in config.yaml:
download:
  keep_files: true  # ✅ Must be true
```

**Q: How to manually clean up old files?**
```yaml
# Temporarily set:
download:
  keep_files: false  # ⚠️ Deletes all files!
```

Then change back to `true` after cleanup.

**Q: Cache hit but file is corrupted?**
System auto-detects and re-downloads. Check logs for:
```
⚠️  Cached video file is corrupted, will re-download
```

---

**Version:** 1.3.0
**Last Updated:** 2024-11-26
**For Contributors & Developers**

