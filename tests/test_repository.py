from datetime import datetime, timedelta

from models import User
from repository import (
    get_average_confidence,
    get_class_distribution,
    get_confidence_values,
    get_recent_predictions,
    get_today_count,
    get_total_count,
    get_user_predictions,
    log_prediction,
)


def _make_user(session, username="alice"):
    user = User(username=username, password_hash="x", role="user")
    session.add(user)
    session.commit()
    return user


def test_log_prediction_persists_row(session):
    user = _make_user(session)
    prediction = log_prediction(session, user.id, "Healthy", 91.5, b"thumb")

    assert prediction.id is not None
    assert get_total_count(session) == 1


def test_get_class_distribution_counts_by_class(session):
    user = _make_user(session)
    log_prediction(session, user.id, "Healthy", 90.0, b"t")
    log_prediction(session, user.id, "Healthy", 80.0, b"t")
    log_prediction(session, user.id, "Early Blight", 70.0, b"t")

    distribution = get_class_distribution(session)
    assert distribution == {"Healthy": 2, "Early Blight": 1}


def test_get_confidence_values_and_average(session):
    user = _make_user(session)
    log_prediction(session, user.id, "Healthy", 90.0, b"t")
    log_prediction(session, user.id, "Healthy", 80.0, b"t")

    values = get_confidence_values(session)
    assert sorted(values) == [80.0, 90.0]
    assert get_average_confidence(session) == 85.0


def test_get_average_confidence_returns_zero_when_empty(session):
    assert get_average_confidence(session) == 0.0


def test_get_recent_predictions_orders_newest_first(session):
    user = _make_user(session)
    first = log_prediction(session, user.id, "Healthy", 90.0, b"t")
    first.created_at = datetime.utcnow() - timedelta(hours=1)
    session.commit()
    second = log_prediction(session, user.id, "Leaf Spot", 70.0, b"t")

    recent = get_recent_predictions(session, limit=10)
    assert recent[0].id == second.id
    assert recent[1].id == first.id


def test_get_user_predictions_filters_by_user(session):
    alice = _make_user(session, "alice")
    bob = _make_user(session, "bob")
    log_prediction(session, alice.id, "Healthy", 90.0, b"t")
    log_prediction(session, bob.id, "Late Blight", 60.0, b"t")

    alice_predictions = get_user_predictions(session, alice.id)
    assert len(alice_predictions) == 1
    assert alice_predictions[0].predicted_class == "Healthy"


def test_get_today_count_excludes_past_predictions(session):
    user = _make_user(session)
    old = log_prediction(session, user.id, "Healthy", 90.0, b"t")
    old.created_at = datetime.utcnow() - timedelta(days=2)
    session.commit()
    log_prediction(session, user.id, "Healthy", 80.0, b"t")

    assert get_today_count(session) == 1
