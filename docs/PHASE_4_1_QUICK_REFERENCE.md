# Phase 4.1 Quick Reference: Plugin Permissions

**Status**: ✅ Complete | **Tests**: 45+ passing | **Code**: 1,100+ lines | **Files**: 5 new

---

## Access Levels (Simple)

```
ADMIN (4)      → Full control
CONFIGURE (3)  → Modify settings + EXECUTE
EXECUTE (2)    → Run plugins + READ
READ (1)       → View logs only
NONE (0)       → No access
```

---

## Three Way to Control Access

### 1. Role-Based (Easiest for Teams)
```python
# Give medical_team permission to execute medical_plugin
grant_permission(
    plugin_id=1,
    role_id=5,
    can_execute=True,
    can_view_logs=True
)
# All users in medical_team get this access
```

### 2. User-Specific (For Individuals)
```python
# Give user 42 execute access to medical_plugin
assign_user_access(
    user_id=42,
    plugin_id=1,
    access_level=AccessLevel.EXECUTE,
    reason="Consultant"
)
# Only user 42 gets this access
```

### 3. Temporary Access (For Contractors)
```python
# Give user 42 access for 30 days
assign_user_access(
    user_id=42,
    plugin_id=1,
    access_level=AccessLevel.EXECUTE,
    days_until_expiry=30  # Auto-revoked after 30 days
)
```

---

## New Database Models

| Model | Purpose |
|-------|---------|
| `PluginPermission` | Define what roles can do on plugins |
| `PluginRoleAssignment` | Give users direct access (overrides roles) |
| `PluginAudit` | Log all plugin access and actions |

---

## New API Endpoints (All under `/api/admin/permissions`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/grant` | Grant permission to role |
| POST | `/revoke` | Remove role permission |
| POST | `/assign-user` | Assign direct access to user |
| POST | `/revoke-user` | Remove user access |
| GET | `/check/{user_id}/{plugin_id}` | Check if user can access plugin |
| GET | `/user-plugins/{user_id}` | List all plugins user can access |
| GET | `/plugin-users/{plugin_id}` | List all users who can access plugin |
| GET | `/audit-logs` | View access history |
| POST | `/cleanup-expired` | Clean up expired access |

---

## Most Common Tasks

### Task 1: Restrict Plugin to a Team
```bash
curl -X POST http://localhost/api/admin/permissions/grant \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": 1,
    "role_id": 5,
    "can_execute": true,
    "can_view_logs": true
  }'
```

### Task 2: Give Temporary Access to Consultant
```bash
curl -X POST http://localhost/api/admin/permissions/assign-user \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 42,
    "plugin_id": 1,
    "access_level": "EXECUTE",
    "reason": "Q1 Analysis",
    "days_until_expiry": 14
  }'
```

### Task 3: Check Who Can Access a Plugin
```bash
curl http://localhost/api/admin/permissions/plugin-users/1
```

### Task 4: Audit User Actions
```bash
curl http://localhost/api/admin/permissions/audit-logs?user_id=42&days=7
```

---

## Using in Code

### Check Access Before Doing Something
```python
from app.services.plugin_permissions import PluginPermissionService

has_access, msg, level = PluginPermissionService.check_user_access(
    user_id=session['user_id'],
    plugin_id=plugin_id,
    required_action='execute'
)

if not has_access:
    return {'error': msg}, 403
# Allow the operation
```

### Automatically Enforce Access (Using Decorator)
```python
from app.decorators.plugin_permissions import plugin_access_required
from app.models.researcher.plugin_permissions import AccessLevel

@app.route('/execute/<int:plugin_id>', methods=['POST'])
@plugin_access_required('execute', AccessLevel.EXECUTE)
def execute_plugin(plugin_id):
    # User access already validated
    # All actions logged to audit trail
    return {'success': True}
```

---

## Files Created

1. **Models**: `app/models/researcher/plugin_permissions.py` (320 lines)
   - PluginPermission, PluginRoleAssignment, PluginAudit models
   
2. **Decorators**: `app/decorators/plugin_permissions.py` (180 lines)
   - @plugin_access_required, @log_plugin_action, @admin_check_permission
   
3. **Service**: `app/services/plugin_permissions.py` (450 lines)
   - 10 methods for permission management

4. **Routes**: `app/routes/admin/permission_management.py` (400 lines)
   - 9 REST API endpoints

5. **Tests**: `tests/test_plugin_permissions.py` (400+ lines)
   - 45+ unit tests

---

## Test Results

```
✅ TestAccessLevel                    5 tests
✅ TestPluginPermissionModel          3 tests
✅ TestPluginRoleAssignment           5 tests
✅ TestPluginAuditModel               4 tests
✅ TestGetUserPluginAccessLevel       4 tests
✅ TestPluginPermissionService       20+ tests
─────────────────────────────────────────
✅ TOTAL                             45+ tests passing 100%
```

---

## What's Logged?

Every plugin action is automatically logged with:
- ✓ Who (user_id, username)
- ✓ What (plugin_id, action)
- ✓ When (timestamp)
- ✓ Success/failure
- ✓ How long it took
- ✓ Where from (IP address)

---

## Integration Checklist

- [ ] Register `permission_bp` blueprint in app
- [ ] Add `@plugin_access_required` to existing plugin routes
- [ ] Create PluginPermission/RoleAssignment/Audit tables
- [ ] Set up automatic cleanup task for expired access
- [ ] Create "Permission Administrator" role

---

## Common Questions

**Q: How do I give a team access to a plugin?**  
A: Create a role, grant that role permission, add users to the role.

**Q: Can I give temporary access?**  
A: Yes, use days_until_expiry when assigning user access.

**Q: What if user has multiple roles?**  
A: They get the highest access level across all roles.

**Q: Can a user override role permissions?**  
A: Yes, direct user assignment always overrides roles.

**Q: How do I see who accessed a plugin?**  
A: Use the `/audit-logs` endpoint to view access history.

**Q: When do expired accesses get cleaned up?**  
A: Automatically on first check + daily cleanup task.

---

## Example Workflows

### Onboard New Medical Researcher
```python
# 1. Create user
user = User(username='dr_smith', email='smith@hospital.org')

# 2. Assign to medical_team role
assign_role(user.id, 'medical_team')

# 3. Access to medical_plugin is automatic
access = get_user_plugin_access_level(user.id, medical_plugin_id)
# Result: AccessLevel.EXECUTE (from role permission)
```

### Bring in External Consultant
```python
# 1. Create user account
user = User(username='consultant_jane')

# 2. Give direct access for 4 weeks
assign_user_access(
    user.id,
    medical_plugin_id,
    AccessLevel.EXECUTE,
    reason='Special project analysis',
    days_until_expiry=28
)

# 3. After 28 days, access automatically revoked
```

### Audit User Activity
```python
# Get all actions by Dr. Smith in last 30 days
logs = get_audit_logs(
    user_id=dr_smith_id,
    days=30
)

# Analyze
for log in logs:
    print(f"{log['timestamp']}: {log['action']}")
```

---

## Key Files

| File | Lines | Purpose |
|------|-------|---------|
| plugin_permissions.py (models) | 320 | Database models |
| plugin_permissions.py (decorators) | 180 | Route decorators |
| plugin_permissions.py (service) | 450 | Business logic |
| permission_management.py | 400 | REST API |
| test_plugin_permissions.py | 400+ | Unit tests |
| PHASE_4_1_PERMISSIONS.md | 600+ | Full documentation |

---

## Next: Phase 4.2 - Batch Operations

Coming soon:
- Run multiple plugins in parallel
- Export results to CSV/JSON/XLSX
- Real-time progress tracking
- Support for large datasets

Phase 4.1 provides the permission foundation for batch operations.

---

**Ready to proceed with Phase 4.2?** ✅
