# -*- coding: utf-8 -*-
import json
import os

path = os.path.join(os.path.dirname(__file__), "..", "data", "questions.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

data["bai_thu_hoach"] = [
    {
        "id": 1,
        "question": "Trong văn bản 'Bài thu hoạch', phần Tên loại văn bản (Ô 5a) được trình bày như thế nào theo Nghị định 30/2020/NĐ-CP?",
        "options": [
            "In hoa, in đậm, cỡ chữ 13 đến 14, đặt canh giữa trang",
            "In thường, in nghiêng, cỡ chữ 12, đặt canh trái",
            "In hoa, in nghiêng, cỡ chữ 11, đặt trong bảng 2x2",
            "In thường, in đậm, gạch chân dưới toàn bộ từ"
        ],
        "correct": 0,
        "explanation": "Theo Nghị định 30/2020/NĐ-CP, Tên loại văn bản (Ô 5a) được trình bày bằng chữ in hoa, cỡ chữ từ 13 đến 14, kiểu chữ đứng, đậm, đặt canh giữa trang."
    },
    {
        "id": 2,
        "question": "Tại phần Trích yếu nội dung của Bài thu hoạch (đặt ngay dưới Tên loại văn bản), quy cách trình bày chuẩn là gì?",
        "options": [
            "In hoa toàn bộ, cỡ chữ 14, in nghiêng",
            "In thường, kiểu chữ đứng, đậm, cỡ chữ 13 đến 14, đặt canh giữa",
            "In nghiêng, cỡ chữ 10, đặt trong ngoặc đơn",
            "Bắt đầu bằng chữ 'V/v', in nghiêng, đặt canh phải"
        ],
        "correct": 1,
        "explanation": "Trích yếu nội dung văn bản có tên loại (Ô 5a) được đặt ngay dưới tên loại văn bản, canh giữa, bằng chữ in thường, cỡ chữ từ 13 đến 14, kiểu chữ đứng, đậm."
    },
    {
        "id": 3,
        "question": "Đối với Bài thu hoạch của cá nhân học viên/sinh viên, phần ký tên xác nhận ở cuối văn bản (Ô 7b) thường ghi chức danh nào?",
        "options": [
            "HIỆU TRƯỞNG",
            "TRƯỞNG PHÒNG",
            "NGƯỜI THU HOẠCH (hoặc NGƯỜI VIẾT BÁO CÁO)",
            "TM. HỘI ĐỒNG"
        ],
        "correct": 2,
        "explanation": "Bài thu hoạch cá nhân do chính học viên/sinh viên hoàn thành và chịu trách nhiệm, chức danh ký là 'NGƯỜI THU HOẠCH' bằng chữ in hoa, đậm, cỡ 13-14."
    },
    {
        "id": 4,
        "question": "Số và ký hiệu của Bài thu hoạch (Ví dụ: Số: 01/BTH-ĐT) tại Ô 3 được định dạng theo quy tắc nào?",
        "options": [
            "Từ 'Số' in hoa toàn bộ 'SỐ:', cỡ chữ 14",
            "Từ 'Số' in thường, đứng, cỡ chữ 12-13, sau có dấu ':', giữa số và ký hiệu có dấu '/', nối các từ viết tắt bằng dấu '-' không cách",
            "Dùng dấu gạch dưới '_' để ngăn cách giữa số và tên viết tắt",
            "Đặt tại góc dưới cùng bên phải của trang giấy"
        ],
        "correct": 1,
        "explanation": "Theo Nghị định 30, từ 'Số' in thường, cỡ chữ 12-13, đứng, sau có dấu hai chấm (:). Giữa số và ký hiệu có gạch chéo (/), giữa các chữ viết tắt có dấu gạch nối (-) không có khoảng trắng."
    },
    {
        "id": 5,
        "question": "Mục 'Nơi nhận:' (Ô 9b) ở góc dưới bên trái của Bài thu hoạch được trình bày như thế nào?",
        "options": [
            "Từ 'Nơi nhận:' in nghiêng đậm size 12; các nơi nhận con in thường đứng size 11",
            "Từ 'Nơi nhận:' in đứng size 14; các nơi nhận con in hoa size 13",
            "Tất cả đều in nghiêng, cỡ chữ 13",
            "Không cần trình bày Nơi nhận đối với bài thu hoạch"
        ],
        "correct": 0,
        "explanation": "Dòng 'Nơi nhận:' kiểu chữ in thường, nghiêng, đậm, cỡ chữ 12, sau có dấu (:). Danh sách các nơi nhận cụ thể (ví dụ: - Ban Giảng huấn; - Lưu: Hồ sơ) in thường, đứng, cỡ chữ 11."
    }
]

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Updated questions.json successfully!")
