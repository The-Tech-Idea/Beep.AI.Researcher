"""Extraction schema + AI extraction (Elicit-style). Uses config_manager for Beep.AI.Server."""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.models.researcher import ResearchProject
from app.services.extraction_validation import ExtractionValidationService
from app.services import beep_ai_client
from app.services import extraction_service
from app.services.project_grounded_context_service import build_project_grounded_context
from app.services.project_grounded_prompt_service import merge_supporting_sources
from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)

logger = logging.getLogger(__name__)
validator_service = ExtractionValidationService()

extraction_bp = Blueprint("extraction", __name__)


@extraction_bp.route("/<int:project_id>/extraction/schemas", methods=["GET"])
@login_required
def list_schemas(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.list_schemas(project)
    return jsonify(payload), status_code


@extraction_bp.route("/<int:project_id>/extraction/schemas", methods=["POST"])
@login_required
def create_schema(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.create_schema(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


@extraction_bp.route("/<int:project_id>/extract", methods=["POST"])
@login_required
def run_extraction(project_id):
    """Collect table values from one or more project files."""
    project = get_project_or_404(project_id)
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = extraction_service.run_extraction(
        project,
        request.get_json() or {},
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        merge_supporting_sources_fn=merge_supporting_sources,
    )
    return jsonify(payload), status_code


@extraction_bp.route("/<int:project_id>/extractions", methods=["GET"])
@login_required
def list_extractions(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.list_extractions(
        project, request.args.get("schema_id")
    )
    return jsonify(payload), status_code


@extraction_bp.route(
    "/<int:project_id>/extractions/<int:result_id>/validate", methods=["POST"]
)
@login_required
def validate_extraction_result(project_id, result_id):
    """Validate an extraction result using configured plugins.

    POST body:
    {
        'validate_all_fields': bool (default: false),
        'field_names': [str] (specific fields to validate),
    }
    """
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.validate_extraction_result(
        project,
        result_id,
        request.get_json() or {},
        validator_service=validator_service,
    )
    return jsonify(payload), status_code


@extraction_bp.route(
    "/<int:project_id>/schemas/<int:schema_id>/fields", methods=["GET"]
)
@login_required
def list_schema_fields(project_id, schema_id):
    """List all extraction fields for a schema with plugin configuration."""
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.list_schema_fields(project, schema_id)
    return jsonify(payload), status_code


@extraction_bp.route(
    "/<int:project_id>/schemas/<int:schema_id>/fields", methods=["POST"]
)
@login_required
def create_schema_field(project_id, schema_id):
    """Create or update an extraction field with plugin validators/resolvers.

    POST body:
    {
        'field_name': str,
        'field_type': str (string|number|date|list|object),
        'is_required': bool,
        'description': str,
        'extraction_instructions': str,
        'plugin_validators': [
            {
                'plugin_name': str,
                'validator_method': str,
                'fail_on_error': bool,
                'suggest_corrections': bool,
            }
        ],
        'plugin_resolvers': [
            {
                'plugin_name': str,
                'resolver_method': str,
            }
        ],
    }
    """
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.create_schema_field(
        project, schema_id, request.get_json() or {}
    )
    return jsonify(payload), status_code


@extraction_bp.route(
    "/<int:project_id>/extractions/<int:result_id>/field-values", methods=["GET"]
)
@login_required
def get_extracted_field_values(project_id, result_id):
    """Get all field values from an extraction result."""
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.get_extracted_field_values(
        project, result_id
    )
    return jsonify(payload), status_code


@extraction_bp.route(
    "/<int:project_id>/schemas/<int:schema_id>/validators", methods=["GET"]
)
@login_required
def list_schema_validators(project_id, schema_id):
    """List all validators configured for a schema."""
    project = get_project_or_404(project_id)
    payload, status_code = extraction_service.list_schema_validators(
        project,
        schema_id,
        validator_service=validator_service,
    )
    return jsonify(payload), status_code


guard_project_blueprint(extraction_bp)
