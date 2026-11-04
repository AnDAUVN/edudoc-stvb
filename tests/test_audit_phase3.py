# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động Đợt 3 (Audit Phase 3 Remediation) - EduDoc STVB
Kiểm thử các hạng mục:
- D09: Kiểm tra lề mọi Section trong tài liệu
- D10: Chuẩn hóa khoảng lề chấp nhận theo chuẩn Nghị định 30 (dung sai OpenXML)
- D11: Thẩm định khổ giấy chuẩn A4 (210 x 297 mm)
- D12: Đánh giá Font chữ và Cỡ chữ trên toàn bộ các Runs văn bản
- D13: Ràng buộc tính hợp lệ của câu hỏi và đáp án trắc nghiệm
- D14: Xác minh chữ ký số bảo mật HMAC bằng compare_digest
- D17: Tách bạch điểm Thể thức và Nội dung Ô 6
- D23: Loại trừ boilerplate và nội dung đề bài khi so sánh đạo văn Ô 6
- D26: Chuẩn hóa rule_id và căn cứ pháp lý Nghị định 30 trên checklist
"""
import os
import sys
import io
import json
import time
import unittest
import docx
from docx.shared import Inches, Pt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ["EDUDOC_TESTING"] = "1"

from app import app
from engine.validator import Decree30Validator
from engine.security import (
    generate_anti_cheat_token, verify_anti_cheat_token,
    check_anti_cheat, check_box6_plagiarism, create_student_raw_template
)

class TestAuditPhase3(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        self.test_dir = os.path.join(BASE_DIR, "storage", "templates")
        os.makedirs(self.test_dir, exist_ok=True)

    def _create_base_a4_doc(self):
        d = docx.Document()
        sec = d.sections[0]
        sec.page_width = Inches(8.27)   # 21.0 cm A4
        sec.page_height = Inches(11.69) # 29.7 cm A4
        sec.top_margin = Inches(0.79)   # 2.0 cm
        sec.bottom_margin = Inches(0.79)# 2.0 cm
        sec.left_margin = Inches(1.18)  # 3.0 cm
        sec.right_margin = Inches(0.59) # 1.5 cm
        return d

    def test_d09_multi_section_margins(self):
        """[D09 - P1] Kiểm tra lề trên mọi Section, phát hiện lỗi nếu section 2 sai lề"""
        d = self._create_base_a4_doc()
        d.add_paragraph("Nội dung Section 1 chuẩn mực")

        # Thêm Section 2 với lề trái sai (1.0 cm ~ 0.39 inch)
        sec2 = d.add_section()
        sec2.page_width = Inches(8.27)
        sec2.page_height = Inches(11.69)
        sec2.top_margin = Inches(0.79)
        sec2.bottom_margin = Inches(0.79)
        sec2.left_margin = Inches(0.39)  # 1.0 cm -> SAI
        sec2.right_margin = Inches(0.59)
        d.add_paragraph("Nội dung Section 2 có lề trái sai")

        tmp_path = os.path.join(self.test_dir, "test_d09_multisection.docx")
        d.save(tmp_path)

        val = Decree30Validator(tmp_path, "cong_van_de_nghi")
        res = val.check_page_margins()
        self.assertFalse(res["passed"], "Tài liệu có Section 2 sai lề trái bắt buộc phải không đạt!")
        has_sec2_err = any("Section 2" in err.get("issue", "") and "Lề trái" in err.get("issue", "") for err in res["errors"])
        self.assertTrue(has_sec2_err, "Phải báo rõ lỗi lề tại Section 2!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D09] Thẩm định lề đa Section hoạt động chính xác!")

    def test_d10_margin_strict_tolerance(self):
        """[D10 - P1] Chuẩn hóa khoảng lề chấp nhận theo NĐ 30, từ chối lề trên 1.90cm hoặc 2.60cm"""
        d = self._create_base_a4_doc()
        # Đặt lề trên 1.90 cm (ngoài dung sai 1.95 - 2.55)
        d.sections[0].top_margin = Inches(1.90 / 2.54)
        tmp_path = os.path.join(self.test_dir, "test_d10_margin_strict.docx")
        d.save(tmp_path)

        val = Decree30Validator(tmp_path, "cong_van_de_nghi")
        res = val.check_page_margins()
        self.assertFalse(res["passed"])
        has_top_err = any("Lề trên chưa đạt chuẩn" in err.get("issue", "") for err in res["errors"])
        self.assertTrue(has_top_err, "Lề trên 1.90cm phải bị từ chối!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D10] Chuẩn hóa khoảng lề theo dung sai NĐ 30 chuẩn xác!")

    def test_d11_page_size_a4_validation(self):
        """[D11 - P1] Bắt lỗi khi khổ giấy không phải A4 (ví dụ 10x10 cm hoặc Letter)"""
        d = docx.Document()
        sec = d.sections[0]
        # Khổ 10 x 10 cm (~ 3.94 x 3.94 inch)
        sec.page_width = Inches(3.94)
        sec.page_height = Inches(3.94)
        sec.top_margin = Inches(0.79)
        sec.bottom_margin = Inches(0.79)
        sec.left_margin = Inches(1.18)
        sec.right_margin = Inches(0.59)
        d.add_paragraph("Văn bản khổ 10x10 cm")

        tmp_path = os.path.join(self.test_dir, "test_d11_non_a4.docx")
        d.save(tmp_path)

        val = Decree30Validator(tmp_path, "cong_van_de_nghi")
        res = val.check_page_margins()
        self.assertFalse(res["passed"])
        has_a4_err = any("Khổ giấy chưa đạt chuẩn A4" in err.get("issue", "") for err in res["errors"])
        self.assertTrue(has_a4_err, "Phải bắt lỗi khi khổ giấy là 10x10cm thay vì A4!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D11] Thẩm định khổ giấy A4 theo NĐ 30 thành công!")

    def test_d12_run_level_font_and_size(self):
        """[D12 - P1] Đánh giá Font và Size theo trọng số Run có chữ, chống chèn ký tự hợp lệ ở đầu để đối phó"""
        d = self._create_base_a4_doc()
        p = d.add_paragraph()
        # Chèn 1 ký tự Times New Roman 13pt ở đầu
        r1 = p.add_run("T")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(13)
        # 50 ký tự tiếp theo bằng Arial 30pt
        r2 = p.add_run("he quick brown fox jumps over the lazy dog repeatedly")
        r2.font.name = "Arial"
        r2.font.size = Pt(30)

        tmp_path = os.path.join(self.test_dir, "test_d12_runs.docx")
        d.save(tmp_path)

        val = Decree30Validator(tmp_path, "cong_van_de_nghi")
        font, size, bold, italic = val._get_dominant_font_and_size(p)
        self.assertEqual(font, "Arial", "Font chủ đạo theo trọng số ký tự phải là Arial, không phải Times New Roman!")
        self.assertEqual(size, 30.0, "Cỡ chữ chủ đạo theo trọng số ký tự phải là 30.0, không phải 13.0!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D12] Đánh giá Font/Size chi tiết ở cấp độ Run thành công!")

    def test_d13_quiz_validation_bounds(self):
        """[D13 - P1] Chặn lưu câu hỏi trắc nghiệm khi correct vượt số phương án hoặc âm"""
        # Test 1: correct=99 khi chỉ có 2 phương án
        res_bad = self.client.post("/api/teacher/quiz/save", json={
            "doc_type": "cong_van_de_nghi",
            "question": "Câu hỏi thử nghiệm kiểm tra giới hạn",
            "options": ["Phương án A", "Phương án B"],
            "correct": 99
        })
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn("vượt quá", res_bad.get_json().get("error", "").lower())

        # Test 2: correct âm
        res_neg = self.client.post("/api/teacher/quiz/save", json={
            "doc_type": "cong_van_de_nghi",
            "question": "Câu hỏi thử nghiệm kiểm tra giới hạn",
            "options": ["Phương án A", "Phương án B"],
            "correct": -1
        })
        self.assertEqual(res_neg.status_code, 400)

        # Test 3: options rỗng hoặc không phải list
        res_opt = self.client.post("/api/teacher/quiz/save", json={
            "doc_type": "cong_van_de_nghi",
            "question": "Câu hỏi thử nghiệm kiểm tra giới hạn",
            "options": ["Phương án A", ""],
            "correct": 0
        })
        self.assertEqual(res_opt.status_code, 400)
        print("✔ [D13] Ràng buộc tính hợp lệ của câu hỏi & đáp án trắc nghiệm chuẩn xác!")

    def test_d14_hmac_cryptographic_verification(self):
        """[D14 - P1] Xác minh mã bảo mật HMAC bằng compare_digest, phát hiện phôi bị sửa đổi"""
        # Sinh token HMAC hợp lệ
        valid_token = generate_anti_cheat_token("01", "2200001234", "cong_van_de_nghi", "20261105120000")
        self.assertTrue(verify_anti_cheat_token(valid_token, "01", "2200001234", "cong_van_de_nghi", "20261105120000"))

        # Token giả mạo hoặc sửa đổi
        tampered_token = valid_token[:-4] + "dead"
        self.assertFalse(verify_anti_cheat_token(tampered_token, "01", "2200001234", "cong_van_de_nghi", "20261105120000"))

        # Thử kiểm tra qua check_anti_cheat với file Word có chữ ký HMAC giả mạo
        d = self._create_base_a4_doc()
        d.core_properties.identifier = f"STVB_SIGNATURE:{tampered_token}"
        d.core_properties.keywords = "01|2200001234|Nguyen Van Test|cong_van_de_nghi|20261105120000"
        tmp_path = os.path.join(self.test_dir, "test_d14_tampered_hmac.docx")
        d.save(tmp_path)

        res_check = check_anti_cheat(tmp_path, "01", "2200001234", "Nguyen Van Test", doc_type="cong_van_de_nghi")
        self.assertTrue(res_check["is_fraud"])
        self.assertEqual(res_check["fraud_type"], "FILE_KHONG_HOP_LE")
        self.assertIn("HMAC", res_check["reason"])
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D14] Xác thực chữ ký HMAC bảo mật phôi bài bằng compare_digest thành công!")

    def test_d17_and_d26_content_scoring_and_rule_ids(self):
        """[D17 & D26 - P1] Kiểm tra mức độ đầy đủ nội dung Ô 6 và cấu trúc rule_id trên checklist"""
        d = self._create_base_a4_doc()
        # Thân bài chỉ có 3 từ -> quá ngắn
        p_body = d.add_paragraph("Nội dung ngắn.")
        tmp_path = os.path.join(self.test_dir, "test_d17_short.docx")
        d.save(tmp_path)

        val = Decree30Validator(tmp_path, "cong_van_de_nghi")
        box6_res = val.check_box_6_noi_dung([p_body])
        self.assertFalse(box6_res["passed"], "Nội dung quá ngắn (3 từ) phải không đạt Ô 6!")
        self.assertEqual(box6_res.get("rule_id"), "ND30_O6_NOI_DUNG")
        self.assertIn("Mục II.7", box6_res.get("legal_ref", ""))

        margins_res = val.check_page_margins()
        self.assertEqual(margins_res.get("rule_id"), "ND30_PL1_CAN_LE_KHO_GIAY")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D17 & D26] Phân tách điểm nội dung và gắn nhãn rule_id chuẩn NĐ 30 thành công!")

    def test_d23_boilerplate_exclusion_in_plagiarism(self):
        """[D23 - P1] Loại trừ boilerplate và đề bài cố định khi so khớp đạo văn Ô 6"""
        # Mẫu bài tập có đề bài cố định: hai sinh viên cùng làm đúng đề không bị đánh dấu sao chép
        tmp_path = os.path.join(self.test_dir, "test_d23_fixed.docx")
        d = self._create_base_a4_doc()
        d.add_paragraph("Hiện nay Công ty Ánh Dương đang vào giai đoạn cao điểm sản xuất phục vụ thị trường...")
        d.save(tmp_path)

        # Với doc_type='thong_bao_nhiem_vu' (is_body_blank=False)
        res_plag = check_box6_plagiarism(tmp_path, "01", "2200007777", "SV Test", doc_type="thong_bao_nhiem_vu")
        self.assertFalse(res_plag["is_fraud"], "Đề bài có thân bài cố định không được coi việc gõ đúng đề là đạo văn!")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print("✔ [D23] Loại trừ boilerplate và nội dung đề bài cố định khi so khớp đạo văn thành công!")

if __name__ == "__main__":
    unittest.main()
