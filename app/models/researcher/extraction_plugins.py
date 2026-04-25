"""Extraction schema enhancements with plugin support (Phase 3.6)."""
import json
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db


class ExtractionField(db.Model):
    """Individual field within an extraction schema with plugin support."""
    __tablename__ = 'extraction_fields'
    __table_args__ = (
        db.UniqueConstraint('schema_id', 'field_name', name='uq_field_per_schema'),
        db.Index('ix_extraction_fields_schema_id', 'schema_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    schema_id = db.Column(db.Integer, db.ForeignKey('extraction_schemas.id'), nullable=False)
    
    # Field definition
    field_name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)  # string, number, date, list, object
    description = db.Column(db.Text)
    is_required = db.Column(db.Boolean, default=False)
    
    # Validation and constraints
    min_length = db.Column(db.Integer)  # For strings
    max_length = db.Column(db.Integer)  # For strings
    pattern = db.Column(db.String(512))  # Regex pattern for validation
    enum_values_json = db.Column(db.Text)  # JSON array of allowed values
    
    # Plugin configuration
    plugin_validators_json = db.Column(db.Text)  # JSON list of plugin validators to apply
    plugin_resolvers_json = db.Column(db.Text)  # JSON list of plugins that can suggest values
    extraction_instructions = db.Column(db.Text)  # Instructions for LLM on how to extract
    
    # Metadata
    field_order = db.Column(db.Integer, default=0)  # For UI ordering
    help_text = db.Column(db.String(512))  # UI help text
    example_value = db.Column(db.String(512))  # Example value for documentation
    
    # Statistics
    extraction_count = db.Column(db.Integer, default=0)  # Times extracted
    validation_failure_count = db.Column(db.Integer, default=0)  # Validation failures
    validation_correction_count = db.Column(db.Integer, default=0)  # Times auto-corrected
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    schema = db.relationship('ExtractionSchema', backref='fields')
    validators = db.relationship('PluginValidator', foreign_keys='PluginValidator.extraction_field_id', cascade='all, delete-orphan')
    values = db.relationship('ExtractedFieldValue', backref='field', cascade='all, delete-orphan')
    
    def get_plugin_validators(self):
        """Parse plugin validators JSON.
        
        Returns:
            List of {plugin_name, validator_method, fail_on_error, suggest_corrections} dicts
        """
        if not self.plugin_validators_json:
            return []
        try:
            return json.loads(self.plugin_validators_json)
        except:
            return []
    
    def get_plugin_resolvers(self):
        """Parse plugin resolvers JSON.
        
        Returns:
            List of {plugin_name, resolver_method} dicts
        """
        if not self.plugin_resolvers_json:
            return []
        try:
            return json.loads(self.plugin_resolvers_json)
        except:
            return []
    
    def to_dict(self, include_stats=False):
        """Convert to dictionary."""
        result = {
            'id': self.id,
            'schema_id': self.schema_id,
            'field_name': self.field_name,
            'field_type': self.field_type,
            'description': self.description,
            'is_required': self.is_required,
            'min_length': self.min_length,
            'max_length': self.max_length,
            'pattern': self.pattern,
            'enum_values': json.loads(self.enum_values_json) if self.enum_values_json else [],
            'plugin_validators': self.get_plugin_validators(),
            'plugin_resolvers': self.get_plugin_resolvers(),
            'help_text': self.help_text,
            'example_value': self.example_value,
            'field_order': self.field_order,
        }
        
        if include_stats:
            result.update({
                'extraction_count': self.extraction_count,
                'validation_failure_count': self.validation_failure_count,
                'validation_correction_count': self.validation_correction_count,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            })
        
        return result


class ExtractedFieldValue(db.Model):
    """Individual extracted field value with validation history."""
    __tablename__ = 'extracted_field_values'
    __table_args__ = (
        db.Index('ix_extracted_field_values_result_id', 'result_id'),
        db.Index('ix_extracted_field_values_field_id', 'field_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('extraction_results.id'), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey('extraction_fields.id'), nullable=False)
    
    # Original extracted value
    raw_value = db.Column(db.Text)  # Raw text from LLM
    extracted_value = db.Column(db.Text)  # Final value used
    
    # Validation and correction
    validation_status = db.Column(db.String(50), default="pending")  # pending, valid, invalid, corrected
    validation_errors_json = db.Column(db.Text)  # Validation error messages
    corrections_applied_json = db.Column(db.Text)  # Corrections applied by plugins
    suggested_values_json = db.Column(db.Text)  # Alternative values suggested by plugins
    
    # Plugin execution history
    plugin_executions_json = db.Column(db.Text)  # Plugin execution results
    
    # Metadata
    confidence_score = db.Column(db.Float, default=1.0)  # 0.0-1.0 extraction confidence
    validation_timestamp = db.Column(db.DateTime)  # When validation occurred
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    result = db.relationship('ExtractionResult', backref='field_values')
    
    def get_validation_errors(self):
        """Parse validation errors JSON."""
        if not self.validation_errors_json:
            return []
        try:
            return json.loads(self.validation_errors_json)
        except:
            return []
    
    def get_corrections(self):
        """Parse corrections applied JSON."""
        if not self.corrections_applied_json:
            return []
        try:
            return json.loads(self.corrections_applied_json)
        except:
            return []
    
    def get_suggestions(self):
        """Parse suggested values JSON."""
        if not self.suggested_values_json:
            return []
        try:
            return json.loads(self.suggested_values_json)
        except:
            return []
    
    def get_plugin_executions(self):
        """Parse plugin execution history JSON."""
        if not self.plugin_executions_json:
            return []
        try:
            return json.loads(self.plugin_executions_json)
        except:
            return []
    
    def to_dict(self, include_history=False):
        """Convert to dictionary."""
        result = {
            'id': self.id,
            'field_id': self.field_id,
            'raw_value': self.raw_value,
            'extracted_value': self.extracted_value,
            'validation_status': self.validation_status,
            'confidence_score': self.confidence_score,
            'validation_errors': self.get_validation_errors(),
            'suggested_values': self.get_suggestions(),
        }
        
        if include_history:
            result.update({
                'corrections_applied': self.get_corrections(),
                'plugin_executions': self.get_plugin_executions(),
                'validation_timestamp': self.validation_timestamp.isoformat() if self.validation_timestamp else None,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            })
        
        return result


class ExtractionValidationResult(db.Model):
    """Result of validating an extracted value with plugins."""
    __tablename__ = 'extraction_validation_results'
    __table_args__ = (
        db.Index('ix_extraction_validation_results_field_value_id', 'field_value_id'),
        db.Index('ix_extraction_validation_results_plugin_id', 'plugin_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    field_value_id = db.Column(db.Integer, db.ForeignKey('extracted_field_values.id'), nullable=False)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False)
    
    # Validation result
    is_valid = db.Column(db.Boolean, default=True)
    validation_message = db.Column(db.Text)  # Any validation message from plugin
    correction_applied = db.Column(db.Text)  # Corrected value if auto-corrected
    suggestions_json = db.Column(db.Text)  # Suggested values from plugin
    
    # Metadata
    execution_time_ms = db.Column(db.Float, default=0.0)
    executed_at = db.Column(db.DateTime, default=utcnow_naive)
    
    # Relationships
    field_value = db.relationship('ExtractedFieldValue')
    plugin = db.relationship('Plugin')
    
    def get_suggestions(self):
        """Parse suggestions JSON."""
        if not self.suggestions_json:
            return []
        try:
            return json.loads(self.suggestions_json)
        except:
            return []
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'field_value_id': self.field_value_id,
            'plugin_id': self.plugin_id,
            'is_valid': self.is_valid,
            'validation_message': self.validation_message,
            'correction_applied': self.correction_applied,
            'suggestions': self.get_suggestions(),
            'execution_time_ms': self.execution_time_ms,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
        }


# Update ExtractionSchema to reference fields
def update_extraction_schema():
    """Migration helper to add field support to ExtractionSchema."""
    # Note: In actual migration, would add these columns:
    # schema.plugin_validators_json - JSON list of global validators
    # schema.enable_plugin_suggestions - Boolean to enable plugin suggestions
    # schema.validation_mode - strict | lenient | auto_correct
    pass
