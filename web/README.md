# Web Interface - YouTube Reupload Detector

## 📖 Giới thiệu

Giao diện web hiện đại cho hệ thống phát hiện video YouTube reupload, được thiết kế tương thích hoàn toàn với backend Python hiện có.

## ✨ Tính năng

### 🎨 Giao diện
- **Dark Theme**: Thiết kế tối hiện đại, dễ nhìn
- **Responsive**: Tự động điều chỉnh theo màn hình
- **Drag & Drop**: Kéo thả file Excel trực tiếp
- **Real-time Progress**: Theo dõi tiến trình xử lý
- **Terminal Logs**: Hiển thị logs theo thời gian thực

### 🔧 Chức năng
- Upload file Excel (.xlsx, .xls)
- Xem trước dữ liệu (số video, số Code)
- Cấu hình threshold (audio, video, combined)
- Bật/tắt GPU
- Theo dõi tiến trình qua 6 bước
- Xem kết quả chi tiết
- Xuất báo cáo Excel

### 📊 Hiển thị kết quả
- Tổng số video
- Số video reupload
- Tỷ lệ reupload (%)
- Số cụm reupload
- Terminal logs chi tiết

## 🚀 Cài đặt

### 1. Cài đặt dependencies

```bash
pip install flask flask-cors openpyxl pandas
```

### 2. Cấu trúc thư mục

```
project/
├── web/
│   ├── index.html       # Giao diện chính
│   ├── styles.css       # CSS styling
│   ├── script.js        # Frontend logic
│   ├── api_server.py    # Flask API server
│   └── README.md        # Tài liệu này
├── src/                 # Backend code
├── config.yaml          # Cấu hình
└── main.py             # Entry point cũ
```

## 💻 Chạy ứng dụng

### Khởi động server

```bash
cd web
python api_server.py
```

Server sẽ chạy tại: **http://localhost:5000**

### Mở trình duyệt

Truy cập: **http://localhost:5000**

## 📝 Hướng dẫn sử dụng

### Bước 1: Upload file Excel

1. Kéo thả file Excel vào vùng upload
2. Hoặc click để chọn file
3. Xem preview: số video, số Code

### Bước 2: Cấu hình

Điều chỉnh các ngưỡng:
- **Audio Similarity**: 50-100% (mặc định: 65%)
- **Video Similarity**: 50-100% (mặc định: 75%)
- **Combined Similarity**: 50-100% (mặc định: 70%)
- **GPU**: Bật/tắt (tăng tốc xử lý)

### Bước 3: Bắt đầu phân tích

1. Click **"Bắt đầu phân tích"**
2. Theo dõi tiến trình qua 6 bước:
   - Tải video từ YouTube
   - Trích xuất đặc trưng âm thanh
   - Trích xuất đặc trưng hình ảnh
   - Tính toán ma trận tương đồng
   - Phát hiện cụm reupload
   - Tạo báo cáo

### Bước 4: Xem kết quả

Kết quả hiển thị:
- 📊 Tổng video
- 🔄 Video reupload
- 📈 Tỷ lệ reupload
- 🔍 Số cụm

### Bước 5: Xuất kết quả

Click **"Xuất kết quả Excel"** để tải file báo cáo

## 🔌 API Endpoints

### GET /
Trả về giao diện web chính

### POST /api/upload
Upload file Excel

**Request:**
```
Content-Type: multipart/form-data
file: Excel file
```

**Response:**
```json
{
  "totalVideos": 50,
  "totalCodes": 10,
  "filePath": "/tmp/...",
  "columns": ["Link YouTube", "Code", ...]
}
```

### POST /api/process
Xử lý phát hiện reupload

**Request:**
```json
{
  "filePath": "/tmp/...",
  "config": {
    "audioThreshold": 0.65,
    "videoThreshold": 0.75,
    "combinedThreshold": 0.70,
    "gpuEnabled": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "statistics": {
    "totalVideos": 50,
    "reuploads": 12,
    "percentage": 24.0,
    "clusters": 5,
    "averageSimilarity": 85.5
  }
}
```

### GET /api/export
Xuất kết quả ra file Excel

**Response:**
- File Excel download

### GET /api/status
Kiểm tra trạng thái server

**Response:**
```json
{
  "status": "ready",
  "version": "1.3.0",
  "gpuAvailable": true
}
```

### GET /api/config
Lấy cấu hình hiện tại

**Response:**
```json
{
  "audioThreshold": 0.65,
  "videoThreshold": 0.75,
  "combinedThreshold": 0.70,
  "gpuEnabled": true
}
```

## 🎨 Thiết kế

### Color Scheme
- **Primary**: `#2563eb` (Blue)
- **Success**: `#10b981` (Green)
- **Warning**: `#f59e0b` (Orange)
- **Danger**: `#ef4444` (Red)
- **Background**: `#0f172a` (Dark Navy)
- **Secondary**: `#1e293b` (Lighter Navy)

### Components

#### Upload Zone
- Drag & drop support
- Hover effects
- File preview
- Remove button

#### Configuration Panel
- Range sliders với giá trị động
- Checkbox GPU
- Tooltips giải thích

#### Progress Section
- Progress bar animation
- Step counter (1/6, 2/6, ...)
- Timer đếm giờ
- Cancel button

#### Results Section
- 4 result cards với icons
- Gradient backgrounds
- Hover animations
- Export button

#### Terminal
- Monospace font
- Auto-scroll
- Color-coded messages (success, error, warning)
- Copy & Clear buttons

## 🔧 Tùy chỉnh

### Thay đổi cổng

Sửa trong `api_server.py`:
```python
app.run(host='0.0.0.0', port=5000)
```

### Thay đổi theme

Sửa trong `styles.css`:
```css
:root {
    --primary: #2563eb;  /* Đổi màu chính */
    --bg: #0f172a;       /* Đổi màu nền */
}
```

### Thêm logging

Trong `script.js`:
```javascript
this.addLog('Your message', 'info');  // info, success, warning, error
```

## 🐛 Debug

### Bật debug mode

```python
app.run(debug=True)
```

### Xem logs

- Backend logs: Terminal chạy `api_server.py`
- Frontend logs: Browser Console (F12)
- Processing logs: Web terminal section

### Common Issues

**Issue 1: Cannot connect to API**
- Kiểm tra server đang chạy
- Kiểm tra port 5000 chưa bị chiếm

**Issue 2: CORS error**
- Đã cài `flask-cors`
- CORS đã được enable trong code

**Issue 3: File upload fails**
- Kiểm tra định dạng file (.xlsx, .xls)
- Kiểm tra file có columns đúng

## 🔐 Security Notes

**⚠️ Chú ý:** Đây là phiên bản development

Cho production:
1. Thêm authentication
2. Validate input nghiêm ngặt
3. Rate limiting
4. HTTPS
5. File size limits
6. Secure file storage

## 📦 Dependencies

### Backend
```
flask>=2.0.0
flask-cors>=3.0.0
pandas>=1.3.0
openpyxl>=3.0.0
```

### Frontend
- Vanilla JavaScript (no frameworks)
- CSS3 với animations
- HTML5 với drag & drop API

### Tích hợp với backend hiện có
- `src/pipeline/processing_pipeline.py`
- `src/detection/reupload_detector.py`
- `src/analysis/audio_analyzer.py`
- `src/analysis/video_analyzer.py`
- `src/downloader/youtube_downloader.py`

## 🚀 Production Deployment

### Sử dụng Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

### Sử dụng Nginx

Cấu hình reverse proxy:
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

### Docker

Tạo `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

EXPOSE 5000
CMD ["python", "web/api_server.py"]
```

## 📊 Performance

### Tối ưu hóa

1. **Caching**: Cache pipeline instance
2. **Async**: Xử lý async cho upload lớn
3. **Compression**: Gzip response
4. **CDN**: Host static files trên CDN

### Benchmarks

- Upload file 1MB: ~500ms
- Process 50 videos: ~5-10 phút (GPU)
- Export Excel: ~2-3 giây

## 🤝 Contributing

Đóng góp ý tưởng:
1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push và tạo Pull Request

## 📄 License

Same license as main project

## 📞 Support

- GitHub Issues
- Email: support@example.com
- Documentation: [Link to docs]

---

**Version**: 1.0.0
**Last Updated**: 2024-11-25
**Author**: AI Analysis Team
