# Admin Dashboard Visual Design

## Purpose

`docs/superpowers/plans/2026-07-11-admin-dashboard.md` specifies the functional
build for prediction logging, login, a role-gated top navbar, an Admin
Dashboard page, and a My History page — but it uses plain Streamlit defaults
(bare `st.metric`, default Plotly theme, no color decisions). This spec defines
the visual design system for those new/changed pages: `main.py` (login +
navbar), `pages/predict_page.py`, `pages/my_history_page.py`, and
`pages/admin_dashboard_page.py`. It does not change any business logic, DB
schema, or test scope defined in that plan.

## Direction

Clean neutral dashboard look (not the purple-gradient marketing brand used on
the GitHub Pages landing page / `index.html`) — this is an internal tool, not
a marketing surface. One accent color pulled from the domain (tomato red)
carries the identity instead.

## Design Tokens

**Base palette:**

| Token | Value | Use |
|---|---|---|
| Background | `#FFFFFF` | Page background |
| Surface (secondary bg) | `#F8F9FA` | Card/container fill, sidebar |
| Border | `#E2E5E9` | Card borders, dividers |
| Text | `#1F2933` | Body text |
| Primary accent | `#C0392B` (tomato red) | Buttons, active nav item, links, KPI numbers |

**Semantic class colors** — a severity progression, used consistently
everywhere a predicted class appears (charts, table cells, result text):

| Class | Color | Meaning |
|---|---|---|
| Healthy | `#2E7D32` (green) | Good |
| Early Blight | `#E1A100` (amber) | Mild |
| Leaf Spot | `#C9702C` (burnt orange) | Moderate |
| Late Blight | `#922B21` (deep brick red) | Severe |

Late Blight's red is deliberately darker/browner than the primary tomato-red
accent so chart segments are never mistaken for clickable UI elements.

**Typography:** Streamlit's default system sans-serif. No custom webfont
import.

**Dark mode:** Out of scope for v1. Ships as a single fixed light theme
(`base = "light"` in config.toml). Internal admin tool, not a public product —
revisit only if requested later.

## Implementation Approach

Native Streamlit theming API, not custom CSS injection — lighter, and
survives Streamlit upgrades better.

1. **`.streamlit/config.toml`** (new file) — sets `base`, `primaryColor`,
   `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `font` from the
   base palette above. Streamlit 1.59.1 (confirmed installed) applies these
   automatically to buttons, the top navbar (`st.navigation(position="top")`),
   inputs, and `st.metric` — no per-component styling code required.

2. **`theme.py`** (new module) — exports `CLASS_COLORS: dict[str, str]`
   mapping each of the 4 class names (exact strings, matching the load-bearing
   order in `models.py`/`repository.py`) to its hex value from the semantic
   table above. This is the single source of truth for class color, imported
   by every page that displays a class.

3. **`pages/admin_dashboard_page.py`**:
   - KPI row (Total Predictions, Average Confidence, Predictions Today) — each
     metric wrapped in `st.container(border=True)` instead of a bare
     `st.metric` in a raw column, so each reads as a distinct bordered card.
   - Class distribution pie chart — `px.pie(..., color=..., color_discrete_map=CLASS_COLORS, template="plotly_white")`.
   - Confidence histogram — `px.histogram(..., template="plotly_white")`
     (single series, no per-class coloring needed here).
   - Recent Predictions table — pass a pandas Styler to `st.dataframe` that
     colors the "Class" column's text/background per `CLASS_COLORS`, so the
     table visually echoes the charts.

4. **`pages/my_history_page.py`**: same `st.container(border=True)` treatment
   for the "Total Predictions" metric; confidence-trend line chart uses
   `template="plotly_white"` and the primary accent color for the line.

5. **`pages/predict_page.py`**: the existing "Predicted class: *{class}*"
   result line is rendered in the matching `CLASS_COLORS` color (small addition
   on top of the plan's existing logging hook — no change to predict/Grad-CAM
   logic itself), so the color system is consistent across the whole app, not
   just the dashboard.

6. **`main.py`**: no visual code beyond what `config.toml` already provides —
   the login form and top navbar pick up the theme automatically. Login form
   is centered via a 3-column layout (`st.columns([1, 2, 1])`, form in the
   middle column) inside a bordered container.

## Out of Scope

- Dark mode / theme toggle.
- Custom fonts or CSS injection.
- Changing the GitHub Pages landing page (`index.html`) — it keeps its
  existing purple-gradient brand, unrelated to this app-side theme.
- Any change to DB schema, business logic, or the test scope defined in
  `docs/superpowers/plans/2026-07-11-admin-dashboard.md`.

## Relationship to the Existing Implementation Plan

This spec extends `docs/superpowers/plans/2026-07-11-admin-dashboard.md`. The
next step is to fold these decisions into that plan (new task for
`.streamlit/config.toml` + `theme.py`, and amended code blocks in the tasks
that already touch `pages/admin_dashboard_page.py`,
`pages/my_history_page.py`, `pages/predict_page.py`, and `main.py`) rather
than executing the plan's current code blocks verbatim.
