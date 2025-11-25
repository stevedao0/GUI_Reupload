# Changelog

## [1.3.0] - 2024-10-30

### 🚀 Performance Improvements
- ✅ **2.5x Faster Downloads**: Concurrent fragment downloads (8 fragments per video)
- ✅ **Optimized Buffer & Chunk Sizes**: 10MB chunks, 4MB buffer
- ✅ **Increased Parallel Downloads**: 8 concurrent downloads (up from 6)
- ✅ **Smart Retry Logic**: 10 retries for failed downloads/fragments
- ✅ **Enhanced Audio Extraction**: Parallel processing with progress tracking

### 📊 Real-time Progress Logging
- ✅ **Download Progress**: Shows %, speed (MB/s), ETA for each video
- ✅ **Audio Progress**: Separate progress tracking for audio extraction
- ✅ **Visual Indicators**: Emoji icons (📥 video, 🎵 audio, ✓ complete)
- ✅ **Detailed Statistics**: Max/Min/Avg similarity scores
- ✅ **Threshold Recommendations**: Auto-suggest optimal thresholds

### 🎯 Enhanced Video Comparison
- ✅ **Brightness Analysis**: Categorize scenes (dark/dim/normal/bright)
- ✅ **Color Distribution**: HSV color analysis for better matching
- ✅ **Scene Complexity**: Edge density and texture analysis
- ✅ **Performance Type Detection**: Indoor/outdoor, day/night classification
- ✅ **Combined Scoring**: CLIP (60%) + Enhanced Features (40%)

### 🖱️ UI/UX Improvements
- ✅ **Professional Dark Theme**: VSCode-inspired modern dark theme
- ✅ **Terminal-style Logs**: Monospace font, color-coded output, timestamps
- ✅ **Status Bar**: Real-time status updates at bottom
- ✅ **Icons Throughout**: 📁 ⚙ ⚡ 📊 💻 for better visual hierarchy
- ✅ **Drag & Drop Support**: Kéo thả file Excel vào GUI
- ✅ **Visual Feedback**: Hover states, drop zone highlighting, tooltips
- ✅ **Enhanced Buttons**: Gradient backgrounds, larger sizes, better styling
- ✅ **Improved Spacing**: Professional margins, padding, layout
- ✅ **Better Fonts**: Segoe UI for UI, Consolas for terminal
- ✅ **Auto-load**: Automatically load file after drop
- ✅ **File Validation**: Only accept .xlsx and .xls files

### 🔍 Better Debugging
- ✅ **Audio Debug Logging**: MFCC/Chroma/Spectral breakdown
- ✅ **Similarity Matrix Stats**: Detailed threshold analysis
- ✅ **Clustering Diagnostics**: Show why videos are/aren't clustered
- ✅ **Test Scripts**: Standalone audio/video testing
- ✅ **Troubleshooting Guides**: TROUBLESHOOTING_AUDIO.md, TROUBLESHOOTING_NO_DETECTION.md

### 📝 Documentation
- ✅ **DOWNLOAD_SPEED_IMPROVEMENTS.md**: Complete guide to new download features
- ✅ **VIDEO_COMPARISON_ENHANCED.md**: Enhanced video comparison details
- ✅ **TROUBLESHOOTING_AUDIO.md**: Audio detection troubleshooting
- ✅ **Updated README.md**: New features highlighted

### 🐛 Bug Fixes
- ✅ Fixed audio tempo logging error (numpy array formatting)
- ✅ Fixed similarity matrix shape mismatch when audio fails
- ✅ Fixed "Is Reupload" column not being updated in Excel export
- ✅ Fixed video type detection (now uses user-provided Type column)
- ✅ Fixed segment processing (properly parse time ranges)

### ⚙️ Configuration Updates
- ✅ Lowered default `combined_similarity` threshold: 0.80 → 0.70
- ✅ Added `concurrent_fragments`: 8
- ✅ Added `retries`: 10
- ✅ Added `fragment_retries`: 10
- ✅ Increased `max_parallel`: 6 → 8

---

## [1.0.0] - 2024-10-30

### Added
- 🎉 Initial release
- ✅ YouTube video download with yt-dlp
- ✅ Audio analysis using MFCC, Chroma, Spectral features
- ✅ Video analysis using CLIP deep learning model
- ✅ Optical flow analysis for motion detection
- ✅ OCR-based karaoke detection (EasyOCR/PaddleOCR)
- ✅ Automatic video type classification (Audio/Video/Midi Karaoke/MV Karaoke)
- ✅ Graph-based clustering for reupload detection
- ✅ PyQt6 GUI with modern interface
- ✅ GPU acceleration (NVIDIA CUDA, AMD ROCm)
- ✅ Parallel download support
- ✅ Batch processing
- ✅ Excel import/export
- ✅ Comprehensive logging
- ✅ Configuration management via YAML
- ✅ Dark theme UI
- ✅ Progress tracking
- ✅ Detailed statistics

### Features
- Multi-modal analysis (audio + video + motion)
- Smart clustering algorithm
- Configurable thresholds and weights
- FP16 inference for faster GPU processing
- Automatic temporary file cleanup
- Thread-safe processing
- Error handling and recovery
- Detailed results export

### Documentation
- Complete README with installation guide
- Quick start guide (QUICKSTART.md)
- Sample input file
- GPU test script
- Batch installation scripts for Windows

### Known Issues
- OCR may require large model downloads on first run
- GPU memory usage can be high with 720p+ videos
- Some geo-restricted videos may fail to download

### Future Plans
- [ ] Support for more video platforms (TikTok, Instagram, etc.)
- [ ] Web interface option
- [ ] Real-time monitoring mode
- [ ] Database backend for large-scale processing
- [ ] API endpoint for integration
- [ ] Advanced scene detection
- [ ] Audio fingerprint database matching
- [ ] Distributed processing across multiple machines
- [ ] ML model fine-tuning for specific content types
- [ ] Automatic threshold optimization

