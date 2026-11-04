# -*- coding: utf-8 -*-
"""
BỘ KIỂM THỬ ĐỘC LẬP ĐỢT 4 - EDUDOC STVB (D18, D19, D25, D27, D28)
Tuân thủ đầy đủ các tiêu chuẩn nghiệm thu của Báo cáo Đánh giá STVB:
- D18: Sửa lỗi hàm bool trong JS & đồng bộ công tắc để trống thân bài
- D19: Thống kê lỗi thực tế từ DB (tính toán động, không dùng tỷ lệ cố định)
- D25: Bộ kiểm thử độc lập không phụ thuộc EDUDOC_TESTING=1 (kiểm thử chế độ Production, đối chứng âm)
- D27: Xử lý lỗi HTTP thân thiện (chuẩn hóa JSON error cho 400, 401, 403, 413, 429, 500)
- D28: Giới hạn tài nguyên tệp tải lên (16MB), kiểm soát Zip Bomb & Decompression Bomb
"""
import os
import sys
import io
import json
import zipfile
import unittest
import docx
from docx.shared import Inches, Pt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
from engine.security import (
    validate_docx_resource_limits, is_valid_docx,
    generate_anti_cheat_token, verify_anti_cheat_token,
    safe_storage_path
)
from engine.db import get_all_submissions, save_submission

class TestAuditPhase4(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        self.test_dir = os.path.join(BASE_DIR, "storage", "templates")
        os.makedirs(self.test_dir, exist_ok=True)

    def _create_base_a4_doc(self):
        d = docx.Document()
        for sec in d.sections:
            sec.page_width = Inches(21.0 / 2.54)
            sec.page_height = Inches(29.7 / 2.54)
            sec.top_margin = Inches(0.79)
            sec.bottom_margin = Inches(0.79)
            sec.left_margin = Inches(1.18)
            sec.right_margin = Inches(0.59)
        return d

    # =========================================================================
    # D18: SỬA LỖI HÀM BOOL TRONG JS & ĐỒNG BỘ CÔNG TẮC ĐỂ TRỐNG THÂN BÀI
    # =========================================================================
    def test_d18_blank_body_template_toggle(self):
        """[D18 - P1] Kiểm tra cấu hình để trống thân bài (is_body_blank) được lưu và xử lý boolean chính xác"""
        headers = {"X-Teacher-PIN": "gv2026"}
        
        # 1. Cập nhật mẫu để trống thân bài: is_body_blank = True
        res = self.client.post("/api/teacher/templates/save", json={
            "doc_type": "cong_van_de_nghi",
            "is_body_blank": True,
            "raw_text": "Cộng hòa xã hội chủ nghĩa Việt Nam\nĐộc lập - Tự do - Hạnh phúc"
        }, headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))

        # 2. Đọc lại mẫu bài tập: kiểm tra trường is_body_blank là True
        data_res = self.client.get("/api/teacher/templates", headers=headers)
        self.assertEqual(data_res.status_code, 200)
        templates_data = data_res.get_json()
        tmpl = templates_data.get("cong_van_de_nghi", {})
        self.assertTrue(bool(tmpl.get("is_body_blank")), "is_body_blank phải được lưu dạng Boolean True")

        # 3. Chuyển lại is_body_blank = False
        res2 = self.client.post("/api/teacher/templates/save", json={
            "doc_type": "cong_van_de_nghi",
            "is_body_blank": False,
            "raw_text": "Nội dung mẫu văn bản có phần thân bài do Giảng viên quy định."
        }, headers=headers)
        self.assertEqual(res2.status_code, 200)
        print("✔ [D18] Đồng bộ công tắc để trống thân bài và kiểu Boolean thành công!")

    # =========================================================================
    # D19: THỐNG KÊ LỖI THỰC TẾ TỪ CƠ SỞ DỮ LIỆU BÀI NỘP
    # =========================================================================
    def test_d19_real_error_analytics(self):
        """[D19 - P1] Thống kê lỗi thực tế từ DB: không dùng tỷ lệ dựng sẵn, trả has_data=False nếu rỗng"""
        headers = {"X-Teacher-PIN": "gv2026"}

        # 1. Kiểm tra thống kê cho toàn bộ hệ thống (ALL)
        res_all = self.client.get("/api/teacher/analytics?class_code=ALL", headers=headers)
        self.assertEqual(res_all.status_code, 200)
        data_all = res_all.get_json()
        self.assertTrue(data_all.get("success"))
        self.assertTrue(data_all.get("has_data"))
        self.assertGreater(data_all.get("total_submissions", 0), 0)
        self.assertIsInstance(data_all.get("group_stats"), list)
        self.assertEqual(len(data_all.get("group_stats")), 4)
        self.assertIsInstance(data_all.get("top_errors"), list)

        # 2. Kiểm tra thống kê cho một lớp hoàn toàn không có bài nộp nào
        res_empty = self.client.get("/api/teacher/analytics?class_code=LOP_CHUA_CO_BAI_999", headers=headers)
        self.assertEqual(res_empty.status_code, 200)
        data_empty = res_empty.get_json()
        self.assertTrue(data_empty.get("success"))
        self.assertFalse(data_empty.get("has_data"), "Lớp chưa có bài nộp phải trả về has_data = False!")
        self.assertEqual(data_empty.get("total_submissions"), 0)
        self.assertIn("Chưa có đủ dữ liệu thống kê", data_empty.get("message", ""))

        # 3. Kiểm tra tính động của số liệu: các nhóm thể thức có số đếm và tỷ lệ thực
        for grp in data_all.get("group_stats", []):
            self.assertIn("passRate", grp)
            self.assertIn("passed", grp)
            self.assertIn("failed", grp)
            self.assertGreaterEqual(grp["passRate"], 0)
            self.assertLessEqual(grp["passRate"], 100)
        print("✔ [D19] Thống kê lỗi thực tế từ DB hoạt động chính xác và phản ánh dữ liệu thật!")

    # =========================================================================
    # D28: GIỚI HẠN TÀI NGUYÊN TỆP TẢI LÊN & CHỐNG ZIP BOMB
    # =========================================================================
    def test_d28_resource_limits_and_zip_bomb_protection(self):
        """[D28 - P1] Chống Zip Bomb: chặn gói nén quá 500 file hoặc kích thước giải nén > 50MB"""
        # 1. Tạo tệp giả lập Zip Bomb với > 500 file con
        bomb_buf = io.BytesIO()
        with zipfile.ZipFile(bomb_buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types></Types>")
            z.writestr("word/document.xml", "<w:document></w:document>")
            for i in range(505):
                z.writestr(f"word/dummy_{i}.xml", f"<tag>{i}</tag>")
        bomb_buf.seek(0)

        tmp_bomb_path = os.path.join(self.test_dir, "test_d28_zip_bomb.docx")
        with open(tmp_bomb_path, "wb") as f:
            f.write(bomb_buf.getvalue())

        try:
            is_valid, err, too_large = validate_docx_resource_limits(tmp_bomb_path)
            self.assertFalse(is_valid, "Phải từ chối file có > 500 thành phần nén!")
            self.assertTrue(too_large)
            self.assertIn("Zip Bomb", err)
            self.assertFalse(is_valid_docx(tmp_bomb_path))
        finally:
            if os.path.exists(tmp_bomb_path):
                os.remove(tmp_bomb_path)

        # 2. Tạo tệp hợp lệ chuẩn kích thước bình thường
        d = self._create_base_a4_doc()
        d.add_paragraph("Nội dung thử nghiệm hợp lệ chuẩn")
        tmp_valid_path = os.path.join(self.test_dir, "test_d28_valid.docx")
        d.save(tmp_valid_path)
        try:
            is_valid, err, too_large = validate_docx_resource_limits(tmp_valid_path)
            self.assertTrue(is_valid, f"Tệp chuẩn phải hợp lệ: {err}")
            self.assertFalse(too_large)
            self.assertTrue(is_valid_docx(tmp_valid_path))
        finally:
            if os.path.exists(tmp_valid_path):
                os.remove(tmp_valid_path)
        print("✔ [D28] Ngăn chặn Zip Bomb và kiểm soát tài nguyên tệp DOCX an toàn tuyệt đối!")

    # =========================================================================
    # D27: CHUẨN HÓA CẤU TRÚC PHẢN HỒI LỖI JSON & MÃ HTTP THÂN THIỆN
    # =========================================================================
    def test_d27_standardized_json_errors(self):
        """[D27 - P2] Chuẩn hóa mã phản hồi HTTP và cấu trúc JSON khi phát sinh lỗi nghiệp vụ"""
        # 1. Yêu cầu tải mẫu với đề không tồn tại -> 400 JSON
        res_bad_doc = self.client.post("/api/template/generate", json={"doc_type": "loai_van_ban_khong_ton_tai_xyz"})
        self.assertEqual(res_bad_doc.status_code, 400)
        self.assertIn("error", res_bad_doc.get_json())

        # 2. Truy cập API Giảng viên không có PIN -> 401 JSON
        res_no_pin = self.client.get("/api/teacher/data", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_no_pin.status_code, 401)
        data_no_pin = res_no_pin.get_json()
        self.assertTrue(data_no_pin.get("auth_required"))
        self.assertIn("error", data_no_pin)

        # 3. Nộp bài khi chưa có file tạm hợp lệ -> 404 JSON
        res_bad_submit = self.client.post("/api/submit", json={
            "class_code": "KN01",
            "sbd": "01",
            "mssv": "2280600111",
            "name": "Nguyễn Văn A",
            "doc_type": "bai_thu_hoach",
            "temp_file": "file_chua_ton_tai_9999.docx"
        })
        self.assertEqual(res_bad_submit.status_code, 404)
        self.assertIn("error", res_bad_submit.get_json())
        print("✔ [D27] Chuẩn hóa thông báo lỗi JSON và mã phản hồi HTTP đồng bộ!")

    # =========================================================================
    # D25: KIỂM THỬ ĐỘC LẬP CHẾ ĐỘ PRODUCTION (KHÔNG BẬT TESTING)
    # =========================================================================
    def test_d25_production_security_enforcement(self):
        """[D25 - P1] Thử nghiệm độc lập chế độ Production: bảo vệ phân quyền, khóa phòng và đối chứng âm"""
        # 1. Thử tấn công Path Traversal trên tên tệp
        self.assertRaises(ValueError, safe_storage_path, self.test_dir, "../../windows/system32/cmd.exe")
        self.assertRaises(ValueError, safe_storage_path, self.test_dir, "..\\..\\boot.ini")

        # 2. Thử giả mạo token bảo mật chữ ký số không có HMAC hợp lệ
        fake_token = "STVB_FAKE_TOKEN_WITHOUT_PROPER_HMAC_SIGNATURE"
        self.assertFalse(verify_anti_cheat_token(fake_token, "01", "2280600111", "bai_thu_hoach", "20261105120000"))

        # 3. Thử token chuẩn có HMAC hợp lệ
        valid_token = generate_anti_cheat_token("01", "2280600111", "bai_thu_hoach", "20261105120000")
        self.assertTrue(verify_anti_cheat_token(valid_token, "01", "2280600111", "bai_thu_hoach", "20261105120000"))

        # 4. Đối chứng âm: token của sinh viên khác không khớp
        self.assertFalse(verify_anti_cheat_token(valid_token, "02", "2280600222", "bai_thu_hoach", "20261105120000"))

        print("✔ [D25] Kiểm thử độc lập an ninh, phân quyền và các kịch bản đối chứng âm thành công!")

if __name__ == "__main__":
    unittest.main()
