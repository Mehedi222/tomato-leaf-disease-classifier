from models import Prediction, User


def test_create_user_and_prediction(session):
    user = User(username="alice", password_hash="hashed", role="user")
    session.add(user)
    session.commit()

    prediction = Prediction(
        user_id=user.id,
        predicted_class="Healthy",
        confidence=91.2,
        image_thumbnail=b"fake-bytes",
    )
    session.add(prediction)
    session.commit()

    fetched = session.query(Prediction).first()
    assert fetched.predicted_class == "Healthy"
    assert fetched.confidence == 91.2
    assert fetched.user.username == "alice"
