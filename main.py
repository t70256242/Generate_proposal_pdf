import time
import os
from datetime import datetime
import streamlit as st
from firebase_config import auth, rt_db, bucket, firestore_db
from firebase_admin import firestore
import pycountry
import fitz
from PIL import Image
from cross_plat import EditTextFile
from merge_pdf import Merger
from dotenv import load_dotenv
from proposal_module import proposal_session
from streamlit_sortables import sort_items
from admin_module import render_upload_tab, render_template_management_tab


def login():
    st.sidebar.subheader("Admin Login")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.user = user
            st.sidebar.success("Login successful!")
            st.rerun()

        except Exception as e:
            st.sidebar.error(f"Login failed: {str(e)}")


def logout():
    st.session_state.user = None
    st.sidebar.success("Logged out successfully!")
    st.rerun()


def admin_panel():
    st.header("📤 Admin Dashboard")

    if st.sidebar.button("🚪 Logout"):
        logout()

    tab1, tab2, tab3, tab4 = st.tabs([
        "📤 Upload Templates",
        "📋 Template Management",
        "📇 Upload Index Templates",
        "📑 Index Template Management"
    ])

    with tab1:
        render_upload_tab(bucket, firestore_db, st.session_state.user["email"], DOCUMENT_TYPES)

    with tab2:
        render_template_management_tab(firestore_db, DOCUMENT_TYPES, bucket)

    with tab3:
        render_upload_tab(bucket, firestore_db, st.session_state.user["email"], DOCUMENT_TYPES, is_index=True)

    with tab4:
        render_template_management_tab(firestore_db, DOCUMENT_TYPES, bucket, is_index=True)


DOCUMENT_TYPES = [
    "Proposal",
    "NDA",
    "Contract",
    "Invoice",
    "Pricing List",
    "Hiring Contract",
    "Receipt Generator",
    "Retainer Agreement",
    "API Access Agreement",
    "Maintenance Agreement"
]

if "document_type" not in st.session_state:
    st.session_state.document_type = "Proposal"


if "page" not in st.session_state:
    st.session_state.page = 1

if "user" not in st.session_state:
    st.session_state.user = None

page_1_pdf = None


st.sidebar.title("📑 Document Types")
st.session_state.document_type = st.sidebar.selectbox("Choose a document type", DOCUMENT_TYPES)
st.sidebar.title("🔐 Admin Panel")
is_admin = st.sidebar.checkbox("I'm an admin")


if st.session_state.document_type == "Proposal":
    proposal_session()

if is_admin:
    if st.session_state.user:

        try:
            user = auth.get_account_info(st.session_state.user['idToken'])
            email = user['users'][0]['email']

            if email in st.secrets["custom"]["ADMIN_EMAILS"]:
                admin_panel()
            else:
                st.sidebar.error("Not an admin account")
                logout()

        except Exception as e:
            st.sidebar.error(f"Session expired: {str(e)}")
            logout()
    else:
        login()


