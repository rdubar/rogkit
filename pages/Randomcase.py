import streamlit as st
import random

# Assuming your randomcase function is defined correctly
# If not, here's a simple implementation:
def randomcase(string):
    return ''.join(random.choice([c.upper(), c.lower()]) for c in string)

st.title('Random Case Generator')


if 'input_text' not in st.session_state or st.button('Randomize'):
    st.session_state['input_text'] = st.text_area('Enter text to randomize', value="randomcase")
else:
    st.session_state['input_text'] = st.text_area('Enter text to randomize', value=st.session_state['input_text'])

output_text = randomcase(st.session_state['input_text'])

st.code(output_text, language="")

