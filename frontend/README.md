# CareGuard — Care Coordinator Dashboard

A clinical web dashboard for the CareGuard post-discharge care coordination
platform. Coordinators monitor their monitored patient cohort, review AI voice
outreach, and triage clinical escalations in real time.

Built with **React + TypeScript + Vite + TailwindCSS**, **TanStack Query** for
data fetching, and **Recharts** for analytics.

## Features

- **Overview** — live KPIs (patients monitored, high-risk, open/urgent escalations),
  risk-distribution donut, escalations-by-severity bar chart, recent activity.
- **Patients** — searchable, risk-filterable cohort table with patient detail pages.
- **Patient detail** — demographics, risk score, AI outreach timeline, and the
  patient's escalation history.
- **Escalations** — severity-ranked triage queue with one-click *Resolve* (writes
  back via `PATCH /dashboard/escalations/{id}/resolve`).
- **Auth** — JWT Bearer token sign-in matching the backend's `get_current_user`.
- **Demo Mode** — explore the whole UI with synthetic data, no backend required.
- Dark mode, responsive layout, HIPAA-aware (PHI shown only to signed-in coordinators).

## API contract

The client targets the existing FastAPI `/dashboard/*` endpoints
(see `backend/api/routes/dashboard.py`):

| Method | Path | Used by |
|---|---|---|
| `GET` | `/dashboard/patients?risk_level=` | Patients, Overview |
| `GET` | `/dashboard/patients/{id}/sessions` | Patient detail |
| `GET` | `/dashboard/escalations?unresolved_only=` | Escalations, Overview |
| `PATCH` | `/dashboard/escalations/{id}/resolve` | Resolve action |
| `GET` | `/dashboard/analytics/summary` | Overview KPIs |

Types in `src/lib/types.ts` mirror `backend/models/schemas/*.py`.

## Getting started

```bash
cd frontend
npm install
cp .env.example .env     # optional — set VITE_API_BASE_URL
npm run dev              # http://localhost:5173
```

The dev server proxies `/dashboard` and `/health` to `http://localhost:8000`
(override with `VITE_API_PROXY_TARGET`). With the backend running, sign in using a
coordinator JWT. Without it, click **Explore with demo data**.

## Build

```bash
npm run build     # type-check + production bundle -> dist/
npm run preview   # serve the built bundle
```

## Configuration

| Env var | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Absolute backend URL for production builds. Blank = same-origin / dev proxy. |
| `VITE_API_PROXY_TARGET` | Dev-only proxy target (default `http://localhost:8000`). |
