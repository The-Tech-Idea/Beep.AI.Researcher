"""Plugin base classes and interfaces (Phase 3.1)."""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from app.core.time_utils import utcnow_naive
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Plugin metadata definition."""
    name: str
    display_name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    author_email: str = ""
    plugin_type: str = "custom"  # builtin | custom | external
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class HookContext:
    """Context passed to plugin hooks."""
    hook_point: str  # HookPoint enum value
    project_id: Optional[int] = None
    tenant_id: Optional[int] = None
    user_id: Optional[int] = None
    request_id: Optional[str] = None
    timestamp: datetime = field(default_factory=utcnow_naive)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'hook_point': self.hook_point,
            'project_id': self.project_id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'request_id': self.request_id,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'metadata': self.metadata,
        }


@dataclass
class HookResult:
    """Result returned from a plugin hook."""
    success: bool
    plugin_name: str
    hook_point: str
    execution_time_ms: float
    status: str = "success"  # success | error | timeout | skipped
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'success': self.success,
            'plugin_name': self.plugin_name,
            'hook_point': self.hook_point,
            'execution_time_ms': self.execution_time_ms,
            'status': self.status,
            'error_message': self.error_message,
            'data': self.data,
            'suggestions': self.suggestions,
        }


class PluginBase(ABC):
    """Base class for all plugins (Phase 3.1).
    
    Each plugin must:
    1. Implement __init__ and set self.metadata
    2. Implement required hook methods (on_plugin_load, on_plugin_unload)
    3. Implement any optional hook methods needed
    4. Return HookResult from each hook method
    """

    def __init__(self, metadata: PluginMetadata):
        """Initialize plugin with metadata."""
        self.metadata = metadata
        self.config: Dict[str, Any] = metadata.default_config.copy()
        self.is_loaded = False
        self.hooks: Dict[str, Callable] = {}
        self._setup_hooks()
        logger.info(f"Plugin {metadata.name} initialized")

    def _setup_hooks(self):
        """Discover and register hook methods."""
        hook_methods = [
            'on_plugin_load',
            'on_plugin_unload',
            'on_document_upload',
            'on_document_delete',
            'on_extraction',
            'on_code_creation',
            'on_export',
            'on_search',
            'on_import',
        ]
        
        for hook_name in hook_methods:
            if hasattr(self, hook_name):
                self.hooks[hook_name] = getattr(self, hook_name)

    def set_config(self, config: Dict[str, Any]) -> None:
        """Update plugin configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config.update(config)
        logger.info(f"Plugin {self.metadata.name} configuration updated")

    def get_config(self) -> Dict[str, Any]:
        """Get current plugin configuration.
        
        Returns:
            Configuration dictionary
        """
        return self.config.copy()

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata.
        
        Returns:
            PluginMetadata object
        """
        return self.metadata
    
    @abstractmethod
    async def on_plugin_load(self, context: HookContext) -> HookResult:
        """Called when plugin is loaded/enabled.
        
        Args:
            context: Hook context with plugin info
            
        Returns:
            HookResult indicating success/failure
        """
        pass

    @abstractmethod
    async def on_plugin_unload(self, context: HookContext) -> HookResult:
        """Called when plugin is unloaded/disabled.
        
        Args:
            context: Hook context with plugin info
            
        Returns:
            HookResult indicating success/failure
        """
        pass

    async def on_document_upload(self, context: HookContext) -> HookResult:
        """Called when document is uploaded (optional hook).
        
        Args:
            context: Hook context with document info
                - data['document_id']: Document ID
                - data['project_id']: Project ID
                - data['file_path']: Uploaded file path
                
        Returns:
            HookResult with any modifications
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_document_upload",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_document_delete(self, context: HookContext) -> HookResult:
        """Called when document is deleted (optional hook).
        
        Args:
            context: Hook context with document info
                - data['document_id']: Document ID
                - data['project_id']: Project ID
                
        Returns:
            HookResult
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_document_delete",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_extraction(self, context: HookContext) -> HookResult:
        """Called during field extraction (optional hook).
        
        Args:
            context: Hook context with extraction info
                - data['extraction_id']: Extraction ID
                - data['field_name']: Field being extracted
                - data['extracted_value']: Extracted value
                - data['document_id']: Document ID
                
        Returns:
            HookResult with suggestions or corrections
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_extraction",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_code_creation(self, context: HookContext) -> HookResult:
        """Called when code is generated (optional hook).
        
        Args:
            context: Hook context with code info
                - data['code_id']: Code ID
                - data['generated_code']: Generated code
                - data['project_id']: Project ID
                
        Returns:
            HookResult with suggestions
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_code_creation",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_export(self, context: HookContext) -> HookResult:
        """Called when exporting data (optional hook).
        
        Args:
            context: Hook context with export info
                - data['export_format']: Export format
                - data['project_id']: Project ID
                
        Returns:
            HookResult
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_export",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_search(self, context: HookContext) -> HookResult:
        """Called during search (optional hook).
        
        Args:
            context: Hook context with search info
                - data['query']: Search query
                - data['results']: Search results
                - data['project_id']: Project ID
                
        Returns:
            HookResult with filtering/ranking suggestions
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_search",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def on_import(self, context: HookContext) -> HookResult:
        """Called during import (optional hook).
        
        Args:
            context: Hook context with import info
                - data['import_id']: Import job ID
                - data['documents_count']: Number of documents
                - data['project_id']: Project ID
                
        Returns:
            HookResult
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="on_import",
            execution_time_ms=0.0,
            status="skipped"
        )

    async def validate_field(self, field_name: str, field_value: Any, 
                            field_context: Dict[str, Any]) -> HookResult:
        """Validate extraction field (optional method for validators).
        
        Args:
            field_name: Name of field being validated
            field_value: Value to validate
            field_context: Additional context about field
            
        Returns:
            HookResult with validation status and suggestions
        """
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="validate_field",
            execution_time_ms=0.0,
            status="skipped"
        )

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.metadata.name} v{self.metadata.version}>"


class PluginValidatorBase(PluginBase):
    """Base class for validator plugins that validate extraction fields.
    
    Validator plugins focus on validating extracted field values and
    suggesting corrections.
    """
    
    @abstractmethod
    async def validate(self, field_name: str, field_value: Any, 
                       context: Dict[str, Any]) -> HookResult:
        """Validate a field value.
        
        Args:
            field_name: Name of field being validated
            field_value: Value to validate
            context: Additional context (document, project, etc)
            
        Returns:
            HookResult with validation status and suggestions
        """
        pass
