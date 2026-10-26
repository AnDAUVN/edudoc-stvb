import json

with open('data/questions.json', encoding='utf-8') as f:
    qs = json.load(f)

qs['to_trinh_xin_kinh_phi'] = [
    {
        "id": 1,
        "question": "Ký hiệu văn bản Ô 3 của Tờ trình xin kinh phí do Đoàn Thanh niên trường ban hành được viết như thế nào là ĐÚNG?",
        "options": [
            "Số: 35/TTr-ĐTN",
            "Số: 35/TT-ĐTN",
            "Số: 35/ĐTN",
            "Số: 35/CV-ĐTN"
        ],
        "correct": 0,
        "explanation": "Ký hiệu của Tờ trình bắt buộc phải có tên loại viết tắt 'TTr-' đứng trước tên viết tắt cơ quan/đơn vị ban hành (Số: .../TTr-ĐTN)."
    },
    {
        "id": 2,
        "question": "Trong Tờ trình xin kinh phí, Tên loại văn bản ('TỜ TRÌNH') và Trích yếu nội dung (Ô 5a) được đặt ở vị trí nào?",
        "options": [
            "Đặt ở ngoài Bảng đầu trang, canh giữa trang giấy",
            "Đặt ở trong Bảng đầu trang (Dòng 2 Cột 1 dưới Số ký hiệu)",
            "Đặt ở cuối văn bản ngang hàng Nơi nhận",
            "Đặt sát lề trái của trang giấy"
        ],
        "correct": 0,
        "explanation": "Đối với văn bản có tên loại (như Tờ trình, Thông báo), Tên loại và Trích yếu nội dung (Ô 5a) được đặt ở ngoài Bảng đầu trang, canh giữa trang giấy."
    },
    {
        "id": 3,
        "question": "Mục nơi nhận trực tiếp Kính gửi (Ô 9a) trong Tờ trình xin cấp kinh phí được trình bày như thế nào?",
        "options": [
            "Kính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành. (cỡ 13-14, chữ đứng thường)",
            "KÍNH GỬI: BAN GIÁM HIỆU (in hoa, in đậm, gạch chân)",
            "Kính gửi Ban Giám hiệu (không có dấu hai chấm sau chữ Kính gửi)",
            "Kính gửi đặt ở chân trang ngang hàng chữ ký"
        ],
        "correct": 0,
        "explanation": "Ô 9a (Kính gửi) bắt đầu bằng 'Kính gửi:', sau đó là tên cơ quan nhận, kết thúc bằng dấu chấm (.), kiểu chữ in thường đứng, cỡ 13-14."
    },
    {
        "id": 4,
        "question": "Đối với Tờ trình do Đoàn trường lập trình Ban Giám hiệu, thẩm quyền ký (Ô 7a) là thể thức nào?",
        "options": [
            "Ký trực tiếp: 'BÍ THƯ ĐOÀN TRƯỜNG' (in hoa, in đậm, canh giữa)",
            "Ký thừa lệnh: 'TL. HIỆU TRƯỞNG'",
            "Ký thay: 'KT. HIỆU TRƯỞNG'",
            "Chữ in thường, in nghiêng: 'Bí thư đoàn'"
        ],
        "correct": 0,
        "explanation": "Tờ trình của Đoàn trường do người đứng đầu tổ chức ký trực tiếp: 'BÍ THƯ ĐOÀN TRƯỜNG' (in hoa, in đậm, canh giữa)."
    },
    {
        "id": 5,
        "question": "Đường kẻ phụ nằm dưới Trích yếu nội dung của Tờ trình xin kinh phí có đặc điểm gì theo Nghị định 30?",
        "options": [
            "Nét liền, có độ dài bằng 1/3 đến 1/2 độ dài dòng chữ trích yếu và đặt cân đối",
            "Nét liền có độ dài bằng toàn bộ dòng chữ trích yếu",
            "Dùng lệnh gạch chân Underline (Ctrl + U)",
            "Đường nét đứt dài hết chiều rộng trang giấy"
        ],
        "correct": 0,
        "explanation": "Đường kẻ phụ dưới trích yếu của văn bản có tên loại là nét liền, dài từ 1/3 đến 1/2 độ dài dòng chữ và đặt cân đối so với dòng chữ."
    }
]

with open('data/questions.json', 'w', encoding='utf-8') as f:
    json.dump(qs, f, ensure_ascii=False, indent=2)

print('Added questions for to_trinh_xin_kinh_phi successfully!')
