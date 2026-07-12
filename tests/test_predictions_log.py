import numpy as np

from predictions_log import (
    get_class_distribution,
    get_recent,
    get_total_count,
    log_prediction,
)


def test_log_prediction_persists_row(conn):
    log_prediction(conn, "Healthy", 91.5, b"thumb")
    assert get_total_count(conn) == 1


def test_get_total_count_returns_zero_when_empty(conn):
    assert get_total_count(conn) == 0


def test_get_class_distribution_counts_by_class(conn):
    log_prediction(conn, "Healthy", 90.0, b"t")
    log_prediction(conn, "Healthy", 80.0, b"t")
    log_prediction(conn, "Early Blight", 70.0, b"t")

    distribution = get_class_distribution(conn)
    assert distribution == {"Healthy": 2, "Early Blight": 1}


def test_get_recent_orders_newest_first_and_respects_limit(conn):
    log_prediction(conn, "Healthy", 90.0, b"t1")
    log_prediction(conn, "Early Blight", 70.0, b"t2")
    log_prediction(conn, "Leaf Spot", 60.0, b"t3")

    recent = get_recent(conn, limit=2)
    assert len(recent) == 2
    assert recent[0]["predicted_class"] == "Leaf Spot"
    assert recent[0]["thumbnail"] == b"t3"
    assert recent[1]["predicted_class"] == "Early Blight"


def test_log_prediction_coerces_numpy_confidence_to_float(conn):
    log_prediction(conn, "Healthy", np.float32(91.5), b"t")

    recent = get_recent(conn, limit=1)
    assert isinstance(recent[0]["confidence"], float)
    assert round(recent[0]["confidence"], 1) == 91.5
