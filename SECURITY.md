# Security & Governance

## RBAC (Role-Based Access Control)

OmniMine enforces a **role → permission** mapping in the backend.

Roles:
- `admin`
- `manager`
- `agent`
- `analyst`

Permissions are checked for sensitive actions (org switching, role changes, settings updates, HITL approvals, etc.).

## Audit logging (Compliance)

The backend writes **immutable audit events** to MongoDB (`audit_events`) including:
- actor (id/email/role)
- org_id
- action + resource type/id
- request metadata (request_id, IP, user-agent, method/path, status)
- optional `before` / `after` snapshots (with **PII/secret redaction**)

### Audit retention

Controlled by env var:
- `AUDIT_RETENTION_DAYS` (default: `90`)

Old audit events are cleaned up at startup (best effort).

## Health checks

- `GET /healthz` – process alive
- `GET /readyz` – Mongo connectivity check

