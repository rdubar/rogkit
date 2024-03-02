import streamlit as st
from rogkit_package.bin.pw import PasswordGenerator

# Function to generate password
def generate_password(length, alpha, numeric, special, dashes):
    pw_generator = PasswordGenerator(length=length, alpha=alpha, numeric=numeric, special=special, dashes=dashes)
    return pw_generator.generate_and_store_password()

# Title and introduction
st.title('Password Generator')

# Define user options
length = st.sidebar.slider('Length of password', 1, 100, 16)
alpha = st.sidebar.checkbox('Include letters', value=True)
numeric = st.sidebar.checkbox('Include numbers', value=True)
dashes = st.sidebar.checkbox('Include dashes', value=True)
special = st.sidebar.checkbox('Include special characters')

# Generate the password
password = generate_password(length, alpha, numeric, special, dashes)

# Display the password at the top of the page, allowing the user to click to copy
st.code(password, language="")

# button to regenerate the password
if st.button('Generate new password'):
    password = generate_password(length, alpha, numeric, special, dashes)


