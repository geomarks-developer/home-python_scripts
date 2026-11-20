import streamlit as st
from database import list_books

st.title("📚 BookTracker")
st.caption("Your personal library, reading history, covers, and ebooks in one place.")
books = list_books()

c1, c2, c3 = st.columns(3)
c1.metric("Books", len(books))
c2.metric("Currently Reading", sum(1 for b in books if b["status"] == "Reading"))
c3.metric("Finished", sum(1 for b in books if b["status"] == "Finished"))

st.subheader("Getting started")
st.write("Add your first book, including an optional cover image and EPUB file. Then browse it from My Library.")
