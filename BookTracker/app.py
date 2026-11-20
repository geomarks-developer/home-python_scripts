import streamlit as st
from database import init_db
from storage import ensure_storage

st.set_page_config(page_title="BookTracker", page_icon="📚", layout="wide")
init_db()
ensure_storage()

pages = {
    "Library": [
        st.Page("views/home.py", title="Home", icon="🏠", default=True),
        st.Page("views/library.py", title="My Library", icon="📚"),
        st.Page("views/add_book.py", title="Add Book", icon="➕"),
        st.Page("views/book_details.py", title="Book Details", icon="📖"),
        st.Page("views/edit_book.py", title="Edit Book", icon="✏️"),
    ],
    "Insights": [
        st.Page("views/dashboard.py", title="Dashboard", icon="📊"),
        st.Page("views/settings.py", title="Settings", icon="⚙️"),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
