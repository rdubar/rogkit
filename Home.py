"""
RogKit Streamlit application home page.

Landing page for the rogkit Streamlit web interface.
"""
import streamlit as st  # type: ignore

st.set_page_config(page_title="RogKit", page_icon=":tools:")

st.title("🛠️ RogKit Home")

st.markdown("""
## Welcome to RogKit Web Interface

A collection of 85+ Python utilities with an interactive Streamlit frontend.

### 🚀 Getting Started

Use the **sidebar** (← left) to navigate between different tools and utilities.

### 📱 Available Pages

- **📺 Media** - Browse and visualize your Plex media library with charts
- **🔐 Password** - Generate secure passwords with customizable options
- **🎨 Randomcase** - Convert text to random mixed case

### 💻 Running This Application

To start the Streamlit interface from the command line:

```bash
cd ~/dev/rogkit
streamlit run Home.py
```

Or use the shortcut (if using the rogkit aliases):
```bash
cd ~/dev/rogkit
streamlit run Home.py
```

The application will automatically open in your default web browser at `http://localhost:8501`

### 📚 CLI Tools

RogKit also includes 85+ command-line utilities. View the full command reference:
```bash
rogkit
```

For detailed documentation, see the [README.md](https://github.com/rdubar/rogkit/blob/main/README.md)

---

**Built with Python & Streamlit** | **Made by Roger D.**
""")

# Add a divider
st.divider()

# Quick stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("📦 Total Utilities", "85+")
with col2:
    st.metric("📂 Categories", "15")
with col3:
    st.metric("🐍 Python Version", "3.14")
