from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from db import get_session
from repository import (
    get_average_confidence,
    get_class_distribution,
    get_confidence_values,
    get_recent_predictions,
    get_today_count,
    get_total_count,
)
from theme import CLASS_COLORS, PRIMARY_COLOR

st.title("Admin Dashboard")

session = get_session()

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.metric("Total Predictions", get_total_count(session))
with col2:
    with st.container(border=True):
        st.metric("Average Confidence", f"{get_average_confidence(session):.1f}%")
with col3:
    with st.container(border=True):
        st.metric("Predictions Today", get_today_count(session))

st.subheader("Filters")
default_range = (datetime.utcnow().date() - timedelta(days=30), datetime.utcnow().date())
date_range = st.date_input("Date range", value=default_range)
class_filter = st.selectbox("Class", ["All", "Early Blight", "Healthy", "Late Blight", "Leaf Spot"])

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = date_range, date_range
selected_class = None if class_filter == "All" else class_filter

st.subheader("Class Distribution")
distribution = get_class_distribution(session, start_date=start_date, end_date=end_date)
if distribution:
    class_names_list = list(distribution.keys())
    fig = px.pie(
        names=class_names_list,
        values=list(distribution.values()),
        color=class_names_list,
        color_discrete_map=CLASS_COLORS,
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No predictions in this range yet.")

st.subheader("Confidence Distribution")
confidence_values = get_confidence_values(
    session, start_date=start_date, end_date=end_date, predicted_class=selected_class
)
if confidence_values:
    fig = px.histogram(
        x=confidence_values,
        nbins=20,
        labels={"x": "Confidence (%)"},
        template="plotly_white",
        color_discrete_sequence=[PRIMARY_COLOR],
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No predictions in this range yet.")

st.subheader("Recent Predictions")
recent = get_recent_predictions(
    session, limit=50, start_date=start_date, end_date=end_date, predicted_class=selected_class
)
rows = [
    {
        "Username": p.user.username,
        "Class": p.predicted_class,
        "Confidence": f"{p.confidence:.1f}%",
        "Time": p.created_at.strftime("%Y-%m-%d %H:%M"),
    }
    for p in recent
]
recent_df = pd.DataFrame(rows, columns=["Username", "Class", "Confidence", "Time"])


def _class_cell_style(class_name):
    return f"background-color: {CLASS_COLORS.get(class_name, '#FFFFFF')}; color: white"


styled = recent_df.style.map(_class_cell_style, subset=["Class"])
st.dataframe(styled, use_container_width=True)

session.close()
