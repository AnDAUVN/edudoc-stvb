import sqlite3
import time
from pathlib import Path

# Cố định đường dẫn tuyệt đối đến thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "edudoc.db"

_LAST_BACKUP = 0

def get_db_connection(db_path=None):
    if db_path is None:
        db_path = DB_PATH
    else:
        db_path = Path(db_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Cấu hình WAL mode và timeout 30s chống lỗi Database is locked
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def auto_backup_if_needed(backup_dir=None):
    global _LAST_BACKUP
    now = time.time()
    # Giới hạn sao lưu tối đa 30 phút một lần
    if now - _LAST_BACKUP < 1800:
        return None
    _LAST_BACKUP = now

    b_dir = Path(backup_dir) if backup_dir else (DATA_DIR / "backups")
    b_dir.mkdir(parents=True, exist_ok=True)
    dest = b_dir / f"edudoc_auto_{int(now)}.db"

    try:
        with sqlite3.connect(str(DB_PATH)) as src, sqlite3.connect(str(dest)) as dst:
            src.backup(dst)
        # Tự động dọn dẹp, chỉ giữ tối đa 10 bản sao lưu
        old_files = sorted(b_dir.glob("edudoc_auto_*.db"), key=lambda p: p.stat().st_mtime)
        for f in old_files[:-10]:
            f.unlink(missing_ok=True)
        return dest
    except Exception as e:
        print(f"[CẢNH BÁO BACKUP]: {e}")
        return None