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
from pdf2docx import Converter


def convert_pdf_to_word(pdf_path, output_path):
    try:

        cv = Converter(pdf_path)

        cv.convert(
            output_path,
            start=0,
            end=None,
            multi_processing=False,
            cpu_count=2
        )
        cv.close()

    except Exception as e:
        print(f"Failed to convert PDF to Word: {str(e)}")
        return False


def fetch_index_templates(bucket, firestore_db, doc_type="Proposal"):
    try:

        templates_ref = firestore_db.collection("index_templates").where("doc_type", "==", doc_type)
        templates = templates_ref.stream()

        downloaded_files = {}

        for doc in templates:
            data = doc.to_dict()
            filename = data.get("filename")
            order = data.get("order", 0)
            visible = data.get("visible", True)

            if not visible or not filename:
                continue

            try:

                blob = bucket.blob(f"index_templates/{filename}")
                if not blob.exists():
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
            downloaded_files[order] = temp_path

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
            pix = page.get_pixmap(dpi=150)
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
    st.rerun()


def prev_page():
    st.session_state.page -= 1
    st.rerun()


def proposal_session():
    if "proposal_templates" not in st.session_state:
        st.session_state.proposal_templates = fetch_proposal_templates(bucket, firestore_db)

    if "proposal_index_templates" not in st.session_state:
        st.session_state.proposal_index_templates = fetch_index_templates(bucket, firestore_db, doc_type="Proposal")

    if st.session_state.page == 1:
        st.title("Proposal PDF Generator")
        if not st.session_state.proposal_templates:
            st.warning("No Proposal templates found!")
        else:
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

                    input_pdf = st.session_state.proposal_templates[0]
                    output_pdf = os.path.join(tempfile.gettempdir(), f"page1_filled_{uuid.uuid4().hex}.pdf")
                    pdf_editor = EditTextFile(input_pdf)

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
        if not st.session_state.proposal_index_templates:
            st.warning("No index templates found!")
        else:
            template_options = {}
            for file in st.session_state.proposal_index_templates:
                filename = os.path.basename(file)
                order = filename.split('_')[2]
                display_name = f"Template {order}"
                template_options[display_name] = file

            selected_display = st.selectbox("Choose your Template", list(template_options.keys()))
            selected_pdf = template_options[selected_display]
            st.session_state.filled_page2 = selected_pdf

            if selected_pdf:
                st.image(get_pdf_preview(selected_pdf))
                st.write(f"You selected {selected_display}")
            else:
                st.write("No index Template available")

        col1, col2, col3 = st.columns([1, 8, 1])
        with col1:
            if st.button("Previous"):
                prev_page()
        with col3:
            if st.button("Next"):
                next_page()

    elif st.session_state.page == 3:

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
        word_file = "proposal.docx"
        conversion_success = convert_pdf_to_word(pdf_file, word_file)

        if all_pages:
            # for i, img in enumerate(all_pages):
            #     st.image(img, caption=f"Page {i + 1}", use_column_width=True)
            st.image(all_pages, use_container_width=True)
            # use_container_width = True
        else:
            st.warning("No pages found or unable to render PDF.")

        col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
        with col1:
            if st.button("Previous"):
                prev_page()
        with col3:
            # if conversion_success:
            with open(word_file, "rb") as f:
                st.download_button(
                    label="Download as Word",
                    data=f,
                    file_name="proposal.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        with col4:
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="Download as PDF",
                    data=f,
                    file_name="proposal.pdf",
                    mime="application/pdf"
                )


