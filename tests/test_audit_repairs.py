"""Regression tests for production boundaries; use only temporary test data."""
import csv
from contextlib import closing
import datetime
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from engine import common, db
from routes import student
import run_app


class ProductionBoundaries(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"EDUDOC_TESTING": ""})
        self.env.start()
        self.app = create_app()
        self.app.testing = False
        self.client = self.app.test_client()

    def tearDown(self):
        self.env.stop()

    def test_untrusted_header_cannot_disable_anti_cheat(self):
        with patch.object(common, "get_session_state", return_value={"enable_anti_cheat": True}):
            with self.app.test_request_context(headers={"X-Test-Disable-Anti-Cheat": "1"}):
                self.assertTrue(common.is_anti_cheat_enabled())

    def test_user_agent_does_not_enable_test_policy(self):
        with patch.object(common, "get_session_state", return_value={"enable_anti_cheat": False}):
            with self.app.test_request_context(headers={"User-Agent": "Werkzeug/3.1"}):
                self.assertFalse(common.is_anti_cheat_enabled())

    def test_user_agent_cannot_bypass_bound_device(self):
        with patch.object(student, "get_device_binding", return_value={"device_id": "original"}):
            with self.app.test_request_context(headers={"User-Agent": "Werkzeug/3.1"}):
                self.assertFalse(student.check_client_device("AUDIT", "S01")["valid"])

    def test_quiz_requires_attempt_even_with_spoofed_user_agent(self):
        with patch.object(student, "is_session_open", return_value=True), \
             patch.object(student, "get_session_state", return_value={"enforce_roster": False}), \
             patch.object(student, "check_client_device", return_value={"valid": True}):
            response = self.client.post("/api/quiz/submit", json={
                "class_code": "AUDIT", "mssv": "S01", "doc_type": "cong_van_de_nghi", "answers": {}
            }, headers={"User-Agent": "Werkzeug/3.1"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("attempt_id", response.get_json()["error"])

    def test_public_session_signing_key_cannot_authenticate(self):
        from flask.sessions import SecureCookieSessionInterface
        forged_app = create_app()
        forged_app.secret_key = "edudoc_secret_key_2026_nttu_secure_wal"
        serializer = SecureCookieSessionInterface().get_signing_serializer(forged_app)
        self.client.set_cookie("session", serializer.dumps({"is_teacher_auth": True}))
        self.assertEqual(self.client.get("/api/teacher/data").status_code, 401)

    def test_public_default_pin_is_not_accepted(self):
        with patch.dict(os.environ):
            os.environ.pop("TEACHER_PIN", None)
            client = create_app().test_client()
            self.assertEqual(client.post("/api/teacher/auth", json={"pin": "gv2026"}).status_code, 401)

    def test_non_object_json_is_client_error(self):
        for payload in [[1], "text", 7, True]:
            with self.subTest(payload=payload):
                response = self.client.post("/api/teacher/auth", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.get_json(), dict)

    def test_csv_formula_is_exported_as_text(self):
        with self.client.session_transaction() as sess:
            sess["is_teacher_auth"] = True
        with patch("routes.teacher.get_all_submissions", return_value=[{
            "mssv": "S01", "name": "=1+1", "class_code": "AUDIT", "sbd": "+42"
        }]):
            response = self.client.get("/api/teacher/export-csv")
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertEqual(rows[-1][4], "'=1+1")
        self.assertEqual(rows[-1][2], "'+42")

    def test_busy_port_does_not_kill_other_processes(self):
        with patch.object(run_app.socket, "socket") as sock, \
             patch.object(run_app.subprocess, "run") as command, \
             patch.object(run_app.subprocess, "check_output") as output:
            sock.return_value.__enter__.return_value.bind.side_effect = OSError("busy")
            with self.assertRaises(RuntimeError):
                run_app.cleanup_stale_processes(5000)
            command.assert_not_called()
            output.assert_not_called()

    def test_template_generation_does_not_overwrite_another_class(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            def write_template(**kwargs):
                Path(kwargs["output_path"]).write_text(kwargs["class_code"], encoding="utf-8")
            with patch.object(student, "STORAGE_TEMPLATES", folder), \
                 patch.object(student, "is_session_open", return_value=True), \
                 patch.object(student, "is_student_in_roster", return_value=True), \
                 patch.object(student, "check_client_device", return_value={"valid": True}), \
                 patch.object(student, "get_session_state", return_value={"enforce_quiz": False}), \
                 patch.object(student, "get_student_session", return_value=None), \
                 patch.object(student, "save_student_session"), \
                 patch.object(student, "create_student_raw_template", side_effect=write_template):
                identity = {"sbd": "01", "mssv": "S01", "name": "Test Student", "doc_type": "cong_van_de_nghi"}
                first = self.client.post("/api/template/generate", json={**identity, "class_code": "AUDIT_A"})
                second = self.client.post("/api/template/generate", json={**identity, "class_code": "AUDIT_B"})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            first_name = first.get_json()["filename"]
            self.assertNotEqual(first_name, second.get_json()["filename"])
            self.assertEqual((Path(folder) / first_name).read_text(encoding="utf-8"), "AUDIT_A")


class BackupSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.db_file = self.root / "live.db"
        with closing(sqlite3.connect(self.db_file)) as conn, conn:
            conn.execute("CREATE TABLE submissions(value TEXT)")
            conn.execute("CREATE TABLE student_sessions(value TEXT)")
            conn.execute("CREATE TABLE session_state(value TEXT)")
            conn.execute("INSERT INTO submissions VALUES ('before')")
        self.path_patch = patch.object(db, "DB_PATH", str(self.db_file))
        self.path_patch.start()
        self.data_patch = patch.object(db, "DATA_DIR", str(self.root))
        self.data_patch.start()

    def tearDown(self):
        self.data_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def value(self, path):
        with closing(sqlite3.connect(path)) as conn, conn:
            return conn.execute("SELECT value FROM submissions").fetchone()[0]

    def test_backups_in_same_second_are_distinct(self):
        with patch.object(db.datetime, "datetime", wraps=datetime.datetime) as clock:
            clock.now.return_value = datetime.datetime(2026, 11, 5, 12, 0, 0)
            first = db.backup_database(str(self.root / "backups"))
            with closing(sqlite3.connect(self.db_file)) as conn, conn:
                conn.execute("UPDATE submissions SET value='after'")
            second = db.backup_database(str(self.root / "backups"))
        self.assertNotEqual(first, second)
        self.assertEqual(self.value(first), "before")

    def test_restore_creates_rollback_snapshot(self):
        backup = db.backup_database(str(self.root / "backups"))
        with closing(sqlite3.connect(self.db_file)) as conn, conn:
            conn.execute("UPDATE submissions SET value='after'")
        db.restore_database(backup)
        snapshots = list((self.root / "backups").glob("*.db"))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(self.value(self.db_file), "before")
        self.assertIn("after", [self.value(p) for p in snapshots])

    def test_restore_rejects_unrelated_sqlite_file(self):
        unrelated = self.root / "unrelated.db"
        with closing(sqlite3.connect(unrelated)) as conn, conn:
            conn.execute("CREATE TABLE unrelated(value TEXT)")
        with self.assertRaises(ValueError):
            db.restore_database(str(unrelated))
        self.assertEqual(self.value(self.db_file), "before")

    def test_deleted_submission_does_not_return_after_restart(self):
        database = str(self.root / "migration.db")
        legacy = self.root / "submissions.json"
        legacy.write_text(json.dumps([{"class_code": "AUDIT", "mssv": "S01",
                                      "name": "Synthetic Student", "doc_type": "cv"}]), encoding="utf-8")
        with patch.object(db, "SUBMISSIONS_JSON", str(legacy)), \
             patch.object(db, "FRAUD_LOGS_JSON", str(self.root / "missing-fraud.json")), \
             patch.object(db, "STUDENT_SESSIONS_JSON", str(self.root / "missing-sessions.json")), \
             patch.object(db, "SESSION_STATE_JSON", str(self.root / "missing-state.json")), \
             patch.object(db, "TEACHERS_JSON", str(self.root / "missing-teachers.json")), \
             patch.object(db, "_sync_to_json_cache"):
            db.init_db(database)
            self.assertEqual(len(db.get_all_submissions(db_path=database)), 1)
            db.delete_submission_by_mssv("S01", "cv", "AUDIT", db_path=database)
            db.init_db(database)
            self.assertEqual(db.get_all_submissions(db_path=database), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
