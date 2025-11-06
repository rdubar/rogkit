"""
Streamlit page for random case text generator.

Converts text to random mixed case (e.g., "hello" -> "HeLLo").
"""
import streamlit as st  # type: ignore
import random

st.set_page_config(page_title="RogKit", page_icon=":tools:")


def randomcase(string):
    """Convert string to random mixed case."""
    return ''.join(random.choice([c.upper(), c.lower()]) for c in string)

st.title('Random Case Generator')


if 'input_text' not in st.session_state or st.button('Randomize'):
    st.session_state['input_text'] = st.text_area('Enter text to randomize', value="randomcase")
else:
    st.session_state['input_text'] = st.text_area('Enter text to randomize', value=st.session_state['input_text'])

output_text = randomcase(st.session_state['input_text'])

st.code(output_text, language="")

