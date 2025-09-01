import streamlit as st
from utils.styling import apply_custom_css
from pathlib import Path

# ---------- Page Config ----------
st.set_page_config(page_title="Engineering Sizing Toolkit", layout="wide")
# apply_custom_css()



# ---------- Homepage ----------
st.title("Engineering Toolkit")
st.markdown(
    "<p style='font-size:18px; color:#cccccc;'>"
    "Welcome to the Engineering Sizing Toolkit. Use the sidebar on the left to navigate "
    "to one of the available modules."
    "</p>",
    unsafe_allow_html=True
)


st.divider()
st.markdown("<p style='color:#777; font-size:14px;'>© 2025 Engineering Toolkit | Areeb Ahmed</p>", unsafe_allow_html=True)
