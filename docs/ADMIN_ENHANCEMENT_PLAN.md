# Admin Enhancement Plan — Beep.AI.Researcher
## Document Management · Quota Management · Email · Storage · Enterprise Services

**Created:** 2026-02-25
**Status:** DRAFT — awaiting implementation
**Target:** Enterprise on-premise + cloud hybrid deployments

---

## TL;DR

Five critical gaps exist in the current admin layer. This plan adds:

1. A **full quota system** (per-user, plan/tier-based, and per-tenant hierarchical) with real-time enforcement on every upload/delete operation.
2. A **Document Management admin panel** — global view of all documents, user/project filtering, bulk delete, quota reporting, and orphan cleanup.
3. A complete **Email Configuration fix** — persist the missing `smtp_host` key, add a test-send button, email template management, and OAuth2 mail support for Microsoft 365 and Google Workspace.
4. A **pluggable Storage Backend** system (local filesystem, SMB/NAS, S3-compatible/MinIO, Azure Blob) with an admin UI switch and per-backend credential management.
5. A unified **Application Settings Hub** covering all enterprise deployment settings: identity/SSO, external APIs, global integration credentials, legal/compliance, and instance branding.
6. A **complete User Registration & Management system** — configurable self-registration with invite-only and domain-allowlist modes, email verification, admin-driven user lifecycle (create/edit/suspend/delete/impersonate), and a full **Multi-Factor Authentication (MFA)** stack: TOTP authenticator apps, email OTP, SMS OTP, backup recovery codes, per-user MFA enforcement policy, and admin MFA override/reset.

All work follows existing conventions: Flask Blueprints, SQLAlchemy ORM, Jinja2 templates, `@admin_required` decorator, `config_manager` singleton, Alembic migrations, and `to_dict()` serialization.

---

## Current State — Gap Analysis

### Gap 1: No Quota System (Severity: CRITICAL)

| What is Missing | Impact |
|---|---|
| `storage_quota_bytes` / `document_quota` fields on `User` model | No per-user limits anywhere |
| Per-project quota fields on `ResearchProject` | No project-level limits |
| `UserStorageStats` live usage tracker | No usage reports for admin or user |
| Pre-upload quota check in `documents.py` `upload_document()` | Users can upload unlimited files |
| Admin UI to set/view/edit quotas per user or plan tier | Admin cannot manage quotas |
| `PlanTier` model for SaaS-style or enterprise tier configuration | No tier system |

### Gap 2: Email is Silently Disabled (Severity: HIGH)

| State | Detail |
|---|---|
| Keys defined | `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_use_tls`, `mail_from` all in `CONFIG_KEYS` |
| Config file | Only `smtp_port` and `smtp_use_tls` are written to `app_config.json`; `smtp_host` is absent → `email_service.is_configured()` returns `False` |
| Admin UI | `templates/admin/settings.html` renders all SMTP fields — form exists |
| Service | `email_service.py` is fully implemented; just needs config populated |
| **Gap** | Setup does not default-persist `smtp_host`; email is silently disabled on every fresh install |
| **Missing** | No test-send button, no OAuth2 mail (MS365/Google Workspace), no email template management |

### Gap 3: Storage is Local-Only with No Admin Control (Severity: HIGH)

| Current State | Gap |
|---|---|
| Files always go to `data/uploads/` | No alternative storage backend |
| Path computed by `config_manager.uploads_path` (hardcoded relative) | Admin cannot redirect to NAS, S3, or network share |
| No `storage_backend` config key | Cannot switch backends without code changes |
| No `max_upload_size_mb` enforced at route level | No admin-configurable upload limit |
| Deleted DB records leave files on disk | Orphan file leak since first commit |

### Gap 4: External Integrations Have Models but No Admin UI (Severity: MEDIUM)

The fundamental design gap is that integrations are not categorised by **who owns/manages the credential**. There are three distinct tiers that must be modelled separately:

| Tier | Who Manages | Examples | Current State |
|---|---|---|---|
| **Admin-Global** | Admin only; shared by all users | Beep.AI.Server, SMTP, institutional PubMed/arXiv key, LDAP/SSO | Partially exists but no unified UI |
| **User-Personal** | Each user manages their own; admin cannot see tokens | Personal Google Drive, personal Dropbox/OneDrive, personal Zotero library key, personal GitHub | `IntegrationCredential` model exists; zero UI or routes |
| **Dual-Mode** | Admin enables the service + sets an optional global fallback; users can also connect their own personal account | PubMed (institutional key as fallback, personal key as override), Zotero (org group library + personal library), Mendeley (institution OAuth app + personal account), OpenAI (admin key + user override) | Zero implementation |

**Current specific gaps:**

| Service | Tier | State |
|---|---|---|
| Beep.AI.Server (LLM/RAG) | Admin-Global | ✅ Config keys + admin UI + connection test exist |
| SMTP / OAuth2 email | Admin-Global | ⚠️ Schema + UI exist; config not persisted |
| SSO / LDAP / SAML / OIDC | Admin-Global | ❌ Identity key in schema; zero implementation |
| Institutional PubMed / arXiv / Crossref key | Admin-Global (fallback) | ⚠️ Config keys exist; no UI; no user-override logic |
| Google Drive / Dropbox / OneDrive | User-Personal | ❌ `IntegrationCredential` model exists; no OAuth2 flow, no UI |
| Personal Zotero library | User-Personal | ❌ Planned; zero implementation |
| Personal Mendeley account | User-Personal | ❌ Planned; zero implementation |
| Personal GitHub / GitLab | User-Personal | ❌ Not planned; no model |
| Zotero org group library | Dual-Mode | ❌ Admin can set global key; users should also connect personal |
| Mendeley institution OAuth app | Dual-Mode | ❌ Zero implementation |
| OpenAI / LLM API key | Dual-Mode | ❌ Only global; no per-user override |
| Admin can enable/disable which integrations users may connect | All tiers | ❌ No service registry; users cannot be restricted from connecting arbitrary services |

### Gap 5: Dual Config Manager Split (Severity: MEDIUM)

`app/config_manager.py` (JSON-persisted) and `app/config/manager.py` (in-memory) are two separate systems that can drift. Config must be extended for all new features, so merge them first before adding keys.

### Gap 6: User Registration & Management is Minimal (Severity: HIGH)

| What is Missing | Impact |
|---|---|
| Registration mode (open / invite-only / domain-allowlist / admin-only) | Any person on the network can create an account on open installs |
| Invite system with token-based sign-up links | No way to control who joins without disabling registration entirely |
| Domain allowlist for auto-approved corporate email domains | Cannot enforce `@company.com`-only sign-ups |
| Password policy enforcement (min length, complexity, expiry, history) | No controls; weak passwords allowed |
| Multi-Factor Authentication (MFA) — TOTP, Email OTP, SMS OTP | No second factor; single-factor only |
| Backup / recovery codes for MFA | Users locked out of account if TOTP device is lost |
| Per-user and global MFA enforcement policy | Cannot mandate MFA for all users or specific roles |
| Admin MFA reset / bypass for locked-out users | Users permanently locked out without DB intervention |
| Session management — active sessions list, remote logout | Users cannot see or revoke their own sessions; admin cannot force sign-out |
| User profile page — avatar, display name, contact info | Only username/email exist; no user-facing profile edit |
| Admin user detail page — full edit, role assignment, quota, audit trail | Admin users page only has activate/suspend/role-change |
| Bulk user operations (import CSV, bulk assign role/tier, bulk suspend) | No bulk operations; must do one at a time |
| User activity / audit log per-user view | Global audit log exists but no per-user filtered view |
| Account deletion with data cleanup or reassignment | No user delete flow; only suspend |

---

## Phase 1 — Data Model & Config Foundation (Prerequisites) ✅ PARTIAL

> **Status (2026-02-25):** Data model changes (Phase 1.2 + Phase 8.1 + Phase 9.2) are DONE.
> Config unification (Phase 1.1) and extended config keys (Phase 1.3) are still TODO.

### 1.2 Status — DONE ✅
- `app/models/researcher/storage_quota.py` — `PlanTier`, `TenantQuota`, `UserStorageStats` created.
- `app/models/user_management.py` — `UserInvite`, `PasswordHistory`, `UserSession` created.
- `app/models/integrations_registry.py` — `GlobalIntegrationService`, `UserIntegrationCredential` created.
- `app/models/core.py` → `User` — quota, plan_tier_id, invite_id, lockout, password policy, profile, MFA columns added.
- `app/models/tenant.py` → `Tenant` — `plan_tier_id` FK added.
- `app/models/__init__.py` — all new models exported.
- `migrations/add_quota_user_management_integrations.py` — Alembic migration with upgrade + downgrade.

---

### 1.1 Unify Config Managers

**Problem:** Two separate config systems exist. Both need new keys; merge before adding more.

**Steps:**
- Merge `app/config/manager.py` feature-flags, queue, and cache keys into `app/config_manager.py` `CONFIG_KEYS`.
- Replace all `get_config()` / `set_feature_enabled()` calls in `app/__init__.py` and routes with `config_manager.get()` / `config_manager.set()`.
- Keep backward-compatible property wrappers so existing callers are not broken.
- Deprecate `app/config/manager.py` — add a shim that re-exports from `config_manager` with a deprecation warning.

**Files to modify:**
- `app/config_manager.py` — add merged keys + 40+ new keys (see §1.3)
- `app/config/manager.py` — replace body with import shim
- `app/__init__.py` — update references

### 1.2 Quota Models

**New file:** `app/models/researcher/storage_quota.py`

```python
class PlanTier(db.Model):
    """Defines storage/document limits for a subscription tier or enterprise plan."""
    __tablename__ = 'plan_tiers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)       # "Free", "Standard", "Enterprise", "Custom"
    storage_quota_bytes = db.Column(db.BigInteger, default=1_073_741_824)   # default 1 GB
    document_quota = db.Column(db.Integer, default=500)
    project_quota = db.Column(db.Integer, default=10)
    api_calls_per_day = db.Column(db.Integer, default=1000)
    max_upload_size_bytes = db.Column(db.BigInteger, default=52_428_800)    # default 50 MB
    price_display = db.Column(db.String(40))                           # display only, e.g. "$0/mo"
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TenantQuota(db.Model):
    """Per-tenant pool quota. Members draw from this pool unless overridden at user level."""
    __tablename__ = 'tenant_quotas'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), unique=True)
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)
    storage_quota_bytes = db.Column(db.BigInteger, nullable=True)      # NULL = use plan tier value
    document_quota = db.Column(db.Integer, nullable=True)
    used_storage_bytes = db.Column(db.BigInteger, default=0)
    document_count = db.Column(db.Integer, default=0)
    last_recalculated_at = db.Column(db.DateTime)


class UserStorageStats(db.Model):
    """Live usage tracker per user. Updated atomically on every upload/delete."""
    __tablename__ = 'user_storage_stats'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    used_storage_bytes = db.Column(db.BigInteger, default=0)
    document_count = db.Column(db.Integer, default=0)
    last_upload_at = db.Column(db.DateTime)
    last_recalculated_at = db.Column(db.DateTime)
```

**Modify `app/models/core.py` → `User`** — add columns:
```python
storage_quota_bytes = db.Column(db.BigInteger, nullable=True)   # NULL = inherit from plan/tenant
document_quota = db.Column(db.Integer, nullable=True)
plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)
```

**Modify `app/models/tenant.py` → `Tenant`** — add:
```python
plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)
```

**New Alembic migration:** `migrations/xxxx_add_quota_system.py`

### 1.3 Extended Config Keys

Add the following sections to `CONFIG_KEYS` in `app/config_manager.py`:

**Storage section:**
```python
'storage_backend':           ('local', str),     # 'local' | 'smb' | 's3' | 'azure_blob'
'storage_local_path':        ('data/uploads', str),
'storage_smb_host':          ('', str),
'storage_smb_share':         ('', str),
'storage_smb_username':      ('', str),
'storage_smb_password':      ('', str),
'storage_smb_domain':        ('', str),
'storage_s3_endpoint_url':   ('', str),          # blank = AWS; set for MinIO on-prem
'storage_s3_access_key':     ('', str),
'storage_s3_secret_key':     ('', str),
'storage_s3_bucket_name':    ('', str),
'storage_s3_region':         ('us-east-1', str),
'storage_s3_prefix':         ('researcher/', str),
'storage_azure_connection_string': ('', str),
'storage_azure_container_name':    ('researcher', str),
'storage_azure_prefix':            ('uploads/', str),
```

**Email fix + OAuth2 section:**
```python
'smtp_host':                 ('', str),          # FIX: was missing from defaults
'smtp_port':                 (587, int),
'smtp_user':                 ('', str),
'smtp_password':             ('', str),
'smtp_use_tls':              (True, bool),
'mail_from':                 ('', str),
'mail_auth_method':          ('smtp', str),      # 'smtp' | 'oauth2_ms365' | 'oauth2_google'
'mail_oauth2_client_id':     ('', str),
'mail_oauth2_client_secret': ('', str),
'mail_oauth2_tenant_id':     ('', str),          # Microsoft 365 tenant GUID
'mail_oauth2_refresh_token': ('', str),
```

**Quota defaults section:**
```python
'default_storage_quota_bytes':  (1_073_741_824, int),   # 1 GB
'default_document_quota':       (500, int),
'default_max_upload_size_bytes':(52_428_800, int),       # 50 MB
'quota_enforcement_enabled':    (True, bool),
```

**Enterprise / Identity section:**
```python
'instance_name':             ('Beep.AI Researcher', str),
'instance_logo_url':         ('', str),
'instance_base_url':         ('http://localhost:5001', str),
'sso_enabled':               (False, bool),
'sso_provider':              ('none', str),     # 'none' | 'saml2' | 'oidc' | 'ldap'
'saml_idp_metadata_url':     ('', str),
'saml_sp_entity_id':         ('', str),
'saml_sp_acs_url':           ('', str),
'oidc_discovery_url':        ('', str),
'oidc_client_id':            ('', str),
'oidc_client_secret':        ('', str),
'ldap_server':               ('', str),
'ldap_port':                 (389, int),
'ldap_bind_dn':              ('', str),
'ldap_bind_password':        ('', str),
'ldap_user_search_base':     ('', str),
'ldap_user_search_filter':   ('(sAMAccountName={username})', str),
```

**External APIs — Admin-Global keys (go into `config_manager.py` / `app_config.json`):**

> Only services in the **Admin-Global** tier with a single shared key belong here. Per-user and dual-mode credentials are stored in the database via the new `GlobalIntegrationService` and `UserIntegrationCredential` models (see Phase 9).

```python
# Institutional / shared API keys (admin-global fallback)
'pubmed_api_key':                ('', str),    # institutional key; users may override with personal key
'arxiv_api_email':               ('', str),    # contact email for arXiv API rate limit tier
'crossref_mailto':               ('', str),    # Crossref Polite Pool email
'google_scholar_proxy_url':      ('', str),    # self-hosted proxy; admin-global only

# AI fallback (admin-global; dual-mode override handled per-user via UserIntegrationCredential)
'openai_api_key':                ('', str),    # fallback if Beep.AI.Server unreachable
'openai_model':                  ('gpt-4o-mini', str),
```


**User Registration & MFA section:**
```python
# Registration
'registration_mode':                    ('open', str),        # 'open' | 'invite_only' | 'domain_allowlist' | 'admin_only'
'registration_allowed_domains':         ('', str),            # comma-separated, e.g. 'company.com,partner.org'
'registration_require_email_verification': (True, bool),
'registration_auto_assign_tier':        ('', str),            # PlanTier.name to auto-assign on registration
'registration_auto_assign_role':        ('user', str),        # default role name
'registration_captcha_enabled':         (False, bool),

# Password policy
'password_min_length':                  (8, int),
'password_require_uppercase':           (True, bool),
'password_require_number':              (True, bool),
'password_require_special':             (False, bool),
'password_expiry_days':                 (0, int),             # 0 = never
'password_history_count':               (5, int),             # prevent reuse of last N passwords
'password_max_failed_attempts':         (5, int),
'password_lockout_minutes':             (15, int),

# MFA
'mfa_enabled':                          (False, bool),        # global feature flag
'mfa_enforcement':                      ('optional', str),    # 'optional' | 'required_all' | 'required_by_role'
'mfa_required_roles':                   ('admin', str),       # comma-separated role names for required_by_role mode
'mfa_totp_enabled':                     (True, bool),
'mfa_email_otp_enabled':                (True, bool),
'mfa_sms_otp_enabled':                  (False, bool),
'mfa_backup_codes_count':               (10, int),
'mfa_totp_issuer_name':                 ('Beep.AI Researcher', str),  # shown in authenticator apps
'mfa_otp_expiry_seconds':               (300, int),           # email/SMS OTP validity window

# SMS (required for SMS OTP)
'sms_provider':                         ('', str),            # 'twilio' | 'vonage' | 'aws_sns'
'sms_account_sid':                      ('', str),
'sms_auth_token':                       ('', str),
'sms_from_number':                      ('', str),

# Session management
'session_lifetime_minutes':             (480, int),           # 8 hours default
'session_max_concurrent':               (0, int),             # 0 = unlimited
'session_idle_timeout_minutes':         (60, int),
```

---

## Phase 2 — Storage Service Abstraction

### 2.1 `app/services/storage_service.py` — Factory + Interface

```
app/services/
└── storage/
    ├── __init__.py            ← re-exports get_storage_backend()
    ├── base.py                ← BaseStorageBackend ABC + StorageResult dataclass
    ├── local_backend.py       ← LocalStorageBackend (current behavior)
    ├── smb_backend.py         ← SMBStorageBackend (smbprotocol library)
    ├── s3_backend.py          ← S3StorageBackend (boto3; MinIO-compatible via endpoint_url)
    └── azure_blob_backend.py  ← AzureBlobStorageBackend (azure-storage-blob)
```

**`base.py` interface (abstract methods):**

| Method | Signature | Description |
|---|---|---|
| `save_file` | `(user_id, project_id, filename, file_stream) → StorageResult` | Save uploaded file; returns path + size_bytes |
| `get_file` | `(path) → BinaryIO` | Retrieve file for download |
| `delete_file` | `(path) → bool` | Delete file; returns success |
| `list_files` | `(prefix) → list[StorageEntry]` | List files under a path prefix |
| `get_backend_name` | `() → str` | Human-readable name ("Local Filesystem", "Amazon S3", etc.) |
| `test_connection` | `() → ConnectionTestResult(ok, message, latency_ms)` | Verify backend is reachable and writable |

**Storage path format** — always store a routing key, never a bare relative path:
- Local: `/abs/path/to/file.pdf`
- S3/MinIO: `s3://bucket-name/prefix/uuid-filename.pdf`
- Azure Blob: `azure://container-name/prefix/uuid-filename.pdf`
- SMB: `smb://host/share/prefix/uuid-filename.pdf`

`get_storage_backend()` factory parses the scheme to route retrieval to the correct backend — this enables mixed backends during backend migration.

### 2.2 Integrate Storage Service with Upload Route

**Modify `app/routes/documents.py` `upload_document()`:**

Replace:
```python
upload_path = os.path.join(uploads_dir, safe_filename)
file.save(upload_path)
document.file_path = upload_path
```

With:
```python
from app.services.storage import get_storage_backend
result = get_storage_backend().save_file(current_user.id, project_id, safe_filename, file.stream)
document.file_path = result.path
document.file_size = result.size_bytes
```

**Fix orphan-file leak on delete** — modify document delete route:
```python
get_storage_backend().delete_file(document.file_path)
db.session.delete(document)
```

**Update download/serve route** — replace `send_from_directory` with:
```python
file_stream = get_storage_backend().get_file(document.file_path)
return send_file(file_stream, download_name=document.filename, as_attachment=True)
```

**New dependencies in `requirements.txt`:**
```
boto3>=1.34.0
azure-storage-blob>=12.19.0
smbprotocol>=1.13.0
```

---

## Phase 3 — Quota System

### 3.1 `app/services/quota_service.py`

**Quota resolution order (for `get_effective_quota`):**
```
User.storage_quota_bytes (if not NULL)
  → TenantQuota.storage_quota_bytes (if user has tenant and TenantQuota not NULL)
    → PlanTier.storage_quota_bytes (from User.plan_tier_id OR TenantQuota.plan_tier_id)
      → config_manager.get('default_storage_quota_bytes')
```
Same hierarchy applies for `document_quota` and `max_upload_size_bytes`.

**Public API:**

| Function | Returns | Description |
|---|---|---|
| `get_effective_quota(user_id)` | `QuotaSpec` | Resolved quota limits for a user |
| `get_user_usage(user_id)` | `UsageStats` | Current used bytes + doc count from `UserStorageStats` |
| `check_can_upload(user_id, file_size_bytes)` | `QuotaCheckResult` | Returns allowed/blocked + remaining + reason |
| `record_upload(user_id, size_bytes)` | `None` | Atomically increments `UserStorageStats` |
| `record_delete(user_id, size_bytes)` | `None` | Atomically decrements `UserStorageStats` |
| `recalculate_user_usage(user_id)` | `UsageStats` | Full DB aggregate recalculation for one user |
| `recalculate_all_usage()` | `dict` | Bulk recalculation; returns summary stats |
| `get_quota_summary()` | `QuotaSummary` | Admin overview: total used, top 10 users, over-quota count |

### 3.2 Enforce Quota in Upload Route

**Modify `app/routes/documents.py` — before `storage_service.save_file()`:**

```python
if config_manager.get('quota_enforcement_enabled'):
    check = quota_service.check_can_upload(current_user.id, request.content_length or 0)
    if not check.allowed:
        return jsonify({
            'error': 'quota_exceeded',
            'message': check.reason,
            'quota': check.to_dict()
        }), 413
```

After successful save:
```python
quota_service.record_upload(current_user.id, result.size_bytes)
```

After document delete:
```python
quota_service.record_delete(document.user_id, document.file_size or 0)
```

### 3.3 Admin REST API for Quota

**New file:** `app/routes/admin/quota.py`
**Blueprint:** `quota_admin_bp`
**URL prefix:** `/api/admin/quota`
**Auth:** `@admin_required` on all routes

| Endpoint | Method | Description |
|---|---|---|
| `/users` | GET | All users with used/limit/percent; supports `?page=`, `?search=`, `?overquota=true` |
| `/users/<id>` | GET | Single user quota detail with usage history |
| `/users/<id>` | PUT | Override `storage_quota_bytes` / `document_quota` for a user |
| `/users/<id>/reset` | DELETE | Clear per-user overrides (revert to plan/tenant inheritance) |
| `/users/<id>/recalculate` | POST | Trigger `recalculate_user_usage(id)` |
| `/recalculate-all` | POST | Enqueue `recalculate_all_usage()` via `JobQueue` |
| `/plan-tiers` | GET | List all plan tiers |
| `/plan-tiers` | POST | Create a new plan tier |
| `/plan-tiers/<id>` | PUT | Update a plan tier |
| `/plan-tiers/<id>` | DELETE | Deactivate a plan tier (soft delete) |
| `/tenants` | GET | All tenants with pool usage + limit |
| `/tenants/<id>` | PUT | Override tenant quota pool limits |
| `/summary` | GET | Total storage used, top 10 users by usage, over-quota count, document count distribution |

---

## Phase 4 — Email Configuration & Service

### 4.1 Fix SMTP Persistence Bug

**Root cause:** `app/config_manager.py` `_initialize_defaults()` does not include `smtp_host` — only `smtp_port` and `smtp_use_tls` are seeded. On every fresh install, `smtp_host` is absent from `app_config.json` and `email_service.is_configured()` returns `False`.

**Fix (minimal — 1 line):** Add `smtp_host: ('', str)` to `CONFIG_KEYS`. The `_initialize_defaults()` loop will then write it on first startup.

**Also fix:** `smtp_user`, `smtp_password`, `mail_from` — ensure all 6 SMTP keys are seeded with empty defaults.

### 4.2 `app/services/email/oauth2_mail.py`

New module for OAuth2-authenticated mail:

**Microsoft 365 (Graph API):**
- Uses `msal` library (`pip install msal`).
- Reads `mail_oauth2_client_id`, `mail_oauth2_client_secret`, `mail_oauth2_tenant_id`, `mail_oauth2_refresh_token` from `config_manager`.
- Acquires access token via `ConfidentialClientApplication.acquire_token_by_refresh_token()`.
- Sends via `POST https://graph.microsoft.com/v1.0/me/sendMail`.

**Google Workspace (Gmail API):**
- Uses `google-auth` + `google-api-python-client` libraries.
- Credentials from `mail_oauth2_client_id`, `mail_oauth2_client_secret`, `mail_oauth2_refresh_token`.
- Sends via `gmail.users().messages().send()`.

**Unified interface:**
```python
def send_message(to: str, subject: str, html_body: str,
                 attachments: list = None) -> bool:
    ...
```
Signature matches `email_service.send_email()` for transparent dispatch.

**New dependencies in `requirements.txt`:**
```
msal>=1.26.0
google-auth>=2.28.0
google-api-python-client>=2.116.0
```

### 4.3 Unify Email Dispatch in `email_service.py`

**Modify `app/services/email_service.py`:**
- Add `_get_mail_sender()` that reads `mail_auth_method` config key.
- Dispatch to existing `SMTPMailSender` (`smtp`) or new `OAuth2MailSender` (`oauth2_ms365`, `oauth2_google`).
- Add `test_send(to_address: str) → TestResult(ok: bool, error: str)` public method for admin test button.

All existing callers (`auth_routes.py`, `task_notifications.py`, etc.) need zero changes.

### 4.4 Admin Routes for Email

**Modify `app/routes/admin_routes.py` — add three new endpoints:**

| Route | Method | Description |
|---|---|---|
| `/admin/settings/email/test` | GET | Call `email_service.test_send(mail_from)` → JSON `{ok, error, latency_ms}` |
| `/admin/settings/email/oauth2/authorize` | GET | Redirect to MS365/Google OAuth2 consent screen |
| `/admin/settings/email/oauth2/callback` | GET | Receive auth code, exchange for refresh token, persist to config |

---

## Phase 5 — Admin UI Pages ✅ DONE 2026-02-25

All templates extend `templates/base.html`, use CSS variables from `static/css/design-system.css` and `jenni-theme.css`. All forms use `@admin_required`.

### 5.1 `templates/admin/document_management.html`

**New page** at route `GET /admin/documents`.

**Layout:**
- Header: "Document Management" + stats bar (total files, total size, pending count, error count).
- **Filter bar:** user (autocomplete), project (select), date range, file type (checkbox group), status (All/Pending/Ready/Error), "Over quota only" toggle.
- **Document table:** filename, user, project, size (human-readable), upload date, backend indicator (icon: local/S3/Azure/SMB), status badge.
- **Row actions:** View metadata (modal), Download (via storage backend), Delete (confirm dialog with quota decrement note).
- **Bulk action bar** (shown when rows selected): Bulk Delete, Bulk Reprocess (re-trigger text extraction).
- **Quota column** in user-grouped view: progress bar showing used/limit per user.
- **Orphan Cleanup section** (collapsible): "Scan for orphans" button → lists files on storage backend with no DB record → "Delete selected orphans" button.
- **Export button:** CSV download of filtered document list.

### 5.2 `templates/admin/quota_management.html`

**New page** at route `GET /admin/quota`.

**Layout:**
- **Summary cards row:** Total storage used (all users), Total documents, Active users, Over-quota users (red card if > 0).
- **Plan Tiers section:**
  - Table: tier name, storage limit, doc limit, project limit, max upload, active users count, price display, status.
  - Inline "Edit" button per row → modal with all fields.
  - "Add Plan Tier" button → modal form.
  - "Set as Default" action (updates `default_storage_quota_bytes` config key).
- **User Quota table:**
  - Paginated, 20/page; search by username or email.
  - Columns: User, Plan Tier (dropdown edit-in-place), Storage Used/Limit (progress bar + bytes), Docs Used/Limit (progress bar + count), Last Upload, Override indicator (badge if user has a manual override).
  - Per-row: "Edit Override" button (modal), "Reset Override" (revert to plan), "Recalculate" (force stats refresh).
  - Bulk: "Assign Plan Tier" to selected users.
- **Tenant Quota section:**
  - Per-tenant table: tenant name, plan tier, pool used/limit, member count.
  - "Edit" button → modal for quota pool overrides.
- **Recalculate All button** → POST `/api/admin/quota/recalculate-all` → shows live job status via existing monitoring WebSocket channel.

### 5.3 `templates/admin/settings.html` — Extended Tabs

Add the following accordion/tab sections to the existing settings page (currently has: General, Connection, Features, Queue, Cache):

**Tab: Storage Backend (new)**
- Backend selector: Local Filesystem / SMB / NAS / S3-Compatible / Azure Blob (radio buttons).
- Each backend shows/hides its own config form group (JS toggle on radio change).
  - **Local:** Path input, "Browse" hint.
  - **SMB/NAS:** Host, Share, Username, Password, Domain.
  - **S3-Compatible:** Endpoint URL (blank = AWS; set for MinIO), Access Key, Secret Key, Bucket Name, Region, Key Prefix. Note: "Leave Endpoint URL blank for AWS S3; set to your MinIO address for on-premises deployments."
  - **Azure Blob:** Connection String, Container Name, Path Prefix.
- Max Upload Size (MB) input — applies to all backends.
- "Test Connection" button (per backend) → `POST /api/admin/storage/test` → inline latency + success/error toast.
- "Migrate Files" button (shown when backend is changed and existing files exist) → opens migration modal.

**Tab: Email (extend existing SMTP section)**
- Auth method selector: SMTP / Microsoft 365 (OAuth2) / Google Workspace (OAuth2).
- **SMTP fields** (shown for SMTP auth method): Host, Port, Username, Password, TLS toggle, From Address.
- **OAuth2 fields** (shown for OAuth2 auth method): Client ID, Client Secret, Tenant ID (MS365 only), current token status badge.
- "Authorize" button → opens OAuth2 consent flow in new tab.
- "Send Test Email" button → `GET /admin/settings/email/test` → inline success/error toast with latency.
- Email template preview section (future phase placeholder).

**Tab: Enterprise Identity (new)**
- Instance Name, Logo URL, Base URL (used in email links).
- SSO provider selector: None / SAML 2.0 / OpenID Connect (OIDC) / LDAP / Active Directory.
- Show/hide appropriate fields per selector:
  - **SAML2:** IdP Metadata URL, SP Entity ID, ACS URL, "Download SP Metadata" button.
  - **OIDC:** Discovery URL, Client ID, Client Secret, "Test Discovery" button.
  - **LDAP/AD:** Server, Port, Bind DN, Bind Password, User Search Base, User Search Filter, "Test Bind" button.
- "Test SSO Configuration" button → inline result.

**Tab: External Services & APIs (new)**

Divided into two sub-sections:

**Admin-Global Services** (only admin can configure; credentials shared by all users):
- Beep.AI.Server connection (moved here from General tab).
- Institutional / shared API keys: PubMed API Key, arXiv contact email, Crossref Mailto, Google Scholar Proxy URL.
- OpenAI fallback key (note: "Used as system fallback; users may also add a personal key via their profile").
- Per-service "Test" button.
- Toggle: **"Allow users to add personal credentials"** per service — controls whether dual-mode override is permitted.

**User-Connectable Services** (admin enables the service and registers the OAuth2 app; users connect their own accounts):
- Table of registered services (from `GlobalIntegrationService` model): Name, Type, Scope, Status (Active/Disabled), Connected Users count, Allow Personal Override toggle.
- **"Register New Service"** button → modal to add a service entry: service type selector (Google Drive / Dropbox / OneDrive / Zotero / Mendeley / GitHub / GitLab / Custom), OAuth2 client ID + secret (for OAuth2 services), API key (for key-based services), scope (User-Personal / Dual-Mode), enable/disable toggle.
- **Per service row actions:** Edit credentials, Enable/Disable, View connected users, Disconnect all users.
- Note: Per-user personal credentials (OAuth2 tokens) are never visible to admin — only the connected-or-not status is shown.

**Tab: Quota Defaults (new)**
- Default Storage Quota: GB slider (1–500 GB range) + manual input.
- Default Document Quota: integer input.
- Default Max Upload Size: MB input.
- Quota Enforcement toggle: when off, quota checks are skipped (useful for admin migration).
- Link to "/admin/quota" for per-user/plan management.

### 5.4 `templates/admin/index.html` — Enhanced Dashboard

Extend the sparse existing dashboard (currently shows only user_count, role_count) with:

**New summary card row:**
- Storage Used / Total (with progress bar — warn if > 80%).
- Over-quota Users count (red badge if > 0).
- Pending Documents count.
- Email Service status: "Configured ✓" / "Not Configured ⚠" / "Test Failed ✗".

**New quick-links section:**
- Document Management → `/admin/documents`
- Quota Management → `/admin/quota`
- Storage Settings → `/admin/settings#storage`
- Email Settings → `/admin/settings#email`

**Storage backend status indicator:**
- Backend name + last test status.
- "Run test" inline button → `POST /api/admin/storage/test`.

---

## Phase 6 — Storage Admin REST API

**New file:** `app/routes/admin/storage.py`
**Blueprint:** `storage_admin_bp`
**URL prefix:** `/api/admin/storage`

| Endpoint | Method | Description |
|---|---|---|
| `/stats` | GET | Total used bytes (all backends), file count, per-backend breakdown |
| `/test` | POST | Test connection to current backend; accepts optional config override in body |
| `/backends` | GET | List available backends with config status (configured / unconfigured / untested) |
| `/switch` | POST | Switch `storage_backend` config key; optionally trigger background file migration |
| `/migrate` | POST | Enqueue background job: copy all files from source backend to target backend |
| `/migrate/status` | GET | Poll migration job status via `JobQueue` |
| `/orphans` | GET | Scan storage backend for files with no matching `ResearcherDocument` DB record |
| `/orphans/delete` | DELETE | Delete a list of orphan file paths from storage |
| `/settings/test` | POST | HTML-facing test endpoint used by settings page "Test Connection" button |

---

## Phase 7 — Admin Documents REST API

**New file:** `app/routes/admin/documents.py`
**Blueprint:** `admin_documents_bp`
**URL prefix:** `/api/admin/documents`

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Paginated list; filters: `user_id`, `project_id`, `status`, `date_from`, `date_to`, `overquota`, `file_type` |
| `/<id>` | GET | Full metadata for a single document including extraction status + storage path |
| `/<id>` | DELETE | Delete document + call `storage_service.delete_file()` + call `quota_service.record_delete()` |
| `/bulk-delete` | POST | Delete list of IDs; body: `{"ids": [...]}` |
| `/bulk-reprocess` | POST | Re-enqueue text extraction for list of IDs |
| `/export` | GET | CSV download of filtered document list |
| `/stats` | GET | Counts by status, by user (top 20), by file type, by project; total bytes by user |

---

## Phase 8 — User Registration & Management System

### 8.1 Registration Modes & Invite System

**Modify `app/routes/auth_routes.py` — `register()` endpoint:**

Add a registration gate at the top of the register route that reads `registration_mode`:

| Mode | Behaviour |
|---|---|
| `open` | Anyone can register (current behaviour) |
| `invite_only` | Registration requires a valid invite token in the URL (`/register?invite=<token>`); all other POSTs return 403 |
| `domain_allowlist` | Email domain must be in `registration_allowed_domains`; invalid domains rejected with a friendly error |
| `admin_only` | Self-registration is completely disabled; only admin can create accounts via the admin UI |

**New file:** `app/models/user_management.py`

```python
class UserInvite(db.Model):
    """Invite token for invite_only registration mode."""
    __tablename__ = 'user_invites'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)  # secrets.token_urlsafe(32)
    email = db.Column(db.String(120), nullable=True)               # pre-fill if specified
    role_name = db.Column(db.String(80), nullable=True)
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)                            # NULL = never
    used_at = db.Column(db.DateTime, nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    max_uses = db.Column(db.Integer, default=1)
    use_count = db.Column(db.Integer, default=0)


class PasswordHistory(db.Model):
    """Stores hashed previous passwords to enforce password_history_count policy."""
    __tablename__ = 'password_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserSession(db.Model):
    """Tracks active sessions for session management and remote logout."""
    __tablename__ = 'user_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    session_token_hash = db.Column(db.String(255), unique=True)    # SHA-256 of Flask session ID
    ip_address = db.Column(db.String(45))                          # supports IPv6
    user_agent = db.Column(db.String(255))
    device_label = db.Column(db.String(100))                       # e.g. "Chrome on Windows"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # NULL = self-revoke
```

**Modify `app/models/core.py` → `User`** — add columns:

```python
# Account lockout
failed_login_attempts = db.Column(db.Integer, default=0)
locked_until = db.Column(db.DateTime, nullable=True)

# Password policy
password_changed_at = db.Column(db.DateTime)
must_change_password = db.Column(db.Boolean, default=False)

# Profile
avatar_url = db.Column(db.String(255))
bio = db.Column(db.Text)
phone_number = db.Column(db.String(30))
locale = db.Column(db.String(10), default='en')
timezone = db.Column(db.String(50), default='UTC')

# MFA
mfa_enabled = db.Column(db.Boolean, default=False)
mfa_methods = db.Column(db.String(100), default='')  # comma-sep: 'totp,email,sms'
mfa_totp_secret = db.Column(db.String(64))           # AES-encrypted at rest
mfa_backup_codes_hash = db.Column(db.Text)           # JSON list of bcrypt hashes
mfa_backup_codes_remaining = db.Column(db.Integer, default=0)
mfa_last_used_at = db.Column(db.DateTime)

# Invite tracking
invite_id = db.Column(db.Integer, db.ForeignKey('user_invites.id'), nullable=True)
```

### 8.2 Password Policy Service

**New file:** `app/services/password_policy.py`

| Function | Returns | Description |
|---|---|---|
| `validate_password(password, user_id=None)` | `PolicyResult(ok, errors[])` | Checks length, complexity, and history against config policy |
| `is_password_in_history(user_id, password)` | `bool` | Returns `True` if password matches any of the last N hashes |
| `record_password_change(user_id, new_hash)` | `None` | Appends to `PasswordHistory`; prunes oldest if > `password_history_count` |
| `is_account_locked(user)` | `bool` | Returns `True` if `locked_until > now` |
| `record_failed_login(user)` | `None` | Increments counter; locks account after `password_max_failed_attempts` for `password_lockout_minutes` |
| `record_successful_login(user)` | `None` | Resets `failed_login_attempts` to 0; clears `locked_until` |
| `is_password_expired(user)` | `bool` | Returns `True` if `password_expiry_days > 0` and `password_changed_at` is past expiry |
| `get_policy_summary()` | `dict` | Returns current policy config as JSON for client-side password strength meter |

**Integrate into `auth_routes.py`:**
- `login()` — call `is_account_locked()` before password check; call `record_failed_login()` on bad password; call `record_successful_login()` on success.
- `register()` — call `validate_password()` on submitted password.
- `reset_password()` — call `validate_password()` + `record_password_change()` on new password submission.
- Add `GET /auth/password-policy` → returns `get_policy_summary()` as JSON for client-side strength meters.

### 8.3 MFA Service

**New file:** `app/services/mfa_service.py`

**TOTP (Google Authenticator, Authy, Microsoft Authenticator):**

Uses `pyotp` library.

| Function | Returns | Description |
|---|---|---|
| `generate_totp_secret(user_id)` | `(secret, provisioning_uri, qr_png_b64)` | Generates new secret, returns `otpauth://` URI + base64 QR code PNG |
| `verify_totp(user_id, code)` | `bool` | Validates 6-digit code against stored secret with ±1 window |
| `enable_totp(user_id, code)` | `bool` | Confirms one code then persists secret; adds `totp` to `user.mfa_methods` |
| `disable_totp(user_id)` | `None` | Clears TOTP secret; removes from `mfa_methods` |

**Email OTP:**

| Function | Returns | Description |
|---|---|---|
| `send_email_otp(user_id)` | `bool` | Generates 6-digit code; stores as short-lived `VerificationToken`; sends via `email_service` |
| `verify_email_otp(user_id, code)` | `bool` | Validates and consumes the token |

**SMS OTP:**

| Function | Returns | Description |
|---|---|---|
| `send_sms_otp(user_id)` | `bool` | Generates 6-digit code; sends via configured `sms_provider` (Twilio / Vonage / AWS SNS) |
| `verify_sms_otp(user_id, code)` | `bool` | Validates and consumes the token |

**Backup Recovery Codes:**

| Function | Returns | Description |
|---|---|---|
| `generate_backup_codes(user_id)` | `list[str]` | Generates N plaintext codes; stores bcrypt hashes in `mfa_backup_codes_hash`; sets `mfa_backup_codes_remaining` |
| `verify_backup_code(user_id, code)` | `bool` | Checks against stored hashes; marks code used; decrements remaining count |
| `regenerate_backup_codes(user_id)` | `list[str]` | Invalidates all old codes; generates N fresh ones (requires MFA re-verification) |

**Enforcement helpers:**

| Function | Returns | Description |
|---|---|---|
| `is_mfa_required(user)` | `bool` | `required_all` → always True; `required_by_role` → checks role in `mfa_required_roles`; `optional` → False |
| `get_available_methods(user)` | `list[str]` | Returns `['totp','email','sms','backup']` filtered to configured + user-enrolled methods |
| `is_mfa_compliant(user)` | `bool` | True if `is_mfa_required(user)` is False OR `user.mfa_enabled` is True |

**Dependencies:**
```
pyotp>=2.9.0
qrcode[pil]>=7.4.2
twilio>=8.10.0          # optional; only needed when sms_provider = twilio
```

### 8.4 MFA Auth Flow Integration

**Modify `app/routes/auth_routes.py` — `login()` endpoint** — add two-step flow:

```
Step 1: POST /auth/login  →  verify username + password
  ├─ password_policy: check account locked → 403 if locked
  ├─ verify password hash
  ├─ password_policy: record successful/failed login
  ├─ If MFA not enabled AND not required → issue full session normally
  └─ If MFA enabled OR required:
       → set interim session flag: mfa_pending=True, mfa_user_id=<id>
       → return 200 {"mfa_required": true, "available_methods": [...]}

Step 2: POST /auth/mfa/verify  →  verify second factor
  ├─ Read mfa_pending + mfa_user_id from session; abort 401 if missing
  ├─ Dispatch to appropriate mfa_service.verify_*() function
  └─ On success: clear mfa_pending; create_session(); issue full session; redirect
```

**New routes in `app/routes/auth_routes.py` or new `app/routes/mfa_routes.py`:**

| Route | Method | Description |
|---|---|---|
| `GET /auth/mfa` | GET | MFA challenge page (shows available method tabs) |
| `POST /auth/mfa/verify` | POST | Verify submitted code; complete login on success |
| `POST /auth/mfa/send-otp` | POST | Trigger email or SMS OTP send during login challenge |
| `GET /auth/mfa/setup` | GET | MFA setup wizard (requires active full session) |
| `POST /auth/mfa/setup/totp/init` | POST | Generate TOTP secret + QR code; returns JSON |
| `POST /auth/mfa/setup/totp/confirm` | POST | Confirm TOTP with a code; enables TOTP; returns backup codes |
| `POST /auth/mfa/setup/email/enable` | POST | Enable email OTP method |
| `POST /auth/mfa/setup/sms/enable` | POST | Enable SMS OTP (requires phone number on profile) |
| `POST /auth/mfa/setup/disable` | POST | Disable a method (requires re-authentication) |
| `POST /auth/mfa/setup/backup-codes/regenerate` | POST | Regenerate backup codes (requires full MFA re-auth) |

**Enforce MFA compliance on every authenticated request** — modify `@login_required` / `before_request` in `app/__init__.py`:

```python
# After login_required passes, check MFA compliance:
if not mfa_service.is_mfa_compliant(current_user):
    return redirect(url_for('mfa.setup'))
```

### 8.5 Session Management Service

**New file:** `app/services/session_service.py`

| Function | Returns | Description |
|---|---|---|
| `create_session(user, request)` | `UserSession` | Creates `UserSession` record; hashes Flask session ID; records IP + User-Agent; enforces `session_max_concurrent` |
| `touch_session(session_token_hash)` | `bool` | Updates `last_seen_at`; returns False (→ force logout) if idle timeout exceeded |
| `get_active_sessions(user_id)` | `list[UserSession]` | Returns non-expired, non-revoked sessions |
| `revoke_session(session_id, revoked_by_id)` | `bool` | Sets `is_active=False`, `revoked_at=now` |
| `revoke_all_sessions(user_id, except_current=None)` | `int` | Revokes all sessions; optionally preserves current; returns count revoked |
| `cleanup_expired_sessions()` | `int` | Background job: sets expired sessions inactive; returns count cleaned |

Integrate `create_session()` after MFA verification (or direct login). Integrate `revoke_session()` on logout. Call `touch_session()` inside `@login_required` decorator wrapper so idle timeout is enforced on every request.

### 8.6 Admin User Management REST API

**New file:** `app/routes/admin/users.py`
**Blueprint:** `admin_users_bp`
**URL prefix:** `/api/admin/users`

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Paginated user list; filters: role, status, plan_tier, mfa_status, date_joined, search |
| `/` | POST | Admin-create user (bypasses registration mode; skip email verify if `send_invite=false`) |
| `/<id>` | GET | Full user detail: profile, roles, quota, MFA status, sessions, recent audit events |
| `/<id>` | PUT | Edit profile, role, plan tier, quota override, `must_change_password`, `is_active` |
| `/<id>` | DELETE | Delete user; body: `{"action": "delete" or "anonymize", "reassign_projects_to": uid}` |
| `/<id>/suspend` | POST | Suspend user + revoke all sessions |
| `/<id>/activate` | POST | Re-activate a suspended user |
| `/<id>/reset-password` | POST | Admin-set new password or send password-reset email |
| `/<id>/unlock` | POST | Clear `failed_login_attempts` and `locked_until` |
| `/<id>/force-password-change` | POST | Set `must_change_password=True` |
| `/<id>/mfa/reset` | POST | Admin MFA reset: clears all secrets + backup codes; disables MFA; sends notification email |
| `/<id>/mfa/status` | GET | Returns enrolled methods, backup codes remaining, last MFA use |
| `/<id>/sessions` | GET | List all sessions (active and revoked) for user |
| `/<id>/sessions/<sid>/revoke` | DELETE | Revoke a specific session |
| `/<id>/sessions/revoke-all` | DELETE | Revoke all sessions (force sign-out everywhere) |
| `/<id>/audit` | GET | Per-user filtered view of `AuditLog` with pagination |
| `/<id>/impersonate` | POST | Create a time-limited impersonation session; action logged to audit |
| `/bulk` | POST | Bulk: `{"action": "suspend/activate/assign_role/assign_tier/delete", "ids": [...]}` |
| `/import` | POST | CSV upload for bulk-create or update users |
| `/import/template` | GET | Download CSV template for user import |
| `/export` | GET | CSV export of filtered user list |
| `/invites` | GET | List all invites with status (pending / used / expired / revoked) |
| `/invites` | POST | Create invite token; body: `{"email": ..., "role": ..., "expires_hours": 48, "max_uses": 1}` |
| `/invites/<token>/revoke` | DELETE | Revoke an unused invite token |

### 8.7 Admin User Management UI

#### `templates/admin/users.html` — Enhanced Users Page

Extend the existing page with:

- **Filter bar:** name/email search, role filter, status (Active/Suspended/Locked/Unverified), plan tier, MFA status (Enabled/Disabled), date-joined range.
- **Enhanced table columns:** Avatar (initials fallback), Name + Email, Role badge, Plan Tier, MFA (shield icon: ✓ or ✗), Storage (mini bar), Last Login, Status badge.
- **Row actions dropdown:** View Detail, Edit, Reset Password, Unlock, Force Password Change, Reset MFA, Suspend/Activate, Impersonate, Delete.
- **Bulk action bar** (visible when rows selected): Assign Role, Assign Tier, Suspend, Activate, Delete, Export Selected.
- **"Add User" button** → modal with admin-create form.
- **"Import Users" button** → CSV upload modal with download template link.
- **"Export" button** → CSV download.
- **"Manage Invites" link** → `/admin/invites`.

#### `templates/admin/user_detail.html` — Full User Admin Detail

New page at `GET /admin/users/<id>` with six tabs:

**Profile tab:** all editable fields (display name, email, phone, bio, locale, timezone, avatar); role assignment; plan tier; quota overrides; account flags toggle.

**Security tab:** "Send Password Reset Email" button; "Admin Set Password" form; `must_change_password` toggle; account lock status with "Unlock" button and failed attempts counter.

**MFA tab:** current MFA status (Enabled/Disabled/Partial); enrolled methods list with enrollment dates; backup codes remaining; "Admin Reset MFA" button (red, confirm dialog); MFA compliance status vs. required by role.

**Sessions tab:** table of sessions (Device, IP, Last Seen, Created, Status); "Revoke" per row; "Revoke All Sessions" button.

**Activity tab:** paginated `AuditLog` filtered to this user; "Export Audit Log" CSV.

**Storage & Quota tab:** inline quota editor (storage used/limit bar; documents used/limit; plan tier override), "Recalculate Usage" button.

#### `templates/admin/invites.html` — Invite Management

New page at `GET /admin/invites`:

- Summary cards: pending, used, expired invite counts.
- Table: token (masked), email, role, tier, created by, expires, uses, status.
- "Create Invite" button → modal (optional email, role, tier, expiry hours, max uses) → displays generated link.
- "Bulk Create" button for team onboarding.
- Row actions: Copy Link, Revoke.

#### `templates/auth/mfa_challenge.html` — MFA Login Challenge

New page at `GET /auth/mfa`:

- Method tabs: Authenticator App / Email Code / SMS Code / Recovery Code.
- Per-tab: 6-digit (or 8-digit backup) code input + "Verify" button.
- "Send Code" button for Email and SMS tabs.
- Remaining backup codes warning shown if < 3.
- "I lost my device / need help" link.

#### `templates/auth/mfa_setup.html` — MFA Setup Wizard

Step-by-step page at `GET /auth/mfa/setup`:

- **Step 1:** Choose primary method.
- **Step 2 (TOTP):** Display QR code + manual entry key; confirm with a 6-digit code.
- **Step 2 (Email OTP):** Send test code; confirm.
- **Step 2 (SMS OTP):** Enter phone number; send test code; confirm.
- **Step 3:** Backup codes one-time reveal with download as `.txt`; force acknowledgement checkbox before continuing.
- **Step 4:** Done — MFA active confirmation.

#### `templates/account/profile.html` — User Self-Service Profile

New page at `GET /account/profile`:

- Edit display name, bio, avatar upload, locale, timezone.
- Change password form (client-side policy meter + server validation with history check).
- MFA section: enrolled methods list; "Manage MFA" link → setup wizard.
- Active Sessions section: own sessions table with per-row "Revoke" and "Sign Out Everywhere".
- Danger Zone: "Delete My Account" with GDPR data export offer before deletion.

### 8.8 Settings UI — Registration, MFA & Password Policy Tabs

Add three new accordion tabs to `templates/admin/settings.html`:

**Tab: User Registration (new)**
- Registration mode selector: Open / Invite Only / Domain Allowlist / Admin Only.
- Allowed domains input (shown for Domain Allowlist mode): comma-separated, e.g. `company.com, partner.org`.
- Email verification toggle.
- Default role selector.
- Default plan tier selector.
- CAPTCHA toggle.

**Tab: Password Policy (new)**
- Minimum length slider (4–32).
- Complexity checkboxes: require uppercase, require number, require special character.
- Password expiry days (0 = never).
- Password history count (0 = disabled).
- Failed attempts before lockout.
- Lockout duration (minutes).
- "Preview Policy" display — shows example valid/invalid passwords based on current settings.

**Tab: MFA (new)**
- Enable MFA feature toggle (master switch).
- Enforcement selector: Optional / Required for All / Required for Specific Roles.
- Roles selector (shown for Required for Specific Roles): multi-select from existing roles.
- Enable/disable individual methods: TOTP, Email OTP, SMS OTP.
- Backup codes count.
- Authenticator app issuer name.
- OTP expiry window (seconds).
- SMS Provider subsection (shown when SMS enabled): provider selector + credentials.

---

## Phase 9 — External Integrations: Three-Tier Management

### 9.1 Integration Tier Model

All external integrations are classified into three tiers. This classification determines where credentials are stored and who manages them.

| Tier | Credential Storage | Admin Can See Tokens | User Can See Tokens | Examples |
|---|---|---|---|---|
| **Admin-Global** | `config_manager` / `app_config.json` | ✅ | ❌ | Beep.AI.Server, SMTP, institutional PubMed key, Google Scholar Proxy |
| **User-Personal** | `UserIntegrationCredential` (DB, encrypted) | ❌ (only connected status) | ✅ | Personal Google Drive, personal Dropbox/OneDrive, personal Zotero library, personal GitHub |
| **Dual-Mode** | Admin-Global key in `GlobalIntegrationService` + optional `UserIntegrationCredential` | Admin sees global key; not user's token | User sees own token | PubMed (institutional fallback + personal override), Zotero (org group + personal library), Mendeley, OpenAI |

**Resolution order for Dual-Mode** (same pattern as quota hierarchy):
```
User's personal UserIntegrationCredential (if present and active)
  → GlobalIntegrationService.global_credential (admin's shared config)
    → config_manager admin-global key (for services that have one)
```

### 9.2 New Models

**New file:** `app/models/integrations_registry.py`

```python
class GlobalIntegrationService(db.Model):
    """
    Admin-registered integration service. Acts as the registry of which external
    services are available in this deployment. Each entry represents one service
    that users may or may not be able to connect their personal accounts to.
    """
    __tablename__ = 'global_integration_services'
    id = db.Column(db.Integer, primary_key=True)
    service_type = db.Column(db.String(50), nullable=False)
    # 'google_drive' | 'dropbox' | 'onedrive' | 'zotero' | 'mendeley'
    # 'pubmed' | 'arxiv' | 'crossref' | 'github' | 'gitlab'
    # 'openai' | 'custom'
    name = db.Column(db.String(100), nullable=False)          # Display name, e.g. "Google Drive"
    description = db.Column(db.Text)
    scope = db.Column(db.String(20), default='user_personal')
    # 'admin_only'    — only admin uses; not user-visible
    # 'user_personal' — only users connect personal accounts; no shared key
    # 'dual'          — admin sets global fallback; users may also connect personal account
    is_enabled = db.Column(db.Boolean, default=True)
    allow_user_override = db.Column(db.Boolean, default=True) # Dual-mode: can users add personal?

    # OAuth2 app registration (for services using OAuth2)
    oauth2_client_id = db.Column(db.String(255))
    oauth2_client_secret_encrypted = db.Column(db.Text)       # AES-encrypted
    oauth2_scopes = db.Column(db.String(500))                 # space/comma separated
    oauth2_auth_url = db.Column(db.String(500))
    oauth2_token_url = db.Column(db.String(500))
    oauth2_redirect_uri = db.Column(db.String(500))

    # Global / shared credential (for admin-global or dual-mode fallback)
    global_api_key_encrypted = db.Column(db.Text)            # AES-encrypted
    global_extra_config = db.Column(db.Text)                 # JSON for service-specific extras

    # Metadata
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    last_tested_at = db.Column(db.DateTime)
    last_test_ok = db.Column(db.Boolean)
    connected_user_count = db.Column(db.Integer, default=0)  # cached count; updated on connect/disconnect


class UserIntegrationCredential(db.Model):
    """
    Per-user credential for a GlobalIntegrationService. Stores the user's personal
    OAuth2 tokens or API keys. Admin can see connected/not status but never the tokens.
    Replaces/supersedes the existing IntegrationCredential model.
    """
    __tablename__ = 'user_integration_credentials'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('global_integration_services.id'), nullable=False)

    # OAuth2 tokens (encrypted at rest)
    access_token_encrypted = db.Column(db.Text)
    refresh_token_encrypted = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    token_scopes = db.Column(db.String(500))

    # API key alternative (for key-based services like personal Zotero)
    api_key_encrypted = db.Column(db.Text)

    # Connection metadata (admin-visible)
    is_active = db.Column(db.Boolean, default=True)
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    last_sync_at = db.Column(db.DateTime)
    disconnected_at = db.Column(db.DateTime, nullable=True)
    display_name = db.Column(db.String(200))                  # e.g. "john@gmail.com (Google Drive)"
    extra_data = db.Column(db.Text)                           # JSON for service-specific extras

    __table_args__ = (db.UniqueConstraint('user_id', 'service_id', name='uq_user_service'),)
```

**Migrate existing `IntegrationCredential`** — create a migration that moves data from the old table into `UserIntegrationCredential` and links to auto-created `GlobalIntegrationService` entries. Retain the old table temporarily as a backup; drop after verification.

### 9.3 Integration Service

**New file:** `app/services/integration_service.py`

| Function | Description |
|---|---|
| `get_credential(user_id, service_type)` | Returns the best available credential using tier resolution order; returns `None` if none available |
| `get_global_service(service_type)` | Returns the `GlobalIntegrationService` for a given type, or `None` if not registered / disabled |
| `connect_user_oauth2(user_id, service_id, auth_code)` | Exchanges auth code for tokens; creates/updates `UserIntegrationCredential`; increments connected count |
| `disconnect_user(user_id, service_id)` | Revokes tokens (calls OAuth2 revoke endpoint if available); marks credential inactive; decrements count |
| `refresh_user_token(user_id, service_id)` | Refreshes OAuth2 access token using stored refresh token; updates encrypted tokens |
| `test_global_service(service_id)` | Admin test: uses global credential to make a lightweight API call; returns `TestResult(ok, latency_ms, error)` |
| `test_user_credential(user_id, service_id)` | User test: uses personal credential to verify it is still valid |
| `get_user_connections(user_id)` | Returns all active `UserIntegrationCredential` records for a user with service metadata |
| `get_service_connected_users(service_id)` | Admin: returns list of users connected to a service (no tokens; display_name + connected_at only) |
| `admin_disconnect_user(service_id, user_id)` | Admin-initiated disconnect (e.g. when disabling a service) |
| `admin_disconnect_all(service_id)` | Disconnect all users from a service (called before disabling/deleting a service) |
| `seed_default_services()` | Called at startup: ensures well-known service entries (Google Drive, Dropbox, Zotero, Mendeley, GitHub) exist in DB with default config; skips if already present |

### 9.4 Admin REST API for Integrations

**New file:** `app/routes/admin/integrations.py`
**Blueprint:** `admin_integrations_bp`
**URL prefix:** `/api/admin/integrations`

| Endpoint | Method | Description |
|---|---|---|
| `/services` | GET | List all registered `GlobalIntegrationService` entries with connected user counts |
| `/services` | POST | Register a new integration service (admin creates entry) |
| `/services/<id>` | GET | Full detail including oauth2 config (secrets masked) |
| `/services/<id>` | PUT | Update service config (name, scopes, client credentials, enabled, allow_user_override) |
| `/services/<id>` | DELETE | Delete service + admin_disconnect_all() first |
| `/services/<id>/enable` | POST | Enable a disabled service |
| `/services/<id>/disable` | POST | Disable service + optionally disconnect all users |
| `/services/<id>/test` | POST | Test global credential; return `TestResult` |
| `/services/<id>/connected-users` | GET | List users connected to this service (no token data) |
| `/services/<id>/disconnect-all` | DELETE | Admin bulk-disconnect all users from a service |
| `/services/<id>/disconnect/<user_id>` | DELETE | Admin-disconnect a single user |
| `/services/oauth2/callback` | GET | Admin OAuth2 callback — stores tokens as the service's global credential |

### 9.5 User-Facing Integrations Routes

**New file:** `app/routes/integrations_routes.py`
**Blueprint:** `integrations_bp`
**URL prefix:** `/integrations`
**Auth:** `@login_required` on all routes

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | List all enabled services; for each: connected status + "Connect" or "Disconnect" button |
| `/<service_id>/connect` | GET | Redirect to OAuth2 auth URL (or show API key input for key-based services) |
| `/<service_id>/callback` | GET | OAuth2 callback — exchange code for tokens; create `UserIntegrationCredential` |
| `/<service_id>/connect-key` | POST | Connect using an API key (for key-based services like Zotero personal) |
| `/<service_id>/disconnect` | POST | Revoke and disconnect personal credential |
| `/<service_id>/test` | GET | Test own credential; return status |
| `/<service_id>/status` | GET | JSON: connected, last_used_at, display_name, token_expires_at |

### 9.6 User Integrations UI

#### `templates/account/integrations.html` — User Connected Services

New tab/page accessible from user profile or sidebar:

- **Grid of integration cards**, one per enabled `GlobalIntegrationService`:
  - Service icon + name.
  - Status badge: Connected (green, shows `display_name` + last used date) / Not Connected (grey) / Token Expired (orange).
  - **Connected state:** "Test Connection" button + "Disconnect" button.
  - **Not Connected state:** "Connect" button → launches OAuth2 flow or API key input modal depending on `service_type`.
  - **Admin key available** (dual-mode with global fallback): note "Using institutional key — connect your personal account for personal library access".
  - Cards for services where `allow_user_override = False` are shown as read-only "Available via institution" with no connect option.

#### `templates/account/profile.html` — Add Integrations Link

Add an "Integrations" section or tab to the existing profile page with a summary of connected services count and a link to the full integrations page.

### 9.7 Admin Integrations UI

#### `templates/admin/integrations.html` — Integration Services Registry

New page at `GET /admin/integrations`:

- **Summary cards:** total registered services, enabled services, total user-service connections.
- **Services table:** icon, name, type, scope (Admin-Global / User-Personal / Dual-Mode), enabled toggle, OAuth2 configured indicator, global key indicator, connected users count, last tested, actions.
- **"Register Service" button** → modal with:
  - Service type selector (pre-populates default OAuth2 URLs for known types).
  - Name, description.
  - Scope selector (Admin-Global / User-Personal / Dual-Mode).
  - OAuth2 fields (Client ID, Secret, Scopes, Auth URL, Token URL, Redirect URI) — shown for OAuth2 services.
  - API Key field — shown for key-based services.
  - "Allow user override" toggle (shown for Dual-Mode).
  - "Test before saving" checkbox.
- **Row actions:** Edit, Test, View Connected Users (slide-out panel), Disable/Enable, Disconnect All, Delete.
- **"Connected Users" side panel:** list of `display_name` + `connected_at` + last used for the selected service; "Disconnect" per row.

---

## Files to Create

| File | Purpose |
|---|---|
| `app/models/researcher/storage_quota.py` | `PlanTier`, `TenantQuota`, `UserStorageStats` models |
| `app/services/storage/__init__.py` | `get_storage_backend()` factory; re-exports base types |
| `app/services/storage/base.py` | `BaseStorageBackend` ABC, `StorageResult`, `ConnectionTestResult` |
| `app/services/storage/local_backend.py` | Local filesystem implementation (replaces current inline code) |
| `app/services/storage/smb_backend.py` | SMB/NAS implementation using `smbprotocol` |
| `app/services/storage/s3_backend.py` | S3/MinIO implementation using `boto3` |
| `app/services/storage/azure_blob_backend.py` | Azure Blob implementation using `azure-storage-blob` |
| `app/services/quota_service.py` | Quota resolution, enforcement checks, usage tracking |
| `app/services/email/oauth2_mail.py` | Microsoft 365 + Google Workspace OAuth2 mail sender |
| `app/routes/admin/quota.py` | `quota_admin_bp` REST blueprint (10 endpoints) |
| `app/routes/admin/storage.py` | `storage_admin_bp` REST blueprint (9 endpoints) |
| `app/routes/admin/documents.py` | `admin_documents_bp` REST blueprint (7 endpoints) |
| `templates/admin/document_management.html` | Global document admin UI |
| `templates/admin/quota_management.html` | Quota & plan tier admin UI |
| `migrations/xxxx_add_quota_system.py` | Alembic auto-generated migration for quota schema |
| `app/models/user_management.py` | `UserInvite`, `PasswordHistory`, `UserSession` models |
| `app/services/mfa_service.py` | TOTP, Email OTP, SMS OTP, backup codes — full MFA stack |
| `app/services/password_policy.py` | Password validation, history check, lockout enforcement |
| `app/services/session_service.py` | Session creation, tracking, idle timeout, revocation |
| `app/routes/admin/users.py` | `admin_users_bp` REST blueprint (24 endpoints incl. invites, bulk ops, import/export) |
| `app/routes/mfa_routes.py` | MFA challenge + setup routes (`mfa_bp`, prefix `/auth/mfa`) |
| `app/routes/account_routes.py` | User self-service profile + password change (`account_bp`, prefix `/account`) |
| `templates/admin/user_detail.html` | Full admin user detail page (6 tabs: Profile, Security, MFA, Sessions, Activity, Quota) |
| `templates/admin/invites.html` | Invite token management UI |
| `templates/auth/mfa_challenge.html` | MFA login challenge page (TOTP / Email / SMS / Backup tabs) |
| `templates/auth/mfa_setup.html` | Step-by-step MFA enrollment wizard |
| `templates/account/profile.html` | User self-service profile + password change + session management |
| `migrations/xxxx_add_user_management.py` | Alembic migration: `user_invites`, `password_history`, `user_sessions`; new `User` columns |
| `app/models/integrations_registry.py` | `GlobalIntegrationService` + `UserIntegrationCredential` models |
| `app/services/integration_service.py` | Credential resolution, OAuth2 flows, token refresh, admin bulk-disconnect |
| `app/routes/admin/integrations.py` | `admin_integrations_bp` REST blueprint (12 endpoints incl. OAuth2 callback) |
| `app/routes/integrations_routes.py` | `integrations_bp` user-facing OAuth2 + key connect/disconnect routes (7 endpoints) |
| `templates/admin/integrations.html` | Admin global service registry UI |
| `templates/account/integrations.html` | User self-service connected integrations grid |
| `migrations/xxxx_add_integration_registry.py` | Alembic migration: `global_integration_services`, `user_integration_credentials` tables |

---

## Files to Modify

| File | What Changes |
|---|---|
| `app/models/core.py` | Add `storage_quota_bytes`, `document_quota`, `plan_tier_id` to `User` |
| `app/models/tenant.py` | Add `plan_tier_id` FK to `Tenant` |
| `app/config_manager.py` | Merge config layers; add 40+ new config keys (storage, email, quota, enterprise, external APIs) |
| `app/config/manager.py` | Replace body with import shim re-exporting from `config_manager` |
| `app/__init__.py` | Register 6 new blueprints: `quota_admin_bp`, `storage_admin_bp`, `admin_documents_bp`, `admin_users_bp`, `mfa_bp`, `account_bp` |
| `app/routes/documents.py` | Use `storage_service`; enforce quota pre-upload; fix orphan-file leak on delete |
| `app/routes/admin_routes.py` | Add HTML routes for `/admin/documents`, `/admin/quota`, `/admin/users`, `/admin/invites`; add email test + OAuth2 callback routes |
| `app/services/email_service.py` | Add `mail_auth_method` dispatch; add `test_send()` public method |
| `app/routes/auth_routes.py` | Registration mode gate; invite validation; domain allowlist; lockout checks; two-step MFA login flow; password policy on reset; `GET /auth/password-policy` |
| `app/decorators/__init__.py` | Update `@login_required` to call `session_service.touch_session()`, enforce idle timeout, and redirect to MFA setup if `mfa_service.is_mfa_compliant()` is False |
| `templates/admin/settings.html` | Add Storage, Enterprise Identity, External APIs, Quota Defaults, Registration, Password Policy, MFA tabs |
| `templates/admin/index.html` | Add storage/email/quota/MFA summary cards, quick-links, backend status indicator |
| `templates/admin/users.html` | Enhanced: MFA status column, bulk actions, import/export buttons, invite management link |
| `config/app_config.json` | Seed all SMTP keys + storage + registration + MFA defaults on first boot |
| `requirements.txt` | Add `boto3`, `azure-storage-blob`, `smbprotocol`, `msal`, `google-auth`, `google-api-python-client`, `pyotp`, `qrcode[pil]`, `twilio` (optional), `cryptography` (AES token encryption) |
| `app/__init__.py` | Also register `admin_integrations_bp` and `integrations_bp` (Phase 9 additions) |
| `app/routes/admin_routes.py` | Add HTML route for `GET /admin/integrations` |
| `app/models/researcher/integrations.py` | Migrate existing `IntegrationCredential` data to new `UserIntegrationCredential`; retain legacy table temporarily during migration |

---

## Verification Checklist

- [ ] **Quota enforcement** — upload a file as a user whose `storage_quota_bytes` is set to `1`; expect HTTP 413 with `quota_exceeded` JSON body.
- [ ] **Quota inheritance** — user with no override inherits plan tier limits via `get_effective_quota()`.
- [ ] **Tenant pool** — tenant members share pool limit; per-user override takes priority over tenant pool.
- [ ] **Storage backend switch** — switch config to S3/MinIO; upload a document; verify file appears in MinIO bucket; `file_path` column contains `s3://...` key.
- [ ] **SMB backend** — switch config to SMB; upload; verify file on SMB share.
- [ ] **Azure Blob backend** — switch config to Azure Blob; upload; verify file in container.
- [ ] **Backend migration** — with files in local backend, switch to S3 and trigger migration job; verify all files copied; verify downloads work after migration.
- [ ] **Orphan cleanup** — manually drop a DB document row; run orphan scan; file appears in list; delete removes it from storage.
- [ ] **Email SMTP fix** — fresh install; set `smtp_host` via settings; click "Send Test Email"; verify delivery.
- [ ] **OAuth2 MS365 mail** — set `mail_auth_method = oauth2_ms365`; authorize via admin UI; click test; verify Graph API mail delivery.
- [ ] **OAuth2 Google mail** — set `mail_auth_method = oauth2_google`; authorize; test send.
- [ ] **Admin document management** — open `/admin/documents`; verify pagination, filters, bulk delete, CSV export all work.
- [ ] **Plan tier creation** — create "Free" tier at 100 MB / 50 docs; assign to user; verify `get_effective_quota()` returns 100 MB.
- [ ] **Recalculate all** — run recalculate via admin UI; verify `UserStorageStats` matches actual DB aggregate.
- [ ] **Alembic migration** — run `flask db upgrade`; verify all new columns exist in SQLite.
- [ ] **Config unification** — verify `get_config()` / `set_feature_enabled()` calls still work after merge (backward compat shim).
- [ ] **SSO settings save** — configure LDAP via settings; verify config persisted; test bind button returns result.
- [ ] **Registration — open mode** — register without invite; verify account created.
- [ ] **Registration — invite_only mode** — attempt to register without a token; expect 403. Register with a valid token; verify success; verify invite marked as used.
- [ ] **Registration — domain_allowlist mode** — register with `@company.com` (allowed); verify success. Register with `@gmail.com` (not allowed); expect 403 with `domain_not_allowed` error.
- [ ] **Registration — admin_only mode** — attempt to register; expect 403 regardless of any invite token.
- [ ] **Password policy** — attempt registration with a 4-character password; expect policy violation error. Register with a compliant password; expect success.
- [ ] **Password history** — change password to the same value as an existing history entry; expect rejection. Change to a new value; expect success.
- [ ] **Account lockout** — fail login 5 times consecutively; expect `account_locked` response on 5th attempt. Wait lockout period; expect access restored.
- [ ] **TOTP MFA setup** — enroll TOTP via `/auth/mfa/setup`; confirm with a valid 6-digit code; receive and acknowledge backup codes.
- [ ] **TOTP login challenge** — log in with a TOTP-enrolled user; expect MFA challenge page; submit correct code; expect full session issued.
- [ ] **TOTP invalid code** — submit an incorrect TOTP code; expect 401 with error; session not issued.
- [ ] **Email OTP login** — enroll email OTP; log in; click "Send Code"; receive email; submit code; expect session.
- [ ] **SMS OTP login** — enroll SMS OTP with a phone number; log in; click "Send Code"; receive SMS; submit code; expect session.
- [ ] **Backup code login** — use one backup code; expect success; verify `mfa_backup_codes_remaining` decremented by 1.
- [ ] **Backup code — invalid** — submit a used or non-existent backup code; expect 401.
- [ ] **MFA enforcement: required_all** — set `mfa_enforcement = required_all`; log in as user with no MFA; expect redirect to MFA setup wizard before any other page is accessible.
- [ ] **MFA enforcement: required_by_role** — set role `admin` as required; log in as admin without MFA; expect redirect to setup. Log in as regular user without MFA; expect normal access.
- [ ] **Admin MFA reset** — admin POSTs to `/api/admin/users/<id>/mfa/reset`; verify all MFA data cleared; verify notification email sent to user; verify user can log in with password only.
- [ ] **Session management — view** — log in from two different browsers; open `/account/profile` Sessions tab; verify both sessions listed.
- [ ] **Session management — revoke one** — revoke one session via profile; verify that session receives 401 on next request; other session unaffected.
- [ ] **Session management — admin force logout** — admin calls `DELETE /api/admin/users/<id>/sessions/revoke-all`; verify all sessions revoked; user receives 401 on next request.
- [ ] **Idle timeout** — configure `session_idle_timeout_minutes = 1`; wait 90 seconds without any request; make a request; expect 401 or redirect to login.
- [ ] **Admin create user** — POST `/api/admin/users/` with valid payload; verify user created with correct role and plan tier.
- [ ] **Admin user CSV import** — upload a valid CSV via `/api/admin/users/import`; verify users created with correct fields.
- [ ] **Admin user CSV export** — GET `/api/admin/users/export`; verify downloaded CSV contains all columns and filtered users.
- [ ] **Invite create and use** — create an invite via admin UI; copy link; register a new user with the link; verify invite `used_at` set and `use_count` incremented.
- [ ] **Invite revoke** — create an invite; revoke it; attempt to register with the token; expect 403.
- [ ] **Impersonation** — admin POSTs to `/api/admin/users/<id>/impersonate`; verify audit log records admin ID + target user ID; verify impersonation session expires per configured limit.
- [ ] **User self-service profile** — user updates timezone and display name; verify persisted. User changes password with correct current password; verify login with new password works.
- [ ] **Account self-deletion** — user requests deletion; verify data export is offered; confirm deletion; verify account anonymized/deleted per configured action.
- [ ] **Integration registry seeding** — on fresh install, verify `seed_default_services()` creates entries for Google Drive, Dropbox, Zotero, Mendeley, and GitHub in a disabled state.
- [ ] **Admin registers Google Drive** — POST to `/api/admin/integrations/services` with `service_type=google_drive`, OAuth2 client ID/secret, `scope=user_personal`; verify entry created and appears in admin integrations table.
- [ ] **Admin enables service** — POST to `/api/admin/integrations/services/<id>/enable`; verify `is_enabled` is True; service now appears on user integrations page.
- [ ] **User connects personal Google Drive** — user clicks Connect; OAuth2 flow redirects to Google; callback stores encrypted tokens; card shows Connected badge with account display name.
- [ ] **User disconnects Google Drive** — user clicks Disconnect; `UserIntegrationCredential` marked inactive; card reverts to Not Connected state; admin-side connected user count decrements.
- [ ] **Credential resolution — personal first** — for a Dual-Mode service where user has a personal credential: `get_credential(user_id, service_type)` returns user's personal credential.
- [ ] **Credential resolution — global fallback** — for a Dual-Mode service where user has NO personal credential: `get_credential()` returns the global service credential.
- [ ] **Credential resolution — no credential** — service is User-Personal only and user has not connected: `get_credential()` returns `None`.
- [ ] **Admin disables service** — POST to disable; existing user connections still exist in DB but `integrations_bp` blocks new connection requests with 403; user card shows "Unavailable" badge.
- [ ] **Admin disconnect-all** — DELETE `/api/admin/integrations/services/<id>/disconnect-all`; verify all `UserIntegrationCredential` rows for this service are set inactive; connected count drops to 0.
- [ ] **Admin disconnect single user** — DELETE `/api/admin/integrations/services/<id>/disconnect/<user_id>`; verify only that user's credential deactivated; other connections unaffected.
- [ ] **Token refresh** — simulate expired access token; call `refresh_user_token()`; verify new access token stored encrypted; expiry updated.
- [ ] **Allow user override = False** — admin sets `allow_user_override = False` on a Dual-Mode service; user integrations page shows "Available via institution" with no Connect button.
- [ ] **OAuth2 admin callback** — admin connects a service via `/api/admin/integrations/services/oauth2/callback`; `GlobalIntegrationService.global_api_key_encrypted` updated with the new access token.
- [ ] **Admin test service** — admin clicks Test on a correctly configured service; `last_test_ok = True` and latency displayed. Admin tests a misconfigured service; `last_test_ok = False` and error message shown.
- [ ] **Admin-only service** — register a service with `scope=admin_only`; verify it does NOT appear on the user integrations page.
- [ ] **Migration compatibility** — existing `IntegrationCredential` rows migrated to `UserIntegrationCredential`; old table preserved; verify data integrity after `flask db upgrade`.

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| **Quota hierarchy: User → Tenant → Plan → Global** | Matches standard SaaS + enterprise billing models; `NULL` means "inherit from next level" so admins can override at any granularity |
| **Storage path routing by URI scheme** | Storing `s3://bucket/key` instead of just `key` enables transparent mixed-backend retrieval during migration and avoids a backend lookup table |
| **`smbprotocol` for SMB** | Pure Python, cross-platform, supports SMB2/3, actively maintained — preferred over `pysmb` |
| **`email_service.py` as single dispatch point** | All existing email callers (`auth_routes.py`, notifications, etc.) continue to work unchanged; only dispatch logic changes internally |
| **OAuth2 refresh token in `app_config.json`** | Consistent with other secrets already in the config file; for production, recommend placing `app_config.json` on an encrypted volume or using environment variable override (already supported by `config_manager`) |
| **No removal of local storage** | Local filesystem backend is always available as a fallback; admin cannot disable it if another backend fails its connection test |
| **`quota_enforcement_enabled` toggle** | Allows admins to temporarily disable quota enforcement during migrations, bulk imports, or legacy data loads without touching user quota values |
| **Soft-delete for plan tiers** | `is_active = False` instead of SQL DELETE prevents breaking FK references from users already on the tier |
| **Two-step MFA login via interim session flag** | Using a `mfa_pending` + `mfa_user_id` flag in the Flask session avoids an extra DB table while preventing session fixation; the full session is issued only after the second factor is verified |
| **TOTP secret encrypted at rest** | `user.mfa_totp_secret` is AES-encrypted using the app `SECRET_KEY` before storage; a DB dump does not directly expose raw TOTP seeds |
| **Backup codes as bcrypt hashes list** | Stored as a JSON list of individual bcrypt hashes in a single column — allows O(N) verification with N ≈ 10 without a lookup table; each hash is independently marked consumed |
| **`pyotp` for TOTP** | RFC 6238/4226 compliant, supports ±1 window for clock skew, actively maintained, zero native dependencies |
| **`UserSession` model instead of relying on Flask's session cookie** | Gives admin visibility into active sessions, enables server-side revocation, supports idle timeout enforcement, and provides an audit trail without requiring Redis or an external session store |
| **Password history as a separate table** | Enables efficient bcrypt hash comparison for the last N passwords; automatically pruned to N records per user; avoids storing a large blob in the `User` row |
| **Registration mode is a runtime config key** | Admin can switch from `open` to `invite_only` at runtime without a code deployment — critical for enterprise rollouts and security incidents |
| **Impersonation logged to AuditLog** | Admin impersonation is a high-risk action; every use is recorded with admin user ID, target user ID, timestamp, and impersonation session token hash for compliance |
| **`GlobalIntegrationService` as a runtime registry** | Storing integration service definitions in the DB (not just config) allows admins to register, enable, and configure services at runtime without a code deployment or restart |
| **Personal OAuth2 tokens never exposed to admin** | Admin routes return only `display_name`, `connected_at`, and `is_active` — never raw tokens; all token columns are `_encrypted` suffixed and excluded from admin serializers |
| **Credential resolution: personal → global fallback** | Mirrors the quota hierarchy pattern (user → tenant → plan → global); consistent mental model across the codebase; resolvers are pure functions easy to test in isolation |
| **AES-GCM encryption for stored tokens** | Flask `SECRET_KEY`-derived AES-256-GCM; same mechanism as TOTP secrets; a DB dump without the app secret cannot decrypt tokens; for production, recommend Azure Key Vault-backed key |
| **`allow_user_override` on dual-mode services** | Admin can lock a dual-mode service to institutional key only (compliance requirement) without changing the service's tier classification |
| **`seed_default_services()` at startup** | Pre-populates the registry with known service types in disabled state; gives admins a starting point with correct OAuth2 URL templates without manual entry |

---

## Implementation Order

```
Phase 1b: Add quota models + Alembic migration                            ✅ DONE 2026-02-25
Phase 8a: User & session models + Alembic migration                       ✅ DONE 2026-02-25
Phase 9a: GlobalIntegrationService + UserIntegrationCredential models     ✅ DONE 2026-02-25
          + Alembic migration + migrate legacy IntegrationCredential data
Phase 1a: Fix config_manager (unify + add keys + fix smtp_host default)   ✅ DONE 2026-02-25
Phase 2:  Storage service abstraction + integrate with upload route        ✅ DONE 2026-02-25
Phase 3a: quota_service.py                                                ✅ DONE 2026-02-25
Phase 3b: Enforce quota in upload route + admin quota API                 ✅ DONE 2026-02-25
Phase 4:  Email fix + OAuth2 mail + admin email routes                    ✅ DONE 2026-02-25
Phase 5a: Admin UI — settings.html extended tabs                          ✅ DONE 2026-02-25
Phase 5b: Admin UI — document_management.html                             ✅ DONE 2026-02-25
Phase 5c: Admin UI — quota_management.html                                ✅ DONE 2026-02-25
Phase 5d: Admin UI — index.html enhanced dashboard                        ✅ DONE 2026-02-25
Phase 6:  Storage admin REST API (test endpoint)                          ✅ DONE 2026-02-25
Phase 7:  Admin documents REST API (list + delete)                        ✅ DONE 2026-02-25
Phase 8b: password_policy_service + lockout + password history            ✅ DONE 2026-02-26
Phase 8c: mfa_service — TOTP + email OTP + backup codes                  ✅ DONE 2026-02-26
Phase 8d: session_service + integrate into login / logout / decorator      ✅ DONE 2026-02-26
Phase 8e: Two-step MFA login flow + auth routes + templates                ✅ DONE 2026-02-26
Phase 8f: Registration mode gate + invite system + domain allowlist        ✅ DONE 2026-02-26
Phase 8g: SMS OTP + provider integration (optional)                        ✅ DONE 2026-02-26
Phase 8h: Admin users REST API (24 endpoints incl. MFA reset, impersonate) ✅ DONE 2026-02-26
Phase 8i: Admin UI — user_detail.html + invites.html + user_create.html +  ✅ DONE 2026-02-26
          user_import.html + enhanced users.html (search, detail links)
Phase 8j: User self-service profile MFA + sessions section                 ✅ DONE 2026-02-26
Phase 8k: Settings UI — Registration + Password Policy + MFA tabs          ✅ DONE 2026-02-26
Phase 9b: integration_service.py — credential resolution, OAuth2 flows,    ✅ DONE 2026-02-26
          token refresh, test methods, seed_default_services()
Phase 9c: Admin integrations REST API (admin_integrations.py)              ✅ DONE 2026-02-26
          + Admin integrations UI (templates/admin/integrations.html)
          + templates/admin/integration_users.html
Phase 9d: User integrations routes (user_integrations.py)                  ✅ DONE 2026-02-26
          + User integrations UI (templates/integrations/my_integrations.html)
─────────────────────────────────────────────────────────────────────────────────
Total estimate: 39–47 developer-days
  Phase 1–7:  16–19 days
  Phase 8:    18–21 days
  Phase 9:     5–7 days
```
