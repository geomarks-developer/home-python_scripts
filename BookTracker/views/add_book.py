from datetime import date
import streamlit as st
from database import add_book, add_book_file, find_duplicates
from storage import save_uploaded_file

st.title("➕ Add Book")
st.caption("Create a library record and optionally keep a cover image and EPUB with it.")

with st.form("add_book_form", clear_on_submit=False):
    left, right = st.columns([2, 1])
    with left:
        title = st.text_input("Title *")
        subtitle = st.text_input("Subtitle")
        author = st.text_input("Author *")
        c1, c2 = st.columns(2)
        series = c1.text_input("Series")
        series_number = c2.number_input("Series #", min_value=0.0, step=0.5, value=None)
        c1, c2 = st.columns(2)
        isbn = c1.text_input("ISBN")
        publisher = c2.text_input("Publisher")
        c1, c2, c3 = st.columns(3)
        publication_year = c1.number_input("Publication year", min_value=0, max_value=3000, value=None, step=1)
        pages = c2.number_input("Pages", min_value=0, value=None, step=1)
        genre = c3.text_input("Genre")
        description = st.text_area("Description")
    with right:
        cover = st.file_uploader("Book cover", type=["jpg", "jpeg", "png", "webp"])
        if cover:
            st.image(cover, caption="Cover preview", width=220)
        epub = st.file_uploader("EPUB file", type=["epub"])
        if epub:
            st.success(f"Ready to save: {epub.name}")

    st.subheader("My Copy")
    formats = st.multiselect("Formats owned", ["Hardcover", "Paperback", "EPUB", "Kindle", "Audiobook", "PDF"])
    c1, c2, c3 = st.columns(3)
    status = c1.selectbox("Status", ["Want to Read", "Reading", "Finished", "Reference"])
    rating = c2.selectbox("Rating", [None, 1, 2, 3, 4, 5], format_func=lambda x: "Not rated" if x is None else "★" * x)
    favorite = c3.checkbox("Favorite")
    current_page = st.number_input("Current page", min_value=0, step=1, value=0)

    with st.expander("Acquisition and reading dates"):
        c1, c2 = st.columns(2)
        date_acquired = c1.date_input("Date acquired", value=None)
        purchase_price = c2.number_input("Purchase price", min_value=0.0, value=None, step=0.01)
        purchased_from = st.text_input("Purchased from")
        c1, c2 = st.columns(2)
        date_started = c1.date_input("Date started", value=None)
        date_finished = c2.date_input("Date finished", value=None)

    review = st.text_area("My review")
    notes = st.text_area("Notes")
    submitted = st.form_submit_button("Save Book", type="primary")

if submitted:
    if not title.strip() or not author.strip():
        st.error("Title and Author are required.")
    elif find_duplicates(title, author, isbn):
        match = find_duplicates(title, author, isbn)[0]
        st.error(f"Possible duplicate: {match['title']} by {match['author']} already exists as book #{match['id']}.")
    else:
        def iso(v): return v.isoformat() if isinstance(v, date) else None
        book_id = add_book({
            "title": title.strip(), "subtitle": subtitle.strip(), "author": author.strip(),
            "series": series.strip(), "series_number": series_number, "isbn": isbn.strip(),
            "publisher": publisher.strip(), "publication_year": publication_year, "genre": genre.strip(),
            "pages": pages, "description": description.strip(), "status": status,
            "current_page": current_page, "rating": rating, "favorite": int(favorite),
            "date_acquired": iso(date_acquired), "date_started": iso(date_started),
            "date_finished": iso(date_finished), "purchase_price": purchase_price,
            "purchased_from": purchased_from.strip(), "review": review.strip(), "notes": notes.strip(),
        }, formats)

        for uploaded, kind in [(cover, "cover"), (epub, "epub")]:
            if uploaded:
                path = save_uploaded_file(book_id, uploaded, kind)
                add_book_file(book_id, kind, uploaded.name, str(path), path.stat().st_size)
        st.session_state["selected_book_id"] = book_id
        st.success(f"Saved '{title}' as book #{book_id}.")
        st.balloons()
