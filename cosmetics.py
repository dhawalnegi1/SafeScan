import streamlit as st
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from google.cloud import vision
from PIL import Image
import io, os, re, requests
import hashlib
from pymongo import MongoClient
from flask_bcrypt import Bcrypt

# Initialize the Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

def get_db():
    client = MongoClient('mongodb://localhost:27017/')
    return client['cosmetic_compass']

bcrypt = Bcrypt(app)

def register_user(username, password):
    db = get_db()
    users_collection = db['users']
    
    # Check if the username already exists
    if users_collection.find_one({'username': username}):
        return {'success': False, 'message': 'Username already exists'}
    
    # Hash the password
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    # Insert the new user into the database
    users_collection.insert_one({'username': username, 'password': hashed_password})
    return {'success': True, 'message': 'User registered successfully'}

def login_user(username, password):
    db = get_db()
    users_collection = db['users']
    
    # Find the user by username
    user = users_collection.find_one({'username': username})
    if user and bcrypt.check_password_hash(user['password'], password):
        return {'success': True, 'message': 'Login successful'}
    return {'success': False, 'message': 'Invalid username or password'}

def register_page():
    st.markdown('<p class="sidebar-info">Register</p>', unsafe_allow_html=True)
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        result = register_user(username, password)
        st.write(result['message'])
        if result['success']:
            st.session_state.page = "login"

def login_page():
    st.markdown('<p class="sidebar-info">Login</p>', unsafe_allow_html=True)
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        result = login_user(username, password)
        st.write(result['message'])
        if result['success']:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.page = "main"

# Ensure the uploads folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize the Google Cloud Vision client
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'service_account.json'
vision_client = vision.ImageAnnotatorClient()

# Helper function to check if the file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def clean_text(text):
    """Removes unwanted characters such as newlines and Unicode characters."""
    text = text.replace("\n", " ")  # Replace newlines with spaces
    text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII characters
    return text.strip()

def recognize_product(file_path):
    """Uses Google Cloud Vision API to identify the product in the image."""
    with open(file_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    # Label detection for general characteristics
    label_response = vision_client.label_detection(image=image)
    labels = [clean_text(label.description) for label in label_response.label_annotations]

    # Object detection to identify specific objects
    object_response = vision_client.object_localization(image=image)

    # Filter objects to ignore "hand" or similar irrelevant items
    relevant_objects = []
    for obj in object_response.localized_object_annotations:
        if obj.name.lower() not in ['hand', 'person', 'finger']:  # Exclude hand-related objects
            relevant_objects.append((clean_text(obj.name), obj.bounding_poly))

    # Sort objects by area (largest to smallest), assuming the largest is the product
    relevant_objects.sort(key=lambda x: (x[1].normalized_vertices[2].x - x[1].normalized_vertices[0].x) *
                                      (x[1].normalized_vertices[2].y - x[1].normalized_vertices[0].y), 
                          reverse=True)
    # Only keep the name of the most prominent object
    detected_objects = [relevant_objects[0][0]] if relevant_objects else []

    # Text detection to look for explicit product names
    text_response = vision_client.text_detection(image=image)
    detected_text = ""
    if text_response.text_annotations:
        detected_text = clean_text(text_response.text_annotations[0].description)

    # Use color detection if available
    dominant_colors = []
    image_properties = vision_client.image_properties(image=image)
    if image_properties.image_properties_annotation:
        for color in image_properties.image_properties_annotation.dominant_colors.colors:
            rgb_color = (color.color.red, color.color.green, color.color.blue)
            dominant_colors.append(f"RGB{rgb_color}")

    # Construct a descriptive search query
    visual_features = " ".join(labels + detected_objects + dominant_colors)
    search_query = f"{detected_text} {visual_features}".strip()
    product_link = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

    # Fetch the first result from the Google search
    product_name = fetch_product_name_from_google(search_query)

    # Build response with cleaned text
    return {
        'message': "Is this the product you're showing?",
        'detected_labels': labels,
        'detected_objects': detected_objects,
        'dominant_colors': dominant_colors,
        'detected_text': detected_text,
        'product_name': product_name or "Product Name Unknown",
        'product_link': product_link,
        'confirmation_prompt': f"Is this the product you're showing? {detected_text or 'Unknown Product'}",
        'link': product_link
    }

def fetch_product_name_from_google(query):
    """Fetch the most relevant product name from the Google search results, ignoring ads."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

    response = requests.get(f"https://www.google.com/search?q={query.replace(' ', '+')}", headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Gather all relevant search results
        product_names = []
        for h3 in soup.find_all('h3'):
            parent = h3.find_parent('a')
            # Skip sponsored links
            if parent and 'href' in parent.attrs and not '/aclk' in parent.attrs['href']:
                product_names.append(clean_text(h3.get_text()))

        # Attempt to find the most relevant product name based on the detected text
        if product_names:
            detected_text = query  # Use the original query for matching
            best_match = max(product_names, key=lambda name: similarity_score(detected_text, name), default=None)
            return best_match or "Product Name Unknown"
    
    return None

def similarity_score(detected_text, product_name):
    """Calculate a simple similarity score between the detected text and a product name."""
    detected_words = set(detected_text.lower().split())
    product_words = set(product_name.lower().split())
    # Calculate the intersection of detected and product words
    return len(detected_words.intersection(product_words))

# Function to show the main page
def main_page():
    st.markdown('<p class="title-text">Cosmetic Compass</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Meet Cosmetic Compass, your guide to transparent, healthy skincare.</p>', unsafe_allow_html=True)

    # File uploader for image files
    st.markdown('<br><p class="file-uploader-prompt">Please choose an image file (JPG, PNG, JPEG) to get safety information about your product:</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload your image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        # Save the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(uploaded_file.name))
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Call the Google Vision API to recognize the product
        product_info = recognize_product(file_path)
        st.write(product_info)

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
if st.sidebar.button('Login', key='login_button'):
    st.session_state.page = "login"
elif st.sidebar.button('Register', key='register_button'):
    st.session_state.page = "register"
elif st.sidebar.button('About', key='about_button'):
    st.session_state.page = "about"
elif st.sidebar.button('Our Mission', key='mission_button'):
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
