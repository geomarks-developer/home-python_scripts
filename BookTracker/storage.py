from pathlib import Path
import shutil

BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / "library"


def ensure_storage():
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def book_dir(book_id):
    path = LIBRARY_DIR / f"{int(book_id):06d}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_file(book_id, uploaded_file, kind):
    if uploaded_file is None:
        return None
    suffix = Path(uploaded_file.name).suffix.lower()
    filename = f"cover{suffix}" if kind == "cover" else f"book{suffix}"
    target = book_dir(book_id) / filename
    with target.open("wb") as f:
        shutil.copyfileobj(uploaded_file, f)
    return target
