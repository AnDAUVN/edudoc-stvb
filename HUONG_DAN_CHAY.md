# Chạy bản EDUDOC đã sửa

## 1. Môi trường

Đã chạy kiểm tra trên Windows, Python 3.15.0, Flask 3.1.3 và python-docx 1.2.0. Dự án gốc khai báo Python 3.11.9 cho Render; phiên bản đó và Linux/macOS chưa được chạy kiểm chứng trong đợt này.

Giải nén `edudoc-stvb-fixed.zip` vào một thư mục mới. Không ghi đè lên thư mục đang phục vụ lớp học. Gói có dữ liệu SQLite, JSON và tệp Word từ RAR gốc; không có dữ liệu sinh viên giả tạo trong đợt kiểm thử.

## 2. Cài và chạy bằng PowerShell

Mở PowerShell tại thư mục `edudoc-stvb-fixed`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Mở `http://127.0.0.1:5000/` cho sinh viên, `http://127.0.0.1:5000/gv` cho giảng viên. `app.py` lắng nghe cả mạng LAN theo cấu hình gốc. Có thể chạy chỉ trên máy này bằng:

```powershell
.\.venv\Scripts\python.exe -c "from app import app; app.run(host='127.0.0.1', port=5000, debug=False)"
```

Không dùng `EDUDOC_TESTING=1` trên máy chủ thật: biến này cố ý bỏ qua một số kiểm soát khi chạy bộ thử.

## 3. PIN và khóa phiên

Nếu chưa đặt biến `TEACHER_PIN`, ứng dụng tạo PIN ngẫu nhiên trong `data/.teacher-pin`. Sau lần khởi chạy đầu, mở PowerShell thứ hai tại cùng thư mục để xem PIN:

```powershell
Get-Content .\data\.teacher-pin
```

Đăng nhập trang giảng viên bằng PIN đó. PIN mặc định cũ không còn được chấp nhận khi chưa có cấu hình riêng. Có thể tự đặt `TEACHER_PIN` trong môi trường trước khi chạy; không ghi PIN thật vào mã nguồn hoặc lịch sử Git.

`SECRET_KEY` cũng được đọc từ môi trường; nếu không có, khóa riêng được lưu trong `data/.session-key`. Giữ tệp này giữa các lần khởi động. Các phiên đăng nhập dùng khóa mặc định cũ sẽ hết hiệu lực và cần đăng nhập lại. Gói bàn giao không chứa PIN/khóa phiên đã tạo ở môi trường thử nghiệm.

Khóa HMAC `EDUDOC_SECRET_KEY` vẫn giữ tương thích với các phôi cũ. Mã gốc có giá trị dự phòng công khai; trước kỳ thi mới cần cấu hình khóa riêng. Việc đổi khóa sẽ làm các phôi đã ký bằng khóa cũ không hợp lệ; cần kết thúc ca thi cũ và cấp lại phôi theo kế hoạch, không đổi giữa ca.

## 4. Dữ liệu và khôi phục

Giữ nguyên cả `data/` và `storage/` khi sao lưu/di chuyển. Sao lưu qua giao diện hiện chỉ sao lưu SQLite, không bao gồm JSON quản lý lớp/câu hỏi/đề và các bài Word.

Bản sửa không thay cấu trúc bảng lưu dữ liệu. JSON cũ chỉ được nhập tự động khi tạo DB mới; không còn dùng để nạp lại bảng đã xóa sạch trong DB hiện có.

Khôi phục SQLite sẽ tạo thêm bản sao DB hiện tại trong `data/backups/` trước khi thay dữ liệu, và kiểm tra nguồn có các bảng cốt lõi. Chỉ khôi phục trong thời gian bảo trì khi đã dừng ghi dữ liệu của sinh viên. Để hoàn tác, chọn bản sao vừa được tạo. Khôi phục SQLite không khôi phục các tệp Word/JSON tương ứng.

Nếu muốn quay lại mã cũ, dừng ứng dụng rồi dùng RAR gốc; giữ bản sao toàn bộ dữ liệu hiện tại trước khi chuyển. Không ghép dữ liệu thử nghiệm vào dữ liệu thật.

## 5. Chạy kiểm thử

```powershell
.\.venv\Scripts\python.exe tests\run_all_tests.py
```

Trình chạy tạo bản sao tạm của dự án và chỉ sửa dữ liệu ở bản sao đó. Cổng 5000 cần trống; trình chạy sẽ dừng nếu có máy chủ khác sử dụng cổng. Không chạy riêng các script kiểm thử cũ trên dữ liệu thật: nhiều script thêm, xóa hoặc xóa sạch bảng.

Nếu có Node.js, chạy thêm kiểm thử JavaScript thuần:

```powershell
node tests\test_ui_rendering.cjs
```

Bài kiểm tra JavaScript dùng DOM giả tối thiểu, không thay thế kiểm thử bố cục, thao tác và khả năng truy cập trong trình duyệt thật.

## 6. Khởi chạy một chạm và triển khai

`run.bat` gọi `run_app.py`. Bản sửa không tự tắt tiến trình khác chiếm cổng. Trình khởi chạy gốc có cơ chế mở Cloudflare Tunnel nếu tìm được chương trình `cloudflared`; đợt kiểm tra không chạy hoặc công bố tunnel. Dùng `app.py` như hướng dẫn trên để kiểm tra trước.

Chưa xác minh triển khai Render, lưu dữ liệu qua redeploy, TLS, nhiều worker hay tải lớp học thực tế. Đặt các khóa riêng, chuẩn bị lưu trữ bền vững, sao lưu toàn bộ dữ liệu và rà soát các giới hạn còn lại trong báo cáo trước khi dùng cho kỳ thi quan trọng.
