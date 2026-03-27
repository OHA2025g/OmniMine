# OmniMine — Detailed user guide

This document explains **how to use OmniMine** screen-by-screen: buttons, fields, and workflows as implemented in the current web app.

- **Pure step-by-step procedures:** [STEP_BY_STEP_OMNIMINE.md](./STEP_BY_STEP_OMNIMINE.md)  
- **Short overview:** [HOW_TO_USE_OMNIMINE.md](./HOW_TO_USE_OMNIMINE.md)  
- **Deployment and ops:** [DEPLOYMENT.md](../DEPLOYMENT.md)

---

## Table of contents

1. [What you need](#1-what-you-need)
2. [Starting the application](#2-starting-the-application)
3. [Signing in and registering](#3-signing-in-and-registering)
4. [Application shell (layout)](#4-application-shell-layout)
5. [Dashboard](#5-dashboard)
6. [Feedback](#6-feedback)
7. [Cases](#7-cases)
8. [Smart Routing (Agents page)](#8-smart-routing-agents-page)
9. [Analytics](#9-analytics)
10. [Alerts](#10-alerts)
11. [Surveys](#11-surveys)
12. [Settings](#12-settings)
13. [Admin Console](#13-admin-console)
14. [Roles and permissions](#14-roles-and-permissions)
15. [Deep links and integrations](#15-deep-links-and-integrations)
16. [Troubleshooting](#16-troubleshooting)
17. [Related documentation](#17-related-documentation)

---

## 1. What you need

- A **supported browser** (Chrome, Edge, Firefox, Safari — current versions).
- The **web app URL** (e.g. `http://localhost:4005` when running Docker locally).
- **Credentials** issued by your administrator, or access to **Register** if self-sign-up is allowed.
- Optional: **Backend URL** configured in the frontend (`REACT_APP_BACKEND_URL`) so API calls and evidence file links resolve correctly.

---

## 2. Starting the application

### 2.1 Local Docker

From the repository root:

```bash
docker compose up --build
```

| Service | Typical URL |
|--------|----------------|
| Web UI | `http://localhost:4005` |
| API | `http://localhost:8001` |
| MongoDB | `localhost:27017` |

### 2.2 Health (for operators)

- **Liveness:** `GET /healthz` on the API host.
- **Readiness (DB):** `GET /readyz` on the API host.

If the UI loads but data fails, check **`/readyz`** first.

---

## 3. Signing in and registering

### 3.1 Login (`/login`)

1. Open **`/login`**.
2. Enter **Email** and **Password**.
3. Click **Sign in**.
4. On success, you are redirected to the **Dashboard** (`/`).

A link **Create account** goes to **`/register`**.

### 3.2 Register (`/register`)

1. Open **`/register`**.
2. Fill in:
   - **Full Name** (required)
   - **Email** (required)
   - **Password** (required, minimum 6 characters in the form)
   - **Role** — choose one of: **Analyst**, **Agent**, **Manager**, **Admin**  
     > In production, restrict who may register as **Admin** or **Manager**; the UI allows selection for development convenience.
3. Click **Create account**.
4. On success, you are signed in and sent to the **Dashboard**.

A link **Sign in** returns to **`/login`**.

---

## 4. Application shell (layout)

After login you see:

- **Left sidebar** — navigation to main modules.
- **Top area** — user menu, optional **organization** control, and on smaller screens a **menu** control to open the sidebar.
- **Main content** — the selected page.

### 4.1 Navigation items

| Sidebar label | Path | Notes |
|---------------|------|--------|
| Dashboard | `/` | Home |
| Feedback | `/feedback` | |
| Cases | `/cases` | |
| Smart Routing | `/agents` | Agent profiles & skills |
| Analytics | `/analytics` | |
| Alerts | `/alerts` | |
| Surveys | `/surveys` | |
| Settings | `/settings` | |
| Admin Console | `/admin` | **Only if your user role is `admin`** |

### 4.2 Organization switching (admins)

Users with role **`admin`** can switch the **active organization** from the header control (orgs are loaded from the API). After switching:

- Lists and metrics refresh for the **new org**.
- If data looks wrong, confirm the org name shown in the header matches the tenant you expect.

### 4.3 Sign out

Use the user menu in the header and choose sign out (terminates the session in the app).

### 4.4 Real-time alerts (background)

While logged in, the app opens a **Server-Sent Events (SSE)** stream for alerts. You may see **toast notifications** for important events (e.g. case escalated, SLA breach). **Escalation-style** toasts may be auto-marked read to avoid repeats.

### 4.5 Dev-only: feedback floater

In some dev builds, a **floating control** can generate sample feedback. Do not rely on it in production training.

---

## 5. Dashboard

**Path:** `/`

### 5.1 Purpose

High-level view of feedback volume, sentiment, sources, recent items, and **live monitoring** snapshots.

### 5.2 Header actions

- **Executive Digest** — opens a dialog:
  - Choose window **7d**, **14d**, or **30d**.
  - Click **Generate** to fetch an AI-style digest.
  - When present, the dialog shows **Summary**, **Top themes**, **Risks**, and **Recommended actions**.
- **Load Demo Data** — visible when there is **no feedback yet**. Seeds demo content via the API, then refreshes widgets.

### 5.3 Live monitoring

A card refreshes approximately every **3 seconds** with live monitoring metrics (when the backend supports it). If it stays empty on first load, wait briefly or check API connectivity.

### 5.4 Charts and lists

Typical content includes:

- Sentiment / trend charts (e.g. last 14 days for initial load).
- Source distribution.
- **Recent feedback** and **recent cases** with links to drill in.

Use the Dashboard as the starting point; open **Feedback** or **Cases** for full tables.

---

## 6. Feedback

**Path:** `/feedback`

### 6.1 Purpose

Capture customer or internal feedback, run **AI analysis** (sentiment, themes, emotions, etc.), optionally **create cases**, and browse history with filters.

### 6.2 Add feedback

1. Click **Add Feedback**.
2. In the dialog:
   - **Source** — Twitter, Facebook, YouTube, Website, Support Ticket, Email, Survey, or Manual.
   - **Author Name** (optional).
   - **Feedback Content** (required).
3. Click **Add & Analyze**.  
   - The system analyzes the text.  
   - If a **case** is auto-created (e.g. from negative feedback), a second success message may appear.

### 6.3 Filters and search

- **Search** — filters the table by text in **content** or **author name** (client-side).
- **Source** — All or a specific channel.
- **Sentiment** — All, Positive, Neutral, Negative (server-side filter on refresh).

### 6.4 Table columns

- **Feedback** — snippet and optional author.
- **Source**, **Sentiment** (or **Pending** if not analyzed yet).
- **Themes** — up to two theme badges.
- **Date**.
- **Actions** — **View** (eye), **Re-analyze** (refresh icon), **Create case** (folder) for **negative** items **without** a case yet, or **View case** when `case_id` exists.

### 6.5 Feedback detail dialog

Open with the **eye** icon. You may see:

- Full **content**, **source**, **author**.
- **AI Analysis**: sentiment + confidence, sarcasm flag, **emotions**, **themes**, **key phrases**.
- Buttons: **Re-analyze**, **Create Case** (if no case), **View Case** (if linked).

---

## 7. Cases

**Path:** `/cases`

### 7.1 Purpose

Track issues from **open** through **assignment**, **in progress**, **resolved**, **verified** / **closed**, and **escalated** (status exists in filters when applicable).

### 7.2 List filters

- **Search** — by **title** (client-side).
- **Status** — All, Open, Assigned, In Progress, Resolved, Verified, Closed, Escalated.
- **Priority** — All, Low, Medium, High, Critical.

### 7.3 Row actions

- **Smart Routing** (lightning) — only when the case is **unassigned**. Opens routing analysis (see §7.8).
- **View** (eye) — opens **Case Details** dialog.

### 7.4 Case details — top section

Shows **title**, **status**, **priority**, **created** and **due** dates, and **SLA badges** on the list:

- **Overdue** if past `due_date` (and not closed).
- **Due soon** if within about **4 hours** of due.

### 7.5 Related feedback

If the case has a linked feedback record, the original text and sentiment summary appear in a highlighted block.

### 7.6 Assignment

- Shows current assignee or **Unassigned**.
- **Assign** / **Reassign** opens a dialog: pick a user with role **agent** or **manager**, then **Assign**.  
- Not shown for **resolved** or **closed** cases in the same way as active work states.

### 7.7 Status-driven action bar

- **Assigned** → **Start Work** → moves case to **in progress**.
- **In progress** (and not resolved/closed/assigned-only state per UI logic) → **Resolve Case** → requires **Resolution notes** in the dialog.
- **Resolved** → **Verify & Close** → opens **Customer Verification** dialog:
  - **Rating** 1–5.  
  - UI hint: **Rating ≥ 4 closes the case**; lower ratings **reopen** to **In Progress**.
  - Optional **comments**.

### 7.8 Smart Routing dialog (unassigned cases)

1. Click the **lightning** icon on an unassigned row.
2. Wait for **AI analysis** (category, complexity, required skills, reasoning).
3. Use **Auto-assign** when shown to assign the recommended agent (API `/routing/auto-assign/...`).

### 7.9 AI Copilot (inside case details)

- **Run Triage** — uses related **feedback** to suggest category, priority, and recommended actions.
- **Draft Reply** — generates **customer reply** and **internal note** drafts for the case.
- **Run Workflow** — starts a **multi-step orchestration** that can pause at **HITL** (human-in-the-loop) steps. When a step **needs approval**, use **Approve** or **Reject**. The panel shows outputs such as suggested priority, draft reply, or proposed assignee per step.

Always **review and edit** AI output before sending anything to customers.

### 7.10 Evidence

- Lists uploaded files with optional **note** and **upload time**.
- **View** opens the file URL (served from the backend — ensure `REACT_APP_BACKEND_URL` is correct).
- **Upload file** + optional **Note**, then **Upload Evidence**.

### 7.11 Verification banner

If present, shows **pending** / **passed** / **failed** and rating summary after verification.

### 7.12 Activity log

Chronological **case activity** entries (action, notes, timestamp).

### 7.13 Opening a case via URL

If the app is opened with query **`?case_id=<id>`** on `/cases`, the UI attempts to load and open that case’s details automatically.

---

## 8. Smart Routing (Agents page)

**Path:** `/agents` (labeled **Smart Routing** in the nav)

### 8.1 Purpose

Manage **agent profiles** used by routing: **skills**, **max workload**, **availability**, **shift** times.

### 8.2 Typical workflow

1. Open the page; wait for the agent list to load.
2. Select an agent to view or edit.
3. Adjust **skills** (toggles or checklist), **capacity**, **availability** switch, and **shift** window as offered.
4. Save changes.  
   Permission to update profiles is enforced on the API (`agent:profile_update` — typically **manager** or **admin**).

---

## 9. Analytics

**Path:** `/analytics`

### 9.1 Purpose

Deeper charts than the dashboard: **positive rate**, distributions, **sentiment trends**, **sources**, **themes**, **emotions**.

### 9.2 Trend window

A control (e.g. **30 days** default) refetches **sentiment trends** when changed.

### 9.3 Usage tips

- Use with **Feedback** filters to validate spikes you see here.
- **Analyst** users often spend most of their time here and on read-only audit (Admin or future analyst views per deployment).

---

## 10. Alerts

**Path:** `/alerts`

### 10.1 Purpose

List **in-app alerts** (may overlap with SSE toasts). Shows **severity** (e.g. critical, high, medium, low).

### 10.2 Actions

- Filter **All** vs **Unread**.
- **Mark read** on a single alert.
- **Mark all read** (if available).
- When an alert references a case, use **Open case** (or equivalent) to jump to **`/cases?case_id=...`**.

---

## 11. Surveys

**Path:** `/surveys`

### 11.1 Purpose

Record **post-resolution** satisfaction tied to a **case**.

### 11.2 Submit a survey

1. Click **Add** / create control to open the dialog.
2. Select a **case** — dropdown is populated from cases in **resolved** status.
3. Set **rating** and optional **comments**.
4. Submit; the list refreshes.

---

## 12. Settings

**Path:** `/settings`

Tabs: **General**, **Social Media**, **Users**, **Teams**, **Export**.

### 12.1 General

- **Organization name** — display name for the org.
- **Email notifications** — toggle **Enable Email Alerts**; set **Notification Email** for alert delivery (when backend email is configured).
- **SLA configuration** — hours for **Critical**, **High**, **Medium**, **Low** priorities.
- **Check SLA Breaches** — triggers a server-side SLA check and shows a result toast.
- **Save Settings** — persists organization + notification + SLA fields via **`PUT /api/settings/system`**.

### 12.2 Social Media

For **Twitter/X**, **Facebook**, **YouTube**, **LinkedIn**:

- Toggle **enabled** per platform.
- **Profile/Page URL** and optional **API key**.
- Save per platform (calls **`PUT /api/settings/social/{platform}`**).

### 12.3 Users

- Lists users in the org.
- **Change role** via dropdown (API `updateUserRole`) — subject to your permissions; admins often do this from **Admin Console** instead for governance.

### 12.4 Teams

- Create **teams** and add members (name, description, member management as per UI).

### 12.5 Export

- Export data in **PDF** or **CSV** for configured resource types (feedback, cases, etc. — as implemented).  
- Uses **`POST /api/export/{type}/{format}`** with file download in the browser.

---

## 13. Admin Console

**Path:** `/admin`  
**Access:** UI requires logged-in user with **`role === 'admin'`**. Others see a short “Admin access is required” message.

### 13.1 Summary cards

Top row shows counts such as: **Users**, **Feedback**, **Cases**, **Open Cases**, **Audit (24h)**.

**Refresh** reloads all admin data.

### 13.2 Tab: Users & Roles

Per user card shows **name**, **email**, **id**, **role**, **org**, **active/inactive**.

- **Role** dropdown — `admin`, `manager`, `agent`, `analyst` → saves on change.
- **Organization** dropdown — **move user to org** on change.

**Bulk user actions** card:

- **User IDs** — comma-separated internal user ids.
- **New password** — required only for **Reset Password**.
- Buttons: **Activate**, **Deactivate**, **Reset Password**.

### 13.3 Tab: Organizations

- **Create Organization** — name + **Create**.
- List of orgs with **id** and **name**.

### 13.4 Tab: Audit & Compliance

- **Action filter** — optional string (e.g. action name); **Filter** reloads audit events.
- **Export CSV** — downloads audit export (respects filter / limits per API).
- **Policy controls** — **Password min length**, **Audit retention days**, **MFA required for admins** (true/false). **Save policy settings** persists.

Below: **audit event cards** — action, resource type, actor, timestamp, method/path, HTTP status.

For manual QA steps, see [ADMIN_UI_E2E_CHECKLIST.md](../ADMIN_UI_E2E_CHECKLIST.md).

---

## 14. Roles and permissions

The **Register** screen lets users pick a role in dev; in production you should control this via process/policy.

Backend **permissions** are grouped by **role**. Summary:

| Area | Admin | Manager | Agent | Analyst |
|------|:-----:|:-------:|:-----:|:-------:|
| Full platform / `org:create` | ✓ | | | |
| Org list & switch | ✓ | ✓ | | |
| User list | ✓ | ✓ | ✓ | ✓ |
| Feedback create | ✓ | ✓ | ✓ | |
| Feedback bulk / ingest | ✓ | ✓ | | |
| Cases: create, assign, verify, escalate | ✓ | ✓ | | |
| Cases: start, resolve, evidence | ✓ | ✓ | ✓ | |
| Settings, reports, SLA run | ✓ | ✓ | | |
| AI run | ✓ | ✓ | ✓ | |
| HITL approve | ✓ | ✓ | | |
| Audit read / export | ✓ | ✓ | | |
| Agent profile update | ✓ | ✓ | | |

**Admins** have all permissions. If the UI shows an error toast or disabled behavior, compare your role to this matrix.

---

## 15. Deep links and integrations

- **Cases:** `/cases?case_id=<uuid>` opens the case detail flow.
- **Evidence links** are absolute to **`REACT_APP_BACKEND_URL`** — misconfiguration causes broken downloads.
- **SSE:** `/api/stream/alerts?token=...` — corporate proxies must allow **SSE** and long-lived connections.

---

## 16. Troubleshooting

| Problem | What to try |
|--------|-------------|
| Empty lists | Wrong **org** (admins: switch org); refresh page. |
| Login works, no data | API URL / CORS; browser network tab; **`/readyz`**. |
| 403 on actions | Role lacks permission; ask **admin**. |
| No AI / digest errors | LLM keys not set in backend env; see **DEPLOYMENT.md**. |
| No toasts / stale alerts | SSE blocked; open **Alerts** and use **Mark read**. |
| Evidence “View” 404 | Set **`REACT_APP_BACKEND_URL`** to the API origin the browser can reach. |

---

## 17. Related documentation

| Document | Use |
|----------|-----|
| [HOW_TO_USE_OMNIMINE.md](./HOW_TO_USE_OMNIMINE.md) | Short getting-started guide |
| [USER_GUIDE.md](../USER_GUIDE.md) | End-to-end guide + quick checklist |
| [DEPLOYMENT.md](../DEPLOYMENT.md) | Docker, env vars, CI |
| [SECURITY.md](../SECURITY.md) | Security configuration |
| [ADMIN_UI_E2E_CHECKLIST.md](../ADMIN_UI_E2E_CHECKLIST.md) | Admin UI validation |

---

*This guide is aligned to the OmniMine frontend pages under `frontend/src/pages/`. If your fork changes labels or flows, update this file alongside UI changes.*
