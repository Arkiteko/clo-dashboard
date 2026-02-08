import hashlib
import pandas as pd
from pathlib import Path
import json
from datetime import datetime

def compute_file_hash(filepath: Path) -> str:
    """MD5 hash of file content for change detection."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def ingest_file(uploaded_file, destination_dir: Path, source_name: str) -> Path:
    """
    Saves uploaded file to raw layer with timestamp name.
    Filename format: YYYYMMDD_HHMMSS_WarehouseName.ext
    The source_name (warehouse) is the only identifier after the timestamp
    to keep parsing simple and consistent.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(uploaded_file.name).suffix

    filename = f"{timestamp}_{source_name}{ext}"
    dest_path = destination_dir / filename

    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return dest_path

def load_excel_safe(filepath: Path) -> pd.DataFrame:
    try:
        return pd.read_excel(filepath)
    except Exception as e:
        return pd.DataFrame() # Or raise
