# Database & History Guide

## Overview

YouTube Content Detector giờ đây có hệ thống database local (SQLite) để lưu trữ lịch sử phân tích và thống kê.

## Features

### 1. 🕐 Lịch sử (History)

**Chức năng:**
- Tự động lưu mọi lần phân tích vào database
- Xem lại các phân tích trước đó
- Tìm kiếm theo tên file
- Xóa các phân tích không cần thiết
- Xem chi tiết từng phân tích

**Cách sử dụng:**
1. Click nút "Lịch sử" ở góc trên bên phải
2. Xem danh sách các lần phân tích
3. Tìm kiếm bằng cách gõ tên file vào ô search
4. Click "Xem chi tiết" để xem thông tin đầy đủ
5. Click "Xóa" để xóa phân tích không cần

### 2. 📈 Thống kê (Statistics)

**Chức năng:**
- Tổng quan về tất cả các lần phân tích
- Số liệu tổng hợp:
  - Tổng số lần phân tích
  - Tổng số videos đã phân tích
  - Tổng số reuploads tìm thấy
  - Tỷ lệ reupload trung bình
- Biểu đồ xu hướng 30 ngày gần đây
- Top 10 kênh reupload nhiều nhất

**Cách sử dụng:**
1. Click nút "Thống kê" ở góc trên bên phải
2. Xem các số liệu tổng quan
3. Phân tích xu hướng qua biểu đồ
4. Xem danh sách top channels

## Database Schema

### Table: `analysis_runs`
Lưu thông tin tổng quan của mỗi lần phân tích

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| created_at | TIMESTAMP | Thời gian phân tích |
| file_name | TEXT | Tên file Excel/CSV |
| total_videos | INTEGER | Tổng số videos |
| reupload_count | INTEGER | Số video reupload |
| reupload_percent | REAL | Tỷ lệ % reupload |
| cluster_count | INTEGER | Số cụm phát hiện |
| audio_threshold | REAL | Ngưỡng audio |
| video_threshold | REAL | Ngưỡng video |
| combined_threshold | REAL | Ngưỡng kết hợp |
| gpu_enabled | BOOLEAN | GPU có được dùng |
| processing_time_seconds | REAL | Thời gian xử lý |

### Table: `video_results`
Lưu chi tiết từng video trong phân tích

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| run_id | INTEGER | Foreign key to analysis_runs |
| video_id | TEXT | YouTube video ID |
| channel_name | TEXT | Tên kênh |
| title | TEXT | Tiêu đề video |
| is_reupload | BOOLEAN | Có phải reupload |
| cluster_id | INTEGER | ID cụm |
| similarity_score | REAL | Điểm tương đồng |

## File Storage

Database được lưu tại: `web/data/analysis_history.db`

- File SQLite đơn giản, portable
- Tự động tạo khi chạy lần đầu
- Có thể backup bằng cách copy file

## API Endpoints

### GET `/api/history`
Lấy danh sách lịch sử phân tích

**Parameters:**
- `limit` (optional): Số lượng kết quả (default: 50)
- `offset` (optional): Vị trí bắt đầu (default: 0)

**Response:**
```json
{
  "success": true,
  "history": [...],
  "count": 10
}
```

### GET `/api/history/<run_id>`
Lấy chi tiết phân tích cụ thể

**Response:**
```json
{
  "success": true,
  "analysis": {
    "id": 1,
    "file_name": "videos.xlsx",
    "total_videos": 100,
    "reupload_count": 25,
    "videos": [...]
  }
}
```

### DELETE `/api/history/<run_id>`
Xóa phân tích

**Response:**
```json
{
  "success": true,
  "message": "Analysis deleted successfully"
}
```

### GET `/api/statistics`
Lấy thống kê tổng quan

**Response:**
```json
{
  "success": true,
  "statistics": {
    "overall": {
      "total_runs": 10,
      "total_videos_analyzed": 1000,
      "total_reuploads_found": 250,
      "avg_reupload_rate": 25.0
    },
    "trend": [...],
    "top_channels": [...]
  }
}
```

### GET `/api/history/search?q=<query>`
Tìm kiếm lịch sử theo tên file

**Response:**
```json
{
  "success": true,
  "results": [...],
  "count": 5
}
```

## Technical Details

### Database Connection
- SQLite3 (built-in Python)
- Connection pooling được quản lý tự động
- Thread-safe operations

### Performance
- Indexed queries cho tốc độ nhanh
- Efficient pagination
- Optimized for typical usage patterns

### Data Retention
- Không có auto-cleanup
- User tự quản lý xóa data cũ
- Có thể implement retention policy sau

## Troubleshooting

### Database không tạo được
```bash
# Kiểm tra quyền write
ls -la web/data/

# Tạo folder manually nếu cần
mkdir -p web/data/
```

### Lỗi khi query
```python
# Check database integrity
sqlite3 web/data/analysis_history.db "PRAGMA integrity_check;"
```

### Reset database
```bash
# Backup trước
cp web/data/analysis_history.db web/data/analysis_history.backup.db

# Xóa database (sẽ tự tạo lại)
rm web/data/analysis_history.db
```

## Future Enhancements

Planned features:
- [ ] Export history to CSV/Excel
- [ ] Compare two analyses side-by-side
- [ ] Advanced filtering and sorting
- [ ] Data retention policies
- [ ] Backup/restore functionality
- [ ] More detailed charts and visualizations
