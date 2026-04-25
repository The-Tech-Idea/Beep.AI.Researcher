# Role & Permission Management - Quick Start Guide

**Created**: February 7, 2026  
**Purpose**: Quick reference for implementing and using the role/permission system

---

## 🎯 What You Can Do

1. **Admin creates custom roles** - Define roles with specific permissions
2. **Assign roles to users** - Grant users access levels (viewer, contributor, lead, admin)
3. **Control document visibility** - Private, group, or public sharing
4. **Group-based sharing** - Share documents with entire teams
5. **Temporary access** - Grant time-limited roles (e.g., 1 week contractor access)

---

## 📋 Use Cases

### Use Case 1: Create a "Data Analyst" Role
```bash
POST /admin/roles
{
  "name": "data_analyst",
  "description": "Can analyze documents and export data",
  "permissions": [
    "document:read",
    "document:export",
    "extraction:read",
    "code:read"
  ]
}
```

**Result**: New role created. Can now assign to users.

---

### Use Case 2: Assign Role to User
```bash
POST /admin/users/user_123/roles
{
  "role_id": "role_uuid_from_above",
  "scope": "global"
}
```

**Result**: User now has "data_analyst" permissions everywhere.

---

### Use Case 3: Assign Project-Level Role
```bash
POST /admin/users/user_456/roles
{
  "role_id": "role_uuid_contributor",
  "scope": "project",
  "scope_id": "project_789"
}
```

**Result**: User is "contributor" only in project_789, not globally.

---

### Use Case 4: Grant Temporary Access (1 Week)
```bash
POST /admin/users/user_contractor/roles
{
  "role_id": "role_uuid_contributor",
  "scope": "project",
  "scope_id": "project_abc",
  "expires_in_days": 7
}
```

**Result**: User has access for 7 days, then automatically revoked.

---

### Use Case 5: Share Document with Group
```bash
POST /projects/proj_1/documents/doc_1/access/share-group
{
  "group_id": "research_team",
  "permissions": ["read"]
}
```

**Result**: All members of "research_team" can read doc_1.

---

### Use Case 6: Share Document with Specific User
```bash
POST /projects/proj_1/documents/doc_1/access/share-user
{
  "user_id": "user_456",
  "permissions": ["read", "write"]
}
```

**Result**: User can read and write the document.

---

### Use Case 7: Make Document Public
```bash
POST /projects/proj_1/documents/doc_1/access/make-public
```

**Result**: Everyone in tenant can read document.

---

### Use Case 8: Make Document Private (Owner Only)
```bash
POST /projects/proj_1/documents/doc_1/access/make-private
```

**Result**: Only owner can access document. All shares revoked.

---

## 🔐 Built-in Roles

### Viewer
- **Permissions**: read-only
- **Can**: View documents, codes, extractions, chat
- **Cannot**: Upload, modify, share

```json
{
  "name": "viewer",
  "permissions": [
    "document:read",
    "code:read",
    "extraction:read",
    "chat:read",
    "task:read"
  ]
}
```

### Contributor
- **Permissions**: read + write
- **Can**: Upload documents, create codes, extract, chat, create tasks
- **Cannot**: Delete others' documents, share, manage users

```json
{
  "name": "contributor",
  "permissions": [
    "document:read",
    "document:write",
    "document:export",
    "code:read",
    "code:write",
    "extraction:read",
    "extraction:write",
    "chat:read",
    "chat:write",
    "task:read",
    "task:write"
  ]
}
```

### Lead
- **Permissions**: manage project + team
- **Can**: Everything contributor can + share documents, assign tasks, manage team
- **Cannot**: Manage users globally, manage roles

```json
{
  "name": "lead",
  "permissions": [
    "document:read",
    "document:write",
    "document:share",
    "document:export",
    "project:read",
    "project:write",
    "project:share",
    "code:read",
    "code:write",
    "extraction:read",
    "extraction:write",
    "chat:read",
    "chat:write",
    "task:read",
    "task:write",
    "task:assign"
  ]
}
```

### Admin
- **Permissions**: Full access
- **Can**: Everything (manage roles, users, settings)
- **Cannot**: Nothing

```json
{
  "name": "admin",
  "permissions": ["*:*"]
}
```

---

## 📖 API Reference

### Admin: List All Roles
```bash
GET /admin/roles

Response:
{
  "success": true,
  "roles": [
    {
      "id": "role_1",
      "name": "viewer",
      "description": "Read-only access",
      "permissions": ["document:read", ...],
      "is_builtin": true,
      "created_at": "2026-02-07T10:00:00Z"
    },
    ...
  ]
}
```

### Admin: Create Custom Role
```bash
POST /admin/roles
Body:
{
  "name": "custom_role_name",
  "description": "What this role does",
  "permissions": ["document:read", "document:write", ...]
}

Response: 201 Created
{
  "success": true,
  "role": {
    "id": "role_uuid",
    "name": "custom_role_name",
    "permissions": [...]
  }
}
```

### Admin: Update Role Permissions
```bash
PUT /admin/roles/<role_id>
Body:
{
  "permissions": ["document:read", "code:read"],
  "description": "Updated description"
}

Response:
{
  "success": true,
  "role": {"id": "...", "name": "..."}
}
```

### Admin: Delete Role
```bash
DELETE /admin/roles/<role_id>

Response:
{
  "success": true
}

Errors:
- 403: Cannot delete built-in roles
- 409: Role has users assigned (remove them first)
```

### Admin: Get User's Roles
```bash
GET /admin/users/<user_id>/roles

Response:
{
  "success": true,
  "user_id": "user_123",
  "roles": [
    {
      "role_id": "role_uuid",
      "role_name": "contributor",
      "scope": "global",
      "scope_id": null,
      "expires_at": null,
      "created_at": "2026-02-07T10:00:00Z"
    }
  ]
}
```

### Admin: Assign Role to User
```bash
POST /admin/users/<user_id>/roles
Body:
{
  "role_id": "role_uuid",
  "scope": "global",  // or "project"
  "scope_id": null,   // set to project_id if scope=project
  "expires_in_days": 7  // optional, for temporary access
}

Response: 201 Created
{
  "success": true,
  "message": "Assigned contributor role to user user_123"
}
```

### Admin: Revoke Role from User
```bash
DELETE /admin/users/<user_id>/roles/<role_id>

Response:
{
  "success": true
}
```

### Document: Get Access Settings
```bash
GET /projects/<project_id>/documents/<doc_id>/access

Response:
{
  "success": true,
  "access": {
    "owner_id": "user_123",
    "access_level": "shared",  // private, shared, group, public
    "shared_with": {
      "users": ["user_456", "user_789"],
      "groups": ["team_1"],
      "roles": []
    },
    "default_permissions": ["read"]
  }
}
```

### Document: Update Access
```bash
PUT /projects/<project_id>/documents/<doc_id>/access
Body:
{
  "access_level": "shared",
  "shared_with": {
    "users": ["user_456"],
    "groups": [],
    "roles": []
  },
  "default_permissions": ["read", "write"]
}

Response:
{
  "success": true,
  "message": "Document access updated"
}
```

### Document: Share with User
```bash
POST /projects/<project_id>/documents/<doc_id>/access/share-user
Body:
{
  "user_id": "user_456",
  "permissions": ["read"]  // or ["read", "write"]
}

Response:
{
  "success": true,
  "message": "Shared with user_456"
}
```

### Document: Share with Group
```bash
POST /projects/<project_id>/documents/<doc_id>/access/share-group
Body:
{
  "group_id": "team_1",
  "permissions": ["read"]
}

Response:
{
  "success": true,
  "message": "Shared with group team_1"
}
```

### Document: Make Private
```bash
POST /projects/<project_id>/documents/<doc_id>/access/make-private

Response:
{
  "success": true,
  "message": "Document is now private"
}
```

### Document: Make Public
```bash
POST /projects/<project_id>/documents/<doc_id>/access/make-public

Response:
{
  "success": true,
  "message": "Document is now public"
}
```

---

## 🔧 Code Examples

### Check if User Has Permission

```python
from beep.services.permission_service import PermissionService

# Check global permission
if PermissionService.user_has_permission('user_123', 'document:write', 'global'):
    print("User can write documents globally")

# Check project-level permission
if PermissionService.user_has_permission('user_123', 'document:write', 'project', 'project_1'):
    print("User can write in project_1")
```

### Check Document Access

```python
from beep.services.permission_service import PermissionService

# Can user read this document?
if PermissionService.can_access_document('user_123', 'doc_1'):
    return fetch_document('doc_1')
else:
    return "Access denied", 403

# Can user write to this document?
if PermissionService.can_write_document('user_123', 'doc_1'):
    return update_document('doc_1', data)
else:
    return "Not authorized to modify", 403
```

### Get All Accessible Documents

```python
from beep.services.permission_service import PermissionService

# Get all documents user can access in a project
docs = PermissionService.get_accessible_documents('user_123', 'project_1')
return jsonify({'documents': docs})
```

### Using Decorators

```python
from beep.decorators.permissions import require_permission, require_document_access
from flask import Blueprint

@app.route('/projects/<id>/documents', methods=['GET'])
@require_permission('document:read', scope='project')
def list_documents(id):
    # User is guaranteed to have document:read in this project
    return get_documents_for_project(id)

@app.route('/projects/<id>/documents/<doc_id>', methods=['PUT'])
@require_document_access('write')
def update_document(id, doc_id):
    # User is guaranteed to have write access to this document
    return save_document(doc_id, request.json)
```

---

## 🚀 Implementation Steps (Phase 1.8)

### Week 1: Database & Core Service

1. Create models: Role, UserRole, DocumentAccess, UserGroup
2. Create migrations
3. Create PermissionService
4. Create decorators
5. Seed built-in roles
6. Write unit tests

### Week 2: Admin Routes

1. Create admin role management routes
2. Create admin user role assignment routes
3. Create document access control routes
4. Write API tests
5. Documentation

### Week 3: Integration & Testing

1. Apply decorators to existing routes
2. Write integration tests
3. Manual testing
4. Staging deployment
5. User testing

---

## 📚 Files Reference

- **Models**: See [ROLE_PERMISSION_MANAGEMENT.md](ROLE_PERMISSION_MANAGEMENT.md#1-data-models)
- **PermissionService**: See [ROLE_PERMISSION_MANAGEMENT.md](ROLE_PERMISSION_MANAGEMENT.md#2-permission-checking-service)
- **Admin Routes**: See [ROLE_PERMISSION_MANAGEMENT.md](ROLE_PERMISSION_MANAGEMENT.md#3-admin-routes)
- **Document Routes**: See [ROLE_PERMISSION_MANAGEMENT.md](ROLE_PERMISSION_MANAGEMENT.md#4-document-access-control-routes)
- **Implementation Guide**: [ROLE_PERMISSION_MANAGEMENT.md](ROLE_PERMISSION_MANAGEMENT.md)
- **Todo**: [Todo.md](../Todo.md#18-role--permission-management-system-new)

---

## ❓ FAQ

**Q: Can users create their own roles?**  
A: No, only admins (users with `admin:roles` permission) can create roles.

**Q: What happens when a role expires?**  
A: Role assignment is automatically deleted at midnight on expiry date. User loses all permissions from that role.

**Q: Can I share a document with a role?**  
A: Not directly. You can share with users or groups. If all users in a group have a role, they get that role's permissions.

**Q: What if I delete a role?**  
A: You can only delete custom roles. Built-in roles (viewer, contributor, lead, admin) cannot be deleted. Any users with the deleted role lose those permissions.

**Q: Can document owner change access level anytime?**  
A: Yes. Document owner can change from private → public → shared → project at any time.

**Q: What's the difference between "shared" and "group"?**  
A: **group**: fixed members (team members). **shared**: specific users you choose.

---

## 🎓 Complete Workflow Example

### Step 1: Create a "Medical Researcher" Role
```bash
curl -X POST http://localhost:5000/admin/roles \
  -H "X-User-ID: admin_1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "medical_researcher",
    "description": "Can access medical research documents",
    "permissions": [
      "document:read",
      "document:write",
      "extraction:read",
      "code:read"
    ]
  }'
```

**Response**: `role_id` = `abc123`

### Step 2: Assign Role to User
```bash
curl -X POST http://localhost:5000/admin/users/dr_smith/roles \
  -H "X-User-ID: admin_1" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "abc123",
    "scope": "global"
  }'
```

**Result**: Dr. Smith now has medical researcher permissions everywhere.

### Step 3: Dr. Smith Uploads Document
```bash
curl -X POST http://localhost:5000/projects/proj_1/documents/upload \
  -H "X-User-ID: dr_smith" \
  -F "file=@medical_paper.pdf"
```

**Result**: Document created with `owner_id=dr_smith`, `access_level=private`

### Step 4: Dr. Smith Shares with Team
```bash
curl -X POST http://localhost:5000/projects/proj_1/documents/doc_1/access/share-group \
  -H "X-User-ID: dr_smith" \
  -H "Content-Type: application/json" \
  -d '{
    "group_id": "medical_team",
    "permissions": ["read"]
  }'
```

**Result**: All members of "medical_team" group can read the document.

### Step 5: Grant Intern Temporary Access (2 weeks)
```bash
curl -X POST http://localhost:5000/admin/users/intern_john/roles \
  -H "X-User-ID: admin_1" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "abc123",
    "scope": "project",
    "scope_id": "proj_1",
    "expires_in_days": 14
  }'
```

**Result**: Intern John has medical researcher permissions in proj_1 for 2 weeks, then access is revoked.

### Step 6: Verify Access (from Intern's Perspective)
```bash
# Intern can now:
# - View documents they have access to
# - View extractions
# - Create codes
# - But NOT upload new documents (no document:write)

curl -X GET http://localhost:5000/projects/proj_1/documents/doc_1 \
  -H "X-User-ID: intern_john"
```

**Result**: Document returned (access granted through group membership)

---

## ✅ Checklist for Implementation

- [ ] Read ROLE_PERMISSION_MANAGEMENT.md completely
- [ ] Create database models (Role, UserRole, DocumentAccess, UserGroup)
- [ ] Create migrations script
- [ ] Create PermissionService class
- [ ] Create permission decorators
- [ ] Create admin routes for role management
- [ ] Create admin routes for user role assignment
- [ ] Create document access routes
- [ ] Update existing document routes to use decorators
- [ ] Seed built-in roles at startup
- [ ] Write unit tests (90%+ coverage)
- [ ] Write integration tests
- [ ] Test with Postman/curl
- [ ] Create admin UI (if applicable)
- [ ] Document for team
- [ ] Deploy to staging
- [ ] Deploy to production

---
