# Admin Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add prediction logging (DB-backed) plus a role-gated, top-navbar admin dashboard (total predictions, class distribution, confidence distribution/average, recent predictions table) and a per-user history page to the existing Tomato Leaf Disease Streamlit app, styled with a consistent neutral-dashboard theme and semantic per-class colors.

**Architecture:** Direct DB integration (Approach A from `plan.md`) — the Streamlit app writes prediction rows straight to the database after each `predict()` call; a new `main.py` entry point handles login and renders a role-based top navbar (`st.navigation(pages, position="top")`) that swaps between the Predict page, My History page, and (admin-only) Admin Dashboard page. See `plan.md`'s "Admin Dashboard — আর্কিটেকচার ডিজাইন" section for the approved functional design, and `docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md` for the approved visual design this plan implements.

**Tech Stack:** SQLAlchemy ORM, bcrypt (password hashing), Plotly (charts), pytest (business-logic tests), Streamlit `st.navigation`/`st.Page`, Streamlit native theming (`.streamlit/config.toml`).

## Global Constraints

- Python 3.11/3.12 (per README prerequisite) — use the project's existing `.venv` (`.venv/Scripts/python.exe` on this Windows machine).
- New dependencies added to `requirements.txt`: `sqlalchemy`, `psycopg2-binary`, `bcrypt`, `plotly`, `pytest`, `python-dotenv`.
- `DATABASE_URL` env var (loaded via `python-dotenv` from a local `.env` file) controls the DB target. Defaults to `sqlite:///tomato_app.db` when unset — this lets every task in this plan run and be tested locally on this machine (no Postgres/Docker installed here). Production deployments set `DATABASE_URL` to a real Postgres connection string per `plan.md`'s approved design; no code change is needed to switch — SQLAlchemy abstracts the driver.
- No ground-truth accuracy tracking — confidence-only metrics, per the approved design in `plan.md`.
- Class name order is load-bearing and must stay exactly: `["Early Blight", "Healthy", "Late Blight", "Leaf Spot"]` (matches existing `App.py` and the model's output order).
- Visual design tokens (colors, semantic class-color mapping) are defined once in `theme.py` and `.streamlit/config.toml` per `docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md` — every page imports from `theme.py` rather than hardcoding hex values. Dark mode is explicitly out of scope for this plan.
- The existing Grad-CAM/predict logic in `App.py` must remain behaviorally unchanged when moved to `pages/predict_page.py` — only the DB logging call and the result-text color are new.
- **Testing scope**: pure-Python modules (DB models, auth, repository/query functions, thumbnail helper) get pytest unit tests with an in-memory SQLite fixture. The Streamlit UI files themselves (`main.py`, `pages/*.py`) are verified manually in Task 10 (run the app, click through both roles) — Streamlit's `AppTest` does not reliably simulate `st.navigation` page-switching or the file-upload → Grad-CAM flow, so forcing brittle automated UI tests there would be false confidence, not real coverage.

---

### Task 1: Database models and engine

**Files:**
- Modify: `requirements.txt`
- Create: `db.py`
- Create: `models.py`
- Create: `.env.example`
- Create: `tests/conftest.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `models.Base` (SQLAlchemy declarative base), `models.User` (columns: `id`, `username`, `password_hash`, `role`, `created_at`; relationship `predictions`), `models.Prediction` (columns: `id`, `user_id`, `predicted_class`, `confidence`, `image_thumbnail`, `created_at`; relationship `user`).
- Produces: `db.init_db()` (creates all tables), `db.get_session()` (returns a new SQLAlchemy `Session`).
- Produces: `tests/conftest.py` fixture `session` (function-scoped, in-memory SQLite `Session`) — used by every later test file.

- [ ] **Step 1: Add new dependencies to `requirements.txt`**

Append to the existing file (keep all current lines):
```
sqlalchemy
psycopg2-binary
bcrypt
plotly
pytest
python-dotenv
```

- [ ] **Step 2: Install the new dependencies into the project venv**

Run: `.venv/Scripts/python.exe -m pip install -r requirements.txt`
Expected: all packages listed above install without error.

- [ ] **Step 3: Write `models.py`**

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="user")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    predicted_class = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    image_thumbnail = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="predictions")
```

- [ ] **Step 4: Write `db.py`**

```python
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tomato_app.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    return SessionLocal()
```

- [ ] **Step 5: Write `.env.example`**

```
DATABASE_URL=postgresql://tomato_user:tomato_pass@localhost:5432/tomato_db
```

- [ ] **Step 6: Write `tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    db_session = TestSession()
    yield db_session
    db_session.close()
```

- [ ] **Step 7: Write the failing test `tests/test_models.py`**

```python
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
```

- [ ] **Step 8: Run the test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models'` (files not created yet) — if Steps 3/6 above are already saved, instead run this *before* saving them to confirm the fail; since steps are ordered, at this point the file should already exist, so instead confirm PASS here (see Step 9).

- [ ] **Step 9: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py -v`
Expected: `1 passed`

- [ ] **Step 10: Commit**

```bash
git add requirements.txt db.py models.py .env.example tests/conftest.py tests/test_models.py
git commit -m "feat: add SQLAlchemy models and DB session setup"
```

---

### Task 2: Auth utilities

**Files:**
- Create: `auth_utils.py`
- Test: `tests/test_auth_utils.py`

**Interfaces:**
- Consumes: `models.User` (Task 1).
- Produces: `auth_utils.hash_password(password: str) -> str`, `auth_utils.verify_password(password: str, password_hash: str) -> bool`, `auth_utils.create_user(session, username: str, password: str, role: str = "user") -> User`, `auth_utils.authenticate(session, username: str, password: str) -> User | None`.

- [ ] **Step 1: Write the failing tests `tests/test_auth_utils.py`**

```python
from auth_utils import authenticate, create_user, hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_authenticate_returns_user_for_correct_credentials(session):
    create_user(session, "alice", "secret123", role="admin")
    user = authenticate(session, "alice", "secret123")
    assert user is not None
    assert user.username == "alice"
    assert user.role == "admin"


def test_authenticate_returns_none_for_wrong_password(session):
    create_user(session, "alice", "secret123", role="admin")
    assert authenticate(session, "alice", "wrong") is None


def test_authenticate_returns_none_for_unknown_user(session):
    assert authenticate(session, "nobody", "secret123") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_utils'`

- [ ] **Step 3: Write `auth_utils.py`**

```python
import bcrypt

from models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(session, username: str, password: str, role: str = "user") -> User:
    user = User(username=username, password_hash=hash_password(password), role=role)
    session.add(user)
    session.commit()
    return user


def authenticate(session, username: str, password: str) -> User | None:
    user = session.query(User).filter_by(username=username).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth_utils.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add auth_utils.py tests/test_auth_utils.py
git commit -m "feat: add password hashing and authentication helpers"
```

---

### Task 3: Seed admin script

**Files:**
- Create: `seed_admin.py`
- Test: `tests/test_seed_admin.py`

**Interfaces:**
- Consumes: `db.init_db`, `db.get_session` (Task 1), `auth_utils.create_user` (Task 2).
- Produces: `seed_admin.seed_admin(session, username: str, password: str) -> User` (raises `ValueError` if username already exists).

- [ ] **Step 1: Write the failing tests `tests/test_seed_admin.py`**

```python
import pytest

from models import User
from seed_admin import seed_admin


def test_seed_admin_creates_admin_role(session):
    user = seed_admin(session, "root", "adminpass123")
    assert user.role == "admin"
    stored = session.query(User).filter_by(username="root").first()
    assert stored is not None
    assert stored.password_hash != "adminpass123"


def test_seed_admin_rejects_duplicate_username(session):
    seed_admin(session, "root", "adminpass123")
    with pytest.raises(ValueError):
        seed_admin(session, "root", "otherpass")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seed_admin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'seed_admin'`

- [ ] **Step 3: Write `seed_admin.py`**

```python
import getpass

from auth_utils import create_user
from db import get_session, init_db
from models import User


def seed_admin(session, username: str, password: str) -> User:
    existing = session.query(User).filter_by(username=username).first()
    if existing is not None:
        raise ValueError(f"User '{username}' already exists")
    return create_user(session, username, password, role="admin")


def main():
    init_db()
    session = get_session()
    username = input("Admin username: ")
    password = getpass.getpass("Admin password: ")
    user = seed_admin(session, username, password)
    print(f"Created admin user '{user.username}' (id={user.id})")
    session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_seed_admin.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add seed_admin.py tests/test_seed_admin.py
git commit -m "feat: add CLI script to seed the first admin user"
```

---

### Task 4: Thumbnail helper and prediction repository

**Files:**
- Create: `imaging.py`
- Create: `repository.py`
- Test: `tests/test_imaging.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `models.Prediction`, `models.User` (Task 1).
- Produces: `imaging.make_thumbnail(image: PIL.Image.Image, size: tuple[int, int] = (64, 64)) -> bytes`.
- Produces: `repository.log_prediction(session, user_id, predicted_class, confidence, thumbnail) -> Prediction`, `repository.get_total_count(session, start_date=None, end_date=None, predicted_class=None) -> int`, `repository.get_today_count(session) -> int`, `repository.get_class_distribution(session, start_date=None, end_date=None) -> dict`, `repository.get_confidence_values(session, start_date=None, end_date=None, predicted_class=None) -> list[float]`, `repository.get_average_confidence(session, start_date=None, end_date=None, predicted_class=None) -> float`, `repository.get_recent_predictions(session, limit=50, start_date=None, end_date=None, predicted_class=None) -> list[Prediction]`, `repository.get_user_predictions(session, user_id, limit=50) -> list[Prediction]`.

- [ ] **Step 1: Write the failing test `tests/test_imaging.py`**

```python
from io import BytesIO

from PIL import Image

from imaging import make_thumbnail


def test_make_thumbnail_returns_jpeg_bytes_within_bounds():
    image = Image.new("RGB", (224, 224), color=(255, 0, 0))
    thumb_bytes = make_thumbnail(image, size=(64, 64))

    assert isinstance(thumb_bytes, bytes)
    assert len(thumb_bytes) > 0

    result = Image.open(BytesIO(thumb_bytes))
    assert result.format == "JPEG"
    assert result.width <= 64
    assert result.height <= 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_imaging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'imaging'`

- [ ] **Step 3: Write `imaging.py`**

```python
from io import BytesIO

from PIL import Image


def make_thumbnail(image: Image.Image, size: tuple = (64, 64)) -> bytes:
    thumb = image.copy()
    thumb.thumbnail(size)
    buffer = BytesIO()
    thumb.convert("RGB").save(buffer, format="JPEG")
    return buffer.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_imaging.py -v`
Expected: `1 passed`

- [ ] **Step 5: Write the failing tests `tests/test_repository.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'repository'`

- [ ] **Step 7: Write `repository.py`**

```python
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
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_repository.py -v`
Expected: `7 passed`

- [ ] **Step 9: Commit**

```bash
git add imaging.py repository.py tests/test_imaging.py tests/test_repository.py
git commit -m "feat: add thumbnail helper and prediction query repository"
```

---

### Task 5: Theme tokens and Streamlit config

**Files:**
- Create: `.streamlit/config.toml`
- Create: `theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces: `theme.CLASS_COLORS` (dict mapping each of the 4 class names to a hex color string), `theme.PRIMARY_COLOR` (hex string) — consumed by `pages/predict_page.py` (Task 6), `pages/my_history_page.py` (Task 8), `pages/admin_dashboard_page.py` (Task 9).
- Values per `docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md`: base palette `#FFFFFF` background, `#F8F9FA` secondary background, `#E2E5E9` border, `#1F2933` text, `#C0392B` primary accent (tomato red); semantic class colors `Healthy=#2E7D32`, `Early Blight=#E1A100`, `Leaf Spot=#C9702C`, `Late Blight=#922B21`.

- [ ] **Step 1: Write the failing test `tests/test_theme.py`**

```python
from theme import CLASS_COLORS

EXPECTED_CLASSES = {"Early Blight", "Healthy", "Late Blight", "Leaf Spot"}


def test_class_colors_has_exactly_the_four_classes():
    assert set(CLASS_COLORS.keys()) == EXPECTED_CLASSES


def test_class_colors_are_hex_strings():
    for color in CLASS_COLORS.values():
        assert isinstance(color, str)
        assert color.startswith("#")
        assert len(color) == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_theme.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'theme'`

- [ ] **Step 3: Write `theme.py`**

```python
PRIMARY_COLOR = "#C0392B"
BACKGROUND_COLOR = "#FFFFFF"
SECONDARY_BACKGROUND_COLOR = "#F8F9FA"
BORDER_COLOR = "#E2E5E9"
TEXT_COLOR = "#1F2933"

CLASS_COLORS = {
    "Early Blight": "#E1A100",
    "Healthy": "#2E7D32",
    "Late Blight": "#922B21",
    "Leaf Spot": "#C9702C",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_theme.py -v`
Expected: `2 passed`

- [ ] **Step 5: Write `.streamlit/config.toml`**

```toml
[theme]
base = "light"
primaryColor = "#C0392B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F8F9FA"
textColor = "#1F2933"
borderColor = "#E2E5E9"
font = "sans-serif"
```

- [ ] **Step 6: Commit**

```bash
git add theme.py tests/test_theme.py .streamlit/config.toml
git commit -m "feat: add theme tokens and Streamlit native theme config"
```

---

### Task 6: Predict page (moved from App.py) with logging hook

**Files:**
- Create: `pages/predict_page.py`
- Delete: `App.py` (logic moves into `pages/predict_page.py`; see Task 7 for the new entry point)

**Interfaces:**
- Consumes: `db.get_session` (Task 1), `repository.log_prediction` (Task 4), `imaging.make_thumbnail` (Task 4), `theme.CLASS_COLORS` (Task 5), `st.session_state["user"]["id"]` (set by `main.py`, Task 7).

- [ ] **Step 1: Create `pages/predict_page.py` with the existing predict logic plus the logging call**

```python
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
```

- [ ] **Step 2: Delete the old `App.py`**

Run: `git rm App.py`

- [ ] **Step 3: Manual verification (deferred to Task 11)**

This file has no automated test per the Global Constraints testing-scope note — it's exercised end-to-end in Task 11 (upload a sample image, predict, confirm a DB row appears).

- [ ] **Step 4: Commit**

```bash
git add pages/predict_page.py
git commit -m "refactor: move predict/Grad-CAM logic into predict_page and log predictions"
```

---

### Task 7: Login gate and role-based top navbar (`main.py`)

**Files:**
- Create: `main.py`
- Modify: `run.bat`

**Interfaces:**
- Consumes: `db.init_db`, `db.get_session` (Task 1), `auth_utils.authenticate` (Task 2), `pages/predict_page.py` (Task 6), `pages/my_history_page.py` (Task 8 — referenced by path string, not imported), `pages/admin_dashboard_page.py` (Task 9 — referenced by path string).
- Produces: `st.session_state["user"]` dict with keys `id`, `username`, `role`, set after a successful login; this is the contract every page under `pages/` relies on.

- [ ] **Step 1: Write `main.py`**

```python
import streamlit as st

from auth_utils import authenticate
from db import get_session, init_db


def render_login():
    _, center, _ = st.columns([1, 2, 1])
    with center:
        with st.container(border=True):
            st.title("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Log in"):
                session = get_session()
                user = authenticate(session, username, password)
                session.close()
                if user is None:
                    st.error("Invalid username or password")
                else:
                    st.session_state["user"] = {
                        "id": user.id,
                        "username": user.username,
                        "role": user.role,
                    }
                    st.rerun()


def render_app():
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state['user']['username']}**")
        if st.button("Logout"):
            del st.session_state["user"]
            st.rerun()

    pages = [
        st.Page("pages/predict_page.py", title="Predict", icon="🔬"),
        st.Page("pages/my_history_page.py", title="My History", icon="📜"),
    ]

    if st.session_state["user"]["role"] == "admin":
        pages.append(st.Page("pages/admin_dashboard_page.py", title="Admin Dashboard", icon="📊"))

    navigation = st.navigation(pages, position="top")
    navigation.run()


init_db()

if "user" not in st.session_state:
    render_login()
else:
    render_app()
```

- [ ] **Step 2: Update `run.bat` to launch the new entry point**

Change only the first line of `run.bat` from:
```
python -m streamlit run App.py
```
to:
```
python -m streamlit run main.py
```
Leave every other line in `run.bat` untouched (it currently has unrelated notes/links below the command).

- [ ] **Step 3: Manual verification (deferred to Task 11)**

No automated test per the Global Constraints testing-scope note. Verified in Task 11 (login form appears, wrong password rejected, correct login shows the navbar).

- [ ] **Step 4: Commit**

```bash
git add main.py run.bat
git commit -m "feat: add login gate and role-based top navbar entry point"
```

---

### Task 8: My History page

**Files:**
- Create: `pages/my_history_page.py`

**Interfaces:**
- Consumes: `db.get_session` (Task 1), `repository.get_user_predictions` (Task 4), `theme.PRIMARY_COLOR` (Task 5), `st.session_state["user"]["id"]` (Task 7).

- [ ] **Step 1: Write `pages/my_history_page.py`**

```python
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
```

- [ ] **Step 2: Manual verification (deferred to Task 11)**

No automated test per the Global Constraints testing-scope note.

- [ ] **Step 3: Commit**

```bash
git add pages/my_history_page.py
git commit -m "feat: add per-user prediction history page"
```

---

### Task 9: Admin Dashboard page

**Files:**
- Create: `pages/admin_dashboard_page.py`

**Interfaces:**
- Consumes: `db.get_session` (Task 1), `repository.get_total_count`, `repository.get_today_count`, `repository.get_class_distribution`, `repository.get_confidence_values`, `repository.get_average_confidence`, `repository.get_recent_predictions` (Task 4), `theme.CLASS_COLORS`, `theme.PRIMARY_COLOR` (Task 5). Uses `pandas` (already an installed transitive dependency of `streamlit`/`plotly`; no `requirements.txt` change needed) to apply per-class colors to the recent-predictions table via `DataFrame.style`.

- [ ] **Step 1: Write `pages/admin_dashboard_page.py`**

```python
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
```

- [ ] **Step 2: Manual verification (deferred to Task 11)**

No automated test per the Global Constraints testing-scope note.

- [ ] **Step 3: Commit**

```bash
git add pages/admin_dashboard_page.py
git commit -m "feat: add admin dashboard with themed KPIs, charts, and recent predictions table"
```

---

### Task 10: README and project docs update

**Files:**
- Modify: `README.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Add a "Database & Admin Dashboard" section to `README.md`**

Insert after the existing "## 🚀 Running the Application" section:

```markdown
## 🗄️ Database & Admin Dashboard

This app now requires a database for login and prediction logging.

1. Copy `.env.example` to `.env` and set `DATABASE_URL` (defaults to a local
   SQLite file `tomato_app.db` if unset — fine for local dev/testing; use a
   real PostgreSQL URL in production).
2. Create the first admin account:
   ```bash
   python seed_admin.py
   ```
3. Run the app:
   ```bash
   streamlit run main.py
   ```
4. Log in. Every user sees **Predict** and **My History** in the top navbar;
   admins additionally see **Admin Dashboard** (total predictions, class
   distribution, confidence distribution/average, recent predictions).

The app ships with a themed look (`.streamlit/config.toml`, tomato-red accent)
and color-codes each disease class consistently across the Predict result,
Admin Dashboard charts/table, and My History — see
`docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md` for the
full token reference.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document database setup and admin dashboard usage"
```

---

### Task 11: End-to-end manual verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full automated test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all tests from Tasks 1-5 pass (`18 passed` total: 1 models + 5 auth + 2 seed_admin + 1 imaging + 7 repository + 2 theme).

- [ ] **Step 2: Seed the first admin user against the local dev DB**

Run: `.venv/Scripts/python.exe seed_admin.py`
Enter a username (e.g. `admin`) and password when prompted.
Expected: prints `Created admin user 'admin' (id=1)`.

- [ ] **Step 3: Start the app**

Run: `.venv/Scripts/python.exe -m streamlit run main.py --server.headless true --server.port 8501`
Expected: server starts, `curl http://localhost:8501` returns `200`.

- [ ] **Step 4: Verify the login gate**

Open `http://localhost:8501` in a browser (or take a screenshot). Confirm a
login form is shown (no navbar, no predict UI) before logging in, rendered as
a bordered card centered on the page, and that the "Log in" button is
tomato-red (`#C0392B`, the `primaryColor` from `.streamlit/config.toml`).

- [ ] **Step 5: Verify the admin flow and visual theme**

Log in as the seeded admin user. Confirm the top navbar shows **Predict**,
**My History**, and **Admin Dashboard**, with the active item highlighted in
tomato-red. Upload one image from `sample/Healthy/`, click Predict, confirm
the prediction and Grad-CAM render as before, and that the "Predicted class:
Healthy" text is rendered in green (`#2E7D32`). Switch to **Admin Dashboard**
and confirm: the 3 KPI metrics each render inside a bordered card; the
total-predictions KPI is at least 1; the class distribution pie chart's
"Healthy" slice is green and matches the semantic class-color mapping in
`docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md`; and the
recent-predictions table shows the row just created with its "Class" cell
background-colored to match the same green.

- [ ] **Step 6: Verify role gating for a regular user**

Create a second user directly via a Python shell:
```bash
.venv/Scripts/python.exe -c "from db import get_session; from auth_utils import create_user; s = get_session(); create_user(s, 'farmer1', 'pass1234', role='user'); s.close()"
```
Log out, log in as `farmer1`. Confirm the top navbar shows only **Predict**
and **My History** — **Admin Dashboard** must not appear. Upload a sample
image and predict; switch to **My History** and confirm it shows only this
user's own prediction, not the admin's earlier one.

- [ ] **Step 7: Stop the server**

Stop the background Streamlit process once verification is complete.
