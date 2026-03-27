# OmniMine — End-to-end user guide

This guide walks you through using the OmniMine web app from first login through daily operations, monitoring, AI-assisted workflows, and (for administrators) governance. It matches the current UI routes and backend permissions.

- **Numbered procedures (do this, then this):** **[docs/STEP_BY_STEP_OMNIMINE.md](docs/STEP_BY_STEP_OMNIMINE.md)**  
- **Screen-by-screen reference:** **[docs/DETAILED_USER_GUIDE.md](docs/DETAILED_USER_GUIDE.md)**

---

## 1. What OmniMine does

OmniMine helps teams **collect feedback**, **open and manage cases**, **monitor sentiment and spikes**, **run AI-assisted triage and routing**, and **stay compliant** with audit trails and org-scoped data. Access is **multi-tenant**: each user belongs to one or more **organizations**; most data and actions are scoped to the **active organization**.

---

## 2. Getting the app running

### 2.1 Local Docker (recommended)

From the repository root:

```bash
docker compose up --build
```

| Service    | URL |
|-----------|-----|
| **Web app** | `http://localhost:4005` |
| **API**     | `http://localhost:8001` |
| **MongoDB** | `mongodb://localhost:27017` |

See **`DEPLOYMENT.md`** for environment variables (`JWT_SECRET_KEY`, optional LLM keys, SLA/monitoring intervals).

### 2.2 Health checks (operators)

- `GET http://localhost:8001/healthz` — process is up  
- `GET http://localhost:8001/readyz` — database connectivity  

---

## 3. First-time access

### 3.1 Register

1. Open **`/register`** (e.g. `http://localhost:4005/register`).  
2. Complete the form to create an account.  
3. Your **role** and **organization** are determined by how the deployment seeds users (first user may be admin in dev; production should follow your IT policy).

### 3.2 Sign in

1. Open **`/login`**.  
2. Enter email and password.  
3. After login you land on the **Dashboard** (`/`).

### 3.3 Forgot password / invitations

If your deployment uses email or invite flows, follow your administrator’s instructions. The UI entry points are the same **Login** and **Register** pages unless customized.

---

## 4. Navigation (main menu)

After sign-in, the sidebar includes:

| Route | Label (UI) | Purpose |
|-------|------------|---------|
| `/` | Dashboard | Overview, quick stats, entry to workflows |
| `/feedback` | Feedback | Submit and review feedback |
| `/cases` | Cases | Case queue, SLA, evidence, resolution |
| `/agents` | Smart Routing | Agent profiles and intelligent routing |
| `/analytics` | Analytics | Trends, monitoring, spike detection |
| `/alerts` | Alerts | In-app alert list |
| `/surveys` | Surveys | Survey-related flows |
| `/settings` | Settings | Org and operational settings |
| `/admin` | Admin Console | **Visible only if your role is `admin`** |

**Mobile:** Use the menu control to open/close the sidebar.

---

## 5. Organization context (multi-tenant)

- Most API calls use your **active organization** (`org_id`).  
- **Admins** can **switch organization** from the header/org control (loads orgs you belong to).  
- Non-admins typically work inside a single assigned org unless your deployment grants **org list/switch** to other roles.

If something is “empty,” confirm you are in the correct org.

---

## 6. Real-time alerts (SSE)

While you are logged in, the app opens a **Server-Sent Events** connection to stream **alerts** (e.g. escalations, SLA-related events).

- **Toasts** may appear for important events (e.g. case escalated, SLA breach).  
- Open **Alerts** (`/alerts`) to review and **mark items read**.  
- Unread counts may appear in the shell UI.

**Note:** The stream uses your session token in the query string as required by browsers; protect your screen session like any authenticated tab.

---

## 7. Dashboard (`/`)

Use the dashboard to:

- See **at-a-glance** status for your org.  
- Jump into **Feedback**, **Cases**, or **Analytics** as needed.

Exact widgets depend on your build; treat it as the home base after login.

---

## 8. Feedback (`/feedback`)

### 8.1 Manual feedback

- Create feedback with **source** (e.g. website, support ticket, survey, manual), **text**, and **sentiment** where applicable.  
- **Negative** feedback can feed **case creation** and triage rules depending on org settings and automation.

### 8.2 Bulk / ingest (roles)

**Managers** and **admins** typically can **bulk-create** or **ingest** feedback (API-backed). In the UI, use any provided **bulk** or **import** actions; if an action is missing, your role may not include `feedback:bulk_create` or `feedback:ingest`.

### 8.3 Dev helper: feedback floater

In development builds, a **floating feedback generator** may be available to seed sample data quickly. Do not rely on it in production.

---

## 9. Cases (`/cases`)

Cases represent **work items** tied to customer issues, escalations, or internal follow-ups.

### 9.1 Typical lifecycle

1. **Create** — from feedback automation or manually (permission: `case:create`).  
2. **Assign** — manager/admin often assigns owners (`case:assign`).  
3. **Start / work** — agent picks up and progresses (`case:start`).  
4. **Evidence** — attach proof (screenshots, exports) (`case:evidence_upload`).  
5. **Resolve** — mark resolved (`case:resolve`).  
6. **Verify** — optional QA or manager verification (`case:verify`).  
7. **Escalate** — if SLA or severity requires it (`case:escalate`).

### 9.2 SLA and monitoring

SLA timers and **breach** behavior depend on backend settings and scheduled checks. **Analytics** and **Alerts** help you see pressure before deadlines slip.

If you lack permission for an action, the button or API will be denied — ask a **manager** or **admin**.

---

## 10. Smart Routing (`/agents`)

Use this area to:

- Review **agent profiles** and routing configuration.  
- Align **skills**, capacity, or rules with how cases are distributed.

**Managers/admins** can usually update agent-related settings where permitted (`agent:profile_update`).

---

## 11. Analytics (`/analytics`)

- Review **sentiment trends**, volumes, and **spike** indicators.  
- Use filters/date ranges if the UI exposes them.  
- Pair with **Alerts** when investigating incidents or campaign effects.

**Analysts** focus here and on **read-only audit** views (see roles below).

---

## 12. Surveys (`/surveys`)

- Create or manage **survey**-linked feedback channels as your deployment enables.  
- Survey responses may appear as **feedback** with source `survey`.

---

## 13. Settings (`/settings`)

Org-level settings may include:

- **Branding** and display name.  
- **SLA** targets and operational toggles.  
- **Social** or connector-related options (where implemented).  
- **Scheduled reports** and recipients (manager/admin with `reports:manage`).

Changes usually require **`settings:update`** (managers/admins). **Social settings** may use a separate permission in API (`social_settings:update`).

---

## 14. AI, orchestration, and human-in-the-loop (HITL)

Where enabled:

- **AI run** (`ai:run`) — triage suggestions, summaries, or routing hints.  
- **HITL approve** (`hitl:approve`) — managers/admins confirm sensitive automated actions before they commit.

Always review AI output before acting on **compliance-** or **customer-facing** decisions.

---

## 15. Admin Console (`/admin`) — **admin role only**

If you are an **admin**, you will see **Admin Console** in the nav. Typical capabilities:

- **Platform summary** — high-level counts and health of orgs/users/activity.  
- **Users** — list, invite or adjust users as implemented; **bulk actions** where available.  
- **Organizations** — create or manage org records (`org:create` is admin-only in the permission map).  
- **Audit** — query audit events; **export** to CSV where UI/API allows (`audit:read`, `audit:export`).  
- **Policy / retention** — system-level fields on settings (e.g. retention) per your build.

For a **manual QA checklist** of admin flows, see **`ADMIN_UI_E2E_CHECKLIST.md`**.

---

## 16. Who can do what (roles)

The backend maps **roles** to **permissions**. Summary:

| Capability | Admin | Manager | Agent | Analyst |
|------------|:-----:|:-------:|:-----:|:-------:|
| All permissions | ✓ | | | |
| Org list / switch | ✓ | ✓ | | |
| User list | ✓ | ✓ | ✓ | ✓ |
| Feedback create | ✓ | ✓ | ✓ | |
| Feedback bulk / ingest | ✓ | ✓ | | |
| Case create / assign / verify / escalate | ✓ | ✓ | | |
| Case start / resolve / evidence | ✓ | ✓ | ✓ | |
| Settings / reports / SLA run | ✓ | ✓ | | |
| AI run | ✓ | ✓ | ✓ | |
| HITL approve | ✓ | ✓ | | |
| Audit read / export | ✓ | ✓ | | |
| Agent profile update | ✓ | ✓ | | |
| Org **create** | ✓ | | | |

**Admins** have every permission, including **`org:create`**.

For security practices and headers, see **`SECURITY.md`**.

---

## 17. Common issues

| Symptom | What to check |
|--------|----------------|
| Blank lists | Active **org**; refresh after **org switch**. |
| 401 / logged out | Token expiry; sign in again. |
| Actions disabled or 403 | Your **role** lacks that **permission**; ask admin. |
| No alerts | SSE blocked by network/proxy; try another network or check backend logs. |
| API errors after deploy | **`/readyz`** and Mongo connectivity; see **`DEPLOYMENT.md`**. |

---

## 18. Related documents

| Document | Use |
|----------|-----|
| `docs/STEP_BY_STEP_OMNIMINE.md` | Numbered steps for each workflow |
| `docs/DETAILED_USER_GUIDE.md` | Screen-by-screen field and button reference |
| `DEPLOYMENT.md` | Docker, ports, env, CI, health endpoints |
| `SECURITY.md` | Security configuration |
| `ADMIN_UI_E2E_CHECKLIST.md` | Manual admin UI validation |
| `.github/workflows/ci.yml` | Automated build and API smoke tests |

---

## 19. Quick start checklist (new user)

1. Open app → **Register** or **Login**.  
2. Confirm **organization** (admins: use org switcher if needed).  
3. Skim **Dashboard** → open **Feedback** and submit a test item.  
4. Open **Cases** and walk one item through **assign → resolve** (as your role allows).  
5. Open **Analytics** and **Alerts** to see monitoring.  
6. If you are **admin**, open **Admin Console** and verify **summary** and **audit** access.

---

*This guide reflects the repository’s current routes and permission model. If your deployment customizes roles or hides features, your administrator’s documentation takes precedence.*
