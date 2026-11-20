import streamlit as st
from database import list_books

st.title("📊 Dashboard")
books = list_books()
if not books:
    st.info("Dashboard statistics will appear after you add books.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Books", len(books))
c2.metric("Reading", sum(b["status"] == "Reading" for b in books))
c3.metric("Finished", sum(b["status"] == "Finished" for b in books))
c4.metric("Favorites", sum(bool(b["favorite"]) for b in books))
st.caption("More charts and reading statistics will be added after the core library workflow is complete.")
