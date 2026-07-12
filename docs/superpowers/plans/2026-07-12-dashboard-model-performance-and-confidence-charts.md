# Admin Dashboard: Model Performance + Live Confidence Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a static "Model Performance" reference section (hardcoded ~96% validation accuracy + embedded training curve image) and live confidence-based charts (average confidence, confidence over time, confidence distribution) to the Admin Dashboard.

**Architecture:** Two new pure functions in `predictions_log.py` (unit-tested against the existing `conn` fixture), consumed by `main.py`'s `render_admin_dashboard()`. See `docs/superpowers/specs/2026-07-12-dashboard-model-performance-and-confidence-charts.md` for the approved design.

**Tech Stack:** `numpy.histogram` for confidence bucketing (already an available dependency via `tensorflow`), `st.line_chart`/`st.bar_chart`/`st.image` (native Streamlit, no new dependencies).

## Global Constraints

- "Accuracy" is never computed from live prediction data — the app has no ground truth. The ~96% figure is a hardcoded string constant, not derived from `predictions.db`.
- `assets/training_history.png` may not exist (the user adds it manually after this plan lands). The dashboard must render `st.info(...)` instead of crashing when it's missing — never assume the file is present.
- Testing scope (unchanged convention): `predictions_log.py` functions get pytest unit tests with the `conn` fixture; `main.py` UI is verified manually.

---

### Task 1: `predictions_log.py` — average confidence and confidence series

**Files:**
- Modify: `predictions_log.py`
- Modify: `tests/test_predictions_log.py`

**Interfaces:**
- Produces: `predictions_log.get_average_confidence(conn) -> float` (returns `0.0` when there are no rows), `predictions_log.get_confidence_series(conn) -> list[dict]` (each dict has keys `created_at`, `confidence`; ordered oldest-first by `id ASC` — the opposite order from `get_recent`, which is newest-first).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_predictions_log.py`:

```python
from predictions_log import get_average_confidence, get_confidence_series


def test_get_average_confidence_returns_zero_when_empty(conn):
    assert get_average_confidence(conn) == 0.0


def test_get_average_confidence_averages_logged_predictions(conn):
    log_prediction(conn, "Healthy", 90.0, b"t")
    log_prediction(conn, "Healthy", 80.0, b"t")

    assert get_average_confidence(conn) == 85.0


def test_get_confidence_series_orders_oldest_first(conn):
    log_prediction(conn, "Healthy", 90.0, b"t1")
    log_prediction(conn, "Early Blight", 70.0, b"t2")

    series = get_confidence_series(conn)
    assert len(series) == 2
    assert series[0]["confidence"] == 90.0
    assert series[1]["confidence"] == 70.0
    assert "created_at" in series[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_predictions_log.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_average_confidence'`

- [ ] **Step 3: Add the two functions to `predictions_log.py`**

Append to the end of the file:

```python
def get_average_confidence(conn: sqlite3.Connection) -> float:
    cursor = conn.execute("SELECT AVG(confidence) FROM predictions")
    result = cursor.fetchone()[0]
    return float(result) if result is not None else 0.0


def get_confidence_series(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT created_at, confidence FROM predictions ORDER BY id ASC")
    return [{"created_at": row[0], "confidence": row[1]} for row in cursor.fetchall()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_predictions_log.py -v`
Expected: `8 passed` (5 existing + 3 new)

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: `13 passed` (10 from before + 3 new)

- [ ] **Step 6: Commit**

```bash
git add predictions_log.py tests/test_predictions_log.py
git commit -m "feat: add average confidence and confidence series queries"
```

---

### Task 2: Dashboard sections in `main.py`

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `predictions_log.get_average_confidence`, `predictions_log.get_confidence_series` (Task 1); `theme.PRIMARY_COLOR` (existing, already imported).

- [ ] **Step 1: Add the `os` import**

```python
import base64
import os
```
(at the top of `main.py`, alongside the existing `import base64`)

- [ ] **Step 2: Import the two new `predictions_log` functions**

Change:
```python
from predictions_log import (
    get_class_distribution,
    get_connection,
    get_recent,
    get_total_count,
    init_db,
    log_prediction,
)
```
to:
```python
from predictions_log import (
    get_average_confidence,
    get_class_distribution,
    get_confidence_series,
    get_connection,
    get_recent,
    get_total_count,
    init_db,
    log_prediction,
)
```

- [ ] **Step 3: Rewrite `render_admin_dashboard()`**

Replace the entire function (from `def render_admin_dashboard():` through its closing `conn.close()`) with:

```python
def render_admin_dashboard():
    st.title("Admin Dashboard")

    conn = get_connection()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Predictions", get_total_count(conn))
    with col2:
        st.metric("Average Confidence", f"{get_average_confidence(conn):.1f}%")

    st.subheader("Model Performance")
    st.metric("Final Validation Accuracy", "~96%")
    training_history_path = "assets/training_history.png"
    if os.path.exists(training_history_path):
        st.image(training_history_path, caption="Training history")
    else:
        st.info("Training history chart not found — add it at assets/training_history.png")

    st.subheader("Class Distribution")
    distribution = get_class_distribution(conn)
    if distribution:
        st.bar_chart(pd.Series(distribution, name="Count"), color=PRIMARY_COLOR)
    else:
        st.info("No predictions logged yet.")

    st.subheader("Confidence Over Time")
    series = get_confidence_series(conn)
    if series:
        times = [row["created_at"] for row in series]
        confidences = [row["confidence"] for row in series]
        st.line_chart(pd.Series(confidences, index=times, name="Confidence (%)"), color=PRIMARY_COLOR)
    else:
        st.info("No predictions logged yet.")

    st.subheader("Confidence Distribution")
    if series:
        confidence_values = [row["confidence"] for row in series]
        counts, bin_edges = np.histogram(confidence_values, bins=10)
        bin_labels = [f"{bin_edges[i]:.0f}-{bin_edges[i + 1]:.0f}" for i in range(len(bin_edges) - 1)]
        st.bar_chart(pd.Series(counts, index=bin_labels, name="Count"), color=PRIMARY_COLOR)
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
```

Everything below `st.subheader("Recent Predictions")` is copied verbatim from the current file — only the KPI row and the new Model Performance / Confidence Over Time / Confidence Distribution sections are new.

- [ ] **Step 4: Sanity-check syntax**

Run: `.venv/Scripts/python.exe -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Manual verification**

No automated test for `main.py` per the Global Constraints testing-scope note.

1. Remove any stale local `predictions.db` so counts start fresh: `rm -f predictions.db`.
2. Start the app: `.venv/Scripts/python.exe -m streamlit run main.py --server.headless true --server.port 8501`.
3. **Missing-asset fallback**: before adding the real image, confirm `assets/training_history.png` does not exist yet, log in as admin, open Admin Dashboard, and confirm the Model Performance section shows the `st.info` fallback message rather than an error.
4. **Empty-state**: with no predictions logged yet, confirm Confidence Over Time and Confidence Distribution both show "No predictions logged yet." rather than crashing (division-by-zero / empty-histogram edge cases).
5. Upload 2-3 sample images from different classes in `sample/` and click Predict for each (public flow, no login needed) to generate real data.
6. Return to Admin Dashboard: confirm Average Confidence shows a sensible percentage, Confidence Over Time shows a line with as many points as predictions made, and Confidence Distribution shows a bar chart with at least one non-empty bucket — all in the tomato-red primary color, consistent with Class Distribution.
7. If the user has by this point saved `assets/training_history.png`, confirm it now renders in the Model Performance section instead of the fallback message.
8. Stop the background Streamlit process once verification is complete.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: add Model Performance section and live confidence charts to Admin Dashboard"
```
