import shutil
from pathlib import Path

for pattern in ("data/raw/*.csv", "data/processed/*.parquet", "data/exports/*.csv", "data/warehouse/*.duckdb"):
    for path in Path(".").glob(pattern):
        if path.is_file():
            path.unlink()

for path in Path("artifacts").glob("*") if Path("artifacts").exists() else []:
    shutil.rmtree(path) if path.is_dir() else path.unlink()
