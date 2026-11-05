"""Private installation credentials, kept outside source and database backups."""
import os
from pathlib import Path
import secrets
import time

from engine.common import DATA_DIR


def installation_secret(env_name, filename):
    configured = os.environ.get(env_name, "").strip()
    if configured:
        return configured
    path = Path(DATA_DIR) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(32))
            stream.flush()
            os.fsync(stream.fileno())
    # Another worker may have created the file and still be writing its value.
    for _ in range(50):
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
        time.sleep(0.02)
    raise RuntimeError(f"Credential file is empty: {path.name}")
