# OmniMine — Step-by-step user guide

Follow the sections below **in order** for your situation. Each **Step** is one clear action.  
For screen reference (what every field means), see **[DETAILED_USER_GUIDE.md](./DETAILED_USER_GUIDE.md)**. For roles and troubleshooting, see **[USER_GUIDE.md](../USER_GUIDE.md)**.

## Table of contents

| Part | Topic |
|------|--------|
| **A** | Start OmniMine (Docker) |
| **B** | Create your account |
| **C** | Sign in |
| **CN** | Main navigation (sidebar) |
| **D** | Load demo data & live dashboard |
| **E** | Switch organization (admins) |
| **F** | Submit feedback |
| **G** | Review feedback |
| **H** | Create a case from negative feedback |
| **I** | Work a case end-to-end |
| **U** | Smart Routing — agent profiles |
| **J** | AI Copilot on a case |
| **K** | AI workflow with HITL |
| **L** | Executive digest |
| **M** | Analytics |
| **N** | Alerts |
| **O** | Post-resolution survey |
| **P**–**R** | Settings (general, social, users/teams/export) |
| **S** | Admin Console |
| **T** | Sign out |
| **W** | When something goes wrong |

---

## Part A — Start OmniMine on your computer

**Step A1.** Open a terminal on the machine where the project lives.

**Step A2.** Go to the **repository root** (folder that contains `docker-compose.yml`).

**Step A3.** Run:

```bash
docker compose up --build
```

**Step A4.** Wait until the **frontend** and **backend** services are running without errors.

**Step A5.** Open a browser and go to:

`http://localhost:4005`

You should see the OmniMine **login** or **landing** experience.

> **Note:** The API is usually at `http://localhost:8001`. See **[DEPLOYMENT.md](../DEPLOYMENT.md)** for environment variables.

---

## Part B — Create your account (first time only)

**Step B1.** In the browser, go to **`/register`**, e.g.  
`http://localhost:4005/register`

**Step B2.** Enter your **Full Name**.

**Step B3.** Enter your **Email**.

**Step B4.** Enter a **Password** (at least 6 characters as required by the form).

**Step B5.** Open the **Role** dropdown and choose one:
- **Analyst** — mostly read/analytics  
- **Agent** — handle cases  
- **Manager** — broader operations  
- **Admin** — full access including Admin Console  

> In production, your IT team should control who gets **Admin** / **Manager**.

**Step B6.** Click **Create account**.

**Step B7.** If the page redirects to the **Dashboard**, registration succeeded.

---

## Part C — Sign in (returning users)

**Step C1.** Go to **`/login`**, e.g.  
`http://localhost:4005/login`

**Step C2.** Enter **Email**.

**Step C3.** Enter **Password**.

**Step C4.** Click **Sign in**.

**Step C5.** Confirm you land on the **Dashboard** (`/`).

---

## Part CN — Main navigation (sidebar)

Use this once after login to learn where everything lives.

**Step CN1.** Find the **left sidebar** (on small screens, open it with the **menu** control in the header).

**Step CN2.** Click **Dashboard** — home, charts, digest, and live monitoring.

**Step CN3.** Click **Feedback** — add and browse feedback.

**Step CN4.** Click **Cases** — case queue and detail workflows.

**Step CN5.** Click **Smart Routing** — agent profiles and skills (supports routing).

**Step CN6.** Click **Analytics** — trends and distributions.

**Step CN7.** Click **Alerts** — list of notifications; link to cases when applicable.

**Step CN8.** Click **Surveys** — satisfaction after resolution.

**Step CN9.** Click **Settings** — org name, SLA, social, users, teams, export.

**Step CN10.** If you are an **admin**, click **Admin Console** — cross-org users, orgs, audit, policy.

---

## Part D — Optional: load sample data (empty tenant)

Use this when there is no feedback yet and you want charts populated quickly.

**Step D1.** Sign in and open the **Dashboard** (click **Dashboard** in the left sidebar if needed).

**Step D2.** If you see **Load Demo Data**, click it.

**Step D3.** Wait for the success message.

**Step D4.** Refresh or wait for widgets to update; open **Feedback** to confirm items exist.

**Step D5.** On the **Dashboard**, locate the **Live monitoring** section (it refreshes about every **3 seconds** when the backend is healthy).

**Step D6.** Use it to confirm the app is receiving monitoring data; if it stays empty, check **[DEPLOYMENT.md](../DEPLOYMENT.md)** and API health (`/readyz`).

---

## Part E — Switch organization (admins only)

**Step E1.** Sign in as a user whose **role** is **admin**.

**Step E2.** In the **top header**, find the **organization** control (org name or switcher).

**Step E3.** Click it and select another **organization** you belong to.

**Step E4.** Wait for the confirmation toast; lists and metrics now apply to the **selected org**.

---

## Part F — Submit feedback (manual)

**Step F1.** Click **Feedback** in the sidebar (`/feedback`).

**Step F2.** Click **Add Feedback**.

**Step F3.** Choose **Source** (e.g. Website, Support Ticket, Manual).

**Step F4.** Optionally enter **Author Name**.

**Step F5.** Type the **Feedback Content** (required).

**Step F6.** Click **Add & Analyze**.

**Step F7.** Read the success toast. If a case was auto-created from negative feedback, a second message may appear.

**Step F8.** Confirm the new row appears in the table (use **Search** or **Sentiment** filter if needed).

---

## Part G — Review feedback in the list

**Step G1.** Stay on **Feedback**.

**Step G2.** Use **Search** to find text in content or author name.

**Step G3.** Use **Source** and **Sentiment** dropdowns to narrow the list.

**Step G4.** Click the **eye** icon on a row to open **Feedback Details**.

**Step G5.** Read **AI Analysis** (sentiment, themes, emotions, etc.).

**Step G6.** Optional: click **Re-analyze** to run analysis again.

**Step G7.** Close the dialog when finished.

---

## Part H — Create a case from negative feedback

**Step H1.** On **Feedback**, find an item with **negative** sentiment **without** a case yet.

**Step H2.** Either:
- Click the **folder** icon on the row, **or**  
- Open details (eye) and click **Create Case**.

**Step H3.** Confirm the success toast.

**Step H4.** Click **Cases** in the sidebar to see the new case (or use **View Case** from feedback if shown).

---

## Part I — Work a case end-to-end (typical agent/manager flow)

### I.1 Open the case

**Step I1.** Click **Cases** in the sidebar.

**Step I2.** Optionally filter by **Status** or **Priority**, or **Search** by title.

**Step I3.** Click the **eye** icon on a case to open **Case Details**.

---

### I.2 Assign the case (if unassigned)

**Step I4.** In **Case Details**, under **Assigned To**, click **Assign** (or **Reassign**).

**Step I5.** Choose a **team member** (agents and managers appear in the list).

**Step I6.** Click **Assign** in the dialog.

**Step I7.** Confirm the assignee name updates in the detail view.

---

### I.3 Optional: Smart Routing (before assign)

If the case is **unassigned**, you can use AI routing from the **list**:

**Step I8.** On the **Cases** list, click the **lightning** icon on that row.

**Step I9.** Wait for **Smart Routing Analysis** to finish.

**Step I10.** Review category, skills, and reasoning.

**Step I11.** Click **Auto-Assign to Best Match** if you accept the recommendation (when the button is shown).

---

### I.4 Start work

**Step I12.** With status **Assigned**, open **Case Details** again if needed.

**Step I13.** Click **Start Work**.

**Step I14.** Confirm in the dialog; status becomes **In Progress**.

---

### I.5 Upload evidence (optional)

**Step I15.** In **Case Details**, scroll to **Evidence**.

**Step I16.** Click **Choose file** / file input and pick a file.

**Step I17.** Optionally add a **Note** (e.g. “screenshot of error”).

**Step I18.** Click **Upload Evidence**.

**Step I19.** Use **View** on a row to open the file in a new tab (requires correct **API URL** in frontend config).

---

### I.6 Resolve the case

**Step I20.** While status is **In Progress**, click **Resolve Case**.

**Step I21.** Enter **Resolution Notes** (required).

**Step I22.** Click **Resolve** in the dialog.

**Step I23.** Confirm status shows **Resolved** and notes appear in the detail view.

---

### I.7 Verify and close

**Step I24.** With status **Resolved**, click **Verify & Close**.

**Step I25.** Choose a **Rating** (1–5).

**Step I26.** Optionally add **Comments**.

**Step I27.** Click **Submit**.

**Step I28.** Note: **Rating ≥ 4** typically **closes** the case; **below 4** may **reopen** it to **In Progress** (as indicated in the UI).

---

### I.8 Open a case from a link (deep link)

**Step I29.** When someone shares a URL like  
`http://localhost:4005/cases?case_id=<CASE_ID>`  
open it in the same browser where you are **logged in**.

**Step I30.** Wait for the **Cases** page to load; the app should open **Case Details** for that id automatically.

**Step I31.** If nothing opens, confirm the **case id** is correct, you are in the right **organization** (admins), and you have access to that case.

---

## Part U — Smart Routing (agent profiles)

Use this to keep **agent skills**, **capacity**, and **availability** aligned with automated routing.

**Step U1.** Click **Smart Routing** in the sidebar (`/agents`).

**Step U2.** Wait for the **agent table** to load (name, email, skills, workload bar, satisfaction, availability).

**Step U3.** Find the agent to update; click the **gear** icon on their row (**Edit**).

**Step U4.** In **Edit Agent Profile**, set **Availability Status** (switch) — whether they can receive new assignments.

**Step U5.** Set **Max workload** (capacity) and, if shown, **Shift start** and **Shift end**.

**Step U6.** In **Skills**, toggle each skill the agent should cover (e.g. Technical Support, Billing, Complaints — labels vary).

**Step U7.** Click **Save Profile**. Wait for the success toast.

**Step U8.** Optional: go to **Cases**, pick an **unassigned** case, click the **lightning** icon, and click **Auto-Assign to Best Match** to see routing use profiles.

> If **Save Profile** fails with **403**, your role may lack `agent:profile_update` — ask an admin or manager.

---

## Part J — Use AI Copilot on a case

**Step J1.** Open **Case Details** for a case that has **related feedback**.

**Step J2.** In **AI Copilot**, click **Run Triage** to see category, suggested priority, and actions.

**Step J3.** Click **Draft Reply** to generate **customer reply** and **internal note** drafts.

**Step J4.** Read outputs carefully; **edit before sending** anything to a real customer.

---

## Part K — Run an AI workflow with approvals (HITL)

**Step K1.** Open **Case Details**.

**Step K2.** In **AI Copilot**, click **Run Workflow**.

**Step K3.** Wait until a step shows **needs approval** (or similar).

**Step K4.** Read the step output (priority, draft text, assignee suggestion, etc.).

**Step K5.** Click **Approve** to continue or **Reject** to stop that path.

**Step K6.** Repeat for any further approval steps until the workflow completes or stops.

**Step K7.** Refresh the case if needed to see updated state in the list.

---

## Part L — Executive digest (Dashboard)

**Step L1.** Open **Dashboard**.

**Step L2.** Click **Executive Digest**.

**Step L3.** Choose **7d**, **14d**, or **30d**.

**Step L4.** Click **Generate**.

**Step L5.** Read **Summary**, **Top themes**, **Risks**, and **Recommended actions**.

**Step L6.** Close the dialog when done.

---

## Part M — Analytics

**Step M1.** Click **Analytics** in the sidebar.

**Step M2.** Review overview cards (e.g. positive rate).

**Step M3.** Change the **trend** window if a control is shown (e.g. number of days).

**Step M4.** Scroll through charts for sources, themes, and emotions.

---

## Part N — Alerts

**Step N1.** Click **Alerts** in the sidebar.

**Step N2.** Use the **All** or **Unread** buttons at the top to filter the list.

**Step N3.** For a single unread alert, click the **check** icon on the row to mark it read.

**Step N4.** If you have several unread items, click **Mark All Read** (shown when there is at least one unread alert).

**Step N5.** For alert types such as **case escalated**, **SLA breach**, **case created**, or **case auto assigned**, click **View** on the row to open **`/cases?case_id=...`** for that case.

---

## Part O — Post-resolution survey

**Step O1.** Click **Surveys** in the sidebar.

**Step O2.** Click **Add Survey Response** (top right).

**Step O3.** In **Record Survey Response**, open **Resolved Case** and pick a case (only **resolved** cases are listed).

**Step O4.** Click the **stars** to set **Rating** (1–5); optional: type **Comments**.

**Step O5.** Click **Submit** (or wait for **Submitting...** to finish).

**Step O6.** Confirm the new row appears in the surveys table below.

---

## Part P — Settings: organization, email, SLA

**Step P1.** Click **Settings** in the sidebar.

**Step P2.** Open the **General** tab.

**Step P3.** Set **Organization Name** as needed.

**Step P4.** Toggle **Enable Email Alerts** and set **Notification Email** if you use email alerts.

**Step P5.** Adjust **SLA** hours for Critical / High / Medium / Low.

**Step P6.** Optional: click **Check SLA Breaches** to run a server check.

**Step P7.** Click **Save Settings** at the bottom.

---

## Part Q — Settings: social integrations

**Step Q1.** In **Settings**, open the **Social Media** tab.

**Step Q2.** For each platform (Twitter/X, Facebook, YouTube, LinkedIn):

**Step Q3.** Toggle **enabled** if you use that channel.

**Step Q4.** Enter **Profile/Page URL** and optional **API key**.

**Step Q5.** Save that platform’s configuration (per-card save action).

---

## Part R — Settings: users, teams, export

**Step R1.** Open **Users** tab — review users; change **role** only if your permissions allow.

**Step R2.** Open **Teams** tab — **create team** or add members as the UI provides.

**Step R3.** Open **Export** tab — choose type and **PDF** or **CSV**, then download.

---

## Part S — Admin Console (admin role only)

**Step S1.** Sign in as **admin**.

**Step S2.** Click **Admin Console** in the sidebar (`/admin`).

**Step S3.** Review the **summary** numbers at the top (users, feedback, cases, audit).

**Step S4.** Open tab **Users & Roles**:
- Change a user’s **role** or **organization** from the dropdowns.  
- For bulk work: paste comma-separated **User IDs**, optionally **New password** for reset, then **Activate**, **Deactivate**, or **Reset Password**.

**Step S5.** Open tab **Organizations**:
- Enter a name and click **Create** for a new org.  
- Review listed organizations.

**Step S6.** Open tab **Audit & Compliance**:
- Optionally enter an **Action filter** and click **Filter**.  
- Click **Export CSV** for an audit file.  
- Under **Policy controls**, set password minimum length, audit retention, MFA-for-admins, then **Save policy settings**.

**Step S7.** Click **Refresh** anytime to reload admin data.

---

## Part T — Sign out

**Step T1.** Open your **user menu** in the header.

**Step T2.** Choose **Sign out** (or equivalent).

**Step T3.** Confirm you return to a public/login state.

---

## Part W — When something goes wrong (troubleshooting)

Work through these in order.

**Step W1.** **Blank lists everywhere** — If you are an **admin**, use the header **organization** switcher and pick the correct org; refresh the page.

**Step W2.** **Kicked to login / “Unauthorized”** — Session expired; go to **`/login`** and sign in again.

**Step W3.** **Button fails or “permission” error** — Your **role** may not allow the action; compare with **[USER_GUIDE.md](../USER_GUIDE.md)** (roles matrix) or ask an **admin**.

**Step W4.** **Evidence “View” opens wrong or 404** — Set frontend **`REACT_APP_BACKEND_URL`** to the API base URL the **browser** can reach (see **[DEPLOYMENT.md](../DEPLOYMENT.md)**).

**Step W5.** **No AI / digest errors** — Backend LLM keys may be missing; check env vars in **DEPLOYMENT.md**.

**Step W6.** **No live toasts / alerts feel stale** — Corporate network may block **SSE**; open **Alerts** and use **Mark All Read**; try another network or ask IT to allow long-lived connections to the API.

**Step W7.** **App loads but APIs fail** — Open `http://localhost:8001/readyz` (or your API host). If not OK, fix **MongoDB** and backend logs per **DEPLOYMENT.md**.

---

## Quick path cheat sheet

| I want to… | Go to… | First steps |
|------------|--------|-------------|
| Log in | `/login` | Email → Password → Sign in |
| Add feedback | Feedback | Add Feedback → fill → Add & Analyze |
| Fix an issue | Cases | Open case → Assign → Start Work → Resolve |
| See trends | Analytics | Open page → adjust trend window |
| Get leadership summary | Dashboard | Executive Digest → pick days → Generate |
| Change SLA | Settings → General | Edit hours → Save Settings |
| Manage all tenants/users | Admin Console | Users & Roles / Orgs / Audit tabs |
| Tune who gets routed cases | Smart Routing | Gear on agent → skills & Save Profile |

---

## Related documents

| Document | Purpose |
|----------|---------|
| [DETAILED_USER_GUIDE.md](./DETAILED_USER_GUIDE.md) | Every screen explained in depth |
| [HOW_TO_USE_OMNIMINE.md](./HOW_TO_USE_OMNIMINE.md) | Short overview |
| [USER_GUIDE.md](../USER_GUIDE.md) | Roles matrix, SSE, troubleshooting |
| [ADMIN_UI_E2E_CHECKLIST.md](../ADMIN_UI_E2E_CHECKLIST.md) | Admin QA checklist |

---

*Steps match the OmniMine UI in `frontend/src/pages/`. If your deployment hides features or changes labels, follow your administrator’s instructions.*
