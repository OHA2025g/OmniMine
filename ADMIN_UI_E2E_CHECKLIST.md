# Admin Console End-to-End Checklist (Manual)

Use this checklist to validate the **Admin Console UI** in the browser. The checks below map 1:1 to backend behavior already validated via API smoke tests.

## Pre-req
1. Start the app stack (`docker compose up -d` from project root).
2. Open the Admin Console page:
   - `http://127.0.0.1:4005/admin`
3. Login as an `admin` user (if prompted).

## 1) Bulk user actions: deactivate/activate + refresh
1. In **Users & Roles** tab, find any user with:
   - `id:` visible
   - `agent` role (recommended for testing)
2. Copy that user `id` into **Bulk user actions → User IDs (comma separated)**.
3. Click **Deactivate**.
   - Expected: success toast “Bulk action complete …”
4. Click top-right **Refresh**.
   - Expected: the same user shows `inactive` badge.
5. Click **Activate**.
   - Expected: success toast.
6. Click **Refresh** again.
   - Expected: the same user shows `active` badge.

## 2) Audit CSV export downloads a real CSV
1. Go to **Audit & Compliance** tab.
2. Click **Export CSV**.
   - Expected: download starts (a CSV file).
   - Expected: no error toast appears.

## 3) Policy controls save + UI reflects updated values
1. In **Audit & Compliance** tab, locate **Policy controls** card.
2. Change **Password min length** by `+1`.
3. Click **Save policy settings**.
   - Expected: success toast “Policy settings saved”.
4. Click **Refresh** (top-right).
   - Expected: the Policy controls input reflects the new value.

## 4) Generate survey response from resolved case
1. Open **Surveys** page:
   - `http://127.0.0.1:4005/surveys`
2. Click **Add Survey Response**.
3. In **Record Survey Response** dialog:
   - Select any case from **Resolved Case** dropdown.
   - Pick a star **Rating** (for test, use `5`).
   - Optionally add **Comments**.
4. Click **Submit**.
   - Expected: success toast “Survey submitted successfully”.
5. Verify the new survey entry appears in the table.
   - Expected: selected case mapping is shown.
   - Expected: rating/comments reflect submitted values.

## 5) CI gate robustness (what to look for)
This repo includes a CI job that runs `backend/scripts/rbac_permission_matrix_smoke_test.py` on every `push` and `pull_request`.
If it fails only in CI, typical causes are boot timing. The workflow is already hardened to wait for:
- `/healthz`
- `/readyz`

## Helpful notes
- The Admin Console UI displays each user’s `id` and an `active/inactive` badge to support end-to-end validation of bulk actions.
- If a download doesn’t trigger in your browser, check DevTools → Network for a call to:
  - `POST /api/audit/export/csv`

