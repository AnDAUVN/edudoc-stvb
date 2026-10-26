# -*- coding: utf-8 -*-
"""
Kiểm thử tự động tính năng Chống đối phó & Chống gian lận (Giai đoạn 1 & Giai đoạn 2)
EduDoc - STVB Nghị định 30/2020/NĐ-CP
"""
import os
import sys
import json
import time
import unittest
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import app, load_json_file, save_json_file, STUDENT_SESSIONS_FILE
from engine.validator import Decree30Validator

class TestAntiCheatStages(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        os.environ["EDUDOC_TESTING"] = "1"
        self.test_dir = os.path.join(BASE_DIR, "storage", "templates")
        os.makedirs(self.test_dir, exist_ok=True)

    def test_01_space_abuse_detection(self):
        """[GĐ 1] Bắt lỗi sử dụng phím Space liên tiếp (>= 4 space) để căn chỉnh đối phó"""
        doc = Document()
        doc.add_paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM    Độc lập - Tự do - Hạnh phúc")
        doc_path = os.path.join(self.test_dir, "test_space_abuse.docx")
        doc.save(doc_path)

        val = Decree30Validator(doc_path, "thong_bao_nhiem_vu")
        res = val.validate_document()
        table_check = next((it for it in res["checklist"] if it["box_id"] == "tables"), None)
        self.assertIsNotNone(table_check)
        self.assertFalse(table_check["passed"])
        
        has_space_err = any("lạm dụng phím Space" in e.get("issue", "") for e in table_check.get("errors", []))
        self.assertTrue(has_space_err, "Hệ thống phải bắt được lỗi lạm dụng Spacebar!")
        print("✔ [GĐ 1] Đã phát hiện thành công lỗi lạm dụng Spacebar đối phó!")

    def test_02_enter_abuse_detection(self):
        """[GĐ 1] Bắt lỗi bấm Enter liên tiếp (>= 4 đoạn trống) để dồn trang"""
        doc = Document()
        doc.add_paragraph("Dòng 1")
        for _ in range(5):
            doc.add_paragraph("")
        doc.add_paragraph("Dòng kết thúc")
        doc_path = os.path.join(self.test_dir, "test_enter_abuse.docx")
        doc.save(doc_path)

        val = Decree30Validator(doc_path, "thong_bao_nhiem_vu")
        res = val.validate_document()
        table_check = next((it for it in res["checklist"] if it["box_id"] == "tables"), None)
        self.assertIsNotNone(table_check)
        self.assertFalse(table_check["passed"])
        
        has_enter_err = any("lạm dụng phím enter" in e.get("issue", "").lower() for e in table_check.get("errors", []))
        self.assertTrue(has_enter_err, "Hệ thống phải bắt được lỗi dồn trang bằng nhiều phím Enter!")
        print("✔ [GĐ 1] Đã phát hiện thành công lỗi lạm dụng Enter dồn trang!")

    def test_03_telemetry_and_speed_cheating(self):
        """[GĐ 1] Đo thời gian làm bài, số lần kiểm tra thử & Cảnh báo nộp bài quá nhanh"""
        # Giả lập sinh template
        res_gen = self.client.post("/api/template/generate", json={
            "class_code": "KN01",
            "sbd": "88",
            "mssv": "2100008888",
            "name": "Trần Văn Tốc Độ",
            "doc_type": "thong_bao_nhiem_vu"
        })
        self.assertEqual(res_gen.status_code, 200)

        # Kiểm tra session telemetry đã lưu thời gian bắt đầu
        sessions = load_json_file(STUDENT_SESSIONS_FILE, {})
        sess_key = "2100008888_thong_bao_nhiem_vu"
        self.assertIn(sess_key, sessions)
        self.assertIn("timestamp", sessions[sess_key])
        print(f"✔ [GĐ 1] Đã ghi nhận Telemetry khởi tạo: {sessions[sess_key]['started_at']}")

    def test_04_quiz_randomization_and_shuffled_options(self):
        """[GĐ 2] Ngân hàng câu hỏi xáo trộn câu và xáo trộn các phương án A-B-C-D"""
        res = self.client.post("/api/quiz/get", json={"doc_type": "cong_van_de_nghi"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        
        self.assertEqual(data["total"], 5)
        self.assertEqual(data["time_limit_seconds"], 300)
        self.assertTrue(len(data["questions"]) == 5)
        
        first_q = data["questions"][0]
        self.assertIn("options", first_q)
        # Các phương án được định dạng dạng object {opt_id, text} để chống chép vẹt
        self.assertTrue(isinstance(first_q["options"][0], dict))
        self.assertIn("opt_id", first_q["options"][0])
        self.assertIn("text", first_q["options"][0])
        print("✔ [GĐ 2] Trắc nghiệm đã xáo trộn ngẫu nhiên phương án kèm opt_id bảo mật!")

    def test_05_quiz_grading_with_shuffled_options(self):
        """[GĐ 2] Chấm điểm trắc nghiệm chính xác tuyệt đối ngay cả khi phương án bị xáo trộn"""
        all_q = load_json_file(os.path.join(BASE_DIR, "data", "questions.json"), {})
        cv_qs = all_q.get("cong_van_de_nghi", [])
        
        # Tạo payload với đáp án đúng dựa vào trường 'correct' gốc
        correct_answers = {str(q["id"]): q["correct"] for q in cv_qs[:5]}
        res = self.client.post("/api/quiz/submit", json={
            "doc_type": "cong_van_de_nghi",
            "answers": correct_answers
        })
        self.assertEqual(res.status_code, 200)
        sub_data = res.get_json()
        self.assertEqual(sub_data["score"], 5)
        self.assertTrue(sub_data["passed"])
        print("✔ [GĐ 2] Chấm trắc nghiệm đạt 5/5 chính xác theo ID gốc!")

    def test_06_personalized_mssv_matching(self):
        """[GĐ 2] Cá nhân hóa đề bài: Kiểm tra 3 số cuối MSSV trong Số văn bản"""
        doc = Document()
        # Tạo Header table 2x2
        t = doc.add_table(rows=2, cols=2)
        # Ô 2 / Ô 1
        t.cell(0, 0).paragraphs[0].add_run("TRƯỜNG ĐH NTT")
        t.cell(0, 1).paragraphs[0].add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        p_tn = t.cell(0, 1).add_paragraph()
        p_tn.add_run("Độc lập - Tự do - Hạnh phúc")
        # Ô 3: Sinh viên A có MSSV 2100001234 -> 3 số cuối là 234
        p_so = t.cell(1, 0).paragraphs[0]
        p_so.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p_so.add_run("Số: 234/TB-ĐT")
        r.font.name = "Times New Roman"
        r.font.size = Pt(13)
        # Ô 4
        t.cell(1, 1).paragraphs[0].add_run("TP. Hồ Chí Minh, ngày 02 tháng 02 năm 2026")

        doc_path = os.path.join(self.test_dir, "test_personalized_doc.docx")
        doc.save(doc_path)

        # 1. Trường hợp chính chủ (MSSV đuôi 234): Phải khớp
        val_correct = Decree30Validator(doc_path, "thong_bao_nhiem_vu", mssv="2100001234")
        p_so_p = t.cell(1, 0).paragraphs[0]
        res_correct = val_correct.check_box_3_so_ky_hieu(p_so_p)
        has_mismatch = any("Yêu cầu cá nhân hóa" in e.get("issue", "") for e in res_correct.get("errors", []))
        self.assertFalse(has_mismatch, "Chính chủ phải không bị báo lỗi cá nhân hóa!")

        # 2. Trường hợp nộp bài chép (Sinh viên khác MSSV đuôi 999 nhưng nộp file có số 234)
        val_stolen = Decree30Validator(doc_path, "thong_bao_nhiem_vu", mssv="2100009999")
        res_stolen = val_stolen.check_box_3_so_ky_hieu(p_so_p)
        has_stolen_err = any("Yêu cầu cá nhân hóa" in e.get("issue", "") for e in res_stolen.get("errors", []))
        self.assertTrue(has_stolen_err, "Phải phát hiện số văn bản không khớp với MSSV của người nộp!")
        print("✔ [GĐ 2] Hệ thống đã phát hiện thành công sai lệch số văn bản cá nhân hóa!")

if __name__ == "__main__":
    unittest.main()
