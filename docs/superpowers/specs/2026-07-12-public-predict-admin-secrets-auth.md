# Public Predict + Secrets-Based Admin Auth

## Purpose

Replace the multi-user, DB-backed login system (built earlier and currently
live on `main`) with a two-tier access model:

1. **Public**: any visitor lands directly on the predict UI, no login,
   no session check blocking the flow.
2. **Admin**: a single admin identity, credentials in `st.secrets`
   (`.streamlit/secrets.toml`), logged in via an unobtrusive sidebar
   expander. Only the admin sees an Admin Dashboard tab.

This supersedes the "মাল্টি-ইউজার লগইন, ২টা রোল" (multi-user login, two
roles) decision recorded in `plan.md`'s Admin Dashboard architecture
section for this app. `plan.md` is not rewritten by this spec — it
documents history, and this file's "What gets removed" section below is
the authoritative record of the pivot.

## Direction confirmed with user

- Full replacement, not an add-on: mandatory-login-for-everyone goes away
  entirely, along with the SQLAlchemy `users`/`predictions` tables,
  `pages/`+`st.navigation` multi-page structure, and per-user My History.
- Prediction log storage: SQLite via Python's stdlib `sqlite3` (not
  SQLAlchemy — nothing needs a real DB connection anymore since there's
  no `users` table).
- File shape: `main.py` stays the only Streamlit page (no `pages/`
  folder, no `st.navigation` — closes the sidebar auto-discovery leak
  found during the previous implementation's E2E testing, and satisfies
  the "admin page must not be auto-listed" requirement), with two small
  helper modules (`admin_auth.py`, `predictions_log.py`) for the parts
  that benefit from unit tests without a running Streamlit session.
- Charts: native `st.bar_chart` for class distribution, dropping Plotly
  as a dependency (no other page needs it once the multi-chart admin
  dashboard page is gone).

## What gets removed

- `db.py`, `models.py`, `auth_utils.py`, `seed_admin.py`, `repository.py`
- `pages/` (entire folder) — `predict_page.py`'s Grad-CAM/predict logic
  moves into `main.py` unchanged, it is not deleted
- `.env.example`, local `tomato_app.db`
- `requirements.txt`: `sqlalchemy`, `psycopg2-binary`, `python-dotenv`,
  `plotly`
- `tests/conftest.py`'s SQLAlchemy `session` fixture and every test file
  that depended on the removed modules (`test_models.py`,
  `test_auth_utils.py`, `test_seed_admin.py`, `test_repository.py`)

## What is kept unchanged

- `theme.py` (color tokens, `CLASS_COLORS`) and `.streamlit/config.toml`
  (native Streamlit theme) — unrelated to the auth architecture.
- `imaging.py`'s `make_thumbnail()` — reused for the log's stored
  thumbnail.
- The Grad-CAM/predict logic itself (model loading, `predict()`,
  `get_gradcam_heatmap()`) — behaviorally unchanged, just relocated from
  `pages/predict_page.py` back into `main.py`.
- `run.bat` (`streamlit run main.py`) — no change needed.

## New/changed files

### `predictions_log.py` (new)

Stdlib `sqlite3` wrapper, connection-per-call (no caching/pooling —
writes are one-per-prediction-click, low volume).

- `get_connection(db_path: str = "predictions.db") -> sqlite3.Connection`
- `init_db(conn) -> None` — creates the `predictions` table if missing:
  `id INTEGER PRIMARY KEY, predicted_class TEXT, confidence REAL,
  thumbnail BLOB, created_at TEXT`.
- `log_prediction(conn, predicted_class: str, confidence: float, thumbnail: bytes) -> None`
- `get_total_count(conn) -> int`
- `get_class_distribution(conn) -> dict[str, int]`
- `get_recent(conn, limit: int = 20) -> list[dict]` — each dict has keys
  `id`, `predicted_class`, `confidence`, `thumbnail`, `created_at`,
  ordered newest-first.

### `admin_auth.py` (new)

- `verify_password(password: str, password_hash: str) -> bool` — pure
  `bcrypt.checkpw` wrapper (same shape as the old `auth_utils.py`
  function it replaces), independently unit-testable.
- `check_admin_login(username: str, password: str) -> bool` — thin glue:
  reads `st.secrets["admin_username"]` / `st.secrets["admin_password_hash"]`
  and delegates to `verify_password`. Not unit-tested (requires a live
  Streamlit session for `st.secrets`); covered by manual verification.

### `main.py` (rewritten)

Top of the script, unconditionally (no session check):
- Model loading (`@st.cache_resource`), file uploader, Predict button,
  prediction + confidence display, Grad-CAM heatmap + overlay — today's
  logic from `pages/predict_page.py`, unchanged.
- After every successful prediction: `predictions_log.log_prediction(...)`
  using a thumbnail from `imaging.make_thumbnail()`. Runs for every
  visitor, logged in or not — there is no per-user identity to filter by
  in this design.

Sidebar, always rendered at the bottom via `st.sidebar` +
`st.expander("Admin")`:
- If `st.session_state.get("is_admin")` is not `True`: username + password
  fields and a "Log in" button. On success (`check_admin_login`), set
  `st.session_state.is_admin = True` and `st.rerun()`. On failure,
  `st.error(...)`, no hint about which field was wrong.
- If already admin: "Logged in as admin" + a "Logout" button that does
  `del st.session_state["is_admin"]` (mirrors the old app's logout
  pattern) and reruns.

Page body structure:
- If not admin: render the predict UI directly (as above), no tabs.
- If admin: wrap the same predict UI plus a new Admin Dashboard section
  in `st.tabs(["Predict", "Admin Dashboard"])`, so the second tab only
  exists in the rendered output for an authenticated admin — not merely
  visually hidden.

### Admin Dashboard tab contents

- `st.metric("Total Predictions", predictions_log.get_total_count(conn))`
- Class distribution via `st.bar_chart` (native, uses the theme's
  `primaryColor` automatically; no per-bar class-color mapping — that
  level of chart customization needs Plotly, which this spec drops).
- Most recent 20 predictions via `st.dataframe`: thumbnail, predicted
  class (colored per `theme.CLASS_COLORS`, same Styler approach as the
  previous `admin_dashboard_page.py`), confidence, timestamp.

### `.streamlit/secrets.toml.example` (new)

```toml
admin_username = "admin"
admin_password_hash = "$2b$12$replace-with-a-real-bcrypt-hash"

# Generate a hash for your chosen password:
#   python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
```

`.streamlit/secrets.toml` itself (the real, non-example file) must be
gitignored — `.streamlit/*` already is except the explicit
`!.streamlit/config.toml` allow-rule added previously, so no `.gitignore`
change is needed; `secrets.toml` stays excluded by the wildcard.

### `README.md`

Replace the current "🗄️ Database & Admin Dashboard" section (which
documents `seed_admin.py` / `DATABASE_URL`, both gone) with:
- How to create `.streamlit/secrets.toml` locally from the `.example`
  file and generate a bcrypt hash.
- How to set the same two keys via Streamlit Cloud's Secrets manager
  (Settings → Secrets) for a deployed app.
- A note that Predict requires no login; the Admin Dashboard is reached
  via the "Admin" expander at the bottom of the sidebar.

## Testing scope

Consistent with this repo's existing convention (see the original plan's
Global Constraints): pure-Python modules get pytest unit tests with
fixtures; Streamlit UI files are verified manually/in-browser.

- `tests/test_predictions_log.py`: exercises `predictions_log.py`
  against a fixture-provided in-memory `sqlite3.Connection`
  (`tests/conftest.py` gets a new `conn` fixture replacing the removed
  SQLAlchemy `session` fixture). Covers: logging persists a row, total
  count, class distribution counts by class, `get_recent` orders
  newest-first and respects `limit`.
- `tests/test_admin_auth.py`: exercises `verify_password` only (roundtrip
  + wrong-password rejection) — mirrors the old `test_auth_utils.py`'s
  password tests. `check_admin_login` is not unit-tested (needs
  `st.secrets`); verified manually via Task-11-style browser E2E
  (wrong credentials rejected, correct credentials reveal the Admin
  Dashboard tab, Logout hides it again, and — given the sidebar-leak bug
  found last time — confirm there is no `pages/` directory and no
  automatic multi-page sidebar nav at all).

## Out of scope

- Multiple admin accounts, or any regular-user role/login.
- Per-user prediction history (no "My History" — there is no user
  identity for public predictions to belong to).
- Rate limiting or abuse protection on the now-public Predict endpoint.
- Migrating any data from the old `tomato_app.db` — it is deleted, not
  migrated (the two schemas are unrelated: multi-user relational vs.
  flat prediction log).
