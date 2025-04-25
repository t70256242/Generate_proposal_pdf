import streamlit as st
from firebase_admin import firestore
import fitz
from PIL import Image
import tempfile
import uuid
import os


def generate_pdf_preview(bucket, storage_path, is_index=False):
    try:
        # Determine the correct storage path based on whether it's an index or regular template
        prefix = "index_templates/" if is_index else "pdf_templates/"
        blob = bucket.blob(f"{prefix}{storage_path}")

        temp_filename = f"{uuid.uuid4()}.pdf"
        temp_path = os.path.join(tempfile.gettempdir(), temp_filename)

        # Download the file
        blob.download_to_filename(temp_path)
        try:
            doc = fitz.open(temp_path)
            if doc.page_count == 0:
                doc.close()
                os.unlink(temp_path)
                return None

            pix = doc[0].get_pixmap(dpi=100)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            os.unlink(temp_path)
            return img

        except Exception as e:
            try:
                os.unlink(temp_path)
            except:
                pass
            return f"Preview generation failed during rendering: {str(e)}"

    except Exception as e:
        return f"Preview generation failed: {str(e)}"


def render_upload_tab(bucket, firestore_db, user_email, document_types, is_index=False):
    template_type = "Index Template" if is_index else "Template"
    collection_name = "index_templates" if is_index else "templates"
    storage_prefix = "index_templates/" if is_index else "pdf_templates/"

    st.subheader(f"Upload New {template_type}")
    col1, col2 = st.columns(2)

    with col1:
        doc_type = st.selectbox("Document Type", document_types,
                                key=f"doc_type_select_{'index' if is_index else 'normal'}")
        template_name = st.text_input(f"{template_type} Name",
                                      placeholder=f"e.g. Clean {template_type} Layout",
                                      key=f"template_name_input_{'index' if is_index else 'normal'}")
        order = st.number_input("Display Order", min_value=1, step=1,
                                key=f"template_order_input_{'index' if is_index else 'normal'}")
        uploaded_file = st.file_uploader(f"Choose PDF {template_type}", type=["pdf"],
                                         key=f"template_uploader_{'index' if is_index else 'normal'}")

    with col2:
        if uploaded_file:
            st.info("Ready to upload:")
            st.write(f"📄 Type: {doc_type}")
            st.write(f"📎 File: {uploaded_file.name}")
            st.write(f"📝 {template_type} Name: {template_name}")
            st.write(f"🔢 Order: {order}")

            if st.button(f"✅ Upload {template_type}", key=f"upload_button_{'index' if is_index else 'normal'}"):

                if not template_name.strip():
                    st.warning("Please enter a template name.")
                else:
                    try:
                        # Test bucket connection
                        blob = bucket.blob("test_connection.txt")
                        blob.upload_from_string("connection test", content_type="text/plain")
                        blob.delete()

                        filename = f"template_{order}.pdf"
                        firebase_path = f"{storage_prefix}{doc_type}/{filename}"
                        blob = bucket.blob(firebase_path)

                        with st.spinner(f"Uploading {uploaded_file.name}..."):
                            blob.upload_from_file(uploaded_file, content_type="application/pdf")

                        firestore_db.collection(collection_name).add({
                            "doc_type": doc_type,
                            "filename": f"{doc_type}/{filename}",
                            "template_name": filename,
                            "order": int(order),
                            "visible": True,
                            "uploaded_at": firestore.SERVER_TIMESTAMP,
                            "uploaded_by": user_email
                        })

                        st.success(f"✅ Successfully uploaded to: {firebase_path}")
                        st.balloons()

                    except Exception as e:
                        st.error(f"❌ Upload failed: {str(e)}")


def render_template_expander(template_id, template_data, selected_for_delete, firestore_db, bucket, is_index=False):
    collection_name = "index_templates" if is_index else "templates"
    template_type = "Index Template" if is_index else "Template"

    with st.expander(f"{template_data['template_name']} (Order: {template_data.get('order', 0)})"):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Path:** `{template_data.get('filename', 'N/A')}`")

            uploaded_at = template_data.get('uploaded_at')
            if isinstance(uploaded_at, str):
                uploaded_display = uploaded_at
            elif hasattr(uploaded_at, 'strftime'):
                uploaded_display = uploaded_at.strftime('%Y-%m-%d %H:%M')
            else:
                uploaded_display = "Unknown date"

            st.write(f"**Uploaded:** {uploaded_display} by {template_data.get('uploaded_by', 'Unknown')}")

            # 🔍 PDF Preview
            st.write("**Preview:**")
            preview_result = generate_pdf_preview(bucket, template_data.get('filename'), is_index=is_index)
            if isinstance(preview_result, Image.Image):
                st.image(preview_result, use_container_width=True)
            else:
                st.warning(preview_result)

            # Visibility checkbox
            visibility_key = f"vis_{'index_' if is_index else ''}{template_id}"
            current_visibility = template_data.get("visible", True)
            new_visibility = st.checkbox("Visible to Users", value=current_visibility, key=visibility_key)
            if new_visibility != current_visibility:
                try:
                    firestore_db.collection(collection_name).document(template_id).update({"visible": new_visibility})
                    st.success("Visibility updated!")
                except Exception as e:
                    st.error(f"Failed to update visibility: {str(e)}")

        with col2:
            delete_key = f"delete_{'index_' if is_index else ''}{template_id}"
            if st.checkbox("🗑️ Select for Delete", key=delete_key):
                selected_for_delete.append(template_id)


def handle_bulk_delete(selected_ids, firestore_db, is_index=False):
    collection_name = "index_templates" if is_index else "templates"
    template_type = "Index Template" if is_index else "Template"

    with st.spinner("Deleting..."):
        for t_id in selected_ids:
            try:
                firestore_db.collection(collection_name).document(t_id).delete()
            except Exception as e:
                st.error(f"Failed to delete {template_type.lower()} {t_id}: {str(e)}")
        st.success(f"Deleted {len(selected_ids)} {template_type.lower()}{'s' if len(selected_ids) != 1 else ''}.")
        st.rerun()


def render_template_management_tab(firestore_db, document_types, bucket, is_index=False):
    from streamlit_sortables import sort_items

    collection_name = "index_templates" if is_index else "templates"
    template_type = "Index Template" if is_index else "Template"

    st.subheader(f"Existing {template_type}s")

    selected_doc_type = st.selectbox(f"Filter by Document Type",
                                     document_types,
                                     key=f"doc_type_filter_{'index' if is_index else 'normal'}")

    try:
        templates = list(firestore_db.collection(collection_name)
                         .where("doc_type", "==", selected_doc_type)
                         .stream())

        valid_templates = []
        for t in templates:
            try:
                t_data = t.to_dict()
                if t_data:
                    t_data['template_name'] = t_data.get('template_name', 'Untitled').encode('utf-8', 'ignore').decode(
                        'utf-8')
                    valid_templates.append((t.id, t_data))
            except Exception as e:
                st.warning(f"Skipping {template_type.lower()} due to error: {str(e)}")

        if not valid_templates:
            st.info(f"No {template_type.lower()}s found for document type '{selected_doc_type}'")
            return

        valid_templates.sort(key=lambda x: x[1].get('order', 0))
        selected_for_delete = []
        reorder_labels = []
        label_to_id_map = {}

        for t_id, t_data in valid_templates:
            label = f"{t_data['template_name']} (Order: {t_data.get('order', 0)})"
            reorder_labels.append(label)
            label_to_id_map[label] = t_id
            render_template_expander(t_id, t_data, selected_for_delete, firestore_db, bucket, is_index=is_index)

        if selected_for_delete:
            st.warning(
                f"{len(selected_for_delete)} {template_type.lower()}{'s' if len(selected_for_delete) != 1 else ''} selected for deletion")
            if st.button(f"⚠️ Confirm Delete Selected {template_type}s"):
                handle_bulk_delete(selected_for_delete, firestore_db, is_index=is_index)

        st.subheader(f"Reorder {template_type}s")
        st.caption(f"Drag and drop items to reorder within the selected document type")

        try:
            sorted_labels = sort_items(reorder_labels, direction="vertical")
            if sorted_labels != reorder_labels:
                if st.button(f"✅ Save New {template_type} Order"):
                    handle_template_reordering(sorted_labels, label_to_id_map, firestore_db, is_index=is_index)
        except Exception as e:
            st.error(f"Error in reordering: {str(e)}")

    except Exception as e:
        st.error(f"Error loading {template_type.lower()}s: {str(e)}")


def handle_template_reordering(sorted_labels, label_to_id_map, firestore_db, is_index=False):
    collection_name = "index_templates" if is_index else "templates"
    template_type = "Index Template" if is_index else "Template"

    with st.spinner("Updating order..."):
        for new_order, label in enumerate(sorted_labels, start=1):
            doc_id = label_to_id_map[label]
            try:
                firestore_db.collection(collection_name).document(doc_id).update({"order": new_order})
            except Exception as e:
                st.error(f"Failed to update order for {label}: {str(e)}")
        st.success(f"✅ {template_type} order saved!")


# def generate_pdf_preview(bucket, storage_path):
#     try:
#         # blob = bucket.blob(storage_path)
#         blob = bucket.blob(f"pdf_templates/{storage_path}")
#
#         temp_filename = f"{uuid.uuid4()}.pdf"
#         temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
#
#         # Download the file
#         blob.download_to_filename(temp_path)
#         try:
#             doc = fitz.open(temp_path)
#             if doc.page_count == 0:
#                 doc.close()
#                 os.unlink(temp_path)
#                 return None
#
#             pix = doc[0].get_pixmap(dpi=100)
#             img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
#             doc.close()
#
#             os.unlink(temp_path)
#             return img
#
#         except Exception as e:
#             try:
#                 os.unlink(temp_path)
#             except:
#                 pass
#             return f"Preview generation failed during rendering: {str(e)}"
#
#     except Exception as e:
#         return f"Preview generation failed: {str(e)}"
#
#
# def render_upload_tab(bucket, firestore_db, user_email, document_types):
#     st.subheader("Upload New Template")
#     col1, col2 = st.columns(2)
#
#     with col1:
#         doc_type = st.selectbox("Document Type", document_types, key="doc_type_select")
#         template_name = st.text_input("Template Name", placeholder="e.g. Clean Proposal Layout",
#                                       key="template_name_input")
#         order = st.number_input("Display Order", min_value=1, step=1, key="template_order_input")
#         uploaded_file = st.file_uploader("Choose PDF Template", type=["pdf"], key="template_uploader")
#
#     with col2:
#         if uploaded_file:
#             st.info("Ready to upload:")
#             st.write(f"📄 Type: {doc_type}")
#             st.write(f"📎 File: {uploaded_file.name}")
#             st.write(f"📝 Template Name: {template_name}")
#             st.write(f"🔢 Order: {order}")
#
#             if st.button("✅ Upload Template", key="upload_button"):
#
#                 if not template_name.strip():
#                     st.warning("Please enter a template name.")
#                 else:
#                     try:
#                         # Test bucket connection
#                         blob = bucket.blob("test_connection.txt")
#                         blob.upload_from_string("connection test", content_type="text/plain")
#                         blob.delete()
#
#                         filename = f"template_{order}.pdf"
#                         firebase_path = f"pdf_templates/{doc_type}/{filename}"
#                         blob = bucket.blob(firebase_path)
#
#                         with st.spinner(f"Uploading {uploaded_file.name}..."):
#                             blob.upload_from_file(uploaded_file, content_type="application/pdf")
#
#                         firestore_db.collection("templates").add({
#                             "doc_type": doc_type,
#                             "filename": f"{doc_type}/{filename}",
#                             "template_name": filename,
#                             "order": int(order),
#                             "visible": True,
#                             "uploaded_at": firestore.SERVER_TIMESTAMP,
#                             "uploaded_by": user_email
#                         })
#
#                         st.success(f"✅ Successfully uploaded to: {firebase_path}")
#                         st.balloons()
#
#                     except Exception as e:
#                         st.error(f"❌ Upload failed: {str(e)}")
#
#
# def render_template_expander(template_id, template_data, selected_for_delete, firestore_db, bucket):
#     with st.expander(f"{template_data['template_name']} (Order: {template_data.get('order', 0)})"):
#         col1, col2 = st.columns([3, 1])
#         with col1:
#             st.write(f"**Path:** `{template_data.get('filename', 'N/A')}`")
#
#             uploaded_at = template_data.get('uploaded_at')
#             if isinstance(uploaded_at, str):
#                 uploaded_display = uploaded_at
#             elif hasattr(uploaded_at, 'strftime'):
#                 uploaded_display = uploaded_at.strftime('%Y-%m-%d %H:%M')
#             else:
#                 uploaded_display = "Unknown date"
#
#             st.write(f"**Uploaded:** {uploaded_display} by {template_data.get('uploaded_by', 'Unknown')}")
#
#             # 🔍 PDF Preview
#             st.write("**Preview:**")
#             preview_result = generate_pdf_preview(bucket, template_data.get('filename'))
#             if isinstance(preview_result, Image.Image):
#                 st.image(preview_result, use_column_width=True)
#             else:
#                 st.warning(preview_result)
#
#             # Visibility checkbox
#             visibility_key = f"vis_{template_id}"
#             current_visibility = template_data.get("visible", True)
#             new_visibility = st.checkbox("Visible to Users", value=current_visibility, key=visibility_key)
#             if new_visibility != current_visibility:
#                 try:
#                     firestore_db.collection("templates").document(template_id).update({"visible": new_visibility})
#                     st.success("Visibility updated!")
#                 except Exception as e:
#                     st.error(f"Failed to update visibility: {str(e)}")
#
#         with col2:
#             delete_key = f"delete_{template_id}"
#             if st.checkbox("🗑️ Select for Delete", key=delete_key):
#                 selected_for_delete.append(template_id)
#
#
# def handle_bulk_delete(selected_ids, firestore_db):
#     with st.spinner("Deleting..."):
#         for t_id in selected_ids:
#             try:
#                 firestore_db.collection("templates").document(t_id).delete()
#             except Exception as e:
#                 st.error(f"Failed to delete template {t_id}: {str(e)}")
#         st.success(f"Deleted {len(selected_ids)} templates.")
#         st.experimental_rerun()
#
#
# def render_template_management_tab(firestore_db, document_types, bucket):
#     from streamlit_sortables import sort_items
#
#     st.subheader("Existing Templates")
#
#     selected_doc_type = st.selectbox("Filter by Document Type", document_types, key="doc_type_filter")
#
#     try:
#         templates = list(firestore_db.collection("templates")
#                          .where("doc_type", "==", selected_doc_type)
#                          .stream())
#
#         valid_templates = []
#         for t in templates:
#             try:
#                 t_data = t.to_dict()
#                 if t_data:
#                     t_data['template_name'] = t_data.get('template_name', 'Untitled').encode('utf-8', 'ignore').decode('utf-8')
#                     valid_templates.append((t.id, t_data))
#             except Exception as e:
#                 st.warning(f"Skipping template due to error: {str(e)}")
#
#         if not valid_templates:
#             st.info(f"No templates found for document type '{selected_doc_type}'")
#             return
#
#         valid_templates.sort(key=lambda x: x[1].get('order', 0))
#         selected_for_delete = []
#         reorder_labels = []
#         label_to_id_map = {}
#
#         for t_id, t_data in valid_templates:
#             label = f"{t_data['template_name']} (Order: {t_data.get('order', 0)})"
#             reorder_labels.append(label)
#             label_to_id_map[label] = t_id
#             # render_template_expander(t_id, t_data, selected_for_delete, firestore_db)
#             render_template_expander(t_id, t_data, selected_for_delete, firestore_db, bucket)
#
#         if selected_for_delete:
#             st.warning(f"{len(selected_for_delete)} templates selected for deletion")
#             if st.button("⚠️ Confirm Delete Selected Templates"):
#                 handle_bulk_delete(selected_for_delete, firestore_db)
#
#         st.subheader("Reorder Templates")
#         st.caption("Drag and drop items to reorder within the selected document type")
#
#         try:
#             sorted_labels = sort_items(reorder_labels, direction="vertical")
#             if sorted_labels != reorder_labels:
#                 if st.button("✅ Save New Order"):
#                     handle_template_reordering(sorted_labels, label_to_id_map, firestore_db)
#         except Exception as e:
#             st.error(f"Error in reordering: {str(e)}")
#
#     except Exception as e:
#         st.error(f"Error loading templates: {str(e)}")
#
#
# def handle_template_reordering(sorted_labels, label_to_id_map, firestore_db):
#     with st.spinner("Updating order..."):
#         for new_order, label in enumerate(sorted_labels, start=1):
#             doc_id = label_to_id_map[label]
#             try:
#                 firestore_db.collection("templates").document(doc_id).update({"order": new_order})
#             except Exception as e:
#                 st.error(f"Failed to update order for {label}: {str(e)}")
#         st.success("✅ Template order saved!")
