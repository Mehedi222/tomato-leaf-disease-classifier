import plotly.express as px
import streamlit as st

from db import get_session
from repository import get_user_predictions
from theme import PRIMARY_COLOR

st.title("My Prediction History")

session = get_session()
user_id = st.session_state["user"]["id"]
predictions = get_user_predictions(session, user_id, limit=50)

with st.container(border=True):
    st.metric("Total Predictions", len(predictions))

if predictions:
    ordered = list(reversed(predictions))
    fig = px.line(
        x=[p.created_at for p in ordered],
        y=[p.confidence for p in ordered],
        labels={"x": "Time", "y": "Confidence (%)"},
        template="plotly_white",
        color_discrete_sequence=[PRIMARY_COLOR],
    )
    st.plotly_chart(fig, use_container_width=True)

    rows = [
        {
            "Class": p.predicted_class,
            "Confidence": f"{p.confidence:.1f}%",
            "Time": p.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for p in predictions
    ]
    st.dataframe(rows, use_container_width=True)
else:
    st.info("You haven't made any predictions yet.")

session.close()
