"""Admin settings, localization, and governance routes."""

from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required

from app.config_manager import config_manager
from app.config import get_config
from app.database import db
from app.routes.admin_routes import admin_bp, admin_required


@admin_bp.route("/settings")
@login_required
@admin_required
def settings():
    """Settings overview and management."""
    schema = config_manager.get_schema()
    values = {}
    for key in schema:
        v = config_manager.get(key)
        if v is not None and v != "":
            values[key] = v
    runtime_config = get_config()

    persisted_features = config_manager.get("features") or {}
    if not isinstance(persisted_features, dict):
        persisted_features = {}

    persisted_queue = config_manager.get("queue") or {}
    if not isinstance(persisted_queue, dict):
        persisted_queue = {}

    persisted_cache = config_manager.get("cache") or {}
    if not isinstance(persisted_cache, dict):
        persisted_cache = {}

    feature_flags = runtime_config.get_all_features()
    for name, enabled in persisted_features.items():
        if name in feature_flags and isinstance(enabled, bool):
            if isinstance(feature_flags[name], dict):
                feature_flags[name]["enabled"] = enabled
            else:
                feature_flags[name] = {"enabled": enabled}
    enriched_features = {}
    for name, config in feature_flags.items():
        enabled = (
            config.get("enabled", False) if isinstance(config, dict) else bool(config)
        )
        enriched_features[name] = {
            "enabled": enabled,
            "description": config.get("description", "")
            if isinstance(config, dict)
            else "",
            "level": config.get("level", "optional")
            if isinstance(config, dict)
            else "optional",
        }
    queue_config = runtime_config.get_queue_config()
    cache_config = runtime_config.get_cache_config()
    return render_template(
        "admin/settings.html",
        schema=schema,
        values=values,
        feature_flags=enriched_features,
        queue_config=queue_config,
        cache_config=cache_config,
    )


@admin_bp.route("/localization")
@login_required
@admin_required
def localization():
    """Localization settings."""
    from app.services.localization_manager import LocalizationManager

    localization_manager = LocalizationManager()
    supported_locales = localization_manager.get_supported_locales() or ["en"]
    translations = localization_manager.get_all_translations()

    keys = set()
    for locale_translations in translations.values():
        keys.update(locale_translations.keys())
    keys = sorted(keys)

    locale_names = {
        loc: localization_manager.get_locale_label(loc) for loc in supported_locales
    }

    return render_template(
        "admin/localization.html",
        supported_locales=supported_locales,
        translations=translations,
        keys=keys,
        locale_names=locale_names,
    )


@admin_bp.route("/localization/update", methods=["POST"])
@login_required
@admin_required
def localization_update():
    """Update localization settings."""
    from app.services.localization_manager import LocalizationManager

    key = request.form.get("key", "").strip()
    locale = request.form.get("locale", "").strip()
    value = request.form.get("value", "").strip()

    if not key or not locale or not value:
        flash("All fields are required.", "danger")
        return redirect(url_for("admin.localization"))

    try:
        localization_manager = LocalizationManager()
        localization_manager.update_translation(locale, {key: value})
        flash(f"Translation updated: {key} ({locale})", "success")
    except Exception as e:
        flash(f"Error updating translation: {e}", "danger")

    return redirect(url_for("admin.localization"))


@admin_bp.route("/localization/upload", methods=["POST"])
@login_required
@admin_required
def localization_upload():
    """Upload localization file."""
    from io import StringIO
    from app.services.localization_manager import LocalizationManager

    csv_file = request.files.get("csv_file")
    if not csv_file or not csv_file.filename:
        flash("No file selected.", "danger")
        return redirect(url_for("admin.localization"))

    try:
        content = csv_file.read().decode("utf-8")
        stream = StringIO(content)
        localization_manager = LocalizationManager()
        imported, skipped = localization_manager.import_from_csv(stream)
        flash(f"Imported {imported} translations, skipped {skipped}.", "success")
    except Exception as e:
        flash(f"Error importing CSV: {e}", "danger")

    return redirect(url_for("admin.localization"))


@admin_bp.route("/governance")
@login_required
@admin_required
def governance():
    """Governance and compliance — retention policies, audit logs, export history."""
    from app.models.researcher import ResearchProject
    from app.models.core import AuditLog, User

    retention_policies = config_manager.get("retention.policies") or {}
    retention_entries = []
    for project_id_str, policy in retention_policies.items():
        try:
            project = db.session.get(ResearchProject, int(project_id_str))
            if project:
                retention_entries.append(
                    {
                        "project_id": project.id,
                        "project_name": project.name,
                        "retention_days": policy.get("retention_days"),
                    }
                )
        except (ValueError, TypeError):
            pass

    audit_rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    audit_entries = []
    for row in audit_rows:
        user = db.session.get(User, row.user_id) if row.user_id else None
        audit_entries.append(
            {
                "timestamp": row.created_at.isoformat() if row.created_at else None,
                "user": user.username if user else None,
                "action": row.action,
                "resource": row.resource,
                "resource_id": row.resource_id,
            }
        )

    export_entries = []
    for row in audit_rows:
        action = (row.action or "").lower()
        if "export" not in action:
            continue
        user = db.session.get(User, row.user_id) if row.user_id else None
        project = (
            db.session.get(ResearchProject, row.project_id) if row.project_id else None
        )
        export_entries.append(
            {
                "timestamp": row.created_at.isoformat() if row.created_at else None,
                "project": project.name if project else "Unknown project",
                "project_id": project.id if project else None,
                "user": user.username if user else None,
                "action": row.action,
            }
        )

    return render_template(
        "admin/governance.html",
        retention_entries=retention_entries,
        audit_entries=audit_entries,
        export_entries=export_entries,
        total_audit=len(audit_entries),
    )


@admin_bp.route("/settings/update", methods=["POST"])
@login_required
@admin_required
def settings_update():
    """Update config settings."""
    schema = config_manager.get_schema()
    data = request.form.to_dict()
    runtime_config = get_config()

    BOOL_CHECKBOX_KEYS = [
        "quota_enforcement_enabled",
        "sso_enabled",
        "registration_require_email_verification",
        "registration_captcha_enabled",
        "login_captcha_enabled",
        "password_require_uppercase",
        "password_require_lowercase",
        "password_require_number",
        "password_require_special",
        "mfa_enabled",
        "mfa_totp_enabled",
        "mfa_email_otp_enabled",
        "mfa_sms_otp_enabled",
    ]
    for key in BOOL_CHECKBOX_KEYS:
        config_manager.set(key, key in data)

    skip_keys = set(BOOL_CHECKBOX_KEYS)

    alias_map = {
        "storage_smb_server": "storage_smb_host",
        "storage_s3_bucket": "storage_s3_bucket_name",
        "storage_azure_container": "storage_azure_container_name",
        "ldap_base_dn": "ldap_user_search_base",
        "ldap_use_ssl": "ldap_tls_enabled",
        "saml2_idp_metadata_url": "saml_idp_metadata_url",
        "saml2_sp_entity_id": "saml_sp_entity_id",
        "saml2_sp_acs_url": "saml_sp_acs_url",
        "mail_ms365_tenant_id": "mail_oauth2_tenant_id",
        "mail_ms365_client_id": "mail_oauth2_client_id",
        "mail_ms365_client_secret": "mail_oauth2_client_secret",
        "mail_google_client_id": "mail_oauth2_client_id",
        "mail_google_client_secret": "mail_oauth2_client_secret",
        "mail_google_refresh_token": "mail_oauth2_refresh_token",
        "quota_default_storage_bytes": "default_storage_quota_bytes",
        "quota_default_document_count": "default_document_quota",
        "quota_default_max_upload_bytes": "default_max_upload_size_bytes",
    }

    fields_processed = set()
    for key in schema:
        if key in skip_keys:
            continue
        actual_key = key
        form_key = key

        if form_key not in data:
            for fk, ak in alias_map.items():
                if ak == key and fk in data:
                    form_key = fk
                    break

        if form_key not in data:
            continue

        val = data[form_key].strip()
        fields_processed.add(form_key)

        typ = schema[key].get("type", str)
        if typ == int:
            if not val:
                continue
            try:
                val = int(val)
            except ValueError:
                continue
            if key == "server_port" and not (1 <= val <= 65535):
                flash(f"Server port must be between 1 and 65535.", "danger")
                continue
        elif typ == bool:
            val = val.lower() in ("true", "1", "yes", "on")
        else:
            config_manager.set(key, val)
            continue

        config_manager.set(key, val)

    for form_key, actual_key in alias_map.items():
        if form_key in data and form_key not in fields_processed:
            val = data[form_key].strip()
            if val:
                typ = schema.get(actual_key, {}).get("type", str)
                if typ == int:
                    try:
                        val = int(val)
                    except ValueError:
                        continue
                elif typ == bool:
                    val = val.lower() in ("true", "1", "yes", "on")
                config_manager.set(actual_key, val)

    feature_overrides = {}
    for feature_name in runtime_config.get_all_features().keys():
        field_name = f"feature_{feature_name}"
        enabled = field_name in request.form
        runtime_config.set_feature_enabled(feature_name, enabled)
        feature_overrides[feature_name] = enabled
    config_manager.set("features", feature_overrides)

    queue_overrides = {}
    for key in ("max_workers", "max_retries", "job_timeout_seconds"):
        raw = data.get(f"queue_{key}")
        if raw and str(raw).isdigit():
            queue_overrides[key] = int(raw)
    if queue_overrides:
        runtime_config.set_queue_values(queue_overrides)
        config_manager.set("queue", queue_overrides)

    cache_overrides = {}
    cache_field_map = {
        "cache_ttl_seconds": "cache_ttl_seconds",
        "max_cache_entries": "cache_max_entries",
        "max_cache_size_mb": "cache_max_size_mb",
    }
    for config_key, field_name in cache_field_map.items():
        raw = data.get(field_name)
        if raw and str(raw).isdigit():
            cache_overrides[config_key] = int(raw)
    if cache_overrides:
        runtime_config.set_cache_values(cache_overrides)
        config_manager.set("cache", cache_overrides)

    config_manager.save()
    flash("Settings updated successfully.", "success")
    return redirect(url_for("admin.settings"))
