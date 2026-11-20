from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "booktracker.db"


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subtitle TEXT,
            author TEXT NOT NULL,
            series TEXT,
            series_number REAL,
            isbn TEXT,
            publisher TEXT,
            publication_year INTEGER,
            genre TEXT,
            pages INTEGER,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'Want to Read',
            current_page INTEGER NOT NULL DEFAULT 0,
            rating INTEGER CHECK (rating BETWEEN 1 AND 5),
            favorite INTEGER NOT NULL DEFAULT 0,
            date_acquired TEXT,
            date_started TEXT,
            date_finished TEXT,
            purchase_price REAL,
            purchased_from TEXT,
            review TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS book_formats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            format TEXT NOT NULL,
            UNIQUE(book_id, format),
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS book_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            date_added TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
        );
        """)


def add_book(book, formats):
    fields = [
        "title", "subtitle", "author", "series", "series_number", "isbn",
        "publisher", "publication_year", "genre", "pages", "description",
        "status", "current_page", "rating", "favorite", "date_acquired",
        "date_started", "date_finished", "purchase_price", "purchased_from",
        "review", "notes"
    ]
    values = [book.get(f) for f in fields]
    placeholders = ",".join("?" for _ in fields)
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO books ({','.join(fields)}) VALUES ({placeholders})", values
        )
        book_id = cur.lastrowid
        conn.executemany(
            "INSERT OR IGNORE INTO book_formats (book_id, format) VALUES (?, ?)",
            [(book_id, f) for f in formats],
        )
    return book_id


def add_book_file(book_id, file_type, file_name, file_path, file_size):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO book_files (book_id,file_type,file_name,file_path,file_size) VALUES (?,?,?,?,?)",
            (book_id, file_type, file_name, file_path, file_size),
        )


def list_books():
    with get_connection() as conn:
        return conn.execute("""
            SELECT b.*,
                   GROUP_CONCAT(DISTINCT bf.format) AS formats,
                   MAX(CASE WHEN x.file_type='cover' THEN x.file_path END) AS cover_path,
                   MAX(CASE WHEN x.file_type='epub' THEN x.file_path END) AS epub_path
            FROM books b
            LEFT JOIN book_formats bf ON bf.book_id=b.id
            LEFT JOIN book_files x ON x.book_id=b.id
            GROUP BY b.id
            ORDER BY b.title COLLATE NOCASE
        """).fetchall()


def get_book(book_id):
    with get_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not book:
            return None, [], []
        formats = [r["format"] for r in conn.execute("SELECT format FROM book_formats WHERE book_id=? ORDER BY format", (book_id,))]
        files = conn.execute("SELECT * FROM book_files WHERE book_id=? ORDER BY date_added", (book_id,)).fetchall()
        return book, formats, files


def find_duplicates(title, author, isbn=None, exclude_book_id=None):
    title = (title or "").strip()
    author = (author or "").strip()
    isbn = (isbn or "").strip().replace("-", "").replace(" ", "")
    sql = """
        SELECT * FROM books
        WHERE (LOWER(TRIM(title)) = LOWER(TRIM(?)) AND LOWER(TRIM(author)) = LOWER(TRIM(?)))
    """
    params = [title, author]
    if isbn:
        sql += " OR REPLACE(REPLACE(LOWER(COALESCE(isbn,'')), '-', ''), ' ', '') = LOWER(?)"
        params.append(isbn)
    if exclude_book_id is not None:
        sql = f"SELECT * FROM ({sql}) WHERE id <> ?"
        params.append(exclude_book_id)
    with get_connection() as conn:
        return conn.execute(sql, params).fetchall()


def update_book(book_id, book, formats):
    fields = [
        "title", "subtitle", "author", "series", "series_number", "isbn",
        "publisher", "publication_year", "genre", "pages", "description",
        "status", "current_page", "rating", "favorite", "date_acquired",
        "date_started", "date_finished", "purchase_price", "purchased_from",
        "review", "notes"
    ]
    assignments = ", ".join(f"{f}=?" for f in fields)
    values = [book.get(f) for f in fields] + [book_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE books SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE id=?", values)
        conn.execute("DELETE FROM book_formats WHERE book_id=?", (book_id,))
        conn.executemany("INSERT OR IGNORE INTO book_formats (book_id, format) VALUES (?, ?)", [(book_id, f) for f in formats])


def delete_book(book_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM books WHERE id=?", (book_id,))
