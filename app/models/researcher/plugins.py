"""Plugin system models (Phase 3.1 & 3.5)."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from enum import Enum
from app.database import db
from sqlalchemy.orm import validates, synonym


class PluginStatus(Enum):
    """Plugin status enumeration."""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    LOADING = "loading"
    installed = "installed"
    enabled = "enabled"
    disabled = "disabled"
    error = "error"
    loading = "loading"


class PluginType(Enum):
    """Plugin type enumeration."""
    BUILTIN = "builtin"      # Built-in plugins (medical, legal, engineering)
    CUSTOM = "custom"         # User-installed custom plugins
    EXTERNAL = "external"     # Third-party plugins
    builtin = "builtin"
    custom = "custom"
    external = "external"


class HookPoint(Enum):
    """Available plugin hook points."""
    ON_PLUGIN_LOAD = "on_plugin_load"
    ON_PLUGIN_UNLOAD = "on_plugin_unload"
    ON_DOCUMENT_UPLOAD = "on_document_upload"
    ON_DOCUMENT_DELETE = "on_document_delete"
    ON_EXTRACTION = "on_extraction"
    ON_CODE_CREATION = "on_code_creation"
    ON_EXPORT = "on_export"
    ON_SEARCH = "on_search"
    ON_IMPORT = "on_import"


class Plugin(db.Model):
    """Plugin registry and configuration (Phase 3)."""
    __tablename__ = 'plugins'
    __table_args__ = (
        db.UniqueConstraint('name', 'version', name='uq_plugin_name_version'),
    )

    id = db.Column(db.Integer, primary_key=True)
    
    # Plugin identification
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)  # e.g., "medical", "legal", "engineering"
    display_name = db.Column(db.String(255), nullable=False, default='Plugin')  # e.g., "Medical Domain Plugin"
    description = db.Column(db.Text)
    
    # Plugin metadata
    version = db.Column(db.String(20), nullable=False, default="1.0.0")  # Semantic version
    author = db.Column(db.String(255))
    author_email = db.Column(db.String(255))
    plugin_type = db.Column(db.String(50), default=PluginType.CUSTOM.value)  # builtin | custom | external
    
    # Plugin class information
    module_path = db.Column(db.String(512), nullable=False, default='app.plugins.default.DefaultPlugin')
    class_name = db.Column(db.String(255), nullable=False, default='DefaultPlugin')
    
    # Status and lifecycle
    status = db.Column(db.String(50), default=PluginStatus.INSTALLED.value)  # installed | enabled | disabled | error | loading
    error_message = db.Column(db.Text)  # If status=error, what went wrong
    enabled = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, nullable=True)
    
    # Configuration
    config_schema_json = db.Column(db.Text)  # JSON schema for plugin configuration
    default_config_json = db.Column(db.Text)  # Default configuration
    
    # Features
    dependencies_json = db.Column(db.Text)  # JSON list of plugin name dependencies
    hooks_enabled_json = db.Column(db.Text)  # JSON list of enabled hook points
    
    # Statistics
    installation_count = db.Column(db.Integer, default=0)  # Number of installations
    execution_count = db.Column(db.Integer, default=0)  # Total hook executions
    error_count = db.Column(db.Integer, default=0)  # Total execution errors
    last_execution_time = db.Column(db.DateTime)  # Last hook execution
    total_execution_time_ms = db.Column(db.Integer, default=0)  # Total execution time across all hooks
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    enabled_at = db.Column(db.DateTime)  # When plugin was last enabled
    disabled_at = db.Column(db.DateTime)  # When plugin was last disabled
    
    # Relationships
    configurations = db.relationship('PluginConfiguration', backref='plugin', cascade='all, delete-orphan')
    hook_registrations = db.relationship('PluginHookRegistration', backref='plugin', cascade='all, delete-orphan')
    execution_logs = db.relationship('PluginExecutionLog', backref='plugin', cascade='all, delete-orphan')
    validators = db.relationship('PluginValidator', backref='plugin', cascade='all, delete-orphan')

    config_schema = synonym('config_schema_json')

    @validates('plugin_type')
    def _validate_plugin_type(self, _, value):
        if isinstance(value, Enum):
            return value.value
        return str(value).lower() if value else PluginType.CUSTOM.value

    @validates('status')
    def _validate_status(self, _, value):
        if isinstance(value, Enum):
            status = value.value
        else:
            status = str(value).lower() if value else PluginStatus.INSTALLED.value
        self.enabled = status == PluginStatus.ENABLED.value
        return status
    
    def to_dict(self, include_config=False):
        """Convert to dict."""
        result = {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'plugin_type': self.plugin_type,
            'status': self.status,
            'error_message': self.error_message,
            'installation_count': self.installation_count,
            'execution_count': self.execution_count,
            'error_count': self.error_count,
            'last_execution_time': self.last_execution_time.isoformat() if self.last_execution_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'enabled_at': self.enabled_at.isoformat() if self.enabled_at else None,
            'disabled_at': self.disabled_at.isoformat() if self.disabled_at else None,
        }
        
        if include_config:
            result['config_schema'] = self.config_schema_json
            result['default_config'] = self.default_config_json
            result['dependencies'] = self.dependencies_json
            result['hooks_enabled'] = self.hooks_enabled_json
        
        return result


class PluginConfiguration(db.Model):
    """Plugin configuration per project or tenant (Phase 3)."""
    __tablename__ = 'plugin_configurations'
    __table_args__ = (
        db.UniqueConstraint('plugin_id', 'project_id', 'tenant_id', name='uq_plugin_config'),
    )

    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), index=True)  # NULL = tenant level
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True)  # NULL = default tenant
    
    # Configuration
    is_enabled = db.Column(db.Boolean, default=True)
    config_json = db.Column(db.Text)  # Override configuration for this project/tenant
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    project = db.relationship('ResearchProject', backref='plugin_configs', foreign_keys=[project_id])
    # Note: tenant relationship deferred due to circular import - can be added after models are stable
    # tenant = db.relationship('Tenant', foreign_keys=[tenant_id])
    
    def to_dict(self):
        """Convert to dict."""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'project_id': self.project_id,
            'tenant_id': self.tenant_id,
            'is_enabled': self.is_enabled,
            'config_json': self.config_json,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PluginHookRegistration(db.Model):
    """Plugin hook registration and event routing (Phase 3.1)."""
    __tablename__ = 'plugin_hook_registrations'
    __table_args__ = (
        db.UniqueConstraint('plugin_id', 'hook_point', name='uq_plugin_hook'),
    )

    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    
    # Hook point this plugin listens to
    hook_point = db.Column(db.String(50), nullable=False)  # HookPoint enum value
    
    # Execution order (lower order = earlier execution)
    execution_order = db.Column(db.Integer, default=100)
    
    # Handler method information
    handler_method = db.Column(db.String(255), nullable=False)  # Method name to call (e.g., "on_extraction")
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    
    # Statistics
    execution_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    last_execution_time = db.Column(db.DateTime)
    average_execution_time_ms = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)


class PluginValidator(db.Model):
    """Plugin validators for extraction schema fields (Phase 3.4)."""
    __tablename__ = 'plugin_validators'
    __table_args__ = (
        db.UniqueConstraint('plugin_id', 'extraction_field_id', name='uq_plugin_validator'),
    )

    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    extraction_field_id = db.Column(db.Integer, db.ForeignKey('extraction_fields.id'), nullable=False, index=True)
    
    # Validator configuration
    validator_method = db.Column(db.String(255), nullable=False)  # Plugin method to call
    is_required = db.Column(db.Boolean, default=True)  # Run even if field is empty
    fail_on_error = db.Column(db.Boolean, default=False)  # Stop extraction if validator fails
    suggest_corrections = db.Column(db.Boolean, default=True)  # Return suggested corrections
    
    # Configuration
    config_json = db.Column(db.Text)  # Validator-specific configuration
    
    # Statistics
    validation_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    suggestion_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    extraction_field = db.relationship('ExtractionField', foreign_keys=[extraction_field_id], overlaps="validators")


class PluginExecutionLog(db.Model):
    """Detailed plugin execution logging (Phase 3.5)."""
    __tablename__ = 'plugin_execution_logs'
    __table_args__ = (
        db.Index('ix_plugin_execution_logs_plugin_id', 'plugin_id'),
        db.Index('ix_plugin_execution_logs_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False)
    
    # Context
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True)
    
    # Execution details
    hook_point = db.Column(db.String(50), nullable=False)  # Which hook was called
    handler_method = db.Column(db.String(255), nullable=False, default='run')
    request_id = db.Column(db.String(255), nullable=True, index=True)
    
    # Request/Response data
    request_data_json = db.Column(db.Text)  # Input to plugin (limited size)
    response_data_json = db.Column(db.Text)  # Output from plugin (limited size)
    
    # Execution metrics
    status = db.Column(db.String(20), default="success")  # success | error | timeout | skipped
    execution_time_ms = db.Column(db.Float, default=0.0)
    error_message = db.Column(db.Text)  # If status=error
    error_traceback = db.Column(db.Text)  # Full Python traceback for debugging
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    created_timestamp_ms = db.Column(db.BigInteger)  # Millisecond precision timestamp
    
    # Relationships
    project = db.relationship('ResearchProject', backref='plugin_logs')
    # Note: tenant relationship deferred due to circular import - can be added after models are stable
    # tenant = db.relationship('Tenant')

    request_data = synonym('request_data_json')
    response_data = synonym('response_data_json')
    traceback = synonym('error_traceback')
    executed_at = synonym('created_at')
    
    def to_dict(self):
        """Convert to dict."""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'project_id': self.project_id,
            'hook_point': self.hook_point,
            'handler_method': self.handler_method,
            'status': self.status,
            'execution_time_ms': self.execution_time_ms,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PluginRegistry(db.Model):
    """Registry for tracking all available plugins (Phase 3.1)."""
    __tablename__ = 'plugin_registry'

    id = db.Column(db.Integer, primary_key=True)
    
    # Registry metadata
    registry_name = db.Column(db.String(255), nullable=False, unique=True, index=True)  # e.g., "builtin", "marketplace", "custom"
    registry_url = db.Column(db.String(512))  # URL to plugin registry (for future marketplace)
    description = db.Column(db.Text)
    
    # Registry status
    is_active = db.Column(db.Boolean, default=True)
    last_sync_time = db.Column(db.DateTime)  # Last time we synced with registry
    
    # Configuration
    config_json = db.Column(db.Text)  # Registry-specific configuration
    
    # Statistics
    total_plugins = db.Column(db.Integer, default=0)
    enabled_plugins = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
