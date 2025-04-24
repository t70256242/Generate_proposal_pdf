import pyrebase
import os
from dotenv import load_dotenv
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage

load_dotenv()


firebaseConfig = {
    "apiKey": st.secrets["API_KEY"],
    "authDomain": st.secrets["AUTH_DOMAIN"],
    "databaseURL": st.secrets["DATABASE_URL"],
    "projectId": st.secrets["PROJECT_ID"],
    "storageBucket": st.secrets["STORAGE_BUCKET"],
    "messagingSenderId": st.secrets["MESSAGING_SENDER_ID"],
    "appId": st.secrets["APP_ID"],
    "measurementId": st.secrets["MEASUREMENT_ID"]
}

# firebaseConfig = {
#     "apiKey": os.getenv("API_KEY"),
#     "authDomain": os.getenv("AUTH_DOMAIN"),
#     "databaseURL": os.getenv("DATABASE_URL"),
#     "projectId": os.getenv("PROJECT_ID"),
#     "storageBucket": os.getenv("STORAGE_BUCKET"),
#     "messagingSenderId": os.getenv("MESSAGING_SENDER_ID"),
#     "appId": os.getenv("APP_ID"),
#     "measurementId": os.getenv("MEASUREMENT_ID")
# }

# firebase_credentials = {
#     "type": os.getenv("FIREBASE_TYPE"),
#     "project_id": os.getenv("FIREBASE_PROJECT_ID"),
#     "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
#     "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
#     "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
#     "client_id": os.getenv("FIREBASE_CLIENT_ID"),
#     "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
#     "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
#     "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
#     "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
# }

# firebase_credentials = {
#     "type": st.secrets["firebase"]["type"],
#     "project_id": st.secrets["firebase"]["project_id"],
#     "private_key_id": st.secrets["firebase"]["private_key_id"],
#     "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
#     "client_email": st.secrets["firebase"]["client_email"],
#     "client_id": st.secrets["firebase"]["client_id"],
#     "auth_uri": st.secrets["firebase"]["auth_uri"],
#     "token_uri": st.secrets["firebase"]["token_uri"],
#     "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
#     "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
# }
firebase_credentials = {
    "type": st.secrets["firebase"]["type"],
    "project_id": st.secrets["firebase"]["project_id"],
    "private_key_id": st.secrets["firebase"]["private_key_id"],
    "private_key": st.secrets["firebase"]["private_key"],  # <- no replace() here
    "client_email": st.secrets["firebase"]["client_email"],
    "client_id": st.secrets["firebase"]["client_id"],
    "auth_uri": st.secrets["firebase"]["auth_uri"],
    "token_uri": st.secrets["firebase"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
}


cred = credentials.Certificate(firebase_credentials)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("STORAGE_BUCKET") or "proposal-pdf-generator.firebasestorage.app"
    })

# Initialize services

bucket = storage.bucket("proposal-pdf-generator.firebasestorage.app")
firestore_db = firestore.client()  # Firestore database

# Initialize Pyrebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()  # Authentication
rt_db = firebase.database()  # Realtime Database



# # Check if files exist in Storage
# test_blob = bucket.blob("index_templates/Proposal/template_1.pdf")
# print("File exists in storage:", test_blob.exists())
