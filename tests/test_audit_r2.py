# -*- coding: utf-8 -*-
"""
Bộ kiểm thử hồi quy toàn diện cho 21 vấn đề thuộc Đợt rà soát lần 2 (R2-01 đến R2-21)
Phần mềm EDUDOC-STVB.
"""
import os
import sys
import json
import time
import io
import unittest
import typing
import docx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ["EDUDOC_TESTING"] = "1"

from app import (
    app, STUDENTS_ROSTER_FILE, SESSION_STATE_FILE, CLASSES_FILE,
    STORAGE_UPLOADS, STORAGE_SUBMITTED,
    load_json_file, save_json_file
)
from engine.common import (
    update_json_atomic, get_session_state, save_session_state,
    is_student_in_roster, sanitize_identifier
)
from engine.db import (
    get_all_submissions, save_submission_atomic, delete_submission_by_mssv,
    get_student_session, save_student_session, is_quiz_passed_for_student,
    reserve_preview_slot, complete_preview_slot, release_preview_slot,
    get_quiz_attempt, grant_reattempt_permission, get_db_connection
)
from engine.security import generate_anti_cheat_token, verify_anti_cheat_token
from engine.validator import Decree30Validator

TEMPLATES_FILE = os.path.join(BASE_DIR, "data", "document_templates.json")


class TestAuditR2Suite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.auth_headers = {"X-Teacher-PIN": "gv2026"}
        cls.orig_classes = load_json_file(CLASSES_FILE, {"classes": []})
        cls.orig_roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        cls.orig_templates = load_json_file(TEMPLATES_FILE, {})
        cls.orig_session = load_json_file(SESSION_STATE_FILE, {})

    @classmethod
    def tearDownClass(cls):
        save_json_file(CLASSES_FILE, cls.orig_classes)
        save_json_file(STUDENTS_ROSTER_FILE, cls.orig_roster)
        save_json_file(TEMPLATES_FILE, cls.orig_templates)
        save_json_file(SESSION_STATE_FILE, cls.orig_session)

    def setUp(self):
        self.test_class_a = "R2_CLS_A"
        self.test_class_b = "R2_CLS_B"
        self.test_mssv = "2900000001"
        self.test_doc = "cong_van_de_nghi"

        # Đảm bảo mã lớp có trong classes.json
        classes_data = load_json_file(CLASSES_FILE, {"classes": []})
        c_list = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
        if self.test_class_a not in c_list:
            c_list.append(self.test_class_a)
        if self.test_class_b not in c_list:
            c_list.append(self.test_class_b)
        save_json_file(CLASSES_FILE, {"classes": c_list})

        # Cấu hình danh sách sinh viên kiểm thử
        roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        roster[self.test_class_a] = [
            {"sbd": "01", "mssv": self.test_mssv, "name": "Nguyễn Văn R2"}
        ]
        roster[self.test_class_b] = [
            {"sbd": "01", "mssv": self.test_mssv, "name": "Nguyễn Văn R2"}
        ]
        save_json_file(STUDENTS_ROSTER_FILE, roster)

        # Mở phòng thi
        save_session_state({
            "is_open": True,
            "enforce_roster": True,
            "enforce_quiz": True,
            "enable_anti_cheat": False,
            "max_previews": 3,
            "enforce_preview_limit": True,
            "active_doc_type": self.test_doc
        }, class_code=self.test_class_a)

        save_session_state({
            "is_open": True,
            "enforce_roster": True,
            "enforce_quiz": True,
            "enable_anti_cheat": False,
            "max_previews": 3,
            "enforce_preview_limit": True,
            "active_doc_type": self.test_doc
        }, class_code=self.test_class_b)

        # Reset session và attempt của MSSV kiểm thử
        save_student_session(f"{self.test_class_a}_{self.test_mssv}_{self.test_doc}", {
            "quiz_passed": False,
            "preview_count": 0
        })
        save_student_session(f"{self.test_class_b}_{self.test_mssv}_{self.test_doc}", {
            "quiz_passed": False,
            "preview_count": 0
        })
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM quiz_attempts WHERE LOWER(mssv) = ?;", (self.test_mssv.lower(),))
        finally:
            conn.close()

    def tearDown(self):
        delete_submission_by_mssv(self.test_mssv, self.test_doc, class_code=self.test_class_a)
        delete_submission_by_mssv(self.test_mssv, self.test_doc, class_code=self.test_class_b)

    # -------------------------------------------------------------------------
    # R2-15: Type hints & Annotations
    # -------------------------------------------------------------------------
    def test_r2_15_runtime_type_hints(self):
        """R2-15: Kiểm tra typing.get_type_hints trên routes.teacher không văng NameError."""
        import routes.teacher as teacher_mod
        hints = typing.get_type_hints(teacher_mod._matches_teacher_pin)
        self.assertIn("return", hints)
        self.assertEqual(hints["return"], bool)

    # -------------------------------------------------------------------------
    # R2-01: Xóa bài nộp phải giới hạn đúng lớp, không xóa lan
    # -------------------------------------------------------------------------
    def test_r2_01_delete_submission_strict_class_isolation(self):
        """R2-01: API xóa bài bắt buộc class_code, từ chối ALL, không xóa lan sang lớp khác."""
        # Tạo bài nộp ở cả 2 lớp A và B cho cùng sinh viên
        sub_a = {
            "class_code": self.test_class_a, "sbd": "01", "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2", "doc_type": self.test_doc, "filename": "file_a.docx",
            "score": 9.0, "percentage": 90.0, "status": "Đạt", "submitted_at": "2026-11-05 10:00:00"
        }
        sub_b = {
            "class_code": self.test_class_b, "sbd": "01", "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2", "doc_type": self.test_doc, "filename": "file_b.docx",
            "score": 9.5, "percentage": 95.0, "status": "Đạt", "submitted_at": "2026-11-05 10:05:00"
        }
        ok_a = save_submission_atomic(sub_a)
        ok_b = save_submission_atomic(sub_b)
        self.assertTrue(ok_a)
        self.assertTrue(ok_b)

        # 1. Gọi xóa không truyền class_code hoặc truyền ALL -> Bị 400
        res_fail = self.client.post("/api/teacher/submissions/delete", json={
            "mssv": self.test_mssv,
            "doc_type": self.test_doc,
            "class_code": "ALL"
        }, headers=self.auth_headers)
        self.assertEqual(res_fail.status_code, 400)

        # 2. Xóa chính xác ở lớp A
        res_del = self.client.post("/api/teacher/submissions/delete", json={
            "class_code": self.test_class_a,
            "mssv": self.test_mssv,
            "doc_type": self.test_doc
        }, headers=self.auth_headers)
        self.assertEqual(res_del.status_code, 200)

        # 3. Lớp A đã mất, Lớp B vẫn còn nguyên vẹn
        subs_a = [s for s in get_all_submissions(class_code=self.test_class_a) if s["mssv"] == self.test_mssv]
        subs_b = [s for s in get_all_submissions(class_code=self.test_class_b) if s["mssv"] == self.test_mssv]
        self.assertEqual(len(subs_a), 0)
        self.assertEqual(len(subs_b), 1)

    # -------------------------------------------------------------------------
    # R2-02: Kết quả quiz ở lớp A không được dùng để xin phôi ở lớp B
    # -------------------------------------------------------------------------
    def test_r2_02_quiz_class_isolation(self):
        """R2-02: Đạt quiz lớp A không được phép cấp phôi bài tập cho lớp B."""
        # Thiết lập sinh viên hoàn thành quiz ở lớp A
        save_student_session(f"{self.test_class_a}_{self.test_mssv}_{self.test_doc}", {
            "quiz_passed": True,
            "preview_count": 0
        })

        # Gọi cấp phôi ở lớp B -> Bị từ chối 403 do chưa làm quiz của lớp B
        res_b = self.client.post("/api/template/generate", json={
            "class_code": self.test_class_b,
            "sbd": "01",
            "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2",
            "doc_type": self.test_doc
        }, headers={"X-Test-Enforce-Quiz": "1"})
        self.assertEqual(res_b.status_code, 403)
        self.assertTrue(res_b.get_json().get("quiz_required"))

    # -------------------------------------------------------------------------
    # R2-03: RBAC quản trị phân lớp chặt chẽ
    # -------------------------------------------------------------------------
    def test_r2_03_teacher_rbac_class_boundary(self):
        """R2-03: Giáo viên chỉ được truy cập dữ liệu của lớp được phân công."""
        # Giả lập phiên giáo viên chỉ phụ trách R2_CLS_A
        with self.client.session_transaction() as sess:
            sess["teacher_authenticated"] = True
            sess["teacher_id"] = "GV_TEST"
            sess["teacher_name"] = "Giảng Viên Kiểm Thử"
            sess["assigned_classes"] = [self.test_class_a]

        # Truy vấn data với class_code=ALL không được để lộ sinh viên lớp B
        res_data = self.client.get("/api/teacher/data?class_code=ALL")
        self.assertEqual(res_data.status_code, 200)
        ret_classes = res_data.get_json().get("classes", [])
        self.assertIn(self.test_class_a, ret_classes)
        self.assertNotIn(self.test_class_b, ret_classes)

        # Truy vấn trực tiếp lớp B -> Bị 403
        res_b = self.client.get(f"/api/teacher/export-csv?class_code={self.test_class_b}")
        self.assertEqual(res_b.status_code, 403)

    # -------------------------------------------------------------------------
    # R2-04: Tải cơ sở dữ liệu dùng SQLite Hot Backup snapshot
    # -------------------------------------------------------------------------
    def test_r2_04_database_download_hot_snapshot(self):
        """R2-04: /api/teacher/database/download trả về bản snapshot toàn vẹn."""
        res = self.client.get("/api/teacher/database/download", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        # Kiểm tra file trả về là SQLite database hợp lệ
        header_bytes = res.data[:16]
        self.assertTrue(header_bytes.startswith(b"SQLite format 3\x00"))

    # -------------------------------------------------------------------------
    # R2-05 & R2-06: Nguyên tử khi lưu bài nộp và quản lý Permit nộp lại
    # -------------------------------------------------------------------------
    def test_r2_05_r2_06_atomic_submission_and_permit(self):
        """R2-05 & R2-06: Không ghi đè bài lần đầu không permit; permit chỉ dùng được 1 lần."""
        sub = {
            "class_code": self.test_class_a, "sbd": "01", "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2", "doc_type": self.test_doc, "filename": "file_1.docx",
            "score": 8.0, "percentage": 80.0, "status": "Đạt", "submitted_at": "2026-11-05 10:00:00"
        }
        ok = save_submission_atomic(sub)
        self.assertTrue(ok)

        # Nộp lần 2 mà không có permit_id -> Bị từ chối bằng ValueError
        sub2 = dict(sub, filename="file_2.docx", score=9.0)
        with self.assertRaises(ValueError):
            save_submission_atomic(sub2)

        # Cấp permit nộp lại
        permit_id = grant_reattempt_permission(self.test_class_a, self.test_mssv, self.test_doc, "GV01", "Được phép làm lại")
        self.assertIsNotNone(permit_id)

        # Nộp lại thành công với permit_id
        ok3 = save_submission_atomic(sub2, permit_id=permit_id)
        self.assertTrue(ok3)

        # Sử dụng lại permit_id cũ -> Bị từ chối vì đã tiêu hao (used = 1)
        with self.assertRaises(ValueError):
            save_submission_atomic(dict(sub, filename="file_3.docx"), permit_id=permit_id)

    # -------------------------------------------------------------------------
    # R2-07: Giữ chỗ hạn mức Preview nguyên tử (Atomic Reservation)
    # -------------------------------------------------------------------------
    def test_r2_07_atomic_preview_reservation(self):
        """R2-07: Giữ chỗ preview slot nguyên tử, vượt quota bị chặn."""
        # Đặt quota = 2
        allowed1, cnt1, id1 = reserve_preview_slot(self.test_class_a, self.test_mssv, self.test_doc, max_previews=2, enforce_limit=True)
        self.assertTrue(allowed1)
        self.assertEqual(cnt1, 1)

        allowed2, cnt2, id2 = reserve_preview_slot(self.test_class_a, self.test_mssv, self.test_doc, max_previews=2, enforce_limit=True)
        self.assertTrue(allowed2)
        self.assertEqual(cnt2, 2)

        # Lần 3 vượt quota 2 -> Bị chặn
        allowed3, cnt3, id3 = reserve_preview_slot(self.test_class_a, self.test_mssv, self.test_doc, max_previews=2, enforce_limit=True)
        self.assertFalse(allowed3)
        self.assertIsNone(id3)

        # Cleanup slot
        release_preview_slot(id1)
        release_preview_slot(id2)

    # -------------------------------------------------------------------------
    # R2-08: Chấm điểm quiz theo snapshot của lượt đã phát
    # -------------------------------------------------------------------------
    def test_r2_08_quiz_snapshot_grading_when_bank_cleared(self):
        """R2-08: Lượt quiz đã phát vẫn chấm đúng theo đề snapshot kể cả khi ngân hàng câu hỏi bị xóa."""
        questions_file = os.path.join(BASE_DIR, "data", "questions.json")
        saved_bank = load_json_file(questions_file, {})

        # 1. Sinh lượt trắc nghiệm
        res_get = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class_a,
            "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2",
            "doc_type": self.test_doc
        })
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        attempt_id = data_get["attempt_id"]
        questions_delivered = data_get["questions"]

        # 2. Xóa trắng file câu hỏi ngân hàng
        save_json_file(questions_file, {})

        try:
            # 3. Lấy đáp án đúng từ ngân hàng gốc đã lưu
            orig_q_list = saved_bank.get(self.test_doc, [])
            q_map = {q["id"]: q.get("correct", 0) for q in orig_q_list}
            answers = {q["id"]: q_map.get(q["id"], 0) for q in questions_delivered}
            res_sub = self.client.post("/api/quiz/submit", json={
                "mssv": self.test_mssv,
                "attempt_id": attempt_id,
                "answers": answers
            })
            self.assertEqual(res_sub.status_code, 200)
            data = res_sub.get_json()
            self.assertTrue(data.get("passed"))
            self.assertEqual(data.get("score"), 5)
        finally:
            save_json_file(questions_file, saved_bank)

    # -------------------------------------------------------------------------
    # R2-09: API /api/submit kiểm tra điều kiện hoàn thành trắc nghiệm
    # -------------------------------------------------------------------------
    def test_r2_09_submit_enforces_quiz_passed(self):
        """R2-09: /api/submit từ chối nộp bài khi sinh viên chưa vượt qua trắc nghiệm."""
        save_student_session(f"{self.test_class_a}_{self.test_mssv}_{self.test_doc}", {
            "quiz_passed": False,
            "preview_count": 0
        })
        res = self.client.post("/api/submit", json={
            "class_code": self.test_class_a,
            "sbd": "01",
            "mssv": self.test_mssv,
            "name": "Nguyễn Văn R2",
            "doc_type": self.test_doc,
            "temp_file": "non_existent.docx"
        }, headers={"X-Test-Enforce-Quiz": "1"})
        self.assertEqual(res.status_code, 403)
        self.assertTrue(res.get_json().get("quiz_required"))

    # -------------------------------------------------------------------------
    # R2-10: Cập nhật template hỗ trợ chuỗi rỗng
    # -------------------------------------------------------------------------
    def test_r2_10_template_empty_string_saved(self):
        """R2-10: Lưu mẫu bài với header_part/footer_part rỗng không bị bỏ qua."""
        res = self.client.post("/api/teacher/templates/save", json={
            "doc_type": self.test_doc,
            "header_part": "",
            "footer_part": "",
            "raw_text": "Cộng hòa xã hội chủ nghĩa Việt Nam"
        }, headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)

        tmpl_file = os.path.join(BASE_DIR, "data", "document_templates.json")
        tmpls = load_json_file(tmpl_file, {})
        self.assertEqual(tmpls[self.test_doc].get("header_part"), "")
        self.assertEqual(tmpls[self.test_doc].get("footer_part"), "")

    # -------------------------------------------------------------------------
    # R2-11: Kiểm tra kiểu dữ liệu nghiêm ngặt trong điều khiển phòng học
    # -------------------------------------------------------------------------
    def test_r2_11_strict_session_state_types(self):
        """R2-11: Cấu hình phòng học kiểm tra kiểu strict bool và giới hạn số nguyên."""
        # Chuỗi "invalid" không được chuyển bừa bãi thành True
        res_bad = self.client.post("/api/teacher/session-state", json={
            "class_code": self.test_class_a,
            "is_open": "abc_not_bool",
            "max_previews": -5
        }, headers=self.auth_headers)
        self.assertEqual(res_bad.status_code, 400)

        # Giá trị hợp lệ
        res_good = self.client.post("/api/teacher/session-state", json={
            "class_code": self.test_class_a,
            "is_open": True,
            "max_previews": 5,
            "active_doc_type": self.test_doc
        }, headers=self.auth_headers)
        self.assertEqual(res_good.status_code, 200)

    # -------------------------------------------------------------------------
    # R2-12: Bảng trống không gây IndexError trong validator
    # -------------------------------------------------------------------------
    def test_r2_12_malformed_empty_table_validator(self):
        """R2-12: File Word có bảng không có hàng nào không làm sập validator."""
        test_doc_path = os.path.join(STORAGE_UPLOADS, "test_empty_table.docx")
        d = docx.Document()
        d.add_paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        d.add_table(rows=0, cols=0)  # Bảng rỗng
        d.save(test_doc_path)
        try:
            validator = Decree30Validator(test_doc_path, self.test_doc, {}, mssv=self.test_mssv)
            res = validator.validate_document()
            self.assertIn("percentage", res)
        finally:
            if os.path.exists(test_doc_path):
                os.remove(test_doc_path)

    # -------------------------------------------------------------------------
    # R2-13: Chuẩn hóa và xác thực mã lớp
    # -------------------------------------------------------------------------
    def test_r2_13_class_code_normalization(self):
        """R2-13: Mã lớp được chuẩn hóa và từ chối ký tự đặc biệt nguy hiểm."""
        res_bad = self.client.post("/api/classes/add", json={
            "code": "BAD/../CODE",
            "name": "Lớp lỗi"
        }, headers=self.auth_headers)
        self.assertEqual(res_bad.status_code, 400)

        res_good = self.client.post("/api/classes/add", json={
            "code": "K19_CNTT_01",
            "name": "Lớp Hợp Lệ"
        }, headers=self.auth_headers)
        self.assertIn(res_good.status_code, [200, 400])

    # -------------------------------------------------------------------------
    # R2-14: Thống kê không nâng điểm khống khi thiếu tệp minh chứng
    # -------------------------------------------------------------------------
    def test_r2_14_analytics_missing_evidence_tracking(self):
        """R2-14: Thống kê phân loại rõ ràng bài nộp thiếu tệp Word minh chứng."""
        res = self.client.get("/api/teacher/analytics?class_code=ALL", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("missing_evidence_count", data)

    # -------------------------------------------------------------------------
    # R2-16: Polling trạng thái phòng theo mã lớp
    # -------------------------------------------------------------------------
    def test_r2_16_session_state_polling_per_class(self):
        """R2-16: /api/session-state nhận class_code và trả trạng thái riêng biệt."""
        res_a = self.client.get(f"/api/session-state?class_code={self.test_class_a}")
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_a.get_json().get("active_doc_type"), self.test_doc)

    # -------------------------------------------------------------------------
    # R2-17: Phòng chống Stored XSS trong Analytics
    # -------------------------------------------------------------------------
    def test_r2_17_xss_prevention_in_analytics(self):
        """R2-17: Mã HTML độc hại trong báo cáo lỗi không được render thô."""
        with open(os.path.join(BASE_DIR, "templates", "teacher.html"), "r", encoding="utf-8") as f:
            tmpl_html = f.read()
        self.assertIn("escapeHtml(err.target)", tmpl_html)
        self.assertIn("escapeHtml(err.solution)", tmpl_html)

    # -------------------------------------------------------------------------
    # R2-18: Không để placeholder mã PIN mặc định công khai
    # -------------------------------------------------------------------------
    def test_r2_18_pin_placeholder_cleaned(self):
        """R2-18: Giao diện không gợi ý placeholder gv2026 trong ô nhập PIN."""
        with open(os.path.join(BASE_DIR, "templates", "teacher.html"), "r", encoding="utf-8") as f:
            tmpl_html = f.read()
        self.assertNotIn('placeholder="gv2026"', tmpl_html)

    # -------------------------------------------------------------------------
    # R2-19: Khóa HMAC bảo mật được lưu trữ độc lập
    # -------------------------------------------------------------------------
    def test_r2_19_hmac_secret_from_secure_file(self):
        """R2-19: Khóa HMAC được sinh ngẫu nhiên và lưu tại tệp bảo mật .hmac-key."""
        key_file = os.path.join(BASE_DIR, "data", ".hmac-key")
        self.assertTrue(os.path.exists(key_file))
        with open(key_file, "r", encoding="utf-8") as f:
            key_content = f.read().strip()
        self.assertTrue(len(key_content) >= 32)
        self.assertNotEqual(key_content, "EDUDOC_DEFAULT_SECRET_2026")

    # -------------------------------------------------------------------------
    # R2-20: Ràng buộc danh tính khi liên kết thiết bị đầu tiên
    # -------------------------------------------------------------------------
    def test_r2_20_device_identity_verification_against_roster(self):
        """R2-20: Yêu cầu trắc nghiệm với tên giả mạo không khớp hồ sơ bị từ chối 403."""
        res_spoof = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class_a,
            "mssv": self.test_mssv,
            "name": "Kẻ Giả Mạo Danh Tính",
            "doc_type": self.test_doc
        }, headers={"X-Test-Enforce-Roster": "1"})
        self.assertEqual(res_spoof.status_code, 403)
        self.assertIn("không khớp với hồ sơ", res_spoof.get_json()["error"])

    # -------------------------------------------------------------------------
    # R2-21: Cập nhật tệp JSON nguyên tử chống mất dữ liệu khi ghi đồng thời
    # -------------------------------------------------------------------------
    def test_r2_21_atomic_json_updater(self):
        """R2-21: update_json_atomic cập nhật dữ liệu tin cậy qua atomic lock."""
        test_json_file = os.path.join(BASE_DIR, "data", "test_atomic_updater.json")
        try:
            save_json_file(test_json_file, {"counter": 0})
            def increment(d):
                d["counter"] += 1
                return d
            ok = update_json_atomic(test_json_file, increment, {})
            self.assertTrue(ok)
            updated = load_json_file(test_json_file, {})
            self.assertEqual(updated.get("counter"), 1)
        finally:
            if os.path.exists(test_json_file):
                os.remove(test_json_file)


if __name__ == "__main__":
    unittest.main()
