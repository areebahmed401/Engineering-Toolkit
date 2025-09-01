import streamlit as st
from pathlib import Path

def apply_custom_css():
    """Load and inject the custom theme CSS into Streamlit."""
    css_path = Path("assets/theme.css")
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
