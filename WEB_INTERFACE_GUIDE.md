# 🌐 Hướng dẫn sử dụng Web Interface

## 📖 Tổng quan

Giao diện web hiện đại cho YouTube Reupload Detector đã được thiết kế và tích hợp hoàn toàn với backend Python hiện có.

## 🎨 Tính năng giao diện

### 1. **Dark Theme hiện đại**
- Thiết kế tối dễ nhìn, chuyên nghiệp
- Màu sắc gradient bắt mắt
- Animation mượt mà

### 2. **Upload thông minh**
- **Drag & Drop**: Kéo thả file Excel trực tiếp
- **File preview**: Xem trước số video, số Code
- **Validation**: Kiểm tra định dạng file tự động

### 3. **Cấu hình linh hoạt**
- Slider điều chỉnh threshold (Audio, Video, Combined)
- Bật/tắt GPU processing
- Hiển thị giá trị real-time

### 4. **Tiến trình chi tiết**
- Progress bar với animation
- 6 bước xử lý rõ ràng:
  1. Downloading videos
  2. Audio feature extraction
  3. Video feature extraction
  4. Similarity calculation
  5. Cluster detection
  6. Report generation
- Timer đếm thời gian
- Nút Cancel bất kỳ lúc nào

### 5. **Kết quả trực quan**
- 4 card thống kê với icons đẹp:
  - 📊 Tổng video
  - 🔄 Video reupload
  - 📈 Tỷ lệ %
  - 🔍 Số cụm
- Export Excel một click

### 6. **Terminal logs**
- Hiển thị logs theo thời gian thực
- Color-coded (success, error, warning)
- Copy & Clear logs
- Auto-scroll

## 🚀 Cài đặt nhanh

### Bước 1: Cài đặt dependencies

```bash
cd web
pip install -r requirements.txt
```

### Bước 2: Khởi động server

**Windows:**
```bash
start_server.bat
```

**Linux/Mac:**
```bash
./start_server.sh
```

**Hoặc chạy trực tiếp:**
```bash
python api_server.py
```

### Bước 3: Mở trình duyệt

Truy cập: **http://localhost:5000**

## 📝 Cách sử dụng

### 1. Upload file Excel

```
Bước 1: Chuẩn bị file Excel
- Columns cần có: Link YouTube, Code, Type, Thời gian
- Format giống như file mẫu hiện tại

Bước 2: Upload
- Kéo thả vào vùng upload
- Hoặc click để chọn file
- Xem preview: 50 videos, 10 codes
```

### 2. Cấu hình xử lý

```
Audio Similarity: [=========>  ] 65%
- Độ tương đồng âm thanh để phát hiện reupload
- Giảm xuống nếu muốn phát hiện nhiều hơn
- Tăng lên nếu có quá nhiều false positive

Video Similarity: [============>] 75%
- Độ tương đồng hình ảnh
- Quan trọng cho Karaoke và Video

Combined Similarity: [==========>] 70%
- Kết hợp Audio + Video
- Threshold chính cho detection

☑️ Sử dụng GPU (nhanh hơn 5-10x)
```

### 3. Bắt đầu phân tích

```
Click: [▶ Bắt đầu phân tích]

Tiến trình hiển thị:
━━━━━━━━━━━━━━━━━━━━ 50%
Bước 3/6: Trích xuất đặc trưng hình ảnh...
Thời gian: 125s

Terminal logs:
$ ============================================================
$ Bắt đầu phân tích...
$ ============================================================
$ Cấu hình: Audio=65%, Video=75%, Combined=70%
$ GPU: Bật
$ Bước 1/6: Đang tải video từ YouTube...
$ ✓ Downloaded 45/50 videos successfully
$ Bước 2/6: Trích xuất đặc trưng âm thanh...
...
```

### 4. Xem kết quả

```
┌────────────────────┐ ┌────────────────────┐
│ 📊 Tổng video     │ │ 🔄 Video reupload │
│      50           │ │      12           │
└────────────────────┘ └────────────────────┘

┌────────────────────┐ ┌────────────────────┐
│ 📈 Tỷ lệ reupload │ │ 🔍 Số cụm        │
│    24.0%          │ │       5           │
└────────────────────┘ └────────────────────┘

[⬇ Xuất kết quả Excel]
```

### 5. Export kết quả

```
Click: [⬇ Xuất kết quả Excel]

File tải về:
📄 reupload_results_20241125_143022.xlsx

Chứa các sheets:
1. All Videos - Tất cả video đã xử lý
2. Reupload Clusters - Các cụm reupload
3. Summary - Tổng hợp
4. Similarity Matrix - Ma trận tương đồng
5. Detailed Comparisons - So sánh chi tiết
6. Statistics - Thống kê
```

## 🔧 Tích hợp với Backend

### API Endpoints được tích hợp

```python
# src/pipeline/processing_pipeline.py
ProcessingPipeline.process()
ProcessingPipeline.export_results()

# src/detection/reupload_detector.py
ReuploadDetector.detect_reuploads()
ReuploadDetector.get_statistics()

# src/analysis/audio_analyzer.py
AudioAnalyzer.batch_extract_features()
AudioAnalyzer.create_similarity_matrix()

# src/analysis/video_analyzer.py
VideoAnalyzer.batch_extract_features()
VideoAnalyzer.create_similarity_matrix()

# src/downloader/youtube_downloader.py
YouTubeDownloader.download_batch_with_segments()
```

### Config mapping

```yaml
# config.yaml → Web UI
thresholds:
  audio_similarity: 0.65    → audioThreshold slider
  video_similarity: 0.75    → videoThreshold slider
  combined_similarity: 0.70 → combinedThreshold slider

gpu:
  enabled: true              → gpuEnabled checkbox
```

## 🎯 Use Cases

### Case 1: Phát hiện reupload cơ bản
```
1. Upload file Excel với 50 videos
2. Giữ nguyên config mặc định
3. Click Bắt đầu phân tích
4. Xem kết quả: 12 reuploads (24%)
5. Export Excel
```

### Case 2: Điều chỉnh sensitivity
```
Nếu không phát hiện được reuploads:
→ Giảm các threshold xuống 60-65%

Nếu có quá nhiều false positive:
→ Tăng các threshold lên 75-80%
```

### Case 3: Xử lý file lớn
```
1. Upload file 1000+ videos
2. Bật GPU để tăng tốc
3. Theo dõi progress qua terminal
4. Chờ 30-60 phút (tùy hardware)
5. Export kết quả chi tiết
```

## 🎨 Tùy chỉnh giao diện

### Thay đổi theme

Sửa file `web/styles.css`:

```css
:root {
    /* Màu chính */
    --primary: #2563eb;      /* Blue - đổi thành màu khác */

    /* Màu nền */
    --bg: #0f172a;           /* Dark navy */
    --bg-secondary: #1e293b; /* Lighter navy */

    /* Màu text */
    --text: #f1f5f9;         /* Light gray */
    --text-secondary: #94a3b8; /* Medium gray */
}
```

### Thêm custom logging

Trong `web/script.js`:

```javascript
// Success log
this.addLog('✅ Thành công!', 'success');

// Error log
this.addLog('❌ Lỗi!', 'error');

// Warning log
this.addLog('⚠️ Cảnh báo!', 'warning');

// Info log
this.addLog('ℹ️ Thông tin', 'info');
```

## 🔧 Troubleshooting

### Lỗi: Cannot connect to server

```bash
# Kiểm tra server đang chạy
ps aux | grep api_server.py

# Khởi động lại server
cd web
python api_server.py
```

### Lỗi: CORS error

```python
# Đã được fix trong api_server.py
from flask_cors import CORS
CORS(app)
```

### Lỗi: Upload file fails

```
Kiểm tra:
1. File phải là .xlsx hoặc .xls
2. File phải có columns: Link YouTube, Code
3. File size < 50MB
```

### Lỗi: Processing timeout

```
Giải pháp:
1. Giảm số lượng video trong file
2. Tăng timeout trong config
3. Sử dụng GPU để tăng tốc
```

## 📊 Performance

### Benchmarks

```
Upload file 1MB:        ~500ms
Parse Excel 50 rows:    ~200ms
Process 50 videos:      ~5-10 minutes (GPU)
Export Excel:           ~2-3 seconds
```

### Tối ưu hóa

```python
# Sử dụng cache
pipeline = None  # Global cache

def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = ProcessingPipeline(config)
    return pipeline
```

## 🔐 Security Notes

**⚠️ Chú ý cho Production:**

1. **Authentication**: Thêm login/password
2. **Rate limiting**: Giới hạn requests
3. **File validation**: Kiểm tra file kỹ hơn
4. **HTTPS**: Sử dụng SSL
5. **Input sanitization**: Clean user input

## 📦 Deployment

### Production với Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 5000
CMD ["python", "web/api_server.py"]
```

```bash
docker build -t youtube-reupload-detector .
docker run -p 5000:5000 youtube-reupload-detector
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🤝 So sánh với PyQt6

| Feature | Web Interface | PyQt6 Desktop |
|---------|---------------|---------------|
| Platform | Cross-platform (browser) | Desktop only |
| Installation | pip install flask | pip install PyQt6 |
| Access | http://localhost:5000 | .exe file |
| UI Update | Edit HTML/CSS | Rebuild UI |
| Mobile | ✅ Responsive | ❌ Desktop only |
| Deployment | Server-based | Standalone |

## 📚 Tài liệu tham khảo

- Flask: https://flask.palletsprojects.com/
- Flask-CORS: https://flask-cors.readthedocs.io/
- CSS Grid: https://css-tricks.com/snippets/css/complete-guide-grid/
- Drag & Drop API: https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API

## 🎯 Roadmap

### Version 1.1 (Planned)
- [ ] WebSocket cho real-time progress
- [ ] Chart visualization (Chart.js)
- [ ] Dark/Light theme toggle
- [ ] Multi-language support
- [ ] Download sample Excel
- [ ] Video preview thumbnails

### Version 1.2 (Future)
- [ ] User authentication
- [ ] History of analyses
- [ ] Compare multiple analyses
- [ ] Advanced filtering
- [ ] Export to PDF/CSV
- [ ] Batch processing queue

## 💡 Tips & Tricks

### 1. Tăng tốc xử lý
```
- Bật GPU
- Giảm video_quality trong config.yaml
- Giảm keyframe_interval
- Tăng max_parallel downloads
```

### 2. Cải thiện accuracy
```
- Tăng num_segments trong audio config
- Tăng max_keyframes trong video config
- Điều chỉnh threshold phù hợp
```

### 3. Debug hiệu quả
```
- Xem terminal logs real-time
- Copy logs để phân tích
- Kiểm tra backend logs
- Dùng Browser Console (F12)
```

---

**Version**: 1.0.0
**Last Updated**: 2024-11-25
**Developed by**: AI Analysis Team
**License**: Same as main project
