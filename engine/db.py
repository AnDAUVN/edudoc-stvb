import sqlite3
import time
from pathlib import Path

_LAST_BACKUP_TIME = 0
BACKUP_COOLDOWN_SECONDS = 900  # Chỉ cho phép backup tối đa 15 phút / lần

def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = str(Path(__file__).parent.parent / "data" / "edudoc.db")
        
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Kích hoạt WAL Mode và tăng thời gian chờ lên 30 giây
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def safe_backup_db(source_db_path: str, backup_dir: str, force: bool = False):
    global _LAST_BACKUP_TIME
    now = time.time()
    if not force and (now - _LAST_BACKUP_TIME) < BACKUP_COOLDOWN_SECONDS:
        return None

    _LAST_BACKUP_TIME = now
    b_dir = Path(backup_dir)
    b_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = b_dir / f"edudoc_backup_{int(now)}.db"
    try:
        # Sử dụng API Online Backup an toàn cho WAL mode
        with sqlite3.connect(source_db_path, timeout=30.0) as src_conn:
            with sqlite3.connect(str(backup_path)) as dst_conn:
                src_conn.backup(dst_conn, pages=100, sleep=0.05)
                
        # Tự động dọn dẹp, chỉ giữ lại 10 bản sao lưu mới nhất
        backups = sorted(b_dir.glob("edudoc_backup_*.db"), key=lambda p: p.stat().st_mtime)
        for old_bkp in backups[:-10]:
            old_bkp.unlink(missing_ok=True)
        return backup_path
    except Exception as e:
        print(f"[ERROR] Backup thất bại: {e}")
        return None