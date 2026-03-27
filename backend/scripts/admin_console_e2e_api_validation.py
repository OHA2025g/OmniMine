import json
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = "http://127.0.0.1:8001"
# Prefer existing local admin credentials if present; otherwise seed fresh users.
ADMIN_EMAIL = "aghoreshwar@hotmail.com"
ADMIN_PASSWORD = "Prince@1804"
SEED_PASSWORD = "AdminSeed@12345"
SEED_NAME_PREFIX = "CI Seed"


def http_json(method: str, path: str, token: str | None = None, payload=None, query: dict | None = None):
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            if "application/json" in resp.headers.get("Content-Type", ""):
                return resp.status, json.loads(body.decode("utf-8")), resp
            # if non-json, return raw bytes
            return resp.status, body, resp
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        ctype = e.headers.get("Content-Type", "") if hasattr(e, "headers") else ""
        try:
            if "application/json" in ctype:
                return e.code, json.loads(raw.decode("utf-8")), e
        except Exception:
            pass
        return e.code, {"detail": raw.decode("utf-8", errors="ignore")[:200]}, e


def login():
    payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    status, data, _ = http_json("POST", "/api/auth/login", payload=payload)
    if status == 200 and isinstance(data, dict) and data.get("access_token"):
        return data["access_token"]
    raise RuntimeError(f"login failed status={status} data={data}")


def register_user(*, email: str, name: str, role: str, password: str):
    payload = {"email": email, "name": name, "role": role, "org_id": "default", "password": password}
    status, data, _ = http_json("POST", "/api/auth/register", payload=payload)
    # If the user already exists, we can proceed to login.
    if status not in (200, 400):
        raise RuntimeError(f"register failed status={status} data={data}")
    return status, data


def get_users(token):
    status, data, _ = http_json("GET", "/api/users", token=token)
    if status != 200:
        raise RuntimeError(f"get_users failed status={status} data={data}")
    return data


def main():
    # 1) Try to login using local creds; if not present (e.g., in CI), seed users.
    seed_suffix = None
    seeded_admin_email = None
    try:
        token = login()
    except Exception:
        seed_suffix = uuid.uuid4().hex[:10]
        admin_email = f"admin_ci_{seed_suffix}@gmail.com"
        seeded_admin_email = admin_email
        agent_email = f"agent_ci_{seed_suffix}@gmail.com"

        # Register admin + agent.
        register_user(
            email=admin_email,
            name=f"{SEED_NAME_PREFIX} Admin",
            role="admin",
            password=SEED_PASSWORD,
        )
        register_user(
            email=agent_email,
            name=f"{SEED_NAME_PREFIX} Agent",
            role="agent",
            password=SEED_PASSWORD,
        )

        # Login using seeded admin.
        status, data, _ = http_json(
            "POST",
            "/api/auth/login",
            payload={"email": admin_email, "password": SEED_PASSWORD},
        )
        if status != 200 or not isinstance(data, dict) or not data.get("access_token"):
            raise RuntimeError(f"seeded login failed status={status} data={data}")
        token = data["access_token"]

    # Pick first agent user (id + is_active must exist for validation).
    users = get_users(token)
    agent = None
    for u in users:
        if u.get("role") == "agent":
            agent = u
            break
    if not agent or not agent.get("id"):
        raise RuntimeError("Could not find agent user in /api/users")

    agent_id = agent["id"]
    print(f"Agent selected: id={agent_id} is_active={agent.get('is_active', True)} email={agent.get('email')}")
    if seeded_admin_email:
        print(f"Seeded admin email: {seeded_admin_email}")

    # 1) Bulk deactivate
    status, data, _ = http_json(
        "POST",
        "/api/users/bulk-action",
        token=token,
        payload={"user_ids": [agent_id], "action": "deactivate"},
    )
    if status != 200:
        raise RuntimeError(f"bulk deactivate failed status={status} data={data}")

    users2 = get_users(token)
    agent2 = next((u for u in users2 if u.get("id") == agent_id), None)
    if not agent2 or agent2.get("is_active") is not False:
        raise RuntimeError(f"bulk deactivate did not apply, is_active={agent2.get('is_active') if agent2 else None}")
    print("Bulk deactivate: PASS")

    # 2) Bulk activate
    status, data, _ = http_json(
        "POST",
        "/api/users/bulk-action",
        token=token,
        payload={"user_ids": [agent_id], "action": "activate"},
    )
    if status != 200:
        raise RuntimeError(f"bulk activate failed status={status} data={data}")

    users3 = get_users(token)
    agent3 = next((u for u in users3 if u.get("id") == agent_id), None)
    if not agent3 or agent3.get("is_active") is not True:
        # if user is missing is_active field, fail hard for strictness
        raise RuntimeError(f"bulk activate did not apply, is_active={agent3.get('is_active') if agent3 else None}")
    print("Bulk activate: PASS")

    # 3) Audit CSV export
    status, csv_body, resp = http_json(
        "POST",
        "/api/audit/export/csv",
        token=token,
        payload={"limit": 10},
    )
    if status != 200:
        raise RuntimeError(f"audit export failed status={status} data={csv_body}")

    content_type = resp.headers.get("Content-Type", "")
    disposition = resp.headers.get("Content-Disposition", "")
    if "text/csv" not in content_type:
        raise RuntimeError(f"unexpected content-type: {content_type}")
    if "attachment" not in disposition.lower():
        raise RuntimeError(f"missing attachment disposition: {disposition}")

    csv_text = csv_body.decode("utf-8", errors="ignore")
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise RuntimeError("CSV export returned too few lines")
    header = lines[0]
    preview = lines[1]
    print(f"Audit CSV export: PASS header='{header}' preview='{preview[:120]}'")

    # 4) Policy controls save
    status, sys_settings, _ = http_json("GET", "/api/settings/system", token=token)
    if status != 200:
        raise RuntimeError(f"get system settings failed status={status} data={sys_settings}")
    prev = int(sys_settings.get("password_min_length", 8))
    new_val = prev + 1

    status, data, _ = http_json(
        "PUT",
        "/api/settings/system",
        token=token,
        payload={"password_min_length": new_val},
    )
    if status != 200:
        raise RuntimeError(f"policy PUT failed status={status} data={data}")

    status, sys_settings_after, _ = http_json("GET", "/api/settings/system", token=token)
    if status != 200:
        raise RuntimeError(f"get system settings after failed status={status} data={sys_settings_after}")
    after = int(sys_settings_after.get("password_min_length", -1))
    if after != new_val:
        raise RuntimeError(f"policy did not persist: expected {new_val}, got {after}")
    print(f"Policy save: PASS password_min_length {prev} -> {after}")

    print("Admin Console end-to-end API validation: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Admin Console end-to-end API validation: FAIL: {e}", file=sys.stderr)
        sys.exit(1)

