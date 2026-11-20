# BookTracker

A local-first personal library app built with Python, Streamlit, and SQLite.

## Included in this starter
- SQLite database initialization
- Add books and multiple owned formats
- Upload/save cover images
- Upload/save EPUB files
- Cover-grid and table library views
- Book details and EPUB download
- Basic dashboard

## Run
1. Create and activate a Python virtual environment.
2. Install dependencies: `python -m pip install -r requirements.txt`
3. Start: `streamlit run app.py`

The app creates/uses `data/booktracker.db` and saves per-book files under `library/`.
