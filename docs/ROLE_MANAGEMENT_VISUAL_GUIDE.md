# Role & Permission System - Visual Architecture & Workflows

**Purpose**: Visual guide showing how role/permission system integrates with Beep.AI.Researcher

---

## 🏗️ System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        BEEP.AI.RESEARCHER                            │
└──────────────────────────────────────────────────────────────────────┘

┌─── ADMIN INTERFACE ──────────────────────────────────────────────────┐
│                                                                       │
│  ROLES                    USERS                  DOCUMENTS            │
│  ├─ Create Role    ───→  ├─ Assign Role ───→   ├─ Share with User   │
│  ├─ Edit Role            ├─ Revoke Role         ├─ Share with Group  │
│  ├─ Delete Role          ├─ View Roles          └─ Make Public/Priv  │
│  └─ List Roles           └─ Temp Access (14d)                        │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                              ↓↓↓
         ┌────────────────────────────────────────┐
         │   SQLite Database (RBAC Tables)        │
         │                                        │
         │  ┌─ Role ─────────────────────────┐   │
         │  │ id, name, permissions, builtin │   │
         │  │ viewer, contributor, lead,     │   │
         │  │ admin, custom_roles            │   │
         │  └────────────────────────────────┘   │
         │                                        │
         │  ┌─ UserRole ────────────────────────┐ │
         │  │ user_id, role_id, scope,          │ │
         │  │ scope_id, expires_at              │ │
         │  │ Tracks: global, project-level    │ │
         │  └────────────────────────────────────┘ │
         │                                        │
         │  ┌─ DocumentAccess ─────────────────┐  │
         │  │ document_id, owner_id,            │  │
         │  │ access_level (private/public),    │  │
         │  │ shared_with {users,groups,roles}  │  │
         │  └────────────────────────────────────┘  │
         │                                        │
         │  ┌─ UserGroup ──────────────────────┐   │
         │  │ id, name, members[], project_id  │   │
         │  │ For group-based sharing           │   │
         │  └────────────────────────────────────┘  │
         │                                        │
         └────────────────────────────────────────┘
                              ↑↑↑
         ┌────────────────────────────────────────┐
         │    PermissionService (Core Logic)      │
         │                                        │
         │  user_has_permission(user, perm,      │
         │    scope, scope_id)                    │
         │    ├─ Query UserRole for user         │
         │    ├─ Check role permissions          │
         │    └─ Return True/False                │
         │                                        │
         │  can_access_document(user, doc)        │
         │    ├─ Query DocumentAccess             │
         │    ├─ Check owner_id                  │
         │    ├─ Check access_level              │
         │    ├─ Check shared_with {users,groups}│
         │    └─ Return True/False                │
         │                                        │
         │  can_write_document(user, doc)         │
         │    ├─ Check can_access first          │
         │    ├─ Check default_permissions       │
         │    └─ Return True/False                │
         │                                        │
         │  get_accessible_documents(user, proj) │
         │    ├─ Query all documents             │
         │    ├─ Filter by access level          │
         │    └─ Return [accessible docs]        │
         │                                        │
         └────────────────────────────────────────┘
                              ↓↓↓
         ┌────────────────────────────────────────┐
         │    Permission Decorators               │
         │                                        │
         │  @require_permission(perm, scope)      │
         │    Pre-checks before route executes    │
         │    Returns 403 if denied               │
         │                                        │
         │  @require_document_access(type)        │
         │    Pre-checks document access          │
         │    Returns 403 if denied               │
         │                                        │
         └────────────────────────────────────────┘
                              ↓↓↓
         ┌────────────────────────────────────────┐
         │      API Routes (All Protected)        │
         │                                        │
         │  Document Routes:                      │
         │  ├─ POST   /docs/upload [write]        │
         │  ├─ GET    /docs/<id>   [read]         │
         │  ├─ DELETE /docs/<id>   [write]        │
         │  └─ PUT    /docs/<id>   [owner]        │
         │                                        │
         │  Sharing Routes:                       │
         │  ├─ PUT    /docs/<id>/access           │
         │  ├─ POST   /docs/<id>/share-user       │
         │  ├─ POST   /docs/<id>/share-group      │
         │  ├─ POST   /docs/<id>/make-public      │
         │  └─ POST   /docs/<id>/make-private     │
         │                                        │
         │  Admin Routes:                         │
         │  ├─ POST   /admin/roles                │
         │  ├─ GET    /admin/roles                │
         │  ├─ PUT    /admin/roles/<id>           │
         │  ├─ DELETE /admin/roles/<id>           │
         │  ├─ POST   /admin/users/<id>/roles     │
         │  └─ DELETE /admin/users/<id>/roles     │
         │                                        │
         └────────────────────────────────────────┘
```

---

## 👤 User Story: Dr. Smith Uploads & Shares a Document

```
1. ADMIN ONBOARDING
   ┌─────────────────────────────────────────┐
   │ Admin creates "Medical Researcher" role  │
   │ Permissions: [                           │
   │   document:read,                         │
   │   document:write,                        │
   │   extraction:read,                       │
   │   code:read                              │
   │ ]                                        │
   │                                         │
   │ Admin assigns role to Dr. Smith          │
   │ Scope: global                            │
   │ Expires: None (permanent)                │
   └─────────────────────────────────────────┘
                    ↓

2. DR. SMITH UPLOADS DOCUMENT
   ┌─────────────────────────────────────────┐
   │ POST /projects/proj_1/documents/upload   │
   │ Headers: X-User-ID: dr_smith             │
   │ File: medical_paper.pdf                  │
   │                                         │
   │ Route: @require_permission('document:write')
   │ ✓ Check: user_has_permission(            │
   │     'dr_smith',                          │
   │     'document:write',                    │
   │     'global'                             │
   │   )                                      │
   │ ✓ Dr. Smith has permission (via role)    │
   │                                         │
   │ Create Document:                         │
   │ {                                        │
   │   id: "doc_1",                           │
   │   name: "medical_paper.pdf",             │
   │   project_id: "proj_1",                  │
   │   created_by: "dr_smith"                 │
   │ }                                        │
   │                                         │
   │ Create DocumentAccess:                   │
   │ {                                        │
   │   id: "access_1",                        │
   │   document_id: "doc_1",                  │
   │   owner_id: "dr_smith",                  │
   │   access_level: PRIVATE,                 │
   │   shared_with: {                         │
   │     users: [],                           │
   │     groups: [],                          │
   │     roles: []                            │
   │   }                                      │
   │ }                                        │
   │ ✓ Document created and private           │
   └─────────────────────────────────────────┘
                    ↓

3. DR. SMITH SHARES WITH TEAM
   ┌─────────────────────────────────────────┐
   │ POST /docs/doc_1/access/share-group      │
   │ Headers: X-User-ID: dr_smith             │
   │ Body: {                                  │
   │   group_id: "medical_team",              │
   │   permissions: ["read"]                  │
   │ }                                        │
   │                                         │
   │ Route: @require_document_access('write') │
   │ ✓ Check: can_write_document(             │
   │     'dr_smith', 'doc_1'                 │
   │   )                                      │
   │ ✓ True (dr_smith is owner)               │
   │                                         │
   │ Update DocumentAccess:                   │
   │ {                                        │
   │   ...                                    │
   │   access_level: GROUP,                   │
   │   shared_with: {                         │
   │     groups: ["medical_team"],            │
   │     users: [],                           │
   │     roles: []                            │
   │   },                                     │
   │   default_permissions: ["read"]          │
   │ }                                        │
   │ ✓ Document now shared with team          │
   └─────────────────────────────────────────┘
                    ↓

4. TEAM MEMBER ACCESSES DOCUMENT
   ┌─────────────────────────────────────────┐
   │ GET /docs/doc_1                          │
   │ Headers: X-User-ID: dr_jones             │
   │ (dr_jones is member of medical_team)     │
   │                                         │
   │ Route: @require_document_access('read')  │
   │ ✓ Check: can_access_document(            │
   │     'dr_jones', 'doc_1'                 │
   │   )                                      │
   │                                         │
   │ PermissionService Logic:                 │
   │ 1. Get DocumentAccess for doc_1          │
   │ 2. owner_id = 'dr_smith' (not dr_jones)  │
   │ 3. access_level = GROUP                  │
   │ 4. Check if dr_jones in groups:          │
   │    is_user_in_group('dr_jones',          │
   │      'medical_team') = True            │
   │ 5. Return True                           │
   │                                         │
   │ ✓ Document returned to dr_jones          │
   │ ✓ Read permissions enforced              │
   │ ✗ Cannot write (permission = read only)  │
   └─────────────────────────────────────────┘
```

---

## 🔄 Permission Check Flow Diagram

```
User Request
    ↓
    ├─ GET /projects/proj_1/documents/doc_1
    ├─ Headers: X-User-ID: user_123
    ↓
Route Handler
    ├─ @require_document_access('read')
    ├─ Decorator intercepts
    ↓
Extract Context
    ├─ user_id = 'user_123'
    ├─ document_id = 'doc_1'
    ↓
Permission Service
    ├─ can_access_document('user_123', 'doc_1')
    ↓
Database Queries
    ├─ SELECT * FROM document_access WHERE document_id='doc_1'
    │  ├─ owner_id='dr_smith', access_level='GROUP'
    │  ├─ shared_with={groups:['medical_team'], ...}
    ↓
Permission Logic
    ├─ Is user_123 == owner? No
    ├─ Is access_level PUBLIC? No
    ├─ Is access_level GROUP? Yes
    │  ├─ Check groups: is_user_in_group('user_123', 'medical_team')
    │  ├─ Query: SELECT * FROM user_group WHERE group_id='medical_team'
    │  ├─ Check members: ['user_123', 'user_456', ...]
    │  ├─ Found! user_123 is in group
    │  ├─ Return True
    ↓
Decision
    ├─ Access Granted ✓
    ↓
Execute Handler
    ├─ Fetch document from database
    ├─ Return to client
    ↓
HTTP 200 OK
    ├─ Document data in response
```

---

## 📊 Access Level Decision Tree

```
Can user access document?
    ↓
    ├─ Is user == document owner?
    │  ├─ YES → Allow ✓
    │  └─ NO ↓
    ├─ Is access_level == PRIVATE?
    │  ├─ YES → Deny ✗
    │  └─ NO ↓
    ├─ Is access_level == PUBLIC?
    │  ├─ YES → Allow ✓
    │  └─ NO ↓
    ├─ Is access_level == PROJECT?
    │  ├─ Is user in project?
    │  │  ├─ YES → Allow ✓
    │  │  └─ NO → Deny ✗
    │  └─
    ├─ Is access_level == GROUP?
    │  ├─ Is user in any shared groups?
    │  │  ├─ YES → Allow ✓
    │  │  └─ NO ↓
    │  └─
    ├─ Is access_level == SHARED?
    │  ├─ Is user in shared_with.users?
    │  │  ├─ YES → Allow ✓
    │  │  └─ NO → Deny ✗
    │
    └─ Default → Deny ✗


Can user WRITE to document?
    ↓
    ├─ First: Can user READ? (above)
    │  ├─ NO → Deny ✗
    │  └─ YES ↓
    ├─ Is user == document owner?
    │  ├─ YES → Allow ✓
    │  └─ NO ↓
    ├─ Is 'write' in default_permissions?
    │  ├─ YES → Allow ✓
    │  └─ NO → Deny ✗
```

---

## 🎭 Role Inheritance Diagram

```
Admin
├─ Permissions: [*:*] (all)
├─ Use Case: System administrators, super users
└─ Examples: admin_1, system_admin

  Lead
  ├─ Permissions: [doc:read, doc:write, doc:share, proj:write, etc.]
  ├─ Use Case: Team leads, project managers
  └─ Examples: team_lead_1, project_manager_2

    Contributor
    ├─ Permissions: [doc:read, doc:write, code:write, etc.]
    ├─ Use Case: Regular users who create content
    └─ Examples: researcher_1, analyst_2

      Viewer
      ├─ Permissions: [doc:read, code:read, extraction:read]
      ├─ Use Case: Read-only access, stakeholders
      └─ Examples: stakeholder_1, auditor_2


Custom Roles (Created by Admin)
├─ medical_researcher
│  ├─ Permissions: [...]
│  └─ Use Case: Medical domain specialists
├─ data_analyst
│  ├─ Permissions: [...]
│  └─ Use Case: Data analysis specialists
└─ legal_reviewer
   ├─ Permissions: [...]
   └─ Use Case: Legal review
```

---

## 📈 Scoped Permissions Example

```
Global Scope (User has permission everywhere)
    user_1
        ├─ Role: viewer (scope: global)
        └─ Can read ANY document accessible to them globally

Project Scope (User has permission in specific project)
    user_2
        ├─ Role: contributor (scope: project, scope_id: proj_123)
        └─ Can write documents ONLY in proj_123
        └─ Cannot write in other projects

Mixed Scopes (User has different permissions in different places)
    user_3
        ├─ Role: viewer (scope: global)
        │  └─ Can read documents globally
        ├─ Role: contributor (scope: project, scope_id: proj_123)
        │  └─ Can write documents in proj_123
        └─ Role: lead (scope: project, scope_id: proj_456)
           └─ Can manage project proj_456


Query: What can user_3 do?
    ├─ Anywhere: Read documents (viewer role)
    ├─ In proj_123: Write documents (contributor role)
    ├─ In proj_456: Manage project (lead role)
    └─ In other projects: No special access
```

---

## ⏰ Temporary Access Workflow

```
Admin wants to give contractor 2-week access to project

1. CREATE TEMPORARY ASSIGNMENT
   POST /admin/users/contractor_john/roles
   {
     "role_id": "uuid_contributor",
     "scope": "project",
     "scope_id": "proj_123",
     "expires_in_days": 14
   }
   
   ↓ Database stores:
   UserRole:
   ├─ user_id: contractor_john
   ├─ role_id: uuid_contributor
   ├─ scope: project
   ├─ scope_id: proj_123
   └─ expires_at: 2026-02-21 10:30:00 (14 days from now)

2. CONTRACTOR ACCESSES PROJECT (Day 1-13)
   ✓ Check: expires_at > now
   ✓ Access granted
   
3. CONTRACTOR ACCESSES PROJECT (Day 14+)
   ✗ Check: expires_at < now
   ✗ Assignment ignored (effectively revoked)
   ✗ Access denied

4. CLEANUP (Automatic, daily)
   Scheduled job:
   ├─ Query: SELECT * FROM user_role WHERE expires_at < NOW()
   ├─ Delete expired assignments
   └─ Log: "Revoked contractor_john access to proj_123"
```

---

## 🔐 Security Layer Validation

```
Request: POST /admin/roles
Handler: create_role()

Validation Layer
├─ Is X-User-ID present? check
├─ Does user exist? check
└─ Is user an admin? check
   ├─ Query: user_has_permission('X-User-ID', 'admin:roles')
   ├─ Check: Does user have role with 'admin:roles' != found
   ├─ Return: 403 Forbidden ✗
   └─ Stop execution

Validation Layer (continued if authorized)
├─ Is role name provided? check
├─ Is role name unique?
│  ├─ Query: SELECT * FROM role WHERE name=<input>
│  ├─ Found: return 409 Conflict ✗
│  └─ Not found: continue
├─ Are permissions valid?
│  ├─ Allowed: ['document:*', 'code:*', 'extraction:*', ...]
│  ├─ Input: ['document:read', 'bad_permission']
│  ├─ Found invalid: return 400 Bad Request ✗
│  └─ All valid: continue
└─ Create role ✓

Database Transaction
├─ INSERT INTO role (...) VALUES (...)
├─ COMMIT
└─ Audit log: {action: 'create_role', by: 'X-User-ID', role: 'name'}

Response: 201 Created
└─ Return role_id to client
```

---

## 📊 Data Flow: Document Upload to Sharing

```
Scenario: End-to-end flow from upload to share

STEP 1: USER UPLOADS DOCUMENT
Request:
  POST /projects/proj_1/documents/upload
  Headers: X-User-ID: researcher_1
  File: dataset.csv
  
Check Permissions:
  @require_permission('document:write')
  ├─ PermissionService.user_has_permission(
  │    'researcher_1', 'document:write', 'global')
  ├─ Query UserRole: find all roles for researcher_1
  ├─ Check if any role has 'document:write'
  └─ ✓ Found in 'contributor' role

Create Document:
  INSERT INTO documents
  (id, name, project_id, created_by)
  VALUES
  ('doc_1', 'dataset.csv', 'proj_1', 'researcher_1')

Create DocumentAccess:
  INSERT INTO document_access
  (id, document_id, owner_id, access_level, shared_with)
  VALUES
  ('access_1', 'doc_1', 'researcher_1', 'PRIVATE', {...})

Response: 201 Created
  {success: true, document_id: 'doc_1'}

STEP 2: OWNER WANTS TO SHARE
Request:
  POST /projects/proj_1/documents/doc_1/access/share-group
  Headers: X-User-ID: researcher_1
  Body: {group_id: 'data_team', permissions: ['read', 'write']}

Check Permissions:
  @require_document_access('write')
  ├─ PermissionService.can_write_document(
  │    'researcher_1', 'doc_1')
  ├─ Query DocumentAccess for doc_1
  ├─ owner_id == 'researcher_1' == X-User-ID
  └─ ✓ User is owner (can modify)

Update DocumentAccess:
  UPDATE document_access
  SET access_level = 'GROUP',
      shared_with = {
        'groups': ['data_team'],
        'users': [],
        'roles': []
      },
      default_permissions = ['read', 'write'],
      updated_at = NOW()
  WHERE document_id = 'doc_1'

Audit Log:
  INSERT INTO audit_log
  (id, action, user_id, resource_id, changes, timestamp)
  VALUES
  ('audit_1', 'share_doc', 'researcher_1', 'doc_1',
   {access_level: 'PRIVATE→GROUP', shared_with: '[data_team]'},
   NOW())

Response: 200 OK
  {success: true, message: 'Shared with data_team'}

STEP 3: TEAM MEMBER ACCESSES DOCUMENT
Request:
  GET /projects/proj_1/documents/doc_1
  Headers: X-User-ID: analyst_1

Check Permissions:
  @require_document_access('read')
  ├─ PermissionService.can_access_document(
  │    'analyst_1', 'doc_1')
  ├─ Query DocumentAccess for doc_1
  │  └─ access_level = 'GROUP'
  │  └─ shared_with.groups = ['data_team']
  ├─ Is analyst_1 in data_team?
  │  ├─ Query UserGroup: find group info
  │  ├─ Check members array
  │  └─ analyst_1 found in members
  └─ ✓ Access granted

Fetch Document:
  SELECT * FROM documents WHERE id = 'doc_1'

Response: 200 OK
  {
    id: 'doc_1',
    name: 'dataset.csv',
    file: <binary>,
    permissions: {
      can_read: true,
      can_write: true,  // from default_permissions
      can_share: false  // analyst_1 is not owner
    }
  }
```

---

## 🎯 Typical Admin Workflow

```
MONDAY: Setup Team & Roles

9:00 AM - Admin creates roles for new project
  ├─ POST /admin/roles → Create "Data Engineer" role
  ├─ POST /admin/roles → Create "Data Scientist" role
  └─ POST /admin/roles → Create "Project Manager" role

9:30 AM - Admin assigns users to project
  ├─ POST /admin/users/john_dev/roles → Data Engineer
  ├─ POST /admin/users/jane_ds/roles → Data Scientist
  └─ POST /admin/users/bob_pm/roles → Project Manager

10:00 AM - Users access project
  ├─ john_dev (engineer): Creates data_pipeline.py code
  ├─ jane_ds (scientist): Uploads train_data.csv
  └─ bob_pm (manager): Views project progress

TUESDAY: Onboard Contractor (2-week assignment)

9:00 AM - Admin adds temporary access
  └─ POST /admin/users/contractor_sam/roles
     {role: "Data Engineer", scope: "project", expires_in: 14}

10:00 AM - Contractor accesses project
  └─ GET /projects/proj_123/documents
     ✓ Can see john_dev's code (shared with engineers)

THURSDAY: Revoke Access (contractor completed early)

11:00 AM - Admin removes contractor access
  └─ DELETE /admin/users/contractor_sam/roles/role_id
     ✓ Immediate access revocation

3:00 PM - Contractor tries to access (should fail now)
  └─ GET /projects/proj_123/documents
     ✗ 403 Forbidden (role assignment deleted)
```

---

## 📋 Permission Matrix Example

```
                      Viewer  Contributor  Lead  Admin
─────────────────────────────────────────────────────────
DOCUMENTS
  document:read         ✓         ✓         ✓     ✓
  document:write        ✗         ✓         ✓     ✓
  document:share        ✗         ✗         ✓     ✓
  document:export       ✗         ✓         ✓     ✓

CODE
  code:read             ✓         ✓         ✓     ✓
  code:write            ✗         ✓         ✓     ✓
  code:delete           ✗         ✗         ✗     ✓

EXTRACTION
  extraction:read       ✓         ✓         ✓     ✓
  extraction:write      ✗         ✓         ✓     ✓

PROJECTS
  project:read          ✓         ✓         ✓     ✓
  project:write         ✗         ✗         ✓     ✓
  project:share         ✗         ✗         ✓     ✓

TASKS
  task:read             ✓         ✓         ✓     ✓
  task:write            ✗         ✓         ✓     ✓
  task:assign           ✗         ✗         ✓     ✓

ADMIN
  admin:users           ✗         ✗         ✗     ✓
  admin:roles           ✗         ✗         ✗     ✓
  admin:audit           ✗         ✗         ✗     ✓
  admin:settings        ✗         ✗         ✗     ✓
```

---

## 🔍 Testing Scenarios

```
### Test Scenario 1: User Tries to Access Private Document
User: analyst_2
Document: doc_1 (private, owner: researcher_1)
Expected: 403 Forbidden

GET /docs/doc_1
├─ can_access_document('analyst_2', 'doc_1')
├─ owner_id='researcher_1' != 'analyst_2'
├─ access_level='PRIVATE'
└─ Return False → 403 Forbidden ✓

### Test Scenario 2: Group Member Accesses Shared Document
User: analyst_2 (in 'data_team' group)
Document: doc_2 (shared with 'data_team')
Expected: 200 OK with document

GET /docs/doc_2
├─ can_access_document('analyst_2', 'doc_2')
├─ access_level='GROUP'
├─ shared_with.groups=['data_team']
├─ is_user_in_group('analyst_2', 'data_team') = True
└─ Return True → 200 OK ✓

### Test Scenario 3: Expired Permission
User: contractor_1 (role expired)
Document: doc_3 (shared with contractor_1)
Expected: 403 Forbidden (expired role doesn't grant permission)

GET /docs/doc_3
├─ PermissionService.can_access_document('contractor_1', 'doc_3')
├─ Check contractor_1's roles:
│  ├─ Query UserRole where user_id='contractor_1'
│  ├─ Found role with expires_at < now
│  ├─ Filter: exclude expired assignments
│  └─ No valid roles found
├─ No permission granted
└─ Return False → 403 Forbidden ✓

### Test Scenario 4: Role Update Affects Access
1. User has 'viewer' role (can read)
2. Admin updates 'viewer' role to add 'document:write'
3. User immediately can write
   
POST /admin/roles/viewer_role_id
{permissions: ['document:read', 'document:write']}
├─ Update Role table
├─ All users with 'viewer' role
├─ Immediately have 'document:write'
└─ No cache invalidation needed (live queries) ✓
```

---

## 🎓 Key Concepts Summary

| Concept | Purpose | Example |
|---------|---------|---------|
| **Role** | Named set of permissions | "viewer", "contributor", "data_analyst" |
| **Permission** | Specific action on resource | "document:read", "code:write" |
| **UserRole** | Assignment of role to user | User 'john' has 'contributor' role |
| **DocumentAccess** | Access control for single document | Doc is private/shared/public |
| **Scope** | Level of permission grant | Global (everywhere) vs Project vs Document |
| **Access Level** | Who can access document | PRIVATE (owner), GROUP (team), PUBLIC (all) |
| **Shared With** | Specific users/groups/roles | {users: ['user1'], groups: ['team1']} |
| **Expير (Expiry) | Time-limited permission | Role expires after 14 days |

---

## ✨ Design Principles

✅ **Permission Inheritance**: User gets all permissions from all assigned roles  
✅ **Fail Secure**: Default is DENY, must explicitly ALLOW  
✅ **Owner Authority**: Document owner controls sharing  
✅ **Scope Isolation**: Project-level permissions don't affect other projects  
✅ **Audit Trail**: All assignments tracked with created_by, created_at  
✅ **Backward Compatible**: Existing documents default to PRIVATE  
✅ **No Caching Issues**: Live database queries (no permission cache)  
✅ **Simple to Extend**: Add new permissions as strings (resources:actions)  

---

*End of Visual Architecture & Workflows Guide*
