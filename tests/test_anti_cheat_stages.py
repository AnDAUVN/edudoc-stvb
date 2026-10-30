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
from engine.security import check_anti_cheat

class TestAntiCheatStages(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        os.environ["EDUDOC_TESTING"] = "1"
        self.test_dir = os.path.join(BASE_DIR, "storage", "templates")
        os.makedirs(self.test_dir, exist_ok=True)
        from engine.db import delete_box6_submission_by_mssv
        for m in ["2100009991", "2100009992", "2100008888"]:
            delete_box6_submission_by_mssv(m)
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                if any(m in f for m in ["2100009991", "2100009992"]):
                    try:
                        os.remove(os.path.join(self.test_dir, f))
                    except Exception:
                        pass

    def tearDown(self):
        from engine.db import delete_box6_submission_by_mssv
        for m in ["2100009991", "2100009992", "2100008888"]:
            delete_box6_submission_by_mssv(m)
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                if any(m in f for m in ["2100009991", "2100009992"]):
                    try:
                        os.remove(os.path.join(self.test_dir, f))
                    except Exception:
                        pass

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

    def test_06_decree30_box3_valid_number_and_formula(self):
        """[GĐ 2 - Phương án 3] Kiểm tra Ô 3: Số thứ tự hợp chuẩn NĐ 30 (Chữ số Ả-rập >= 01, không được 000/0) và ký hiệu"""
        doc = Document()
        # Tạo Header table 2x2
        t = doc.add_table(rows=2, cols=2)
        # Ô 2 / Ô 1
        t.cell(0, 0).paragraphs[0].add_run("TRƯỜNG ĐH NTT")
        t.cell(0, 1).paragraphs[0].add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        p_tn = t.cell(0, 1).add_paragraph()
        p_tn.add_run("Độc lập - Tự do - Hạnh phúc")
        # Ô 3: Số: 45/TB-ĐT
        p_so = t.cell(1, 0).paragraphs[0]
        p_so.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p_so.add_run("Số: 45/TB-ĐT")
        r.font.name = "Times New Roman"
        r.font.size = Pt(13)
        # Ô 4
        t.cell(1, 1).paragraphs[0].add_run("TP. Hồ Chí Minh, ngày 02 tháng 02 năm 2026")

        doc_path = os.path.join(self.test_dir, "test_box3_doc.docx")
        doc.save(doc_path)

        # 1. Trường hợp số chuẩn mực (Số: 45/TB-ĐT): Phải đạt
        val = Decree30Validator(doc_path, "thong_bao_nhiem_vu")
        p_so_p = t.cell(1, 0).paragraphs[0]
        res_correct = val.check_box_3_so_ky_hieu(p_so_p)
        self.assertTrue(res_correct["passed"], "Số văn bản hợp lệ 45/TB-ĐT phải Đạt Ô 3!")

        # 2. Trường hợp số 000 (không phù hợp với văn bản NĐ 30): Phải bắt lỗi
        p_so.text = ""
        r2 = p_so.add_run("Số: 000/TB-ĐT")
        r2.font.name = "Times New Roman"
        r2.font.size = Pt(13)
        res_zero = val.check_box_3_so_ky_hieu(p_so)
        self.assertFalse(res_zero["passed"], "Số văn bản 000 phải bị từ chối!")
        has_zero_err = any("không thể là số 0 hoặc 000" in e.get("issue", "") for e in res_zero.get("errors", []))
        self.assertTrue(has_zero_err, "Phải bắt lỗi số 000 không phù hợp với văn bản NĐ 30!")
        print("✔ [GĐ 2 - Phương án 3] Hệ thống đã bắt chính xác lỗi số 000 không hợp lệ theo NĐ 30!")

    def test_07_detect_copy_paste_from_outside_into_template(self):
        """[GĐ 2] Bắt gian lận: SV copy toàn bộ nội dung tài liệu bên ngoài dán vào file mẫu"""
        # 1. Đăng ký SV vào danh sách lớp
        self.client.post("/api/teacher/students/add", json={
            "class_code": "KN01",
            "sbd": "01",
            "mssv": "2100009991",
            "name": "Cao Thành Trung"
        })

        # 2. Sinh viên tải file mẫu
        res_gen = self.client.post("/api/template/generate", json={
            "class_code": "KN01",
            "sbd": "01",
            "mssv": "2100009991",
            "name": "Cao Thành Trung",
            "doc_type": "cong_van_de_nghi"
        })
        self.assertEqual(res_gen.status_code, 200)
        filename = res_gen.get_json()["filename"]
        template_file_path = os.path.join(self.test_dir, filename)

        # File phôi đề gốc phải hợp lệ không bị báo gian lận
        res_clean = check_anti_cheat(template_file_path, "01", "2100009991", "Cao Thành Trung")
        self.assertFalse(res_clean["is_fraud"], "Phôi mẫu cấp phát ban đầu phải hợp lệ!")

        # 3. Giả lập hành vi gian lận: Mở file mẫu nhưng xóa hết nội dung và dán văn bản bên ngoài vào
        doc = Document(template_file_path)
        for p in list(doc.paragraphs):
            p._element.getparent().remove(p._element)
        for t in list(doc.tables):
            t._element.getparent().remove(t._element)

        # Dán văn bản tùy tiện từ bên ngoài vào (không có thủy ấn số của hệ thống)
        doc.add_paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        doc.add_paragraph("Độc lập - Tự do - Hạnh phúc")
        doc.add_paragraph("Kính gửi: Sở Công Thương quận Gò Vấp")
        doc.add_paragraph("Hiện nay Công ty Ánh Dương đang vào giai đoạn cao điểm...")
        
        tampered_path = os.path.join(self.test_dir, f"tampered_{filename}")
        doc.save(tampered_path)

        # 4. Kiểm tra qua engine: Phải phát hiện COPY_NOI_DUNG_BEN_NGOAI
        fraud_check = check_anti_cheat(tampered_path, "01", "2100009991", "Cao Thành Trung")
        self.assertTrue(fraud_check["is_fraud"], "Hệ thống phải phát hiện hành vi dán đè văn bản bên ngoài!")
        self.assertEqual(fraud_check["fraud_type"], "COPY_NOI_DUNG_BEN_NGOAI")
        print("✔ [GĐ 2] Đã phát hiện chính xác lỗi COPY_NOI_DUNG_BEN_NGOAI qua check_anti_cheat!")

        # 5. Kiểm tra qua endpoint /api/validate: Phải trả về status FRAUD_DETECTED
        with open(tampered_path, "rb") as f:
            res_val = self.client.post("/api/validate", data={
                "file": (f, filename),
                "class_code": "KN01",
                "sbd": "01",
                "mssv": "2100009991",
                "name": "Cao Thành Trung",
                "doc_type": "cong_van_de_nghi"
            }, content_type="multipart/form-data")

        self.assertEqual(res_val.status_code, 200)
        val_data = res_val.get_json()
        self.assertEqual(val_data.get("status"), "FRAUD_DETECTED")
        self.assertEqual(val_data["fraud_info"]["fraud_type"], "COPY_NOI_DUNG_BEN_NGOAI")
        print("✔ [GĐ 2] Endpoint /api/validate đã chặn nộp bài và cảnh báo gian lận thành công!")

        # Dọn dẹp file tạm
        if os.path.exists(tampered_path):
            os.remove(tampered_path)


    def test_08_detect_box6_cross_student_plagiarism(self):
        """[GĐ 2 - Chống sao chép Ô 6] Bắt gian lận: SV B copy nội dung Thân bài (Ô 6) từ file của SV A dán vào file của mình"""
        # 1. Thêm 2 sinh viên vào danh sách lớp KN01
        self.client.post("/api/teacher/students/add", json={
            "class_code": "KN01", "sbd": "01", "mssv": "2100009991", "name": "Trần Văn Gốc"
        })
        self.client.post("/api/teacher/students/add", json={
            "class_code": "KN01", "sbd": "02", "mssv": "2100009992", "name": "Nguyễn Văn Chép Bài"
        })

        # 2. Sinh viên A tải đề Bài thu hoạch và soạn thảo nội dung Ô 6
        res_a = self.client.post("/api/template/generate", json={
            "class_code": "KN01", "sbd": "01", "mssv": "2100009991", "name": "Trần Văn Gốc", "doc_type": "bai_thu_hoach"
        })
        self.assertEqual(res_a.status_code, 200)
        fn_a = res_a.get_json()["filename"]
        path_a = os.path.join(self.test_dir, fn_a)

        doc_a = Document(path_a)
        # SV A soạn thảo nội dung Ô 6
        body_p1 = "Hiện nay Công ty Ánh Dương đang vào giai đoạn cao điểm sản xuất. Tuy nhiên trong thời gian qua tình trạng cúp điện đột ngột liên tục xảy ra gây ảnh hưởng nghiêm trọng đến tiến độ đơn hàng xuất khẩu."
        body_p2 = "Phòng Hành chính kính đề nghị Sở Công Thương quận Gò Vấp và Công ty Điện Lực Gò Vấp nhanh chóng phối hợp làm rõ nguyên nhân và có biện pháp khắc phục triệt để sự cố trên."
        doc_a.add_paragraph(body_p1)
        doc_a.add_paragraph(body_p2)
        doc_a.save(path_a)

        # SV A tải lên kiểm tra thẩm định -> Lưu vết vào box6_submissions
        with open(path_a, "rb") as f:
            res_val_a = self.client.post("/api/validate", data={
                "file": (f, fn_a),
                "class_code": "KN01", "sbd": "01", "mssv": "2100009991", "name": "Trần Văn Gốc", "doc_type": "bai_thu_hoach"
            }, content_type="multipart/form-data")
        self.assertEqual(res_val_a.status_code, 200)
        self.assertNotEqual(res_val_a.get_json().get("status"), "FRAUD_DETECTED")

        # 3. Sinh viên B tải phôi bài chính chủ của mình (đầy đủ metadata & watermark của SV B)
        res_b = self.client.post("/api/template/generate", json={
            "class_code": "KN01", "sbd": "02", "mssv": "2100009992", "name": "Nguyễn Văn Chép Bài", "doc_type": "bai_thu_hoach"
        })
        self.assertEqual(res_b.status_code, 200)
        fn_b = res_b.get_json()["filename"]
        path_b = os.path.join(self.test_dir, fn_b)

        # 4. Sinh viên B mở file của mình nhưng COPY NỘI DUNG Ô 6 TỪ BÀI CỦA SV A DÁN VÀO
        doc_b = Document(path_b)
        doc_b.add_paragraph(body_p1)
        doc_b.add_paragraph(body_p2)
        doc_b.save(path_b)

        # 5. SV B tải lên thẩm định /api/validate: HỆ THỐNG PHẢI BẮT ĐƯỢC GIAN LẬN COPY Ô 6
        with open(path_b, "rb") as f:
            res_val_b = self.client.post("/api/validate", data={
                "file": (f, fn_b),
                "class_code": "KN01", "sbd": "02", "mssv": "2100009992", "name": "Nguyễn Văn Chép Bài", "doc_type": "bai_thu_hoach"
            }, content_type="multipart/form-data")

        self.assertEqual(res_val_b.status_code, 200)
        data_b = res_val_b.get_json()
        self.assertEqual(data_b.get("status"), "FRAUD_DETECTED", "Hệ thống bắt buộc phải phát hiện hành vi copy Ô 6 giữa 2 file!")
        fraud_info = data_b["fraud_info"]
        self.assertEqual(fraud_info["fraud_type"], "COPY_PASTE_NOI_DUNG_O6")
        self.assertEqual(str(fraud_info["student_b"]["mssv"]), "2100009991", "Phải chỉ đúng đích danh SV A là người bị chép bài!")
        self.assertGreaterEqual(fraud_info["similarity"], 80.0, "Độ tương đồng phải >= 80%!")
        print(f"✔ [GĐ 2 - Chống sao chép Ô 6] Đã phát hiện sao chép Thân bài Ô 6 từ SV A với độ tương đồng {fraud_info['similarity']}%!")

if __name__ == "__main__":
    unittest.main()
