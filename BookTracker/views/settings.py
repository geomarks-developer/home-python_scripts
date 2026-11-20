from pathlib import Path
import streamlit as st
from database import DB_PATH
from storage import LIBRARY_DIR

st.title("⚙️ Settings")
st.subheader("Storage")
st.code(str(DB_PATH))
st.code(str(LIBRARY_DIR))
st.info("Backup both the database file and the library folder to preserve your complete collection.")
