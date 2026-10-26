# -*- coding: utf-8 -*-
"""
Kiểm tra tính tuân thủ nghiêm ngặt theo 3 Sơ đồ Bố trí Thể thức Nghị định 30:
1. Sơ đồ Tờ trình, Báo cáo (Hình 1): Có Ô 5a, Có Ô 9a (Kính gửi), Ô 6, Bảng cuối Ô 9b & 7a, 7b
2. Sơ đồ Công văn (Hình 2): Có Ô 5b (trong bảng đầu trang dưới Ô 3), Có Ô 9a (Kính gửi), Ô 6, Bảng cuối Ô 9b & 7a, 7b (KHÔNG CÓ Ô 5a)
3. Sơ đồ Thông báo (Hình 3): Có Ô 5a, TUYỆT ĐỐI KHÔNG CÓ Ô 9a (Kính gửi), Ô 6, Bảng cuối Ô 9b & 7a, 7b
"""
import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from docx import Document
from engine.validator import Decree30Validator

class TestSchemaLayouts(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(BASE_DIR, "tests", "temp_schema_tests")
        os.makedirs(self.test_dir, exist_ok=True)

    def _create_base_doc(self, left_margins=3.0, top_margin=2.0, bot_margin=2.0, right_margin=1.5):
        from docx.shared import Inches, Pt
        doc = Document()
        for sec in doc.sections:
            sec.top_margin = Inches(top_margin / 2.54)
            sec.bottom_margin = Inches(bot_margin / 2.54)
            sec.left_margin = Inches(left_margins / 2.54)
            sec.right_margin = Inches(right_margin / 2.54)
        return doc

    def test_thong_bao_rejects_kinh_gui(self):
        """Thông báo nếu cố tình thêm Kính gửi (Ô 9a) phải bị hệ thống cảnh báo vi phạm sơ đồ NĐ 30"""
        validator = Decree30Validator.__new__(Decree30Validator)
        validator.doc_type_id = "thong_bao_nhiem_vu"
        
        class MockParagraph:
            def __init__(self, text):
                self.text = text
        
        p_kg = MockParagraph("Kính gửi: Toàn thể giảng viên và sinh viên.")
        res = validator.check_box_9a_kinh_gui(p_kg, [])
        
        self.assertIsNotNone(res)
        self.assertFalse(res["passed"])
        self.assertTrue(any("sơ đồ bố trí" in err["issue"].lower() for err in res["errors"]))

    def test_thong_bao_without_kinh_gui_passes(self):
        """Thông báo không có Kính gửi đúng chuẩn sơ đồ Hình 3"""
        validator = Decree30Validator.__new__(Decree30Validator)
        validator.doc_type_id = "thong_bao_nhiem_vu"
        
        res = validator.check_box_9a_kinh_gui(None, [])
        self.assertIsNone(res) # Hợp lệ, không yêu cầu và không xuất hiện

    def test_to_trinh_requires_kinh_gui(self):
        """Tờ trình bắt buộc phải có Ô 9a Kính gửi theo sơ đồ Hình 1"""
        validator = Decree30Validator.__new__(Decree30Validator)
        validator.doc_type_id = "to_trinh_xin_kinh_phi"
        
        res = validator.check_box_9a_kinh_gui(None, [])
        self.assertIsNotNone(res)
        self.assertFalse(res["passed"])
        self.assertTrue(any("bắt buộc phải có" in err["issue"].lower() for err in res["errors"]))

    def test_cong_van_requires_kinh_gui(self):
        """Công văn bắt buộc phải có Ô 9a Kính gửi theo sơ đồ Hình 2"""
        validator = Decree30Validator.__new__(Decree30Validator)
        validator.doc_type_id = "cong_van_de_nghi"
        
        res = validator.check_box_9a_kinh_gui(None, [])
        self.assertIsNotNone(res)
        self.assertFalse(res["passed"])
        self.assertTrue(any("bắt buộc phải có" in err["issue"].lower() for err in res["errors"]))

if __name__ == "__main__":
    unittest.main()
