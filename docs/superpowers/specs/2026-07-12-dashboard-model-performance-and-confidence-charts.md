# Admin Dashboard: Model Performance + Live Confidence Charts

## Purpose

The Admin Dashboard currently shows Total Predictions, a Class Distribution
bar chart, and a Recent Predictions table — all live data from
`predictions.db`. This spec adds two more sections: a static "Model
Performance" reference (the model's training-time metrics, which the app
has no way to compute itself) and live confidence-based charts (the
closest honest analog to "accuracy" the app can produce, since it has no
ground-truth labels for predictions made by real visitors).

## Direction confirmed with user

- "Accuracy percentage" cannot be computed live — the app never learns
  whether a prediction was correct. The user chose to display a **fixed,
  hardcoded** final validation accuracy from the model's training run
  (**~96%**, approximate — not read precisely off a chart image) rather
  than computing anything from live data.
- The reference chart the user shared (training/validation accuracy and
  loss curves over epochs) is training-time data with no source of truth
  in this repo. The user will save that image to `assets/training_history.png`
  and it gets embedded via `st.image()` — not reconstructed as a native
  chart from extracted data points.
- Both static (training) and live (confidence) sections are wanted,
  clearly distinguished so a viewer doesn't mistake one for the other.

## New Dashboard Sections

### 1. Model Performance (static)

Placed above Class Distribution. Contents:
- `st.metric("Final Validation Accuracy", "~96%")` — hardcoded string,
  not computed. The `~` is intentional: this is an approximate figure,
  not read precisely from the source chart.
- `st.image("assets/training_history.png", caption="Training history")`
  if the file exists; otherwise `st.info("Training history chart not found — add it at assets/training_history.png")`.
  Never raises — a missing asset must not crash the dashboard.

### 2. Confidence charts (live, from `predictions.db`)

- **Average Confidence** KPI, added next to the existing Total
  Predictions metric — `predictions_log.get_average_confidence(conn) -> float`,
  `0.0` when there are no predictions yet.
- **Confidence Over Time** — a line chart, x-axis chronological
  (oldest→newest, the opposite order from the existing newest-first
  Recent Predictions table), y-axis confidence. Backed by a new
  `predictions_log.get_confidence_series(conn) -> list[dict]` (keys:
  `created_at`, `confidence`), ordered by `id ASC`.
- **Confidence Distribution** — a histogram of confidence values bucketed
  into ranges, rendered via `st.bar_chart` (no native `st.histogram`
  exists; bucketing is computed in `main.py` with `numpy.histogram`,
  already an available dependency via `tensorflow`).

Both new sections render `st.info("No predictions logged yet.")` when
`predictions.db` is empty, matching the existing Class Distribution /
Recent Predictions empty-state pattern.

## File changes

- `predictions_log.py`: add `get_average_confidence(conn) -> float`,
  `get_confidence_series(conn) -> list[dict]`.
- `main.py`: `render_admin_dashboard()` gains the Model Performance
  section and the two new confidence charts; the KPI row gains Average
  Confidence.
- New directory `assets/` (not created by this spec's code — the user
  places `training_history.png` there manually; the app tolerates its
  absence).

## Testing scope

Same convention as the rest of this repo: `get_average_confidence` and
`get_confidence_series` are pure functions over a `sqlite3.Connection`
and get pytest unit tests with the existing `conn` fixture. The
Model Performance section and the two chart renders in `main.py` have no
automated test (Streamlit UI, per existing convention) — verified
manually, including the missing-file fallback (temporarily rename
`assets/training_history.png` if present, confirm the info message
shows instead of a crash).

## Out of scope

- Computing any real accuracy/precision/recall metric from live data —
  impossible without ground truth, not attempted.
- Re-deriving the training curves as a native, interactive chart from
  extracted per-epoch numbers — the user chose the static-image route.
- Updating the hardcoded ~96% figure automatically if the model is
  retrained — it is a manually-maintained constant until someone edits it.
