import base64
import os

import cv2
import matplotlib.cm as cm
import numpy as np
import pandas as pd
import streamlit as st
import tensorflow as tf
from PIL import Image
from tensorflow.keras.models import load_model
from tf_keras_vis.gradcam import Gradcam
from tf_keras_vis.utils.model_modifiers import ReplaceToLinear
from tf_keras_vis.utils.scores import CategoricalScore

from admin_auth import check_admin_login
from imaging import make_thumbnail
from predictions_log import (
    get_average_confidence,
    get_class_distribution,
    get_confidence_series,
    get_connection,
    get_recent,
    get_total_count,
    init_db,
    log_prediction,
)
from theme import CLASS_COLORS, PRIMARY_COLOR

class_names = ["Early Blight", "Healthy", "Late Blight", "Leaf Spot"]


@st.cache_resource
def get_model():
    model = load_model("model/model.keras")
    return model


model = get_model()


def predict(model, image):
    if isinstance(image, tf.Tensor):
        img_array = image.numpy()
    else:
        img_array = image

    img_array = img_array.astype("float32")

    if len(img_array.shape) == 3:
        img_array = np.expand_dims(img_array, 0)

    predictions = model.predict(img_array, verbose=0)

    predicted_class = class_names[np.argmax(predictions[0])]
    confidence = round(100 * (np.max(predictions[0])), 2)
    return predicted_class, confidence


def get_gradcam_heatmap(model, image, class_index):
    if isinstance(image, tf.Tensor):
        image = image.numpy()

    replace2linear = ReplaceToLinear()
    score = CategoricalScore([class_index])
    gradcam = Gradcam(model, model_modifier=replace2linear, clone=True)

    cam = gradcam(score, image, penultimate_layer=-1)

    heatmap = np.uint8(cm.jet(cam[0])[..., :3] * 255)
    return heatmap


def render_predict():
    st.title("Tomato Leaf Diseases Classification")

    uploaded_file = st.file_uploader(
        "Choose an image...", type=["jpg", "jpeg", "png"], accept_multiple_files=False
    )

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        image = image.convert("RGB")
        image = image.resize((224, 224))
        st.image(image, caption="Uploaded Image", width=400)

        if st.button("Predict", type="primary"):
            img_array = np.array(image, dtype="float32")

            with st.spinner("Predicting..."):
                predicted_class, confidence = predict(model, img_array)

            conn = get_connection()
            log_prediction(conn, predicted_class, float(confidence), make_thumbnail(image))
            conn.close()

            class_color = CLASS_COLORS[predicted_class]
            st.markdown(
                f"## Predicted class: <span style='color:{class_color}'>*{predicted_class}*</span>",
                unsafe_allow_html=True,
            )
            st.write(f"## Confidence: {confidence:.2f}%")

            class_index = class_names.index(predicted_class)

            with st.spinner("Generating Grad-CAM visualization..."):
                img_batch = np.expand_dims(img_array, 0)
                heatmap = get_gradcam_heatmap(model, img_batch, class_index)

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Grad-CAM Heatmap")
                st.image(heatmap, width=400)

            with col2:
                st.subheader("Overlay")
                original_img = np.array(image).astype("float32")
                overlay = cv2.addWeighted(
                    original_img, 0.6, heatmap.astype("float32"), 0.4, 0
                )
                overlay = np.uint8(overlay)
                st.image(overlay, width=400)


def _thumbnail_data_url(thumbnail_bytes: bytes) -> str:
    encoded = base64.b64encode(thumbnail_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def render_admin_dashboard():
    st.title("Admin Dashboard")

    conn = get_connection()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Predictions", get_total_count(conn))
    with col2:
        st.metric("Average Confidence", f"{get_average_confidence(conn):.1f}%")

    st.subheader("Model Performance")
    st.metric("Final Validation Accuracy", "~96%")
    training_history_path = "assets/training_history.png"
    if os.path.exists(training_history_path):
        st.image(training_history_path, caption="Training history")
    else:
        st.info("Training history chart not found — add it at assets/training_history.png")

    st.subheader("Class Distribution")
    distribution = get_class_distribution(conn)
    if distribution:
        st.bar_chart(pd.Series(distribution, name="Count"), color=PRIMARY_COLOR)
    else:
        st.info("No predictions logged yet.")

    st.subheader("Confidence Over Time")
    series = get_confidence_series(conn)
    if series:
        times = [row["created_at"] for row in series]
        confidences = [row["confidence"] for row in series]
        st.line_chart(pd.Series(confidences, index=times, name="Confidence (%)"), color=PRIMARY_COLOR)
    else:
        st.info("No predictions logged yet.")

    st.subheader("Confidence Distribution")
    if series:
        confidence_values = [row["confidence"] for row in series]
        counts, bin_edges = np.histogram(confidence_values, bins=10)
        bin_labels = [f"{bin_edges[i]:.0f}-{bin_edges[i + 1]:.0f}" for i in range(len(bin_edges) - 1)]
        st.bar_chart(pd.Series(counts, index=bin_labels, name="Count"), color=PRIMARY_COLOR)
    else:
        st.info("No predictions logged yet.")

    st.subheader("Recent Predictions")
    recent = get_recent(conn, limit=20)
    if recent:
        rows = [
            {
                "Thumbnail": _thumbnail_data_url(row["thumbnail"]),
                "Class": row["predicted_class"],
                "Confidence": f"{row['confidence']:.1f}%",
                "Time": row["created_at"],
            }
            for row in recent
        ]
        recent_df = pd.DataFrame(rows, columns=["Thumbnail", "Class", "Confidence", "Time"])

        def _class_cell_style(class_name):
            return f"background-color: {CLASS_COLORS.get(class_name, '#FFFFFF')}; color: white"

        styled = recent_df.style.map(_class_cell_style, subset=["Class"])
        st.dataframe(
            styled,
            column_config={"Thumbnail": st.column_config.ImageColumn("Thumbnail")},
            width="stretch",
        )
    else:
        st.info("No predictions logged yet.")

    conn.close()


def render_admin_sidebar():
    with st.sidebar:
        with st.expander("Admin"):
            if st.session_state.get("is_admin"):
                st.write("Logged in as **admin**")
                if st.button("Logout"):
                    del st.session_state["is_admin"]
                    st.rerun()
            else:
                username = st.text_input("Username", key="admin_username_input")
                password = st.text_input("Password", type="password", key="admin_password_input")
                if st.button("Log in", key="admin_login_button"):
                    if check_admin_login(username, password):
                        st.session_state["is_admin"] = True
                        st.rerun()
                    else:
                        st.error("Invalid admin credentials")


_init_conn = get_connection()
init_db(_init_conn)
_init_conn.close()

render_admin_sidebar()

if st.session_state.get("is_admin"):
    predict_tab, admin_tab = st.tabs(["Predict", "Admin Dashboard"])
    with predict_tab:
        render_predict()
    with admin_tab:
        render_admin_dashboard()
else:
    render_predict()
