import streamlit as st
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from google.cloud import vision
from PIL import Image
import io, os, re, requests
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from agent import get_product_info

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}   

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# google cloud vision client
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'service_account.json'
vision_client = vision.ImageAnnotatorClient()

# check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def clean_text(text): # text filtering
    text = text.replace("\n", " ")  # replace newlines with spaces
    text = re.sub(r'[^\x00-\x7F]+', '', text)  # remove non-ASCII characters
    return text.strip()

def recognize_product(file_path): # google cloud vision to identify product
    with open(file_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)

    # label detection for general characteristics
    label_response = vision_client.label_detection(image=image)
    labels = [clean_text(label.description) for label in label_response.label_annotations]

    # object detection to identify specific objects
    object_response = vision_client.object_localization(image=image)

    # Filter objects to ignore "hand" or similar irrelevant items
    relevant_objects = []
    for obj in object_response.localized_object_annotations:
        if obj.name.lower() not in ['hand', 'person', 'finger']:  # exclude hands
            relevant_objects.append((clean_text(obj.name), obj.bounding_poly))

    # sort objects by area (largest to smallest), assuming the largest is the product
    relevant_objects.sort(key=lambda x: (x[1].normalized_vertices[2].x - x[1].normalized_vertices[0].x) *
                                      (x[1].normalized_vertices[2].y - x[1].normalized_vertices[0].y), 
                          reverse=True)
    # only keep the name of the most prominent object
    detected_objects = [relevant_objects[0][0]] if relevant_objects else []

    # text detection to look for explicit product names
    text_response = vision_client.text_detection(image=image)
    detected_text = ""
    if text_response.text_annotations:
        detected_text = clean_text(text_response.text_annotations[0].description)

    # color detection if available
    dominant_colors = []
    image_properties = vision_client.image_properties(image=image)
    if image_properties.image_properties_annotation:
        for color in image_properties.image_properties_annotation.dominant_colors.colors:
            rgb_color = (color.color.red, color.color.green, color.color.blue)
            dominant_colors.append(f"RGB{rgb_color}")

    # make a search query
    visual_features = " ".join(labels + detected_objects + dominant_colors)
    search_query = f"{detected_text} {visual_features}".strip()
    product_link = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

    # fetch the first result from gooogle search
    product_name = fetch_product_name_from_google(search_query)
    print(product_name)
    product_info = get_product_info(f"Tell me about {product_name}")
    
    st.markdown(
    """
    <style>
    .product-info {
        background-color: rgba(0, 0, 0, 0.7); /* Dark but transparent background */
        color: white;
        padding: 10px;
        border-radius: 10px;
        width: 600px;
        margin: auto;
    }
    </style>
    """,
    unsafe_allow_html=True)

    # beautify product info
    st.markdown(
    f"""
    <div class="product-info">
        <h3>Product Information</h3>
        <p><strong>Ingredients:</strong> {product_info['ingredients']}</p>
        <p><strong>Allergens:</strong> {product_info['allergens']}</p>
        <p><strong>Harmful Ingredients:</strong> {product_info['harmful_ingredients']}</p>
        <p><strong>Conclusion:</strong> {product_info['conclusion']}</p>
        <p><strong>Sources:</strong></p>
        <ul>
            {''.join(f'<li><a href="{source.strip()}">{source.strip()}</a></li>' for source in product_info['sources'].splitlines())}
        </ul>
    </div>
    """,
    unsafe_allow_html=True
)
    

def fetch_product_name_from_google(query): # fetch most relevant product name ignoring ads
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

    response = requests.get(f"https://www.google.com/search?q={query.replace(' ', '+')}", headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # gather relevant search results
        product_names = []
        for h3 in soup.find_all('h3'):
            parent = h3.find_parent('a')
            # skip sponsored links
            if parent and 'href' in parent.attrs and not '/aclk' in parent.attrs['href']:
                product_names.append(clean_text(h3.get_text()))

        # attempt to find the most relevant product name based on the detected text
        if product_names:
            detected_text = query  # use the original query for matching
            best_match = max(product_names, key=lambda name: similarity_score(detected_text, name), default=None)
            return best_match or "Product Name Unknown"
    
    return None

def similarity_score(detected_text, product_name):
    """Calculate a simple similarity score between the detected text and a product name."""
    detected_words = set(detected_text.lower().split())
    product_words = set(product_name.lower().split())
    # calculate the intersection of detected and product words
    return len(detected_words.intersection(product_words))

def main_page():
    st.markdown('<p class="title-text">SafeScan</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle-text">Scan Smart, Live Smarter.</p>', unsafe_allow_html=True)

    # image file uploader
    st.markdown('<br><p class="file-uploader-prompt">Please choose an image file (JPG, PNG, JPEG) to get safety information about your product:</p>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload your image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        # save the uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(uploaded_file.name))
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)

        # call google vision api
        product_info = recognize_product(file_path)
        # beautify the product info
        st.write(product_info)

def about_page():
    st.markdown('<p class="section-title">About</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="about-text">
        SafeScan is an innovative platform that empowers users to make informed decisions about beauty products, medications, and packaged foods. By simply uploading a photo of any product label, our advanced AI technology analyzes the ingredients for toxic substances, harmful allergens, and potential side effects, delivering a detailed safety rating and risk report.
        </p>
        """,
        unsafe_allow_html=True
    )

def mission_page():
    st.markdown('<p class="section-title">Our Mission</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <p class="mission-text">
        SafeScan is dedicated to empowering consumers with knowledge and transparency, making it easy for anyone to make informed, health-conscious choices in their daily lives. By harnessing the power of AI, SafeScan aims to demystify ingredient labels on beauty products, medications, and packaged foods, identifying potential risks and harmful substances at the tap of a button. We are dedicated to promoting safer consumer habits, fostering a culture of informed decisions and enhancing public health.
        </p>
        """,
        unsafe_allow_html=True
    )
    
# css to style font and size
st.markdown(
    """
    <style>
    /* import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600;1,700&family=Passion+One:wght@400;700;900&family=Playwrite+GB+S:ital,wght@0,100..400;1,100..400&family=Roboto:ital,wght@0,100;0,300;0,400;0,500;0,700;0,900;1,100;1,300;1,400;1,500;1,700;1,900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500;1,600;1,700&family=Oxygen:wght@300;400;700&family=Passion+One:wght@400;700;900&family=Playwrite+GB+S:ital,wght@0,100..400;1,100..400&family=Roboto:ital,wght@0,100;0,300;0,400;0,500;0,700;0,900;1,100;1,300;1,400;1,500;1,700;1,900&display=swap');

    /* slide down animation */
    @keyframes slide-down {
        from {
            transform: translateY(-50px); /* Start position */
            opacity: 0; /* Start invisible */
        }
        to {
            transform: translateY(0); /* End position */
            opacity: 1; /* End visible */
        }
    }

    .title-text {
        font-family: "Roboto", sans-serif;
        font-weight: 900;
        font-style: normal;
        font-size: 102px;
        color: #FFFFFF;
        text-align: center;
        animation: slide-down 3s ease-out;
    }

    .subtitle-text {
        font-size: 30px;
        color: #FFFFFF;
        text-align: center;
        font-family: "Oxygen", sans-serif;
        font-weight: 400;
        font-style: normal;
    }
    .sidebar-info {
        font-size: 24px;
        color: #000000;
        text-align: center;
        font-family: "Oxygen", sans-serif;
        font-weight: 300;
    }
    /* style the file uploader prompt */
    .file-uploader-prompt {
        font-family: 'Oxygen', sans-serif;
        font-size: 16px;
        color: #FFFFFF;
        font-weight: 500;
        text-align: center;
    }
    /* styles for About and Mission pages */
    .about-text, .mission-text {
        font-size: 20px;
        color: #FFFFFF;
        font-family: "Oxygen", sans-serif;
        font-weight: 500
        line-height: 1.5;
    }

    .section-title {
        font-family: "Roboto", sans-serif;
        font-size: 48px; 
        font-weight: bold;
        color: #FFFFFF;
        text-align: center;
        margin-bottom: 20px;
    }

    .sidebar-title {
        font-family: "Roboto", sans-serif;
        font-size: 48px; 
        font-weight: bold;
        color: #000000;
        text-align: center;
        margin-bottom: 20px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# background image 
bg_img = """
<style>
[data-testid="stAppViewContainer"] {
background-image: url("https://t4.ftcdn.net/jpg/06/07/29/09/360_F_607290966_NJt7a7zGDpkX4HLhuQgoUqEBrSiK2FYG.jpg");
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

sidebar_css = """
<style>
[data-testid="stSidebar"] {
    background-color: #E0E0E0; 
    opacity: 0.95;
}

[data-testid="stSidebar"] button {
    background-color: #000099; 
    color: white; 
    border: 1px solid #0000CC; 
}

[data-testid="stSidebar"] button:hover {
    background-color: #66B2FF; 
    color: white; 
}

[data-testid="stSidebar"] button:focus {
    background-color: white; 
    color: black; 
}
</style>
"""

st.markdown(sidebar_css, unsafe_allow_html=True)

st.sidebar.markdown('<p class="sidebar-title">Navigation</p>', unsafe_allow_html=True)
if st.sidebar.button('Main Page'):
    st.session_state.page = "main"
if st.sidebar.button('About'):
    st.session_state.page = "about"
if st.sidebar.button('Our Mission'):
    st.session_state.page = "mission"

# display the appropriate page based on session state
if 'page' not in st.session_state:
    st.session_state.page = "main"  # default to main

if st.session_state.page == "main":
    main_page()
if st.session_state.page == "about":
    about_page()
if st.session_state.page == "mission":
    mission_page()
