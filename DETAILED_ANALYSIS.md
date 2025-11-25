# 🔍 Phân tích chi tiết kết quả hiện tại

## 📊 Kết quả hiện tại

### ✅ ĐÚNG (6 videos)
1. **STT 1 (boJD0v58LQ4)**: `No - Video gốc` ✅
2. **STT 2 (XziiBwlLsrc)**: `No - Video gốc` ✅
3. **STT 3 (nl7tTmVWHgY)**: `Yes - Reupload của boJD0v58LQ4 (79.9%)` ✅
4. **STT 4 (W0R5hbEaYx4)**: `Yes - Reupload của boJD0v58LQ4 (79.9%)` ✅
5. **STT 5 (W0R5hbEaYx4)**: `Yes - Reupload của XziiBwlLsrc (79.3%)` ✅
6. **STT 6 (q-n97G2NYSY)**: `Yes - Reupload của boJD0v58LQ4 (79.5%)` ✅

### ❌ SAI - False Negatives (7 videos)

#### 1. STT 7 và 8: Không được nhóm lại
- **STT 7 (jHHx4lEgHhg)**: `No - Video độc nhất` ❌
- **STT 8 (e1uYu4fTM24)**: `No - Video độc nhất` ❌
- **Yêu cầu**: "link 7 và 8 là giống nhau, cùng âm thành cùng hình ảnh" → Nên được nhóm lại
- **Phân tích**:
  - Type: Video
  - Có thể là static images (hình tĩnh)
  - Logic static images đã được implement nhưng có thể:
    - Audio similarity < 0.75
    - Hoặc optical flow không được detect đúng
    - Hoặc video_paths không match với matrix indices

#### 2. STT 9, 12, 13: Audio không được nhóm
- **STT 9 (N1BJkNjek78)**: `No - Video độc nhất` (Audio) ❌
- **STT 12 (0NNAOMExL0w)**: `No - Video độc nhất` (Audio) ❌
- **STT 13 (Xn3smBfcILM)**: `No - Video độc nhất` (Audio) ❌
- **Yêu cầu**: "link 12 và 13 là audio nhạc remix khác audio link 9"
  - Link 12 và 13 nên được nhóm với nhau (remix của nhau)
  - Link 9 nên là audio khác (không nhóm với 12-13)
- **Phân tích**:
  - Type: Audio → Dùng `audio_threshold` (0.75)
  - Remix penalty có thể đã được cải thiện nhưng vẫn chưa đủ
  - Base similarity có thể < 0.85 → penalty vẫn quá mạnh
  - Hoặc similarity sau penalty < 0.75

#### 3. STT 10, 11: Có thể đúng hoặc sai
- **STT 10 (9a7HY9etnd4)**: `No - Video độc nhất` ✅ (Cùng âm thanh khác hình ảnh)
- **STT 11 (tr-JsmpjoRI)**: `No - Video độc nhất` ✅ (Cùng âm thanh khác hình ảnh)

---

## 🔍 Vấn đề chính

### 1. Link 7-8 không được nhóm
**Nguyên nhân có thể:**
- Audio similarity < 0.75 (dù đã dùng audio-only cho static images)
- Optical flow không được detect (< 5.0)
- Video_paths không match với matrix indices trong `create_combined_similarity_matrix`

**Giải pháp:**
- Kiểm tra xem optical flow có được extract và pass đúng không
- Có thể cần giảm threshold xuống 0.70 cho static image pairs
- Hoặc cần đảm bảo video_paths order match với matrix order

### 2. Link 12-13 không được nhóm
**Nguyên nhân có thể:**
- Base similarity < 0.85 → penalty vẫn quá mạnh
- Ví dụ: base_similarity = 0.82, remix_features_sim = 0.35
  - Penalty = 0.6 (vì base_sim > 0.80 nhưng < 0.85)
  - Final = 0.82 * 0.6 = 0.492 < 0.75 ❌
- Hoặc base_similarity < 0.80 → penalty còn mạnh hơn

**Giải pháp:**
- Cần kiểm tra similarity thực tế trong logs
- Có thể cần điều chỉnh threshold xuống 0.70 cho Audio type
- Hoặc cải thiện remix penalty logic thêm

---

## 💡 Đề xuất sửa

### 1. Điều chỉnh threshold cho Audio type xuống 0.70
- Audio type videos có thể cần threshold thấp hơn
- Đặc biệt cho remixes

### 2. Đảm bảo static image logic hoạt động đúng
- Kiểm tra video_paths order
- Thêm logging để debug

### 3. Cải thiện remix penalty thêm
- Nếu base_similarity > 0.80 (không cần > 0.85), giảm penalty mạnh hơn

### 4. Thêm logging chi tiết
- Log similarity scores cho từng pair
- Log optical flow values
- Log remix penalty calculations


