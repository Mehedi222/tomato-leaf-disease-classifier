import cv2
import matplotlib.cm as cm
import numpy as np
import streamlit as st
import tensorflow as tf
from PIL import Image
from tensorflow.keras.models import load_model
from tf_keras_vis.gradcam import Gradcam
from tf_keras_vis.utils.model_modifiers import ReplaceToLinear
from tf_keras_vis.utils.scores import CategoricalScore

from db import get_session
from imaging import make_thumbnail
from repository import log_prediction
from theme import CLASS_COLORS

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


st.title("Tomato Leaf Diseases Classification")

uploaded_file = st.file_uploader(
    "Choose an image...", type=["jpg", "jpeg", "png"], accept_multiple_files=False
)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    image = image.convert("RGB")
    image = image.resize((224, 224))
    st.image(image, caption="Uploaded Image", width=400)

    if st.button("Predict"):
        img_array = np.array(image, dtype="float32")

        with st.spinner("Predicting..."):
            predicted_class, confidence = predict(model, img_array)

        db_session = get_session()
        log_prediction(
            db_session,
            st.session_state["user"]["id"],
            predicted_class,
            confidence,
            make_thumbnail(image),
        )
        db_session.close()

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
