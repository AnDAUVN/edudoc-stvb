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

    def test_cong_van_with_illegal_5a_detected(self):
        """Công văn nếu cố tình thêm chữ CÔNG VĂN (Ô 5a) hoặc trích yếu ngoài bảng phải báo lỗi vi phạm Sơ đồ 2"""
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt
        doc = Document()
        
        # Tạo bảng đầu trang 2x2
        tbl = doc.add_table(rows=2, cols=2)
        tbl.cell(0, 0).paragraphs[0].text = "CÔNG TY TNHH HẢI THÀNH"
        tbl.cell(0, 1).paragraphs[0].text = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"
        p_so = tbl.cell(1, 0).paragraphs[0]
        p_so.text = "Số: 01/HT"
        p_so.runs[0].font.name = "Times New Roman"
        p_so.runs[0].font.size = Pt(13)
        p_so.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        p_vv = tbl.cell(1, 0).add_paragraph("V/v xử lý hành vi quấy rối và đảm bảo an ninh tại trụ sở công ty")
        p_vv.runs[0].font.name = "Times New Roman"
        p_vv.runs[0].font.size = Pt(12)
        p_vv.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        p_dd = tbl.cell(1, 1).paragraphs[0]
        p_dd.text = "Thành phố Hồ Chí Minh, ngày 20 tháng 10 năm 2026"
        p_dd.runs[0].font.name = "Times New Roman"
        p_dd.runs[0].font.size = Pt(13)
        p_dd.runs[0].font.italic = True
        p_dd.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Cố tình thêm Ô 5a "CÔNG VĂN" và trích yếu ngoài bảng (như ảnh của người dùng)
        p_title = doc.add_paragraph("CÔNG VĂN")
        p_title.runs[0].font.name = "Times New Roman"
        p_title.runs[0].font.size = Pt(13)
        p_title.runs[0].font.bold = True
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        p_extra = doc.add_paragraph("Về việc đề nghị xử lý hành vi gây rối trật tự công cộng")
        p_extra.runs[0].font.name = "Times New Roman"
        p_extra.runs[0].font.size = Pt(13)
        p_extra.runs[0].font.bold = True
        p_extra.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Kính gửi Ô 9a
        p_kg = doc.add_paragraph("Kính gửi: Công an phường Sài Gòn.")
        p_kg.runs[0].font.name = "Times New Roman"
        p_kg.runs[0].font.size = Pt(13)
        
        # Thân bài Ô 6
        p_body = doc.add_paragraph("Công ty TNHH Hải Thành đang gặp khó khăn về một số đối tượng thường xuyên tụ tập trước cổng công ty...")
        p_body.runs[0].font.name = "Times New Roman"
        p_body.runs[0].font.size = Pt(13)
        
        # Bảng cuối trang 1x2
        tbl_f = doc.add_table(rows=1, cols=2)
        tbl_f.cell(0, 0).paragraphs[0].text = "Nơi nhận:\n- Như kính gửi;\n- Lưu: VT."
        tbl_f.cell(0, 1).paragraphs[0].text = "GIÁM ĐỐC\n\n\n\nNguyễn Văn A"

        test_file = os.path.join(self.test_dir, "test_cv_with_5a.docx")
        doc.save(test_file)

        validator = Decree30Validator(test_file, doc_type_id="cong_van_de_nghi")
        res = validator.validate_document()

        # Kiểm tra Ô 5b phải bị đánh rớt (passed: False) do vi phạm sơ đồ Công văn
        box_5b = next((b for b in res["checklist"] if b["box_id"] == "5b"), None)
        self.assertIsNotNone(box_5b)
        self.assertFalse(box_5b["passed"], "Ô 5b phải bị đánh rớt vì có Ô 5a trong Công văn")
        
        err_issues = [err["issue"].lower() for err in box_5b["errors"]]
        self.assertTrue(any("không có tên loại (ô 5a)" in iss for iss in err_issues), "Phải báo lỗi Công văn không có tên loại 5a")
        self.assertTrue(any("trích yếu đặt ở giữa trang ngoài bảng" in iss for iss in err_issues), "Phải báo lỗi trích yếu thứ 2 ngoài bảng")

if __name__ == "__main__":
    unittest.main()
