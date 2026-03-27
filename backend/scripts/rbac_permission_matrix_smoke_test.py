import json
import sys
import time
import uuid
import urllib.error
import urllib.request
import urllib.parse


BASE_URL = "http://127.0.0.1:8001"

# Use a gmail domain to avoid any strict email validation.
TEST_EMAIL_DOMAIN = "gmail.com"
TEST_PASSWORD = "RbacTest@12345"


def _http_json(
    method: str,
    path: str,
    token: str | None = None,
    payload: dict | None = None,
    query: dict | None = None,
):
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return status, json.loads(body.decode("utf-8"))
            # For CSV export or other non-json responses, return raw bytes.
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        try:
            decoded = body.decode("utf-8")
            return e.code, json.loads(decoded)
        except Exception:
            return e.code, {"detail": decoded[:200]}


def _register_or_login(email: str, name: str, role: str, org_id: str):
    # Register (public endpoint). If already exists, login instead.
    reg_payload = {"email": email, "name": name, "role": role, "org_id": org_id, "password": TEST_PASSWORD}
    status, resp = _http_json("POST", "/api/auth/register", payload=reg_payload)
    if status != 200:
        # Expected: 400 if already registered.
        pass
    status, resp = _http_json("POST", "/api/auth/login", payload={"email": email, "password": TEST_PASSWORD})
    if status != 200:
        raise RuntimeError(f"Login failed for {email}: status={status} resp={resp}")
    return resp["access_token"], resp.get("user", {})


def _must_status(actual: int, expected: int, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def _http_multipart(
    method: str,
    path: str,
    token: str | None,
    fields: dict,
    file_field: str,
    file_name: str,
    file_bytes: bytes,
    file_content_type: str = "text/plain",
):
    boundary = "----Boundary" + uuid.uuid4().hex
    parts = []

    for name, value in (fields or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        )

    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_name}\"\r\nContent-Type: {file_content_type}\r\n\r\n"
    )

    body_prefix = "".join(parts).encode("utf-8")
    body = body_prefix + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url=url, data=body, method=method.upper())
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in ctype:
                return status, json.loads(raw.decode("utf-8"))
            return status, raw
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        try:
            decoded = raw.decode("utf-8")
            return e.code, json.loads(decoded)
        except Exception:
            return e.code, {"detail": decoded[:200]}


def main():
    org_id = "default"

    roles = ["admin", "manager", "agent", "analyst"]
    # Create one unique email per run to avoid conflicts.
    run_tag = uuid.uuid4().hex[:8]
    role_users = {}

    for r in roles:
        email = f"rbac_{r}_{run_tag}@{TEST_EMAIL_DOMAIN}"
        token, user = _register_or_login(email=email, name=f"RBAC {r}", role=r, org_id=org_id)
        role_users[r] = {"email": email, "token": token, "user": user}
        time.sleep(0.2)  # tiny stagger to avoid request bursts

    # Permission expectations for key endpoints:
    # 200 if allowed, 403 if denied.
    expect_403 = {"403"}
    expected = {
        "admin/summary": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
        "orgs_list": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "dummy_feedback_batch": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "audit_query": {"admin": 200, "manager": 200, "agent": 403, "analyst": 200},
        "audit_export": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "sla_check": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "settings_update": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "bulk_user_action": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
        "agent_profile_update": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "case_create": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "case_assign": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "case_start": {"admin": 200, "manager": 200, "agent": 200, "analyst": 403},
        "case_resolve": {"admin": 200, "manager": 200, "agent": 200, "analyst": 403},
        "case_verify": {"admin": 200, "manager": 200, "agent": 200, "analyst": 403},
        "case_evidence_upload": {"admin": 200, "manager": 200, "agent": 200, "analyst": 403},
        "monitoring_live": {"admin": 200, "manager": 200, "agent": 200, "analyst": 200},
        "ingest_website": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "ingest_support_ticket": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "hitl_gate_priority": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "orchestration_start": {"admin": 200, "manager": 200, "agent": 200, "analyst": 200},
        "orchestration_resume": {"admin": 200, "manager": 200, "agent": 200, "analyst": 200},
        "orchestration_cancel": {"admin": 200, "manager": 200, "agent": 200, "analyst": 200},
        "case_escalate": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "auth_switch_org": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "reports_scheduled_create": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "reports_scheduled_delete": {"admin": 200, "manager": 200, "agent": 403, "analyst": 403},
        "social_settings_delete": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
        "org_create": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
        "user_role_change": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
        "user_org_move": {"admin": 200, "manager": 403, "agent": 403, "analyst": 403},
    }

    results = []

    # Admin summary
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("GET", "/api/admin/summary", token=token)
        results.append((role, "admin/summary", status))
        _must_status(status, expected["admin/summary"][role], "admin/summary")

    # Orgs list
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("GET", "/api/orgs", token=token)
        results.append((role, "orgs_list", status))
        _must_status(status, expected["orgs_list"][role], "orgs_list")

    # Dummy feedback batch (HF optional server-side, template fallback should work)
    fb_id = None
    for role in roles:
        token = role_users[role]["token"]
        status, resp = _http_json(
            "POST",
            "/api/dev/dummy-feedback/batch",
            token=token,
            payload={"count": 1, "negative_min": 0.55, "negative_max": 0.6},
        )
        results.append((role, "dummy_feedback_batch", status))
        _must_status(status, expected["dummy_feedback_batch"][role], "dummy_feedback_batch")
        if role == "admin" and isinstance(resp, dict) and resp.get("items"):
            fb_id = resp["items"][0].get("id")

    if not fb_id:
        raise RuntimeError("Failed to obtain feedback id from admin dummy batch")

    # Audit query
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("POST", "/api/audit", token=token, payload={"limit": 5})
        results.append((role, "audit_query", status))
        _must_status(status, expected["audit_query"][role], "audit_query")

    # Audit export (CSV)
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("POST", "/api/audit/export/csv", token=token, payload={"limit": 50})
        results.append((role, "audit_export", status))
        _must_status(status, expected["audit_export"][role], "audit_export")

    # SLA check
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("POST", "/api/sla/check", token=token, payload={})
        results.append((role, "sla_check", status))
        _must_status(status, expected["sla_check"][role], "sla_check")

    # Settings update
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            "/api/settings/system",
            token=token,
            payload={"sla_default_hours": 24},
        )
        results.append((role, "settings_update", status))
        _must_status(status, expected["settings_update"][role], "settings_update")

    # Bulk user action - admin can deactivate an agent
    agent_user = role_users["agent"]["user"]
    agent_id = agent_user.get("id")
    if not agent_id:
        raise RuntimeError("Agent user id missing from token user payload")

    status, _ = _http_json(
        "POST",
        "/api/users/bulk-action",
        token=role_users["admin"]["token"],
        payload={"user_ids": [agent_id], "action": "deactivate"},
    )
    results.append(("admin", "bulk_user_action", status))
    _must_status(status, expected["bulk_user_action"]["admin"], "bulk_user_action")

    # Now agent login should fail with 403 User is deactivated.
    status, _ = _http_json(
        "POST",
        "/api/auth/login",
        payload={"email": role_users["agent"]["email"], "password": TEST_PASSWORD},
    )
    if status != 403:
        raise AssertionError(f"deactivated login: expected 403, got {status}")

    # Reactivate for cleanup.
    status, _ = _http_json(
        "POST",
        "/api/users/bulk-action",
        token=role_users["admin"]["token"],
        payload={"user_ids": [agent_id], "action": "activate"},
    )
    results.append(("admin", "bulk_user_action_cleanup_activate", status))
    _must_status(status, 200, "bulk_user_action_cleanup_activate")

    # Finally agent login should succeed.
    status, _ = _http_json(
        "POST",
        "/api/auth/login",
        payload={"email": role_users["agent"]["email"], "password": TEST_PASSWORD},
    )
    _must_status(status, 200, "agent_login_after_reactivate")

    # Non-admin bulk_user_action calls should be denied.
    for role in ["manager", "agent", "analyst"]:
        status, _ = _http_json(
            "POST",
            "/api/users/bulk-action",
            token=role_users[role]["token"],
            payload={"user_ids": [agent_id], "action": "deactivate"},
        )
        results.append((role, "bulk_user_action_denied", status))
        _must_status(status, expected["bulk_user_action"][role], "bulk_user_action_denied")

    # Agent profile update endpoint
    # Update each role's own profile with a harmless workload change (upsert allowed).
    for role in roles:
        token = role_users[role]["token"]
        target_user_id = role_users[role]["user"].get("id")
        if not target_user_id:
            raise RuntimeError(f"Missing user id for role={role}")
        status, _ = _http_json(
            "PUT",
            f"/api/agents/profiles/{target_user_id}",
            token=token,
            payload={"max_workload": 12},
        )
        results.append((role, "agent_profile_update", status))
        _must_status(status, expected["agent_profile_update"][role], "agent_profile_update")

    # Case lifecycle RBAC (create/assign/start/resolve/verify)
    admin_case_payload = {
        "feedback_id": fb_id,
        "title": f"RBAC case {run_tag}",
        "description": "permission-matrix-smoke-test",
        "priority": "medium",
    }

    admin_case_id = None
    for role in roles:
        token = role_users[role]["token"]
        status, resp = _http_json(
            "POST",
            "/api/cases",
            token=token,
            payload=admin_case_payload,
        )
        results.append((role, "case_create", status))
        _must_status(status, expected["case_create"][role], "case_create")
        if role == "admin" and isinstance(resp, dict):
            admin_case_id = resp.get("id")

    if not admin_case_id:
        raise RuntimeError("Missing admin_case_id after admin case_create")

    # assign (uses query param `assignee_id`)
    agent_user_id = role_users["agent"]["user"].get("id")
    if not agent_user_id:
        raise RuntimeError("Missing agent user id")

    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            f"/api/cases/{admin_case_id}/assign",
            token=token,
            query={"assignee_id": agent_user_id},
        )
        results.append((role, "case_assign", status))
        _must_status(status, expected["case_assign"][role], "case_assign")

    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            f"/api/cases/{admin_case_id}/start",
            token=token,
        )
        results.append((role, "case_start", status))
        _must_status(status, expected["case_start"][role], "case_start")

        status, _ = _http_json(
            "PUT",
            f"/api/cases/{admin_case_id}/resolve",
            token=token,
            query={"resolution_notes": "RBAC smoke test resolve"},
        )
        results.append((role, "case_resolve", status))
        _must_status(status, expected["case_resolve"][role], "case_resolve")

        status, _ = _http_json(
            "POST",
            f"/api/cases/{admin_case_id}/verify",
            token=token,
            payload={
                "case_id": admin_case_id,
                "feedback_id": fb_id,
                "rating": 5,
                "comments": "RBAC verify smoke test",
            },
        )
        results.append((role, "case_verify", status))
        _must_status(status, expected["case_verify"][role], "case_verify")

        # Evidence upload endpoint (multipart/form-data).
        status, _ = _http_multipart(
            "POST",
            f"/api/cases/{admin_case_id}/evidence",
            token=token,
            fields={"note": "RBAC evidence smoke test"},
            file_field="file",
            file_name="evidence.txt",
            file_bytes=b"evidence-bytes",
            file_content_type="text/plain",
        )
        results.append((role, "case_evidence_upload", status))
        _must_status(status, expected["case_evidence_upload"][role], "case_evidence_upload")

    # Monitoring live snapshot should be accessible to all authenticated roles.
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json("GET", "/api/monitoring/live", token=token)
        results.append((role, "monitoring_live", status))
        _must_status(status, expected["monitoring_live"][role], "monitoring_live")

    # Ingestion endpoints are protected by FEEDBACK_INGEST permission.
    ingest_payload = {
        "content": "RBAC ingest test: visibility and permissions",
        "author_name": f"RBAC {run_tag}",
    }
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "POST",
            "/api/ingest/website",
            token=token,
            payload=ingest_payload,
        )
        results.append((role, "ingest_website", status))
        _must_status(status, expected["ingest_website"][role], "ingest_website")

        status, _ = _http_json(
            "POST",
            "/api/ingest/support-ticket",
            token=token,
            payload=ingest_payload,
        )
        results.append((role, "ingest_support_ticket", status))
        _must_status(status, expected["ingest_support_ticket"][role], "ingest_support_ticket")

    # HITL gate endpoint is protected by HITL_APPROVE permission.
    # Create a fresh orchestration run per role so earlier approvals don't change expectations.
    for role in roles:
        token = role_users[role]["token"]
        gate_step_key = None
        run_id = None
        run_resp = None

        # Try starting/cancelling until we find a gate step that is truly "needs_approval".
        for attempt in range(2):
            status, run_resp = _http_json(
                "POST",
                f"/api/agentic/orchestrations/case/{admin_case_id}",
                token=token,
                payload={},
            )
            if status != 200 or not isinstance(run_resp, dict) or not run_resp.get("id"):
                raise RuntimeError(f"Failed to start orchestration for role={role}: status={status}, resp={run_resp}")

            results.append((role, "orchestration_start", status))
            _must_status(status, expected["orchestration_start"][role], "orchestration_start")

            run_id = run_resp["id"]
            steps = run_resp.get("steps") or []
            gate_step_key = None
            for s in steps:
                if s.get("requires_approval") and s.get("status") == "needs_approval":
                    gate_step_key = s.get("key")
                    break

            if gate_step_key:
                break

            # If we don't see a real pending gate, cancel and restart.
            _http_json(
                "POST",
                f"/api/agentic/orchestrations/{run_id}/cancel",
                token=token,
            )

        if not gate_step_key:
            raise RuntimeError(f"Could not find a gate step in needs_approval for role={role}, run={run_resp}")

        status, gate_resp = _http_json(
            "POST",
            f"/api/agentic/orchestrations/{run_id}/gates/{gate_step_key}",
            token=token,
            payload={"decision": "approve", "note": "RBAC smoke test"},
        )
        results.append((role, "hitl_gate_priority", status))
        if status != expected["hitl_gate_priority"][role]:
            # Give more context to debug gate-step state issues.
            raise AssertionError(
                f"hitl_gate_priority role={role} expected {expected['hitl_gate_priority'][role]} got {status} resp={gate_resp}"
            )

        # Resume/cancel are auth-protected but not permission-restricted in backend.
        status, _ = _http_json(
            "POST",
            f"/api/agentic/orchestrations/{run_id}/resume",
            token=token,
            payload=None,
        )
        results.append((role, "orchestration_resume", status))
        _must_status(status, expected["orchestration_resume"][role], "orchestration_resume")

        status, _ = _http_json(
            "POST",
            f"/api/agentic/orchestrations/{run_id}/cancel",
            token=token,
            payload=None,
        )
        results.append((role, "orchestration_cancel", status))
        _must_status(status, expected["orchestration_cancel"][role], "orchestration_cancel")

    # Case escalation (permission-guarded)
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            f"/api/cases/{admin_case_id}/escalate",
            token=token,
            query={"reason": "RBAC smoke test escalation"},
        )
        results.append((role, "case_escalate", status))
        _must_status(status, expected["case_escalate"][role], "case_escalate")

    # Org switch (permission-guarded)
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "POST",
            "/api/auth/switch-org",
            token=token,
            payload={"org_id": "default"},
        )
        results.append((role, "auth_switch_org", status))
        _must_status(status, expected["auth_switch_org"][role], "auth_switch_org")

    # Scheduled reports (permission-guarded)
    report_payload = {
        "name": f"RBAC report {run_tag}",
        "report_type": "daily_digest",
        "schedule": "daily",
        "recipients": ["rbac_test@gmail.com"],
    }

    # Create once (admin) so we have a concrete report_id to test deletes.
    admin_token = role_users["admin"]["token"]
    admin_create_query = {
        "name": report_payload["name"],
        "report_type": report_payload["report_type"],
        "schedule": report_payload["schedule"],
    }
    status, admin_resp = _http_json(
        "POST",
        "/api/reports/scheduled",
        token=admin_token,
        payload=report_payload["recipients"],
        query=admin_create_query,
    )
    results.append(("admin", "reports_scheduled_create", status))
    _must_status(status, expected["reports_scheduled_create"]["admin"], "reports_scheduled_create")
    report_id = admin_resp.get("report_id") if isinstance(admin_resp, dict) else None
    if not report_id:
        raise RuntimeError("Missing report_id from admin scheduled report create")

    # Check create permission for each role.
    for role in roles:
        token = role_users[role]["token"]
        create_query = {
            "name": report_payload["name"],
            "report_type": report_payload["report_type"],
            "schedule": report_payload["schedule"],
        }
        status, _ = _http_json(
            "POST",
            "/api/reports/scheduled",
            token=token,
            payload=report_payload["recipients"],
            query=create_query,
        )
        results.append((role, "reports_scheduled_create", status))
        _must_status(status, expected["reports_scheduled_create"][role], "reports_scheduled_create")

    # Check delete permission for each role using the admin-created report_id.
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "DELETE",
            f"/api/reports/scheduled/{report_id}",
            token=token,
            payload=None,
        )
        results.append((role, "reports_scheduled_delete", status))
        _must_status(status, expected["reports_scheduled_delete"][role], "reports_scheduled_delete")

    # Social media settings delete (permission-guarded)
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "DELETE",
            "/api/settings/social/twitter",
            token=token,
            payload=None,
        )
        results.append((role, "social_settings_delete", status))
        _must_status(status, expected["social_settings_delete"][role], "social_settings_delete")

    # Admin org + role/membership management endpoints.
    analyst_user_id = role_users["analyst"]["user"].get("id")
    if not analyst_user_id:
        raise RuntimeError("Missing analyst user id")

    org_name = f"rbac_org_{run_tag}"
    admin_token = role_users["admin"]["token"]
    status, new_org_resp = _http_json(
        "POST",
        "/api/orgs",
        token=admin_token,
        payload={"name": org_name},
    )
    results.append(("admin", "org_create", status))
    _must_status(status, expected["org_create"]["admin"], "org_create")
    new_org_id = new_org_resp.get("id") if isinstance(new_org_resp, dict) else None
    if not new_org_id:
        raise RuntimeError("Missing new_org_id from org_create response")

    # Verify org_create is denied for non-admin roles.
    for role in ["manager", "agent", "analyst"]:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "POST",
            "/api/orgs",
            token=token,
            payload={"name": f"{org_name}_{role}_denied"},
        )
        results.append((role, "org_create_denied", status))
        _must_status(status, expected["org_create"][role], "org_create_denied")

    # Move analyst user to new org (admin allowed only).
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            f"/api/orgs/{new_org_id}/users/{analyst_user_id}",
            token=token,
            payload=None,
        )
        results.append((role, "user_org_move", status))
        _must_status(status, expected["user_org_move"][role], "user_org_move")

    # Switch admin token into the new org to verify move took effect.
    status, switched = _http_json(
        "POST",
        "/api/auth/switch-org",
        token=role_users["admin"]["token"],
        payload={"org_id": new_org_id},
    )
    if status != 200 or not isinstance(switched, dict) or not switched.get("access_token"):
        raise RuntimeError(f"auth/switch-org failed status={status} resp={switched}")
    admin_token_switched = switched.get("access_token")

    status, users_in_new_org = _http_json(
        "GET",
        "/api/users",
        token=admin_token_switched,
        payload=None,
    )
    if status != 200 or not isinstance(users_in_new_org, list):
        raise RuntimeError(f"get /api/users failed status={status} data={users_in_new_org}")
    moved_user = next((u for u in users_in_new_org if u.get("id") == analyst_user_id), None)
    if not moved_user or moved_user.get("org_id") != new_org_id:
        raise RuntimeError(f"User move not reflected in new org: moved_user={moved_user}")

    # Change user role (admin allowed only).
    # Use query parameter new_role because frontend calls it as query.
    new_role_value = "manager"
    for role in roles:
        token = role_users[role]["token"]
        status, _ = _http_json(
            "PUT",
            f"/api/users/{analyst_user_id}/role",
            token=token,
            payload=None,
            query={"new_role": new_role_value},
        )
        results.append((role, "user_role_change", status))
        _must_status(status, expected["user_role_change"][role], "user_role_change")

    # Verify role changed when admin is in the moved org.
    status, users_in_new_org2 = _http_json(
        "GET",
        "/api/users",
        token=admin_token_switched,
        payload=None,
    )
    moved_user2 = next((u for u in users_in_new_org2 if u.get("id") == analyst_user_id), None)
    if not moved_user2 or moved_user2.get("role") != new_role_value:
        raise RuntimeError(f"Role change not reflected: moved_user2={moved_user2}")

    # Print summary
    print("RBAC permission matrix smoke test: PASS")
    # Keep output compact but useful.
    for role, label, status in results:
        print(f"{role:7s} {label:28s} -> {status}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"RBAC permission matrix smoke test: FAIL: {e}", file=sys.stderr)
        sys.exit(1)

