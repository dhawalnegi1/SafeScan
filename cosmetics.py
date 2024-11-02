import streamlit as st
from PIL import Image
import io

# Function to show the main page
def main_page():
    st.markdown('<p class="title-text">Cosmetic Compass</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Meet Cosmetic Compass, your guide to transparent, healthy skincare.</p>', unsafe_allow_html=True)

    # File uploader for image files
    st.markdown('<br><p class="file-uploader-prompt">Please choose an image file (JPG, PNG, JPEG) to get safety information about your product:</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        # Open and display the image
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Image', use_column_width=True)

        # Process the image (this is where you would integrate AI model analysis)
        st.subheader("Analysis Result")
        st.write("Your image has been successfully uploaded. Here is where the safety analysis results would appear.")

# Function to show the About page
def about_page():
    st.markdown('<p class="sidebar-info">About</p>', unsafe_allow_html=True)
    st.write("Meet Cosmetic Compass, the ultimate tool for conscious beauty consumers. You can upload or snap a picture of any makeup or skincare product to receive an instant safety rating. Powered by AI, the app identifies the product and scans its ingredient list, highlighting any harmful components like carcinogens, hormone disruptors, toxic chemicals, or unknown substances. Along with a clear safety score, users get a detailed report of each ingredient’s impact, supported by links to scientific studies and research. Say goodbye to guesswork and hello to informed, safe beauty choices with Cosmetic Compass — your guide to transparent, healthy skincare.")

    # Button to navigate back to the main page
    if st.button('Back to Main Page'):
        st.session_state.page = "main"  # Set the session state back to main

# Function to show the Mission page
def mission_page():
    st.markdown('<p class="sidebar-info">Our Mission</p>', unsafe_allow_html=True)
    st.write("Cosmetic Compass aims to bridge this gap by empowering users with knowledge. With a quick photo, users can access a detailed analysis of a product's ingredients, highlighting any risks associated with their skincare and beauty choices. This solution enables informed decisions and fosters a safer, more transparent beauty industry for all.")

    # Button to navigate back to the main page
    if st.button('Back to Main Page'):
        st.session_state.page = "main"  # Set the session state back to main

# Inject CSS to style font and size
st.markdown(
    """
    <style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Playwrite+GB+S:ital,wght@0,100..400;1,100..400&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600;1,700&family=Playwrite+GB+S:ital,wght@0,100..400;1,100..400&display=swap');

    .title-text {
        font-family: "Playwrite GB S", cursive;
        font-size: 72px;
        font-weight: bold;
        color: #CCCCFF;
        text-align: center;
        white-space: nowrap;
        overflow: hidden;
        border-right: .15em solid #555;
        animation: typing 3s steps(40, end), blink-caret 0.5s step-end infinite;
    }

    /* Typing effect */
    @keyframes typing {
        from { width: 0; }
        to { width: 100%; }
    }

    /* Blinking cursor effect */
    @keyframes blink-caret {
        from, to { border-color: transparent; }
        50% { border-color: #555; }
    }

    .subtitle-text {
        font-size: 24px;
        color: #000000;
        text-align: center;
        font-family: "Cormorant Garamond", serif;
        font-weight: 300;
        font-style: italic;
    }
    .sidebar-info {
        font-size: 24px;
        color: #FFFFFF;
        text-align: center;
        font-family: "Cormorant Garamond", serif;
        font-weight: 300;
    }
    /* Style the file uploader prompt */
    .file-uploader-prompt {
        font-family: 'Cormorant Garamond', serif;
        font-size: 18px;
        color: #000000;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# Background image style
bg_img = """
<style>
[data-testid="stAppViewContainer"] {
background-image: url("https://png.pngtree.com/background/20210710/original/pngtree-high-end-atmosphere-simple-wind-makeup-area-banner-picture-image_1056850.jpg");
background-size: cover;
background-position: center;
background-repeat: no-repeat;
}
[data-testid="stHeader"] {
background-color: rgba(0, 0, 0, 0);
}
</style>
"""

st.markdown(bg_img, unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.markdown('<p class="sidebar-info">Navigation</p>', unsafe_allow_html=True)
if st.sidebar.button('About'):
    st.session_state.page = "about"
elif st.sidebar.button('Our Mission'):
    st.session_state.page = "mission"
else:
    st.session_state.page = "main"

# Determine which page to display
if 'page' not in st.session_state:
    st.session_state.page = "main"

if st.session_state.page == "main":
    main_page()
elif st.session_state.page == "about":
    about_page()
elif st.session_state.page == "mission":
    mission_page()
