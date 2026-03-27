# How to use OmniMine

OmniMine is a web application for **feedback**, **case management**, **analytics**, **alerts**, and (for admins) **governance**. This page is a short “how to use” guide.

- **Step-by-step (numbered procedures):** **[STEP_BY_STEP_OMNIMINE.md](./STEP_BY_STEP_OMNIMINE.md)**  
- **Detailed (screen-by-screen):** **[DETAILED_USER_GUIDE.md](./DETAILED_USER_GUIDE.md)**  
- **Full reference + roles matrix:** **[USER_GUIDE.md](../USER_GUIDE.md)**

---

## 1. Open the application

**With Docker** (from the project root):

```bash
docker compose up --build
```

Then open the app in your browser:

| What | URL |
|------|-----|
| **OmniMine UI** | `http://localhost:4005` |
| **API** (for integrations / health) | `http://localhost:8001` |

More setup options: **[DEPLOYMENT.md](../DEPLOYMENT.md)**.

---

## 2. Sign in

1. Go to **`/login`** (e.g. `http://localhost:4005/login`).
2. If you have no account yet, use **`/register`** first.
3. After login you start on the **Dashboard** (`/`).

Your data is scoped to an **organization**. If you are an **admin**, you can **switch organization** from the header when you belong to more than one.

---

## 3. Main areas (sidebar)

Use the left navigation to move between:

| Area | Route | What you do there |
|------|--------|-------------------|
| **Dashboard** | `/` | Overview and shortcuts |
| **Feedback** | `/feedback` | Submit and review customer / internal feedback |
| **Cases** | `/cases` | Track issues: assign, add evidence, resolve, escalate |
| **Smart Routing** | `/agents` | Agent profiles and routing-related setup |
| **Analytics** | `/analytics` | Trends, monitoring, spikes |
| **Alerts** | `/alerts` | Read and clear in-app alerts |
| **Surveys** | `/surveys` | Survey-related feedback |
| **Settings** | `/settings` | Organization settings (as your role allows) |
| **Admin Console** | `/admin` | **Admins only** — users, orgs, audit, policies |

---

## 4. Typical day-to-day flow

1. **Check Dashboard** — see what needs attention.  
2. **Alerts** — review notifications (the app can show **live toasts** for urgent items like escalations).  
3. **Feedback** — log or review new input; negative items may drive **cases** automatically depending on configuration.  
4. **Cases** — pick up assigned work: start work, attach **evidence**, **resolve**, and use **verify** / **escalate** when your role allows.  
5. **Analytics** — monitor volume and sentiment between meetings.

If a button or action is missing, your **role** may not have that permission — ask a **manager** or **admin**.

---

## 5. Admins

Admins see **Admin Console** in the sidebar. There you can manage **organizations**, **users**, review **audit** activity, and use bulk tools where the UI exposes them.

Manual checklist for validating the admin UI: **[ADMIN_UI_E2E_CHECKLIST.md](../ADMIN_UI_E2E_CHECKLIST.md)**.

---

## 6. Security and operations

- **Security configuration:** [SECURITY.md](../SECURITY.md)  
- **Health checks:** `http://localhost:8001/healthz` and `/readyz`  
- **Role × permission table:** [USER_GUIDE.md § Who can do what](../USER_GUIDE.md#16-who-can-do-what-roles)

---

## 7. More documentation

- **Step-by-step (numbered):** [STEP_BY_STEP_OMNIMINE.md](./STEP_BY_STEP_OMNIMINE.md)  
- **End-to-end reference** (SSE, AI/HITL, roles, troubleshooting): [USER_GUIDE.md](../USER_GUIDE.md)
