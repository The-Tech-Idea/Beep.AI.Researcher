"""Integration tests for extraction validation service with plugins (Phase 3.6)."""
import asyncio
import json
import pytest
from datetime import datetime

from app.database import db
from app.models.researcher import ResearchProject, ExtractionSchema, ExtractionResult
from app.models.researcher.extraction_plugins import (
    ExtractionField, ExtractedFieldValue, ExtractionValidationResult
)
from app.models.researcher.plugins import Plugin, PluginStatus, HookPoint
from app.services.extraction_validation import ExtractionValidationService
from app.services.plugin_manager import get_plugin_manager


@pytest.fixture
def validation_service():
    """Create extraction validation service."""
    return ExtractionValidationService()


@pytest.fixture
def test_project(app_context):
    """Create test project."""
    from app.models.core import User
    # Create a test user first
    user = User(username='test_user', email='test@example.com', password_hash='hash')
    db.session.add(user)
    db.session.flush()
    
    project = ResearchProject(name='Test Project', description='Test', owner_id=user.id)
    db.session.add(project)
    db.session.commit()
    return project


@pytest.fixture
def test_schema(test_project):
    """Create test extraction schema."""
    schema = ExtractionSchema(
        project_id=test_project.id,
        name='Medical Extraction Schema',
        schema_json=json.dumps([
            {'name': 'diagnosis', 'type': 'string'},
            {'name': 'medication', 'type': 'string'},
            {'name': 'dosage', 'type': 'string'},
        ])
    )
    db.session.add(schema)
    db.session.commit()
    return schema


@pytest.fixture
def test_fields(test_schema):
    """Create test extraction fields with plugin validators."""
    fields = []

    # ICD-10 field with medical plugin validator
    field1 = ExtractionField(
        schema_id=test_schema.id,
        field_name='diagnosis',
        field_type='string',
        is_required=True,
        description='Patient diagnosis code (ICD-10)',
        extraction_instructions='Extract ICD-10 diagnosis code',
        plugin_validators_json=json.dumps([
            {
                'plugin_name': 'medical',
                'validator_method': 'check_icd10_validation',
                'fail_on_error': False,
                'suggest_corrections': True,
            }
        ]),
        plugin_resolvers_json=json.dumps([
            {
                'plugin_name': 'medical',
                'resolver_method': 'resolve_icd10',
            }
        ]),
    )
    db.session.add(field1)
    fields.append(field1)

    # Medication field with medical plugin validator
    field2 = ExtractionField(
        schema_id=test_schema.id,
        field_name='medication',
        field_type='string',
        is_required=True,
        description='Medication name',
        extraction_instructions='Extract medication name',
        plugin_validators_json=json.dumps([
            {
                'plugin_name': 'medical',
                'validator_method': 'check_drug_interaction',
                'fail_on_error': False,
                'suggest_corrections': False,
            }
        ]),
    )
    db.session.add(field2)
    fields.append(field2)

    # Dosage field (no validators for testing)
    field3 = ExtractionField(
        schema_id=test_schema.id,
        field_name='dosage',
        field_type='string',
        is_required=False,
        description='Medication dosage',
        extraction_instructions='Extract medication dosage',
    )
    db.session.add(field3)
    fields.append(field3)

    db.session.commit()
    return fields


@pytest.fixture
def test_extraction_result(test_schema):
    """Create test extraction result."""
    result = ExtractionResult(
        schema_id=test_schema.id,
        document_id=1,
        data_json=json.dumps({
            'diagnosis': 'E11',  # Type 2 diabetes - valid ICD-10
            'medication': 'metformin',
            'dosage': '500mg',
        })
    )
    db.session.add(result)
    db.session.commit()
    return result


@pytest.fixture
def test_plugin(app_context):
    """Create test medical plugin."""
    plugin = Plugin(
        name='medical',
        display_name='Medical Plugin',
        version='1.0.0',
        author='Test Author',
        status=PluginStatus.ENABLED.value,
        plugin_type='builtin',
        module_path='test.module',
        class_name='TestPlugin',
        config_schema_json=json.dumps({
            'properties': {'enable_hipaa': {'type': 'boolean'}},
        }),
    )
    db.session.add(plugin)
    db.session.commit()
    return plugin


class TestExtractionValidationService:
    """Test suite for ExtractionValidationService."""

    def test_service_initialization(self, validation_service):
        """Test validation service initialization."""
        assert validation_service is not None
        assert validation_service.plugin_manager is not None

    def test_validate_field_no_validators(self, validation_service, test_fields):
        """Test validating field with no validators configured."""
        field = test_fields[2]  # dosage field with no validators
        
        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='500mg',
            extracted_value='500mg',
            confidence_score=0.95,
            validation_status='pending',
        )
        db.session.add(field_value)
        db.session.commit()

        # Run validation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            validation_service.validate_extracted_value(field_value, field, {})
        )
        loop.close()

        assert result['is_valid'] is True
        assert result['validation_status'] == 'valid'
        assert len(result['plugin_results']) == 0

    def test_validate_extracted_value_structure(self, validation_service, test_fields):
        """Test validated value has correct structure."""
        field = test_fields[2]
        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
            confidence_score=0.90,
            validation_status='pending',
        )
        db.session.add(field_value)
        db.session.commit()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            validation_service.validate_extracted_value(field_value, field, {})
        )
        loop.close()

        # Check result structure
        assert 'is_valid' in result
        assert 'validation_status' in result
        assert 'errors' in result
        assert 'suggestions' in result
        assert 'corrections' in result
        assert 'plugin_results' in result
        assert 'final_value' in result
        assert 'confidence' in result

        assert isinstance(result['is_valid'], bool)
        assert isinstance(result['errors'], list)
        assert isinstance(result['suggestions'], list)
        assert isinstance(result['plugin_results'], list)

    def test_field_validators_parsing(self, test_fields):
        """Test parsing of plugin validators from field."""
        field = test_fields[0]  # diagnosis field
        validators = field.get_plugin_validators()

        assert len(validators) == 1
        assert validators[0]['plugin_name'] == 'medical'
        assert validators[0]['validator_method'] == 'check_icd10_validation'
        assert validators[0]['fail_on_error'] is False
        assert validators[0]['suggest_corrections'] is True

    def test_field_resolvers_parsing(self, test_fields):
        """Test parsing of plugin resolvers from field."""
        field = test_fields[0]  # diagnosis field
        resolvers = field.get_plugin_resolvers()

        assert len(resolvers) == 1
        assert resolvers[0]['plugin_name'] == 'medical'
        assert resolvers[0]['resolver_method'] == 'resolve_icd10'

    def test_multiple_field_validators(self, test_schema):
        """Test field with multiple validators."""
        field = ExtractionField(
            schema_id=test_schema.id,
            field_name='contract_clause',
            field_type='string',
            is_required=True,
            plugin_validators_json=json.dumps([
                {
                    'plugin_name': 'legal',
                    'validator_method': 'validate_clause',
                    'fail_on_error': False,
                },
                {
                    'plugin_name': 'engineering',
                    'validator_method': 'validate_standards',
                    'fail_on_error': False,
                },
            ]),
        )
        db.session.add(field)
        db.session.commit()

        validators = field.get_plugin_validators()
        assert len(validators) == 2
        assert validators[0]['plugin_name'] == 'legal'
        assert validators[1]['plugin_name'] == 'engineering'

    def test_extracted_field_value_status_tracking(self, test_fields):
        """Test validation status tracking in ExtractedFieldValue."""
        field = test_fields[2]
        
        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='original value',
            extracted_value='extracted value',
            confidence_score=0.85,
            validation_status='pending',
        )
        db.session.add(field_value)
        db.session.commit()

        # Check initial state
        assert field_value.validation_status == 'pending'
        assert field_value.raw_value == 'original value'
        assert field_value.extracted_value == 'extracted value'

        # Simulate status update
        field_value.validation_status = 'valid'
        db.session.commit()

        retrieved = db.session.get(ExtractedFieldValue, field_value.id)
        assert retrieved.validation_status == 'valid'

    def test_validation_errors_json_storage(self, test_fields):
        """Test storage and retrieval of validation errors."""
        field = test_fields[2]
        errors = ['Error 1', 'Error 2', 'Error 3']

        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
            confidence_score=0.80,
            validation_status='invalid',
            validation_errors_json=json.dumps(errors),
        )
        db.session.add(field_value)
        db.session.commit()

        # Retrieve and verify
        retrieved_errors = field_value.get_validation_errors()
        assert len(retrieved_errors) == 3
        assert 'Error 1' in retrieved_errors

    def test_suggestions_json_storage(self, test_fields):
        """Test storage and retrieval of suggestions."""
        field = test_fields[2]
        suggestions = ['Suggestion 1', 'Suggestion 2']

        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
            confidence_score=0.75,
            suggested_values_json=json.dumps(suggestions),
        )
        db.session.add(field_value)
        db.session.commit()

        # Retrieve and verify
        retrieved_suggestions = field_value.get_suggestions()
        assert len(retrieved_suggestions) == 2
        assert 'Suggestion 1' in retrieved_suggestions

    def test_corrections_applied_storage(self, test_fields):
        """Test storage of applied corrections."""
        field = test_fields[2]
        corrections = [
            'Corrected "test" to "TEST"',
            'Trimmed whitespace',
        ]

        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='  test  ',
            extracted_value='TEST',
            confidence_score=0.70,
            validation_status='corrected',
            corrections_applied_json=json.dumps(corrections),
        )
        db.session.add(field_value)
        db.session.commit()

        # Retrieve and verify
        retrieved_corrections = field_value.get_corrections()
        assert len(retrieved_corrections) == 2
        assert 'Corrected' in retrieved_corrections[0]

    def test_plugin_execution_history_storage(self, test_fields):
        """Test storage of plugin execution history."""
        field = test_fields[2]
        execution_history = [
            {
                'plugin_name': 'medical',
                'execution_time_ms': 123.45,
                'success': True,
                'result': 'valid',
            },
            {
                'plugin_name': 'legal',
                'execution_time_ms': 234.56,
                'success': True,
                'result': 'valid',
            },
        ]

        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
            confidence_score=0.80,
            plugin_executions_json=json.dumps(execution_history),
        )
        db.session.add(field_value)
        db.session.commit()

        # Retrieve and verify
        retrieved_executions = field_value.get_plugin_executions()
        assert len(retrieved_executions) == 2
        assert retrieved_executions[0]['plugin_name'] == 'medical'
        assert retrieved_executions[0]['execution_time_ms'] == 123.45

    def test_extraction_validation_result_model(self, test_plugin, test_fields):
        """Test ExtractionValidationResult model."""
        field = test_fields[2]
        field_value = ExtractedFieldValue(
            field_id=field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
            confidence_score=0.85,
        )
        db.session.add(field_value)
        db.session.commit()

        # Create validation result
        val_result = ExtractionValidationResult(
            field_value_id=field_value.id,
            plugin_id=test_plugin.id,
            is_valid=True,
            validation_message='Validation passed',
            correction_applied=None,
            suggestions_json=json.dumps(['Suggestion 1']),
            execution_time_ms=45.67,
        )
        db.session.add(val_result)
        db.session.commit()

        # Retrieve and verify
        retrieved = db.session.get(ExtractionValidationResult, val_result.id)
        assert retrieved.is_valid is True
        assert retrieved.validation_message == 'Validation passed'
        assert retrieved.execution_time_ms == 45.67
        assert len(retrieved.get_suggestions()) == 1

    def test_schema_field_relationship(self, test_schema):
        """Test field relationship to schema."""
        field = ExtractionField(
            schema_id=test_schema.id,
            field_name='test_field',
            field_type='string',
        )
        db.session.add(field)
        db.session.commit()

        # Retrieve and verify relationship
        retrieved_schema = db.session.get(ExtractionSchema, test_schema.id)
        field_from_schema = next(
            (f for f in retrieved_schema.fields if f.field_name == 'test_field'),
            None
        )
        assert field_from_schema is not None
        assert field_from_schema.id == field.id

    def test_extraction_result_field_values_relationship(self, test_extraction_result, test_fields):
        """Test field values relationship to extraction result."""
        # Create field values for extraction result
        for field in test_fields[:2]:
            field_value = ExtractedFieldValue(
                field_id=field.id,
                result_id=test_extraction_result.id,
                raw_value='test',
                extracted_value='test',
                confidence_score=0.90,
            )
            db.session.add(field_value)

        db.session.commit()

        # Retrieve and verify
        field_values = ExtractedFieldValue.query.filter_by(
            result_id=test_extraction_result.id
        ).all()
        assert len(field_values) >= 2

    @pytest.mark.asyncio
    async def test_validate_schema_async(self, validation_service, test_schema):
        """Test async schema validation."""
        # Create fields
        field1 = ExtractionField(
            schema_id=test_schema.id,
            field_name='field1',
            field_type='string',
            plugin_validators_json=json.dumps([
                {'plugin_name': 'medical', 'validator_method': 'validate_field'}
            ]),
        )
        field2 = ExtractionField(
            schema_id=test_schema.id,
            field_name='field2',
            field_type='string',
        )
        db.session.add_all([field1, field2])
        db.session.commit()

        # Validate schema
        result = await validation_service.validate_schema(test_schema.id)

        assert result['success'] is True
        assert result['validation_status']['schema_id'] == test_schema.id
        assert len(result['validation_status']['fields']) == 2
        assert result['validation_status']['fields'][0]['has_validators'] is True
        assert result['validation_status']['fields'][1]['has_validators'] is False


class TestExtractionValidationRoutes:
    """Test extraction routes with validation integration."""

    def test_list_schema_fields(self, client, test_schema, test_fields):
        """Test listing schema fields with plugin config."""
        response = client.get(
            f'/123/extraction/schemas/{test_schema.id}/fields'  # Use dummy project 123
        )
        # Note: This would normally require auth headers

    def test_create_schema_field_with_validators(self, client, test_schema):
        """Test creating field with plugin validators."""
        # Note: This test would need proper auth and project setup
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
