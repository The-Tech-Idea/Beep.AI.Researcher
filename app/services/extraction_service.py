from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.database import db
from app.models.researcher import ExtractionResult, ExtractionSchema, ResearcherDocument
from app.models.researcher.extraction_plugins import ExtractedFieldValue, ExtractionField

logger = logging.getLogger(__name__)


def list_schemas(project):
    schemas = ExtractionSchema.query.filter_by(project_id=project.id).all()
    return {
        "schemas": [
            {
                "id": schema.id,
                "name": schema.name,
                "schema_json": schema.schema_json,
                "created_at": schema.created_at.isoformat() if schema.created_at else None,
            }
            for schema in schemas
        ]
    }, 200


def create_schema(project, data: dict[str, Any]):
    name = (data.get("name") or "").strip()
    schema_json = data.get("schema_json") or data.get("fields", [])

    if not name:
        return {"error": "Enter a name for this table."}, 400

    if isinstance(schema_json, list):
        schema_json = json.dumps(schema_json)

    schema = ExtractionSchema(project_id=project.id, name=name, schema_json=schema_json)
    db.session.add(schema)
    db.session.commit()
    return {"id": schema.id, "name": schema.name}, 201


def _load_schema_fields(schema):
    try:
        raw_fields = json.loads(schema.schema_json) if isinstance(schema.schema_json, str) else schema.schema_json
        if not isinstance(raw_fields, list):
            raw_fields = []
    except (json.JSONDecodeError, TypeError):
        raw_fields = []

    schema_fields = []
    for field in raw_fields:
        if isinstance(field, dict) and (field.get("name") or field.get("field") or field.get("field_name")):
            schema_fields.append(
                {
                    "name": field.get("name") or field.get("field") or field.get("field_name"),
                    "description": field.get("description") or "",
                    "field_type": field.get("type") or field.get("field_type") or "string",
                    "required": bool(field.get("required", False)),
                }
            )
    return schema_fields


def run_extraction(
    project,
    data: dict[str, Any],
    *,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    merge_supporting_sources_fn,
):
    schema_id = data.get("schema_id")
    document_id = data.get("document_id")
    document_ids = data.get("document_ids") or []
    force = bool(data.get("force", False))

    if not schema_id:
        return {"error": "Choose a saved table before starting."}, 400

    schema = ExtractionSchema.query.filter_by(project_id=project.id, id=schema_id).first_or_404()
    schema_fields = _load_schema_fields(schema)
    if not schema_fields:
        return {"error": "This table has no columns yet. Add at least one column before starting."}, 400

    if document_id:
        documents = ResearcherDocument.query.filter_by(project_id=project.id, id=document_id).all()
        if not documents:
            return {"error": "The selected file could not be found in this project."}, 404
    elif document_ids:
        documents = ResearcherDocument.query.filter(
            ResearcherDocument.project_id == project.id,
            ResearcherDocument.id.in_(document_ids),
        ).all()
        if not documents:
            return {"error": "The selected files could not be found in this project."}, 404
    else:
        documents = ResearcherDocument.query.filter_by(project_id=project.id).filter(
            ResearcherDocument.text_content.isnot(None)
        ).all()

    if not documents:
        return {"error": "There are no readable project files available yet."}, 400

    if not beep_ai_client_module.is_configured():
        return {
            "status": "unconfigured",
            "message": "The assistant connection is not ready yet. Ask an administrator to finish setup, then try again.",
            "schema_id": schema.id,
            "schema_name": schema.name,
            "fields": [field["name"] for field in schema_fields],
            "results": [],
        }, 200

    results_out = []
    errors_out = []

    for document in documents:
        if not document.text_content:
            continue

        if not force:
            existing = ExtractionResult.query.filter_by(schema_id=schema.id, document_id=document.id).first()
            if existing:
                try:
                    results_out.append(
                        {
                            "document_id": document.id,
                            "filename": document.filename,
                            "extraction_id": existing.id,
                            "extracted": json.loads(existing.data_json) if existing.data_json else {},
                            "from_cache": True,
                            "supporting_sources": [],
                        }
                    )
                except Exception:
                    pass
                continue

        grounded_context = build_project_grounded_context_fn(
            project,
            document.text_content[:1200],
            max_results=4,
            max_chars_per_result=260,
        )
        ok, ai_result = beep_ai_client_module.extract_structured(
            project=project,
            document_text=document.text_content[:8000],
            schema_fields=schema_fields,
            schema_name=schema.name,
            document_id=str(document.id),
            supporting_context=grounded_context.get("context_text") or None,
        )

        if not ok:
            errors_out.append({"document_id": document.id, "filename": document.filename, "error": str(ai_result)})
            extracted = {}
        else:
            extracted = ai_result.get("extracted_fields") or ai_result.get("fields") or ai_result or {}

        try:
            result_row = ExtractionResult(
                schema_id=schema.id,
                document_id=document.id,
                data_json=json.dumps(extracted, default=str),
            )
            db.session.add(result_row)
            db.session.commit()
            results_out.append(
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "extraction_id": result_row.id,
                    "extracted": extracted,
                    "confidence": ai_result.get("confidence") if ok else None,
                    "from_cache": False,
                    "supporting_sources": merge_supporting_sources_fn([], grounded_context),
                }
            )
        except Exception as exc:
            db.session.rollback()
            errors_out.append({"document_id": document.id, "filename": document.filename, "error": str(exc)})

    return {
        "status": "completed" if not errors_out else ("partial" if results_out else "failed"),
        "message": (
            "Data collection is complete."
            if not errors_out
            else (
                "Data collection finished, but some files could not be read."
                if results_out
                else "Data collection could not be completed for the selected files."
            )
        ),
        "schema_id": schema.id,
        "schema_name": schema.name,
        "results": results_out,
        "errors": errors_out,
        "total_processed": len(results_out),
        "total_errors": len(errors_out),
    }, 200


def list_extractions(project, schema_id=None):
    if schema_id:
        schema = ExtractionSchema.query.filter_by(project_id=project.id, id=schema_id).first_or_404()
        results = ExtractionResult.query.filter_by(schema_id=schema.id).all()
    else:
        results = ExtractionResult.query.join(ExtractionSchema).filter(ExtractionSchema.project_id == project.id).all()

    return {
        "results": [
            {
                "id": result.id,
                "schema_id": result.schema_id,
                "document_id": result.document_id,
                "data_json": result.data_json,
            }
            for result in results
        ]
    }, 200


def validate_extraction_result(project, result_id, data: dict[str, Any], *, validator_service):
    result = db.session.get(ExtractionResult, result_id)
    if result is None:
        return {"error": "Extraction result not found in project"}, 404

    schema = db.session.get(ExtractionSchema, result.schema_id)
    if not schema or schema.project_id != project.id:
        return {"error": "Extraction result not found in project"}, 404

    validate_all = data.get("validate_all_fields", False)
    field_names = data.get("field_names", []) or []

    if validate_all:
        fields = ExtractionField.query.filter_by(schema_id=schema.id).all()
    elif field_names:
        fields = ExtractionField.query.filter(
            ExtractionField.schema_id == schema.id,
            ExtractionField.field_name.in_(field_names),
        ).all()
    else:
        return {"error": "Specify validate_all_fields or field_names"}, 400

    if not fields:
        return {"error": "No fields found to validate"}, 404

    validation_results = []
    try:
        result_data = json.loads(result.data_json) if result.data_json else {}
        for field in fields:
            field_value_str = result_data.get(field.field_name, "")
            field_value = ExtractedFieldValue.query.filter_by(result_id=result_id, field_id=field.id).first()
            if field_value is None:
                field_value = ExtractedFieldValue(
                    result_id=result_id,
                    field_id=field.id,
                    raw_value=field_value_str,
                    extracted_value=field_value_str,
                    confidence_score=0.95,
                    validation_status="pending",
                )
                db.session.add(field_value)
                db.session.commit()

            context = {"project_id": project.id, "schema_id": schema.id, "result_id": result_id}
            validation_result = asyncio.run(
                validator_service.validate_extracted_value(field_value, field, context)
            )
            validation_results.append(
                {
                    "field_name": field.field_name,
                    "field_id": field.id,
                    "is_valid": validation_result["is_valid"],
                    "validation_status": validation_result["validation_status"],
                    "errors": validation_result["errors"],
                    "suggestions": validation_result["suggestions"],
                    "corrections": validation_result["corrections"],
                    "final_value": validation_result["final_value"],
                    "confidence": validation_result["confidence"],
                    "plugin_results": validation_result["plugin_results"],
                }
            )
    except Exception as exc:
        logger.error("Error validating extraction result: %s", exc)
        return {"error": f"Validation failed: {str(exc)}"}, 500

    return {
        "extraction_id": result_id,
        "validation_results": validation_results,
        "all_valid": all(result["is_valid"] for result in validation_results),
    }, 200


def list_schema_fields(project, schema_id):
    schema = ExtractionSchema.query.filter_by(project_id=project.id, id=schema_id).first_or_404()
    fields = ExtractionField.query.filter_by(schema_id=schema.id).all()
    return {
        "fields": [
            {
                "id": field.id,
                "field_name": field.field_name,
                "field_type": field.field_type,
                "is_required": field.is_required,
                "description": field.description,
                "extraction_instructions": field.extraction_instructions,
                "plugin_validators": field.get_plugin_validators(),
                "plugin_resolvers": field.get_plugin_resolvers(),
            }
            for field in fields
        ]
    }, 200


def create_schema_field(project, schema_id, data: dict[str, Any]):
    schema = ExtractionSchema.query.filter_by(project_id=project.id, id=schema_id).first_or_404()
    field_name = (data.get("field_name") or "").strip()
    field_type = data.get("field_type", "string")

    if not field_name:
        return {"error": "field_name required"}, 400
    if field_type not in ["string", "number", "date", "list", "object"]:
        return {"error": "Invalid field_type"}, 400

    field = ExtractionField.query.filter_by(schema_id=schema.id, field_name=field_name).first()
    is_new = field is None
    if field is None:
        field = ExtractionField(schema_id=schema.id, field_name=field_name)

    field.field_type = field_type
    field.is_required = data.get("is_required", False)
    field.description = data.get("description", "")
    field.extraction_instructions = data.get("extraction_instructions", "")
    validators = data.get("plugin_validators", [])
    field.plugin_validators_json = json.dumps(validators) if validators else None
    resolvers = data.get("plugin_resolvers", [])
    field.plugin_resolvers_json = json.dumps(resolvers) if resolvers else None

    db.session.add(field)
    db.session.commit()

    return {
        "id": field.id,
        "field_name": field.field_name,
        "status": "created" if is_new else "updated",
    }, 201 if is_new else 200


def get_extracted_field_values(project, result_id):
    result = db.session.get(ExtractionResult, result_id)
    if result is None:
        return {"error": "Extraction result not found in project"}, 404

    schema = db.session.get(ExtractionSchema, result.schema_id)
    if not schema or schema.project_id != project.id:
        return {"error": "Extraction result not found in project"}, 404

    field_values = ExtractedFieldValue.query.filter_by(result_id=result_id).all()
    return {
        "field_values": [
            {
                "id": field_value.id,
                "field_id": field_value.field_id,
                "field_name": field_value.field.field_name if field_value.field else "unknown",
                "raw_value": field_value.raw_value,
                "extracted_value": field_value.extracted_value,
                "confidence_score": field_value.confidence_score,
                "validation_status": field_value.validation_status,
                "validation_errors": field_value.get_validation_errors(),
                "corrections": field_value.get_corrections(),
                "suggestions": field_value.get_suggestions(),
            }
            for field_value in field_values
        ]
    }, 200


def list_schema_validators(project, schema_id, *, validator_service):
    schema = ExtractionSchema.query.filter_by(project_id=project.id, id=schema_id).first_or_404()
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    try:
        validation_status = event_loop.run_until_complete(
            validator_service.validate_schema(schema.id, {"project_id": project.id})
        )
    finally:
        event_loop.close()

    return validation_status.get("validation_status", {}), 200
