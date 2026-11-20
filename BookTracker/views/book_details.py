from pathlib import Path
import streamlit as st
from database import get_book, list_books

st.title("📖 Book Details")
books = list_books()
if not books:
    st.info("Add a book first.")
    st.stop()

ids = [b["id"] for b in books]
selected = st.session_state.get("selected_book_id", ids[0])
if selected not in ids:
    selected = ids[0]
book_id = st.selectbox("Book", ids, index=ids.index(selected), format_func=lambda x: next(f"{b['title']} — {b['author']}" for b in books if b["id"] == x))
st.session_state["selected_book_id"] = book_id
book, formats, files = get_book(book_id)
cover = next((f for f in files if f["file_type"] == "cover" and Path(f["file_path"]).exists()), None)
epub = next((f for f in files if f["file_type"] == "epub" and Path(f["file_path"]).exists()), None)

left, right = st.columns([1, 2])
with left:
    if cover:
        st.image(cover["file_path"], width="stretch")
    else:
        st.info("No cover saved")
with right:
    st.header(book["title"])
    if book["subtitle"]:
        st.subheader(book["subtitle"])
    st.write(f"**{book['author']}**")
    if book["rating"]:
        st.write("★" * book["rating"])
    st.write(f"**Status:** {book['status']}")
    st.write(f"**Genre:** {book['genre'] or '—'}")
    st.write(f"**Formats:** {', '.join(formats) if formats else '—'}")
    if book["isbn"]:
        st.write(f"**ISBN:** {book['isbn']}")
    if epub:
        data = Path(epub["file_path"]).read_bytes()
        st.download_button("Download EPUB", data=data, file_name=epub["file_name"], mime="application/epub+zip")

if book["review"]:
    st.subheader("My Review")
    st.write(book["review"])
if book["notes"]:
    st.subheader("Notes")
    st.write(book["notes"])
