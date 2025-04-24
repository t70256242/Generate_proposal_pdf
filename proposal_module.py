import time
import os
from datetime import datetime
import streamlit as st
import pycountry
import fitz
from PIL import Image
from cross_plat import EditTextFile
from merge_pdf import Merger
from firebase_config import auth, rt_db, bucket, firestore_db
import tempfile
import os
import uuid


def fetch_index_templates(bucket, firestore_db, doc_type="Proposal"):
    try:
        # Query index templates from Firestore
        templates_ref = firestore_db.collection("index_templates").where("doc_type", "==", doc_type)
        templates = templates_ref.stream()


        downloaded_files = {}

        for doc in templates:
            data = doc.to_dict()
            filename = data.get("filename")
            order = data.get("order", 0)
            visible = data.get("visible", True)

            # Skip if not visible or no filename
            if not visible or not filename:
                continue

            try:
                # Download from index_templates storage
                blob = bucket.blob(f"index_templates/{filename}")
                if not blob.exists():  # Check if file exists in storage
                    st.warning(f"File not found in storage: {filename}")
                    continue

                temp_filename = f"index_order_{order}_{uuid.uuid4().hex}.pdf"
                temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
                blob.download_to_filename(temp_path)
                downloaded_files[order] = temp_path

            except Exception as e:
                st.error(f"Failed to download {filename}: {str(e)}")
                continue

        return [downloaded_files[key] for key in sorted(downloaded_files.keys())]

    except Exception as e:
        st.error(f"Failed to fetch index templates: {str(e)}")
        return []

def fetch_proposal_templates(bucket, firestore_db):
    try:
        # Query templates with doc_type "Proposal"
        templates_ref = firestore_db.collection("templates").where("doc_type", "==", "Proposal")
        templates = templates_ref.stream()

        downloaded_files = {}

        for doc in templates:
            data = doc.to_dict()
            filename = data.get("filename")
            order = data.get("order", 0)

            if not filename:
                continue

            blob = bucket.blob(f"pdf_templates/{filename}")
            temp_filename = f"template_order_{order}_{uuid.uuid4().hex}.pdf"
            temp_path = os.path.join(tempfile.gettempdir(), temp_filename)

            blob.download_to_filename(temp_path)

            # Store by order for consistent sorting
            downloaded_files[order] = temp_path

        # Return list of file paths sorted by order
        return [downloaded_files[key] for key in sorted(downloaded_files.keys())]

    except Exception as e:
        st.error(f"Failed to download proposal templates: {e}")
        return []


def get_pdf_preview(file_path):
    doc = fitz.open(file_path)
    page = doc[0]
    pixmap = page.get_pixmap()
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    return image


def render_all_pdf_pages(pdf_path):
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(dpi=150)  # Higher DPI = better quality
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        return images
    except Exception as e:
        st.error(f"Error rendering PDF: {e}")
        return []


def get_merged_pdf_preview(file_path, page_num=3):
    try:
        doc = fitz.open(file_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        st.error(f"Failed to load PDF: {e}")
        return None


def next_page():
    st.session_state.page += 1
    # st.rerun()
    st.experimental_rerun()


def prev_page():
    st.session_state.page -= 1
    # st.rerun()
    st.experimental_rerun()


def proposal_session():
    if "proposal_templates" not in st.session_state:
        st.session_state.proposal_templates = fetch_proposal_templates(bucket, firestore_db)
        # st.write("Proposal templates loaded:", len(st.session_state.proposal_templates))

    if "proposal_index_templates" not in st.session_state:
        # st.session_state.proposal_index_templates = fetch_index_templates(bucket, firestore_db, doc_type="Proposal")
        st.session_state.proposal_index_templates = fetch_index_templates(bucket, firestore_db, doc_type="Proposal")
        st.write("Index templates loaded:", len(st.session_state.proposal_index_templates))
        # st.write("Index template paths:", st.session_state.proposal_index_templates)

    # for path in st.session_state.proposal_templates:
    #     print(path)
    # print(f"state_1: {st.session_state.proposal_templates[0]}")

    if st.session_state.page == 1:
        st.title("Proposal PDF Generator")
        with st.form("Get Started"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            countries = sorted([country.name for country in pycountry.countries])
            country = st.selectbox("Select Country", countries)
            date = st.date_input("Date")
            submitted = st.form_submit_button("Next")
            if submitted:
                formatted_date = date.strftime("%d %B %Y")
                # call template_1 of the Proposal directory
                # pdf_editor = EditTextFile("Page1_template.pdf")
                # pdf_editor = EditTextFile(st.session_state.proposal_templates[0])
                input_pdf = st.session_state.proposal_templates[0]
                output_pdf = os.path.join(tempfile.gettempdir(), f"page1_filled_{uuid.uuid4().hex}.pdf")
                pdf_editor = EditTextFile(input_pdf)

                # output_pdf = "pdf_list/Page1.pdf"
                # output_pdf = st.session_state.proposal_templates[0]

                modifications = {
                    "Name:": f": {name}",
                    "Email:": f": {email}",
                    "Phone": f": {phone}",
                    "Country": f": {country}",
                    "14 April 2025": f"{formatted_date}"
                }
                pdf_editor.modify_pdf_fields(output_pdf, modifications, 8)
                st.session_state.filled_page1 = output_pdf
                next_page()

    elif st.session_state.page == 2:
        st.title("Select Index Page Style")
        # pdf_file = ["pdf_list/Page2.pdf", "pdf_list/Page2.pdf", "pdf_list/Page2.pdf"]
        # st.write("Available index templates:", st.session_state.proposal_index_templates)
        if not st.session_state.proposal_index_templates:
            st.warning("No index templates found! Check the following:")
            # st.write("1. Verify you have documents in the 'index_templates' collection")
            # st.write("2. Check the 'doc_type' field is set to 'Proposal'")
            # st.write("3. Ensure the 'visible' field is True")
            # st.write("4. Confirm files exist in Storage under 'index_templates/Proposal/'")
        else:
            pdf_previews = {file: get_pdf_preview(file) for file in st.session_state.proposal_index_templates}
            selected_pdf = st.selectbox("Choose your Template", list(pdf_previews.keys()))
            st.session_state.filled_page2 = selected_pdf

            if selected_pdf:
                st.image(pdf_previews[selected_pdf])
                st.write(f"You selected {selected_pdf}")

        # pdf_previews = {file: get_pdf_preview(file) for file in st.session_state.proposal_index_templates}
        # selected_pdf = st.selectbox("Choose your Template", list(pdf_previews.keys()))
        # st.session_state.filled_page2 = selected_pdf
        #
        # if selected_pdf:
        #     st.image(pdf_previews[selected_pdf])
        #     st.write(f"You selected {selected_pdf}")
        # else:
        #     st.write("No index Template available")

        if st.button("Next"):
            next_page()
        if st.button("Previous"):
            prev_page()

        # if st.button("Next", on_click=next_page):  # Use on_click parameter
        #     pass  # The callback already handles the navigation
        #
        # if st.button("Previous", on_click=prev_page):
        #     pass

    elif st.session_state.page == 3:

        # directory = "pdf_list"
        # file_list = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(".pdf")]
        file_list = [
            st.session_state.filled_page1,
            st.session_state.filled_page2,
            *st.session_state.proposal_templates[2:]
        ]

        rino_p = Merger(file_list)
        pdf_file = "merged(1-6)_preview.pdf"
        rino_p.merge_pdf_files(pdf_file)
        st.title("📄 Full Proposal Preview")

        all_pages = render_all_pdf_pages(pdf_file)

        if all_pages:
            # for i, img in enumerate(all_pages):
            #     st.image(img, caption=f"Page {i + 1}", use_column_width=True)
            st.image(all_pages, use_column_width=True)
            # use_container_width = True
        else:
            st.warning("No pages found or unable to render PDF.")

        with open(pdf_file, "rb") as f:
            pdf_bytes = f.read()

        # col1, col2 = st.columns([1, 1])
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("Previous"):
                prev_page()
        with col3:
            st.download_button(
                label="Download Proposal",
                data=pdf_bytes,
                file_name="proposal.pdf",
                mime="application/pdf"
            )
            # if st.button("Next"):
            #     next_page()
