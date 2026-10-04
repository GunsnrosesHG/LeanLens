# LeanLens Frontend v2 — based on shadcn-admin

> **STATUS: ALL PHASES DELIVERED — P0 + P1 + P2 (Oct 3) + P3 (Oct 4).** The v2 UI is live at http://localhost/
> (nginx `location /` → `front-v2`). Old CRA UI kept as fallback — flip `location /`
> back to `http://front:3000` in `nginx/default.conf` + `nginx -s reload` to revert.
> Pages live: Sign-in (JWT), Dashboard (KPIs + 7-day chart + recent reports),
> Reports (filters + evidence-photo dialog), **Cameras (grid + algorithm chips +
> add-camera dialog with network scan / graceful manual fallback + delete with
> confirm — hardened against controller outages)**,
> **Algorithms (per-camera enable/disable — real: the worker suspends detection
> within ~5 s via `toggle-process/` + get-process polling)**,
> **Settings wired to the platform APIs** (Account → djoser password change;
> Company → company API CRUD; Notifications → mailer API: recipients, working
> time, SMTP), **Users (djoser: list / add / delete)**,
> **GDPR (policy + LIVE blur-status indicator fed by the worker heartbeat
> `/api/core/gdpr/worker-status/` → `/api/core/gdpr/status/`)**.
> P3 archive rebuilt: `LeanLens_PFE_Audit.rar` (source v2 + worker + docs + MANIFEST).

Template: https://github.com/satnaing/shadcn-admin (MIT license — attribution kept in `NOTICE.md`).

Template: https://github.com/satnaing/shadcn-admin (MIT license — attribution kept in `NOTICE.md`).
Goal: replace the inherited CRA frontend (currently brand-patched via nginx `sub_filter`
hacks) with a **native LeanLens UI** whose branding is ours in the source, not rewritten
at the proxy.

---

## 1. Why this template fits

| Template feature | LeanLens use |
|---|---|
| Vite + React 19 + TypeScript | Fast build in Docker (multi-stage), modern stack for the report |
| Tailwind v4 + shadcn/ui (Radix) | Accessible, responsive components — zero UI design work |
| TanStack Router (file-based) | Typed routes; `/_authenticated` layout guards sessions for free |
| Light/dark theme + sidebar + topbar | Professional look out of the box |
| `command-menu` (⌘K global search) | Search violations / cameras from anywhere |
| Data-table toolkit (sort, faceted filters, pagination, bulk actions) | Powers the **Reports** page nearly as-is |
| Auth pages (sign-in…) + auth layout | Reused shell; we swap Clerk → Django JWT |
| Error pages (401/403/404/500) |Polished failure states for the demo |

## 2. What we take / adapt / drop

### ✅ Take as-is
- App shell: sidebar (`app-sidebar`), header, top-nav, `authenticated-layout`, theme provider, `config-drawer`
- `data-table/` toolkit, `confirm-dialog`, `date-picker`, `profile-dropdown`, `search`
- Sign-in page, error pages, settings page shells (account / appearance / notifications / display)
- ESLint/Prettier config, `components.json`

### 🔧 Adapt
- **Auth**: delete Clerk everywhere (`src/assets/clerk-*`, `routes/clerk`); replace auth context with a small Django JWT client (`POST /api/auth/jwt/create`, `/api/auth/jwt/refresh`, `/api/auth/users/me/`) storing tokens in memory + refresh on 401. Keep the template's `AuthContext` shape.
- **Users page**: keep UI; wire to djoser endpoints (`/api/auth/users/`) instead of mock JSON.
- **Sidebar data**: replace entries with LeanLens nav (Dashboard, Cameras, Algorithms, Reports, Settings, GDPR).
- **Dashboard**: replace mock cards with KPI cards fed by `/api/reports/all_reports/` + `/api/healthcheck/`.
- **Branding**: `src/assets/logo.tsx` → LeanLens lens mark (`brand/5S.svg` content); favicon → `brand/` icons; dark theme default.

### ❌ Drop
- **Clerk** (external auth service — we have Django)
- **Tasks kanban** page, **Apps/Chat** page — pure demo filler
- **Brand icons** (Discord, Stripe, Zoom…) + `icon-dir`/layout-variant icons we don't expose
- Sign-up / OTP / forgot-password flows (single-tenant, admin-provisioned accounts) — keep `sign-in` only
- Mock data (`src/data/*` for users/tasks), `netlify.toml`, CI, `knip` (optional)
- RTL modifications can stay (harmless) — no need to strip

## 3. LeanLens page map → existing Django API

| New page | Content | Backend endpoints (already live) |
|---|---|---|
| Sign-in | JWT login form | `POST /api/auth/jwt/create` · `/jwt/refresh` · `/users/me/` |
| **Dashboard** | KPI cards (reports today, phone vs idle split, cameras online), recent violations list, mini bar chart by day | `/api/reports/all_reports/` · `/api/healthcheck/` |
| **Cameras** | Card grid; status badge; snapshot thumbnail; add-camera dialog with ONVIF discovery | `GET/POST /api/camera-algorithms/camera/` · `delete-camera/<pk>/` · `camera-for-onvif/` |
| **Algorithms** | Per-camera assignment matrix + enable/disable; algorithm info | `create-process/` · `get-process/<camera_ip>/` · `algorithms-detail/` · `algorithm-info/` |
| **Reports** (the money page) | TanStack table: date range, camera & algorithm faceted filters; row → dialog with **evidence photos (GDPR-blurred)** + status | `search_params/` · `all_reports/` · `by-id/<pk>/` · static `/media/…` photos |
| **Settings** | Company/license info, working time, notifications prefs | `/api/company/` · `/api/mailer/` (WorkingTimeDaysOfWeek) |
| **Users** | djoser user list (admin only) | `/api/auth/users/` |
| **GDPR** | Static policy + blur-status indicator (read from algorithm config) | info only |

## 4. Where it lives & how it ships

```
frontend/                 ← new (clone of shadcn-admin, stripped)
  src/routes/_authenticated/
    dashboard/  cameras/  algorithms/  reports/  settings/  users/  gdpr/
  src/lib/api.ts          ← axios/fetch client: baseURL `/api`, JWT interceptor
Dockerfile.frontend       ← multi-stage: node:20-alpine (pnpm build) → nginx:alpine
```

Compose changes:
- new service `front-v2` (build only, no port published)
- `nginx` proxies `/` → `front-v2:8080` (static), `/api/` + `/media/` + `/images/` → django
- **The old `front` service and every nginx `sub_filter` rewrite + `brand/*.svg` overlay mount become removable** — branding is native. Keep old `front` in the compose file but commented, as demo fallback.

Vite dev proxy (local dev only): `/api` → `http://localhost:8000`.

## 5. Phases (fits the remaining week)

| Phase | Scope | Est. | Demo value |
|---|---|---|---|
| **P0 — Scaffold & brand** ✅ | clone, strip drops, LeanLens logo/theme, sign-in against real JWT, empty pages | ~2 h | Native-brand UI, no proxy hacks |
| **P1 — Money pages** ✅ | Dashboard KPIs + Reports table with evidence-photo dialog + Cameras grid | ~5 h | Jury sees live violations in a modern UI |
| **P2 — Control** ✅ (Oct 3) | Algorithms assignment, settings (company + mailer), users (djoser) | ~3 h | Full management story |
| **P3 — Switch-over** ✅ (Oct 4) | nginx cutover (done in P1), cameras CRUD, GDPR page, audit archive rebuild | ~3 h | Complete page map |

**Recommendation**: P0+P1 before the defense (≈1 day), P2/P3 after. The current UI stays
the fallback at all times — zero risk to the rehearsed demo.

## 6. Risks

- **API contract details** (field names, pagination shape of `all_reports/`) — verify with a live curl before coding each page; the Django endpoints were built for the old UI.
- **Static photo URLs** — reports reference `/media/...` paths; nginx already serves them, keep those location blocks.
- **CORS**: same-origin through nginx → none. For `pnpm dev` only, add CORS_ALLOWED_ORIGINS.
- **Time**: stop at whatever phase the calendar allows; the old UI remains functional.
