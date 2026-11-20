from pathlib import Path, PureWindowsPath
import base64
import mimetypes
import streamlit as st
from database import list_books

st.title("📚 My Library")
st.code(str(Path(__file__).resolve()))
books = list_books()

if not books:
    st.info("Your library is empty. Add your first book from Add Book.")
    st.stop()

def clean_values(values):
    return sorted({str(v).strip() for v in values if v is not None and str(v).strip()}, key=str.casefold)

def resolve_cover_path(cover_path):
    """Resolve saved Windows cover paths locally and on Streamlit Cloud."""
    if not cover_path:
        return None

    raw_path = str(cover_path).strip().strip('"').strip("'")

    if not raw_path:
        return None

    project_dir = Path(__file__).resolve().parent.parent
    library_dir = project_dir / "library"

    # First, try the stored path directly. This handles a valid local path.
    direct_path = Path(raw_path)

    if direct_path.is_file():
        return direct_path.resolve()

    # Parse the saved path using Windows path rules, even on Linux.
    windows_path = PureWindowsPath(raw_path)
    path_parts = windows_path.parts

    # Reconstruct everything following the "library" folder.
    # Example:
    # C:\\...\BookTracker\\library\\000003\\cover.png
    # becomes:
    # <current project>/library/000003/cover.png
    for index, part in enumerate(path_parts):
        if part.casefold() == "library":
            relative_parts = path_parts[index + 1:]

            if relative_parts:
                reconstructed_path = library_dir.joinpath(*relative_parts)

                if reconstructed_path.is_file():
                    return reconstructed_path.resolve()

            break

    # Fallback using the book directory and filename.
    # Example: 000003/cover.png
    if windows_path.parent.name and windows_path.name:
        fallback_path = (
            library_dir
            / windows_path.parent.name
            / windows_path.name
        )

        if fallback_path.is_file():
            return fallback_path.resolve()

    return None


def cover_exists(book):
    return resolve_cover_path(book["cover_path"]) is not None


@st.cache_data(show_spinner=False)
def image_to_data_url(path_string):
    path = Path(path_string)
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
    except OSError:
        return None


def get_cover_data_url(book):
    path = resolve_cover_path(book["cover_path"])
    return image_to_data_url(str(path)) if path else None


def show_cover(book, width="stretch", height=360):
    cover_url = get_cover_data_url(book)
    if not cover_url:
        st.markdown(
            f"<div style='height:{height}px;display:flex;align-items:center;justify-content:center;background:#eee;border-radius:8px;font-size:72px'>📖</div>",
            unsafe_allow_html=True,
        )
        return
    css_width = "100%" if width == "stretch" else f"{width}px" if isinstance(width, int) else str(width)
    html = (
        f'<div style="width:100%;display:flex;justify-content:center;align-items:center;">'
        f'<img src="{cover_url}" alt="Book cover" style="width:{css_width};max-width:100%;height:{height}px;object-fit:cover;display:block;border-radius:10px;box-shadow:0 5px 18px rgba(0,0,0,.25);">'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

all_authors = clean_values(b["author"] for b in books)
all_genres = clean_values(b["genre"] for b in books)
all_statuses = clean_values(b["status"] for b in books)
all_formats = clean_values(fmt.strip() for b in books for fmt in (b["formats"] or "").split(",") if fmt.strip())

st.subheader("Find Books")
search = st.text_input("Search title or author", placeholder="Start typing...", key="library_search").strip().lower()
f1, f2, f3, f4 = st.columns(4)
with f1: genre_filter = st.selectbox("Genre", ["All Genres"] + all_genres, key="library_genre")
with f2: author_filter = st.selectbox("Author", ["All Authors"] + all_authors, key="library_author")
with f3: status_filter = st.selectbox("Status", ["All Statuses"] + all_statuses, key="library_status")
with f4: format_filter = st.selectbox("Format", ["All Formats"] + all_formats, key="library_format")
f5, f6, f7 = st.columns([1, 1, 2])
with f5:
    minimum_rating = st.selectbox("Minimum rating", [0,1,2,3,4,5], format_func=lambda x: "Any Rating" if x == 0 else "★" * x + " & up", key="library_rating")
with f6:
    favorites_only = st.checkbox("Favorites only", key="library_favorites")
    epub_only = st.checkbox("EPUB available", key="library_epub")
with f7:
    sort_by = st.selectbox("Sort by", ["Title A-Z","Title Z-A","Author A-Z","Author Z-A","Rating High-Low","Rating Low-High","Recently Added","Oldest Added","Publication Year New-Old","Publication Year Old-New"], key="library_sort")

if st.button("Clear Filters", key="library_clear"):
    for key in ["library_search","library_genre","library_author","library_status","library_format","library_rating","library_favorites","library_epub","library_sort"]:
        st.session_state.pop(key, None)
    st.session_state["cover_flow_index"] = 0
    st.rerun()

filtered = []
for book in books:
    title, author = (book["title"] or "").lower(), (book["author"] or "").lower()
    formats = [x.strip() for x in (book["formats"] or "").split(",") if x.strip()]
    if search and search not in title and search not in author: continue
    if genre_filter != "All Genres" and book["genre"] != genre_filter: continue
    if author_filter != "All Authors" and book["author"] != author_filter: continue
    if status_filter != "All Statuses" and book["status"] != status_filter: continue
    if format_filter != "All Formats" and format_filter not in formats: continue
    if minimum_rating and (book["rating"] or 0) < minimum_rating: continue
    if favorites_only and not bool(book["favorite"]): continue
    if epub_only and not book["epub_path"]: continue
    filtered.append(book)

if sort_by == "Title A-Z": filtered.sort(key=lambda b:(b["title"] or "").casefold())
elif sort_by == "Title Z-A": filtered.sort(key=lambda b:(b["title"] or "").casefold(), reverse=True)
elif sort_by == "Author A-Z": filtered.sort(key=lambda b:((b["author"] or "").casefold(),(b["title"] or "").casefold()))
elif sort_by == "Author Z-A": filtered.sort(key=lambda b:((b["author"] or "").casefold(),(b["title"] or "").casefold()), reverse=True)
elif sort_by == "Rating High-Low": filtered.sort(key=lambda b:(b["rating"] or 0,(b["title"] or "").casefold()), reverse=True)
elif sort_by == "Rating Low-High": filtered.sort(key=lambda b:(b["rating"] is None,b["rating"] or 0,(b["title"] or "").casefold()))
elif sort_by == "Recently Added": filtered.sort(key=lambda b:b["created_at"] or "", reverse=True)
elif sort_by == "Oldest Added": filtered.sort(key=lambda b:b["created_at"] or "")
elif sort_by == "Publication Year New-Old": filtered.sort(key=lambda b:(b["publication_year"] or 0,(b["title"] or "").casefold()), reverse=True)
elif sort_by == "Publication Year Old-New": filtered.sort(key=lambda b:(b["publication_year"] is None,b["publication_year"] or 0,(b["title"] or "").casefold()))

st.caption(f"Showing {len(filtered)} of {len(books)} books")
if not filtered:
    st.warning("No books match the current filters.")
    st.stop()

view = st.segmented_control("View", ["Cover Flow", "Cover Grid", "Table"], default="Cover Flow", key="library_view")

if view == "Cover Flow":
    n = len(filtered)
    selected_id = st.session_state.get("selected_book_id")
    valid_ids = [b["id"] for b in filtered]
    if "cover_flow_index" not in st.session_state:
        st.session_state["cover_flow_index"] = valid_ids.index(selected_id) if selected_id in valid_ids else 0
    st.session_state["cover_flow_index"] %= n
    idx = st.session_state["cover_flow_index"]

    nav_l, nav_mid, nav_r = st.columns([1, 4, 1])
    with nav_l:
        if st.button("◀ Previous", use_container_width=True, key="flow_prev"):
            st.session_state["cover_flow_index"] = (idx - 1) % n
            st.rerun()
    with nav_mid:
        st.markdown(f"<p style='text-align:center;color:#777'>Book {idx + 1} of {n}</p>", unsafe_allow_html=True)
    with nav_r:
        if st.button("Next ▶", use_container_width=True, key="flow_next"):
            st.session_state["cover_flow_index"] = (idx + 1) % n
            st.rerun()

    # True Cover Flow: center is always largest; near neighbors medium; outer neighbors small.
    if n == 1:
        _, center_col, _ = st.columns([2.2, 2.0, 2.2])
        with center_col:
            show_cover(filtered[idx], width=340, height=500)
    elif n == 2:
        left_idx = (idx - 1) % n
        left_space, left_col, gap, center_col, right_space = st.columns([1.2, 1.25, 0.45, 2.15, 1.2], vertical_alignment="center")
        with left_col:
            show_cover(filtered[left_idx], width=175, height=260)
            if st.button(filtered[left_idx]["title"][:22], key=f"flow_left_{filtered[left_idx]['id']}", use_container_width=True):
                st.session_state["cover_flow_index"] = left_idx
                st.rerun()
        with center_col:
            show_cover(filtered[idx], width=340, height=500)
    else:
        left_idx = (idx - 1) % n
        right_idx = (idx + 1) % n
        flow_cols = st.columns([0.75, 1.35, 2.35, 1.35, 0.75], vertical_alignment="center")

        # Outer books only appear when there are enough unique books.
        if n >= 5:
            outer_left_idx = (idx - 2) % n
            outer_right_idx = (idx + 2) % n
            with flow_cols[0]:
                show_cover(filtered[outer_left_idx], width=105, height=175)
                if st.button("◀", key=f"flow_outer_left_{filtered[outer_left_idx]['id']}", use_container_width=True):
                    st.session_state["cover_flow_index"] = outer_left_idx
                    st.rerun()
            with flow_cols[4]:
                show_cover(filtered[outer_right_idx], width=105, height=175)
                if st.button("▶", key=f"flow_outer_right_{filtered[outer_right_idx]['id']}", use_container_width=True):
                    st.session_state["cover_flow_index"] = outer_right_idx
                    st.rerun()

        with flow_cols[1]:
            show_cover(filtered[left_idx], width=175, height=260)
            if st.button(filtered[left_idx]["title"][:22], key=f"flow_left_{filtered[left_idx]['id']}", use_container_width=True):
                st.session_state["cover_flow_index"] = left_idx
                st.rerun()

        with flow_cols[2]:
            show_cover(filtered[idx], width=340, height=500)

        with flow_cols[3]:
            show_cover(filtered[right_idx], width=175, height=260)
            if st.button(filtered[right_idx]["title"][:22], key=f"flow_right_{filtered[right_idx]['id']}", use_container_width=True):
                st.session_state["cover_flow_index"] = right_idx
                st.rerun()

    current = filtered[st.session_state["cover_flow_index"]]
    st.session_state["selected_book_id"] = current["id"]
    st.markdown(f"<h2 style='text-align:center;margin-bottom:0'>{current['title']}</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;font-size:1.1rem;color:#777'>{current['author']}</p>", unsafe_allow_html=True)
    details = []
    if current["rating"]: details.append("★" * current["rating"])
    if current["status"]: details.append(current["status"])
    if current["formats"]: details.append(current["formats"])
    if current["epub_path"]: details.append("📱 EPUB")
    if current["favorite"]: details.append("⭐ Favorite")
    st.markdown(f"<p style='text-align:center'>{' &nbsp; • &nbsp; '.join(details)}</p>", unsafe_allow_html=True)
    _, b, c, _ = st.columns([1.5, 1, 1, 1.5])
    with b:
        if st.button("📖 View Book", use_container_width=True, type="primary"):
            st.switch_page("views/book_details.py")
    with c:
        if st.button("✏️ Edit Book", use_container_width=True):
            st.switch_page("views/edit_book.py")

elif view == "Table":
    rows = [{"ID":b["id"],"Title":b["title"],"Author":b["author"],"Genre":b["genre"],"Year":b["publication_year"],"Status":b["status"],"Rating":b["rating"],"Favorite":"★" if b["favorite"] else "","Formats":b["formats"] or "","EPUB":"Yes" if b["epub_path"] else "No"} for b in filtered]
    st.dataframe(rows, width="stretch", hide_index=True)

else:
    for start in range(0, len(filtered), 5):
        row_books = filtered[start:start+5]
        cols = st.columns(5)
        for col, book in zip(cols, row_books):
            with col:
                show_cover(book, width="stretch", height=360)
                st.markdown(f"**{book['title']}**")
                st.caption(book["author"])
                if book["rating"]: st.write("★" * book["rating"])
                if book["favorite"]: st.caption("⭐ Favorite")
                metadata = [x for x in [book["status"], book["formats"]] if x]
                if metadata: st.caption(" • ".join(metadata))
                if st.button("View", key=f"view_{book['id']}", use_container_width=True):
                    st.session_state["selected_book_id"] = book["id"]
                    st.switch_page("views/book_details.py")
