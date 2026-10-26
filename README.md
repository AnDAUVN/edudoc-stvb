# EDUDOC - HỆ THỐNG HUẤN LUYỆN & KHẢO THÍ SOẠN THẢO VĂN BẢN (NGHỊ ĐỊNH 30/2020/NĐ-CP)

Dự án phần mềm khảo thí và quản lý giáo dục chuyên ngành Soạn thảo văn bản hành chính theo Nghị định 30/2020/NĐ-CP của Chính phủ.

---

## 🌟 TÍNH NĂNG TOÀN DIỆN & NỔI BẬT

1. **Hỗ trợ đầy đủ 8 Loại văn bản hành chính theo Nghị định 30/2020/NĐ-CP:**
   - 1. Bài thu hoạch
   - 2. Công văn đề nghị
   - 3. Thông báo nhiệm vụ được giao
   - 4. Thông báo thông tin hoạt động
   - 5. Tờ trình xin kinh phí
   - 6. Tờ trình xin bổ sung nhân sự
   - 7. Tờ trình xin máy móc thiết bị
   - 8. Báo cáo

2. **Quản lý Mã lớp Kỹ năng (Mã lớp KN):**
   - Giảng viên tự tạo và quản lý các Mã lớp KN (VD: `HC01K157`, `22DTH01`, `KN01`...).
   - Sinh viên bắt buộc chọn đúng Mã lớp của mình khi đăng nhập làm bài.
   - Bảng Giảng viên có bộ lọc theo từng Mã lớp KN để chấm điểm và theo dõi tiến độ nộp bài.
   - Tên file sinh ra theo đúng chuẩn: `[SBD]_[MSSV]_[HOVATEN]_[LoaiVB].docx`.

3. **Quản lý Ngân hàng Câu hỏi Trắc nghiệm Thể thức:**
   - Giảng viên có thể xem, chỉnh sửa, xóa hoặc bổ sung thêm câu hỏi mới cho bất kỳ loại văn bản nào.
   - Đánh dấu đáp án đúng trực quan và giải thích chuẩn xác theo Nghị định 30.
   - Tiêu chuẩn vượt qua bài trắc nghiệm tự động tính theo tỷ lệ $\ge 80\%$ tổng số câu hỏi.

4. **Tùy biến Đề bài File mẫu & Chế độ Để trống Thân bài:**
   - Giảng viên có thể tự soạn thảo / dán nội dung bài tập thô vào file mẫu.
   - Hỗ trợ công tắc "Để trống phần thân bài" để sinh viên tự gõ theo bài giảng trực tiếp trên lớp.

5. **Cơ chế Chống gian lận 2 Lớp (Chỉ mặt đặt tên cả 2 sinh viên):**
   - **Lớp 1 (Nộp nguyên file của bạn):** Chữ ký số HMAC-SHA256 phát hiện sinh viên A lấy file gốc của sinh viên B ➔ Lập biên bản vi phạm đích danh cả 2 người.
   - **Lớp 2 (Copy - Paste nội dung):** Thủy ấn vô hình (Zero-Width Steganography) mã hóa MSSV ẩn trong từng ký tự ➔ Bắt quả tang chính xác nguồn gốc bài bị chép.

6. **Bộ máy Thẩm định Thể thức Tự động (Ô 1 ➔ Ô 9b):**
   - **Căn lề trang:** Trên: 20-25mm, Dưới: 20-25mm, Trái: 30-35mm, Phải: 15-20mm.
   - **Cấu trúc Bảng:** Bắt buộc Bảng đầu trang 2x2 (chứa Ô 1-5b đối với Công văn; Ô 1-4 đối với Thông báo, Tờ trình) và Bảng cuối trang 1x2 (chứa Ô 9b và Ô 7a, 7b).
   - **Quy ước Thống nhất Cỡ chữ "Số trước - Số sau":** Tự động nhận diện từ Ô 1 (Bộ nhỏ: 12-13pt hoặc Bộ lớn: 13-14pt) và yêu cầu tính đồng bộ toàn bài.
   - **Tách biệt rõ Ô 5a & Ô 5b:**
     + Công văn: Ô 5b trích yếu `V/v` nằm trong Bảng đầu trang dưới Ô 3, cỡ 12-13pt, cách dòng 6pt.
     + Thông báo, Tờ trình: Ô 5a Tên loại & Trích yếu nằm ngoài bảng, căn giữa trang.
   - **Quy tắc Thẩm định Viết hoa theo Phụ lục II Nghị định 30:**
     + *Mục I (Phép đặt câu):* Viết hoa chữ cái đầu câu khi xuống dòng, đầu đoạn, đầu gạch đầu dòng `-`, đầu số thứ tự `1.`, `2.` và sau dấu chấm câu `.`.
     + *Mục IV (Tên cơ quan, tổ chức):* Kiểm tra nghiêm ngặt tại Ô 9a (`Kính gửi: ...`) và Ô 6 (thân bài), viết hoa đúng loại hình và chức năng/lĩnh vực (ví dụ: `Bộ Khoa học và Công nghệ` - từ nối `và` viết thường; `Ban Giám hiệu`; `Công an Phường...`; `Ủy ban nhân dân Phường...`).
     + *Mục III (Địa danh):* Viết hoa `Thành phố Hồ Chí Minh` / `Tp. Hồ Chí Minh`, không viết tắt `HCM`.
   - **Ô 7 & 8:** Chức vụ (in hoa đậm), thể thức đề ký `KT.` (2 dòng kèm chức vụ cấp phó), `TL.` (2 dòng kèm chức vụ trưởng phòng), khoảng trống ký tên 2-2.5cm, Họ tên (in đậm, viết hoa chữ cái đầu).
   - **Ô 9b:** `Nơi nhận:` in nghiêng đậm 12pt; danh sách con in thường đứng 11pt (xử lý OpenXML docDefaults hoàn hảo); dòng cuối `Lưu: VT.`.

7. **Bàn làm việc Giảng viên (Teacher Dashboard):**
   - Thống kê tổng số bài nộp, số trường hợp gian lận sao chép bài.
   - Quản lý mã lớp KN, quản lý câu hỏi trắc nghiệm, quản lý đề bài mẫu.
   - Bảng **Nhật ký vi phạm gian lận (Red Alerts)** kèm bằng chứng kỹ thuật số.
   - Bảng **Danh sách bài tập hoàn thành 100% NĐ 30** có bộ lọc mã lớp và nút tải file nộp.

---

## 📁 CẤU TRÚC THƯ MỤC DỰ ÁN

```text
edudoc-stvb/
├── data/                       # Dữ liệu JSON (đề bài, câu hỏi trắc nghiệm, mã lớp, bài nộp)
├── engine/                     # Bộ máy xử lý lõi (thẩm định thể thức NĐ 30 & bảo mật chống gian lận)
├── static/                     # Tài nguyên tĩnh giao diện (CSS, JS)
├── storage/                    # Kho lưu trữ file mẫu và bài nộp sinh viên
├── templates/                  # Giao diện HTML người dùng (index.html)
├── tests/                      # Toàn bộ bộ kiểm thử tự động (Unit / Regression tests)
│   └── run_all_tests.py        # Trình chạy tự động toàn bộ 10 test suites
├── tools/                      # Các công cụ tiện ích & bảo trì cơ sở dữ liệu
├── app.py                      # Flask Application Server (Backend API)
├── run_app.py                  # Script khởi động server & tự động mở trình duyệt
├── run.bat                     # File chạy 1-click cho người dùng Windows
├── requirements.txt            # Danh sách thư viện Python phụ thuộc
└── README.md                   # Tài liệu hướng dẫn sử dụng
```

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY NHANH

### Cách 1: Chạy bằng file Batch
Nhấp đúp chuột vào file `run.bat` trong thư mục:
`C:\Users\maith\.gemini\antigravity\scratch\edudoc-stvb\run.bat`

### Cách 2: Chạy bằng dòng lệnh PowerShell
```powershell
cd C:\Users\maith\.gemini\antigravity\scratch\edudoc-stvb
python run_app.py
```
Hệ thống sẽ tự động khởi động máy chủ và mở trình duyệt tại địa chỉ: `http://127.0.0.1:5000`.
