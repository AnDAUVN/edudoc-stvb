import os
import sys
import json
from docx import Document

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app
from engine.security import check_anti_cheat

app.testing = True
os.environ["EDUDOC_TESTING"] = "1"

def test_blank_body_feature():
    print("=" * 60)
    print("KIỂM THỬ TÍNH NĂNG: ĐỂ TRỐNG PHẦN THÂN HOẶC GIẢNG VIÊN TỰ ĐƯA VÔ")
    print("=" * 60)

    client = app.test_client()

    # 1. BẬT CHẾ ĐỘ ĐỂ TRỐNG THÂN BÀI CHO 'cong_van_de_nghi'
    res_save = client.post("/api/teacher/templates/save", json={
        "doc_type": "cong_van_de_nghi",
        "is_body_blank": True,
        "header_part": "cơ quan chủ quản: BỘ GIÁO DỤC VÀ ĐÀO TẠO\ncơ quan ban hành: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 12/CV-DNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 15 tháng 01 năm 2026\ntrích yếu công văn: V/v đề nghị hỗ trợ kinh phí\n\nKính gửi: Bộ Khoa học và Công nghệ.",
        "body_part": "",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Lưu: VT.\n\nHIỆU TRƯỞNG\n\n\n\nTrần Ái Cầm"
    })
    assert res_save.status_code == 200
    print("✔ Đã lưu cấu hình: ĐỂ TRỐNG THÂN BÀI cho Công văn đề nghị.")

    # 2. SINH VIÊN TẢI FILE MẪU
    res_gen = client.post("/api/template/generate", json={
        "sbd": "09",
        "mssv": "2100007777",
        "name": "Lê Hoàng Nam",
        "doc_type": "cong_van_de_nghi"
    })
    assert res_gen.status_code == 200
    gen_data = res_gen.get_json()
    file_path = os.path.join("storage", "templates", gen_data["filename"])
    print(f"✔ Đã sinh file mẫu theo cấu hình: {file_path}")

    # Đọc nội dung file docx vừa tạo
    doc = Document(file_path)
    paras_text = [p.text for p in doc.paragraphs if p.text.strip()]
    has_blank_placeholder = any("[Nội dung văn bản:" in t for t in paras_text)
    assert has_blank_placeholder == True
    print("✔ XÁC NHẬN: Phần thân bài đã để trống theo chỉ định của Giảng viên!")

    # 3. KIỂM TRA CHỐNG GIAN LẬN VẪN HOẠT ĐỘNG DÙ THÂN BÀI ĐỂ TRỐNG
    fraud_check = check_anti_cheat(
        docx_path=file_path,
        current_sbd="09",
        current_mssv="2100007777",
        current_name="Lê Hoàng Nam"
    )
    assert fraud_check["is_fraud"] == False
    print("✔ XÁC NHẬN: Mã định danh bảo mật & Thủy ấn số vẫn tồn tại và hợp lệ 100%!")

    # Thử giả lập sinh viên khác lấy file này nộp
    fraud_check_stolen = check_anti_cheat(
        docx_path=file_path,
        current_sbd="99",
        current_mssv="2100009999",
        current_name="Sinh Viên Gian Lận"
    )
    assert fraud_check_stolen["is_fraud"] == True
    assert fraud_check_stolen["student_b"]["mssv"] == "2100007777"
    print("✔ XÁC NHẬN: Bắt quả tang chính xác danh tính người cho chép bài!")

    print("\n" + "=" * 60)
    print("TÍNH NĂNG MỚI ĐÃ HOÀN TẤT VÀ VƯỢT QUA KIỂM THỬ THÀNH CÔNG!")
    print("=" * 60)

if __name__ == "__main__":
    test_blank_body_feature()
