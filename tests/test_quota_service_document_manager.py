import pytest

from app.database import db
from app.models.tenant import Tenant, TenantMember
from app.models.researcher import ResearchProject, ResearcherDocument
from app.models.researcher.storage_quota import TenantQuota, UserStorageStats
from app.services.quota_service import QuotaExceededError, quota_service


def _create_tenant_with_quota(user_id: int, *, storage=1000, documents=2, upload=500):
    tenant = Tenant(name="Quota Tenant", slug=f"quota-tenant-{user_id}")
    db.session.add(tenant)
    db.session.flush()
    db.session.add(TenantMember(tenant_id=tenant.id, user_id=user_id, role="member"))
    db.session.add(TenantQuota(
        tenant_id=tenant.id,
        storage_quota_bytes=storage,
        document_quota=documents,
        max_upload_size_bytes=upload,
        used_storage_bytes=100,
        document_count=1,
    ))
    db.session.add(UserStorageStats(
        user_id=user_id,
        used_storage_bytes=100,
        document_count=1,
    ))
    db.session.commit()
    return tenant


def test_effective_quota_resolves_tenant_membership(app_context, test_user):
    tenant = _create_tenant_with_quota(test_user.id)

    quota = quota_service.get_effective_quota(test_user.id)

    assert quota.source == "tenant"
    assert quota.storage_quota_bytes == 1000
    assert quota.document_quota == 2
    assert quota.max_upload_size_bytes == 500
    assert quota.used_storage_bytes == 100


def test_check_quota_uses_explicit_tenant_id_for_upload_limit(app_context, test_user, monkeypatch):
    from app.config_manager import config_manager

    tenant = _create_tenant_with_quota(test_user.id, upload=250)
    original_get = config_manager.get
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: True if key == "quota_enforcement_enabled" else original_get(key, default),
    )

    with pytest.raises(QuotaExceededError) as exc:
        quota_service.check_quota(test_user.id, upload_size_bytes=300, tenant_id=tenant.id)

    assert exc.value.quota_type == "upload_size"
    assert exc.value.limit == 250


def test_record_upload_and_delete_update_tenant_pool(app_context, test_user):
    tenant = _create_tenant_with_quota(test_user.id)

    quota_service.record_upload(test_user.id, 200, tenant_id=tenant.id)
    quota = TenantQuota.query.filter_by(tenant_id=tenant.id).first()
    assert quota.used_storage_bytes == 300
    assert quota.document_count == 2

    quota_service.record_delete(test_user.id, 150, tenant_id=tenant.id)
    quota = TenantQuota.query.filter_by(tenant_id=tenant.id).first()
    assert quota.used_storage_bytes == 150
    assert quota.document_count == 1


def test_recalculate_user_and_tenant_from_document_records(app_context, test_user):
    tenant = _create_tenant_with_quota(test_user.id)
    project = ResearchProject(
        name="Quota Recalc Project",
        owner_id=test_user.id,
        tenant_id=tenant.id,
        status="active",
    )
    db.session.add(project)
    db.session.flush()
    db.session.add(ResearcherDocument(
        project_id=project.id,
        filename="a.txt",
        file_path="a.txt",
        file_size=111,
        status="ready",
    ))
    db.session.add(ResearcherDocument(
        project_id=project.id,
        filename="b.txt",
        file_path="b.txt",
        file_size=222,
        status="ready",
    ))
    db.session.commit()

    user_stats = quota_service.recalculate_user(test_user.id)
    tenant_quota = quota_service.recalculate_tenant(tenant.id)

    assert user_stats.used_storage_bytes == 333
    assert user_stats.document_count == 2
    assert tenant_quota.used_storage_bytes == 333
    assert tenant_quota.document_count == 2
