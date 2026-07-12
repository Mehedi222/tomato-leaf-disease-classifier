from datetime import datetime

from models import Prediction


def log_prediction(session, user_id, predicted_class, confidence, thumbnail) -> Prediction:
    prediction = Prediction(
        user_id=user_id,
        predicted_class=predicted_class,
        confidence=confidence,
        image_thumbnail=thumbnail,
    )
    session.add(prediction)
    session.commit()
    return prediction


def _apply_filters(query, start_date=None, end_date=None, predicted_class=None):
    if start_date is not None:
        query = query.filter(Prediction.created_at >= start_date)
    if end_date is not None:
        query = query.filter(Prediction.created_at <= end_date)
    if predicted_class is not None:
        query = query.filter(Prediction.predicted_class == predicted_class)
    return query


def get_total_count(session, start_date=None, end_date=None, predicted_class=None) -> int:
    query = _apply_filters(session.query(Prediction), start_date, end_date, predicted_class)
    return query.count()


def get_today_count(session) -> int:
    today = datetime.utcnow().date()
    return get_total_count(session, start_date=today)


def get_class_distribution(session, start_date=None, end_date=None) -> dict:
    query = _apply_filters(session.query(Prediction), start_date, end_date)
    counts = {}
    for prediction in query.all():
        counts[prediction.predicted_class] = counts.get(prediction.predicted_class, 0) + 1
    return counts


def get_confidence_values(session, start_date=None, end_date=None, predicted_class=None) -> list:
    query = _apply_filters(session.query(Prediction), start_date, end_date, predicted_class)
    return [p.confidence for p in query.all()]


def get_average_confidence(session, start_date=None, end_date=None, predicted_class=None) -> float:
    values = get_confidence_values(session, start_date, end_date, predicted_class)
    if not values:
        return 0.0
    return sum(values) / len(values)


def get_recent_predictions(session, limit=50, start_date=None, end_date=None, predicted_class=None) -> list:
    query = _apply_filters(session.query(Prediction), start_date, end_date, predicted_class)
    return query.order_by(Prediction.created_at.desc()).limit(limit).all()


def get_user_predictions(session, user_id, limit=50) -> list:
    return (
        session.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
