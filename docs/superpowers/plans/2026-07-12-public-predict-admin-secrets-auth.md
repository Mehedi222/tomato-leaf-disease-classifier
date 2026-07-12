# Public Predict + Secrets-Based Admin Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mandatory-login, multi-user DB-backed auth system with a two-tier model — Predict is public with zero login friction, and a single admin identity (credentials in `st.secrets`) gates a sidebar-expander login and an Admin Dashboard tab.

**Architecture:** `main.py` becomes the only Streamlit page again (no `pages/` folder, no `st.navigation`) — this closes the sidebar auto-discovery leak found during the previous implementation's E2E testing and satisfies the "admin page must not be auto-listed" requirement. Two small helper modules carry the parts worth unit-testing without a live Streamlit session: `predictions_log.py` (stdlib `sqlite3`, connection-per-call) and `admin_auth.py` (bcrypt against `st.secrets`). See `docs/superpowers/specs/2026-07-12-public-predict-admin-secrets-auth.md` for the approved design this plan implements.

**Tech Stack:** Streamlit native theming (unchanged), stdlib `sqlite3` (new, replaces SQLAlchemy), `bcrypt` (unchanged), `st.secrets`, `st.bar_chart`/`st.dataframe` with `ImageColumn` (native, replaces Plotly).

## Global Constraints

- Class name order stays exactly: `["Early Blight", "Healthy", "Late Blight", "Leaf Spot"]` (load-bearing, matches the model's output order) — unchanged from before.
- The Grad-CAM/predict logic itself (model loading, `predict()`, `get_gradcam_heatmap()`) must remain behaviorally unchanged when moved from `pages/predict_page.py` back into `main.py` — only where it logs to and how login gating works around it are new.
- `theme.py` and `.streamlit/config.toml` are kept as-is; every new UI element reuses `theme.CLASS_COLORS` / `theme.PRIMARY_COLOR` rather than hardcoding hex values.
- `st.column_config.ImageColumn` only renders a cell that is a URL or a base64 **data URL** — raw bytes or local file paths do not work. Thumbail bytes from `predictions_log.get_recent()` must be base64-encoded into a `data:image/jpeg;base64,...` string before being placed in the dataframe shown to the admin.
- `.streamlit/*` is gitignored with a `!.streamlit/config.toml` exception already in place; the new `.streamlit/secrets.toml.example` needs its own `!` exception line or it will silently never be tracked. The real `secrets.toml` (if a user creates one locally) must stay ignored — do not add an exception for it.
- Testing scope (unchanged convention from the prior plan): pure-Python modules (`predictions_log.py`, `admin_auth.py`'s `verify_password`) get pytest unit tests with fixtures; `main.py` itself is verified manually in the final task — Streamlit's `AppTest` does not reliably simulate the file-upload → Grad-CAM flow or `st.secrets`-backed login.
- `README.md` is encoded as **UTF-16 (with BOM) using CRLF line endings**, not UTF-8 — confirmed via its raw bytes (`\xff\xfe` BOM) during the prior plan's execution. A plain text-editing tool that assumes UTF-8 will corrupt it. Task 4 must edit it the same way the prior plan did: read the raw bytes, `.decode("utf-16")`, do the string replacement in Python (matching the file's actual `\r\n` line endings, not `\n`), then `.encode("utf-16")` and write the bytes back — see Task 4 Step 1 for the exact script.

---

### Task 1: `predictions_log.py`, `admin_auth.py`, and the new `conn` test fixture

**Files:**
- Create: `predictions_log.py`
- Create: `admin_auth.py`
- Modify: `tests/conftest.py` (add a `conn` fixture; the existing SQLAlchemy `session` fixture is left in place for now — it still backs the soon-to-be-deleted `test_models.py`/`test_auth_utils.py`/`test_seed_admin.py`/`test_repository.py`, which Task 2 removes together with the fixture)
- Test: `tests/test_predictions_log.py`
- Test: `tests/test_admin_auth.py`

**Interfaces:**
- Produces: `predictions_log.get_connection(db_path: str = "predictions.db") -> sqlite3.Connection`, `predictions_log.init_db(conn) -> None`, `predictions_log.log_prediction(conn, predicted_class: str, confidence: float, thumbnail: bytes) -> None`, `predictions_log.get_total_count(conn) -> int`, `predictions_log.get_class_distribution(conn) -> dict[str, int]`, `predictions_log.get_recent(conn, limit: int = 20) -> list[dict]` (each dict has keys `id`, `predicted_class`, `confidence`, `thumbnail`, `created_at`, newest-first by insertion order).
- Produces: `admin_auth.verify_password(password: str, password_hash: str) -> bool`, `admin_auth.check_admin_login(username: str, password: str) -> bool` (reads `st.secrets["admin_username"]` / `st.secrets["admin_password_hash"]`; returns `False` if either secret is missing rather than raising).
- Produces: `tests/conftest.py` fixture `conn` (function-scoped, in-memory `sqlite3.Connection`, already `init_db`'d) — used by Task 1's own tests and by Task 3's manual verification setup.

- [ ] **Step 1: Write the failing tests `tests/test_predictions_log.py`**

```python
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
```

- [ ] **Step 2: Write the failing tests `tests/test_admin_auth.py`**

```python
import bcrypt

from admin_auth import verify_password


def test_verify_password_roundtrip():
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("secret123", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("wrong", hashed) is False
```

- [ ] **Step 3: Add the `conn` fixture to `tests/conftest.py`**

Append to the existing file (keep the current `session` fixture and its imports untouched — Task 2 removes it):

```python
import sqlite3

from predictions_log import init_db


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_predictions_log.py tests/test_admin_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'predictions_log'` (collection error also breaks the `test_admin_auth.py` run since `conftest.py` now imports it too)

- [ ] **Step 5: Write `predictions_log.py`**

```python
import sqlite3
from datetime import datetime


def get_connection(db_path: str = "predictions.db") -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            predicted_class TEXT NOT NULL,
            confidence REAL NOT NULL,
            thumbnail BLOB,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def log_prediction(conn: sqlite3.Connection, predicted_class: str, confidence: float, thumbnail: bytes) -> None:
    conn.execute(
        "INSERT INTO predictions (predicted_class, confidence, thumbnail, created_at) VALUES (?, ?, ?, ?)",
        (predicted_class, confidence, thumbnail, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_total_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("SELECT COUNT(*) FROM predictions")
    return cursor.fetchone()[0]


def get_class_distribution(conn: sqlite3.Connection) -> dict:
    cursor = conn.execute("SELECT predicted_class, COUNT(*) FROM predictions GROUP BY predicted_class")
    return dict(cursor.fetchall())


def get_recent(conn: sqlite3.Connection, limit: int = 20) -> list:
    cursor = conn.execute(
        "SELECT id, predicted_class, confidence, thumbnail, created_at "
        "FROM predictions ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    columns = ["id", "predicted_class", "confidence", "thumbnail", "created_at"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

- [ ] **Step 6: Write `admin_auth.py`**

```python
import bcrypt
import streamlit as st


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def check_admin_login(username: str, password: str) -> bool:
    expected_username = st.secrets.get("admin_username")
    expected_hash = st.secrets.get("admin_password_hash")
    if expected_username is None or expected_hash is None:
        return False
    if username != expected_username:
        return False
    return verify_password(password, expected_hash)
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_predictions_log.py tests/test_admin_auth.py -v`
Expected: `6 passed`

- [ ] **Step 8: Run the full suite to confirm nothing else broke**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: `25 passed` (19 from before + 6 new; the old SQLAlchemy-backed tests and fixture are untouched in this task)

- [ ] **Step 9: Commit**

```bash
git add predictions_log.py admin_auth.py tests/conftest.py tests/test_predictions_log.py tests/test_admin_auth.py
git commit -m "feat: add sqlite3 prediction log and secrets-based admin auth helpers"
```

---

### Task 2: Remove the multi-user DB auth system

**Files:**
- Delete: `db.py`, `models.py`, `auth_utils.py`, `seed_admin.py`, `repository.py`
- Delete: `pages/predict_page.py`, `pages/my_history_page.py`, `pages/admin_dashboard_page.py` (the `pages/` directory itself becomes empty and is removed)
- Delete: `.env.example`
- Delete: `tests/test_models.py`, `tests/test_auth_utils.py`, `tests/test_seed_admin.py`, `tests/test_repository.py`
- Modify: `tests/conftest.py` (remove the now-unused SQLAlchemy `session` fixture and its imports; keep the `conn` fixture from Task 1)
- Modify: `requirements.txt` (remove `sqlalchemy`, `psycopg2-binary`, `python-dotenv`, `plotly`)

**Interfaces:**
- Consumes: nothing new. This task only removes code; `predictions_log.py`/`admin_auth.py` (Task 1) do not depend on anything being deleted here.
- Note: `main.py` still imports from `db`/`auth_utils`/the `pages/` scripts at this point in the plan — it stays broken until Task 3 rewrites it. This is expected; `main.py` has no automated test (per Global Constraints), so `pytest tests/` still passes after this task even though the app itself won't run yet.

- [ ] **Step 1: Delete the obsolete application files**

```bash
git rm db.py models.py auth_utils.py seed_admin.py repository.py
git rm -r pages/
git rm .env.example
```

- [ ] **Step 2: Delete the obsolete test files**

```bash
git rm tests/test_models.py tests/test_auth_utils.py tests/test_seed_admin.py tests/test_repository.py
```

- [ ] **Step 3: Rewrite `tests/conftest.py` to drop the SQLAlchemy fixture**

```python
import sqlite3

import pytest

from predictions_log import init_db


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()
```

- [ ] **Step 4: Remove the now-unused dependencies from `requirements.txt`**

Resulting file:
```
streamlit
tensorflow
pillow
numpy
tf-keras-vis
opencv-python
matplotlib
bcrypt
pytest
```

- [ ] **Step 5: Run the remaining tests to confirm they still pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: `9 passed` (1 `test_imaging.py` + 2 `test_theme.py` + 4 `test_predictions_log.py` + 2 `test_admin_auth.py`)

- [ ] **Step 6: Uninstall the now-unused packages from the venv (optional but keeps the environment matching requirements.txt)**

Run: `.venv/Scripts/python.exe -m pip uninstall -y sqlalchemy psycopg2-binary python-dotenv plotly`
Expected: packages uninstalled without error

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py requirements.txt
git commit -m "refactor: remove multi-user DB auth system and pages/ multi-page app"
```

---

### Task 3: Rewrite `main.py` as the single public-predict + admin page

**Files:**
- Modify: `main.py` (full rewrite)
- Create: `.streamlit/secrets.toml.example`
- Modify: `.gitignore` (add `!.streamlit/secrets.toml.example` so the example file isn't swallowed by the existing `.streamlit/*` wildcard)

**Interfaces:**
- Consumes: `predictions_log.get_connection`, `predictions_log.init_db`, `predictions_log.log_prediction`, `predictions_log.get_total_count`, `predictions_log.get_class_distribution`, `predictions_log.get_recent` (Task 1); `admin_auth.check_admin_login` (Task 1); `imaging.make_thumbnail` (existing, unchanged); `theme.CLASS_COLORS` (existing, unchanged).
- Produces: `st.session_state["is_admin"]` (bool, set on successful admin login, deleted on logout) — the only session-state contract in this app now; there is no per-visitor identity for public predictions.

- [ ] **Step 1: Write `main.py`**

```python
import base64

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
    get_class_distribution,
    get_connection,
    get_recent,
    get_total_count,
    init_db,
    log_prediction,
)
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
            log_prediction(conn, predicted_class, confidence, make_thumbnail(image))
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

    st.metric("Total Predictions", get_total_count(conn))

    st.subheader("Class Distribution")
    distribution = get_class_distribution(conn)
    if distribution:
        st.bar_chart(pd.Series(distribution, name="Count"))
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
```

- [ ] **Step 2: Write `.streamlit/secrets.toml.example`**

```toml
admin_username = "admin"
admin_password_hash = "$2b$12$replace-with-a-real-bcrypt-hash"

# Generate a hash for your chosen password:
#   python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
```

- [ ] **Step 3: Add the `.gitignore` exception for the example file**

Change:
```
.streamlit/*
!.streamlit/config.toml
```
to:
```
.streamlit/*
!.streamlit/config.toml
!.streamlit/secrets.toml.example
```

- [ ] **Step 4: Manual verification (deferred to Task 5)**

`main.py` has no automated test per the Global Constraints testing-scope note — it's exercised end-to-end in Task 5.

- [ ] **Step 5: Commit**

```bash
git add main.py .streamlit/secrets.toml.example .gitignore
git commit -m "feat: rewrite main.py as public predict + secrets-gated admin dashboard"
```

---

### Task 4: README update

**Files:**
- Modify: `README.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Replace the "🗄️ Database & Admin Dashboard" section**

`README.md` is UTF-16 (BOM) with CRLF line endings (see Global
Constraints) — do **not** edit it with a plain text tool. Run this
script instead, which decodes it, does the replacement with exact CRLF
line endings, and re-encodes it the same way:

```python
old_section = (
    "## \U0001F5C4️ Database & Admin Dashboard\r\n\r\n"
    "This app now requires a database for login and prediction logging.\r\n\r\n"
    "1. Copy `.env.example` to `.env` and set `DATABASE_URL` (defaults to a local\r\n"
    "   SQLite file `tomato_app.db` if unset — fine for local dev/testing; use a\r\n"
    "   real PostgreSQL URL in production).\r\n"
    "2. Create the first admin account:\r\n"
    "   ```bash\r\n"
    "   python seed_admin.py\r\n"
    "   ```\r\n"
    "3. Run the app:\r\n"
    "   ```bash\r\n"
    "   streamlit run main.py\r\n"
    "   ```\r\n"
    "4. Log in. Every user sees **Predict** and **My History** in the top navbar;\r\n"
    "   admins additionally see **Admin Dashboard** (total predictions, class\r\n"
    "   distribution, confidence distribution/average, recent predictions).\r\n\r\n"
    "The app ships with a themed look (`.streamlit/config.toml`, tomato-red accent)\r\n"
    "and color-codes each disease class consistently across the Predict result,\r\n"
    "Admin Dashboard charts/table, and My History — see\r\n"
    "`docs/superpowers/specs/2026-07-12-admin-dashboard-visual-design.md` for the\r\n"
    "full token reference.\r\n\r\n"
)
new_section = (
    "## \U0001F510 Admin Dashboard\r\n\r\n"
    "Predict works for everyone with no login. A single admin account, gated\r\n"
    "behind an **Admin** expander at the bottom of the sidebar, can view a\r\n"
    "dashboard of every prediction logged from the public Predict flow (total\r\n"
    "count, class distribution, most recent 20 predictions with thumbnails).\r\n\r\n"
    "**Local setup:**\r\n\r\n"
    "1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.\r\n"
    "2. Generate a bcrypt hash for your chosen admin password:\r\n"
    "   ```bash\r\n"
    "   python -c \"import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())\"\r\n"
    "   ```\r\n"
    "3. Put your chosen username and the generated hash into\r\n"
    "   `.streamlit/secrets.toml`:\r\n"
    "   ```toml\r\n"
    "   admin_username = \"admin\"\r\n"
    "   admin_password_hash = \"$2b$12$...your generated hash...\"\r\n"
    "   ```\r\n"
    "4. Run the app as usual (`streamlit run main.py` or `run.bat`), open the\r\n"
    "   **Admin** expander in the sidebar, and log in.\r\n\r\n"
    "**On Streamlit Cloud:** open your app's **Settings → Secrets** and paste\r\n"
    "the same two keys (`admin_username`, `admin_password_hash`) in TOML\r\n"
    "format — no `secrets.toml` file is committed or deployed; Streamlit\r\n"
    "Cloud injects these at runtime.\r\n\r\n"
    "Prediction data lives in a local `predictions.db` SQLite file, created\r\n"
    "automatically on first run.\r\n\r\n"
)

data = open("README.md", "rb").read()
text = data.decode("utf-16")
assert text.count(old_section) == 1, "section not found verbatim - check for drift"
text = text.replace(old_section, new_section)
open("README.md", "wb").write(text.encode("utf-16"))
print("done")
```

Run it with `.venv/Scripts/python.exe`, then spot-check with the `Read`
tool that the new section reads correctly (mirrors how the prior plan's
README edit was verified).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document secrets-based admin login, replacing the DB-auth instructions"
```

---

### Task 5: End-to-end manual verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full automated test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: `9 passed` (1 `test_imaging.py` + 2 `test_theme.py` + 4 `test_predictions_log.py` + 2 `test_admin_auth.py`)

- [ ] **Step 2: Set up local secrets**

```bash
cp ".streamlit/secrets.toml.example" ".streamlit/secrets.toml"
.venv/Scripts/python.exe -c "import bcrypt; print(bcrypt.hashpw(b'adminpass123', bcrypt.gensalt()).decode())"
```
Paste the printed hash into `.streamlit/secrets.toml` as `admin_password_hash`, and set `admin_username = "admin"`.

- [ ] **Step 3: Remove any leftover local dev database from the previous system**

Run: `rm -f tomato_app.db predictions.db`
(A fresh `predictions.db` is created automatically on next app start.)

- [ ] **Step 4: Start the app**

Run: `.venv/Scripts/python.exe -m streamlit run main.py --server.headless true --server.port 8501`
Expected: server starts, `curl http://localhost:8501` returns `200`.

- [ ] **Step 5: Verify Predict is public (no login)**

Open `http://localhost:8501`. Confirm the Predict UI (file uploader, title
"Tomato Leaf Diseases Classification") renders immediately — no login
form, no blocking screen. Upload an image from `sample/Healthy/`, click
Predict, confirm the prediction, confidence, and Grad-CAM heatmap/overlay
render exactly as before, and the predicted-class text is colored per
`theme.CLASS_COLORS`.

- [ ] **Step 6: Verify no automatic multi-page sidebar leak**

Confirm there is no `pages/` directory (`ls pages/` should fail — it was
deleted in Task 2) and that the sidebar shows only the "Admin" expander,
never a raw list of page names.

- [ ] **Step 7: Verify admin login gating**

In the "Admin" expander, try an obviously wrong username/password —
confirm `st.error("Invalid admin credentials")` and no Admin Dashboard
tab appears. Then log in with the real credentials from Step 2 — confirm
the page reflows into a "Predict" / "Admin Dashboard" tab pair, the Admin
Dashboard tab shows Total Predictions ≥ 1 (from Step 5's upload), a bar
chart with the "Healthy" class, and a Recent Predictions table with a
visible thumbnail image and a green "Healthy" cell background.

- [ ] **Step 8: Verify logout**

Click Logout in the Admin expander. Confirm the page reverts to the
plain Predict view with no tabs and no Admin Dashboard reachable.

- [ ] **Step 9: Stop the server**

Stop the background Streamlit process once verification is complete.

- [ ] **Step 10: Clean up local secrets before committing anything further**

Confirm `git status` does not show `.streamlit/secrets.toml` (it must
stay gitignored) — only `.streamlit/secrets.toml.example` should ever be
tracked.
