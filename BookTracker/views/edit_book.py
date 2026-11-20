import shutil
from datetime import date
from pathlib import Path
import streamlit as st
from database import list_books, get_book, update_book, delete_book, find_duplicates, add_book_file
from storage import save_uploaded_file, book_dir

st.title("✏️ Edit Book")
books = list_books()
if not books:
    st.info("There are no books to edit.")
    st.stop()
ids = [b["id"] for b in books]
selected = st.session_state.get("selected_book_id", ids[0])
if selected not in ids: selected = ids[0]
book_id = st.selectbox("Select book", ids, index=ids.index(selected), format_func=lambda x: next(f"{b['title']} — {b['author']}" for b in books if b["id"] == x))
st.session_state["selected_book_id"] = book_id
book, formats, files = get_book(book_id)

def d(v):
    return date.fromisoformat(v) if v else None

with st.form(f"edit_{book_id}"):
    c1,c2=st.columns(2)
    title=c1.text_input("Title *", value=book["title"])
    author=c2.text_input("Author *", value=book["author"])
    subtitle=st.text_input("Subtitle", value=book["subtitle"] or "")
    c1,c2=st.columns(2)
    series=c1.text_input("Series", value=book["series"] or "")
    series_number=c2.number_input("Series #", min_value=0.0, step=0.5, value=book["series_number"])
    c1,c2=st.columns(2)
    isbn=c1.text_input("ISBN", value=book["isbn"] or "")
    publisher=c2.text_input("Publisher", value=book["publisher"] or "")
    c1,c2,c3=st.columns(3)
    publication_year=c1.number_input("Publication year", min_value=0, max_value=3000, step=1, value=book["publication_year"])
    pages=c2.number_input("Pages", min_value=0, step=1, value=book["pages"])
    genre=c3.text_input("Genre", value=book["genre"] or "")
    description=st.text_area("Description", value=book["description"] or "")
    owned=st.multiselect("Formats owned", ["Hardcover","Paperback","EPUB","Kindle","Audiobook","PDF"], default=formats)
    c1,c2,c3=st.columns(3)
    statuses=["Want to Read","Reading","Finished","Reference"]
    status=c1.selectbox("Status", statuses, index=statuses.index(book["status"]) if book["status"] in statuses else 0)
    ratings=[None,1,2,3,4,5]
    rating=c2.selectbox("Rating", ratings, index=ratings.index(book["rating"]), format_func=lambda x:"Not rated" if x is None else "★"*x)
    favorite=c3.checkbox("Favorite", value=bool(book["favorite"]))
    current_page=st.number_input("Current page", min_value=0, step=1, value=book["current_page"] or 0)
    cover=st.file_uploader("Replace/add cover", type=["jpg","jpeg","png","webp"])
    epub=st.file_uploader("Replace/add EPUB", type=["epub"])
    with st.expander("Acquisition and reading dates"):
        c1,c2=st.columns(2)
        date_acquired=c1.date_input("Date acquired", value=d(book["date_acquired"]))
        purchase_price=c2.number_input("Purchase price", min_value=0.0, step=0.01, value=book["purchase_price"])
        purchased_from=st.text_input("Purchased from", value=book["purchased_from"] or "")
        c1,c2=st.columns(2)
        date_started=c1.date_input("Date started", value=d(book["date_started"]))
        date_finished=c2.date_input("Date finished", value=d(book["date_finished"]))
    review=st.text_area("My review", value=book["review"] or "")
    notes=st.text_area("Notes", value=book["notes"] or "")
    save=st.form_submit_button("Save Changes", type="primary")

if save:
    dupes=find_duplicates(title, author, isbn, exclude_book_id=book_id)
    if not title.strip() or not author.strip(): st.error("Title and Author are required.")
    elif dupes: st.error(f"Possible duplicate: {dupes[0]['title']} by {dupes[0]['author']} already exists as book #{dupes[0]['id']}.")
    else:
        iso=lambda v:v.isoformat() if isinstance(v,date) else None
        update_book(book_id,{"title":title.strip(),"subtitle":subtitle.strip(),"author":author.strip(),"series":series.strip(),"series_number":series_number,"isbn":isbn.strip(),"publisher":publisher.strip(),"publication_year":publication_year,"genre":genre.strip(),"pages":pages,"description":description.strip(),"status":status,"current_page":current_page,"rating":rating,"favorite":int(favorite),"date_acquired":iso(date_acquired),"date_started":iso(date_started),"date_finished":iso(date_finished),"purchase_price":purchase_price,"purchased_from":purchased_from.strip(),"review":review.strip(),"notes":notes.strip()},owned)
        for uploaded,kind in [(cover,"cover"),(epub,"epub")]:
            if uploaded:
                path=save_uploaded_file(book_id,uploaded,kind)
                add_book_file(book_id,kind,uploaded.name,str(path),path.stat().st_size)
        st.success("Book updated.")

st.divider()
with st.expander("Danger zone"):
    confirm=st.checkbox("I understand this permanently deletes this book and its stored files.")
    if st.button("Delete Book", type="primary", disabled=not confirm):
        delete_book(book_id)
        shutil.rmtree(book_dir(book_id), ignore_errors=True)
        st.session_state.pop("selected_book_id",None)
        st.success("Book deleted.")
        st.rerun()
