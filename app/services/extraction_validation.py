"""Extraction validation service with plugin integration (Phase 3.6)."""
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.database import db
from app.models.researcher.extraction_plugins import (
    ExtractionField, ExtractedFieldValue, ExtractionValidationResult
)
from app.models.researcher.plugins import Plugin
from app.services.plugin_base import HookContext, HookResult
from app.services.plugin_manager import get_plugin_manager

logger = logging.getLogger(__name__)


class ExtractionValidationService:
    """Service for validating extracted fields using plugins.
    
    Features:
    - Plugin-based field validation
    - Automatic correction suggestion
    - Multi-plugin validation chain
    - Validation result tracking
    - Confidence scoring
    """

    def __init__(self):
        """Initialize extraction validation service."""
        self.plugin_manager = get_plugin_manager()

    async def validate_extracted_value(self, field_value: ExtractedFieldValue,
                                      field: ExtractionField,
                                      context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate an extracted field value using configured plugins.
        
        Args:
            field_value: ExtractedFieldValue to validate
            field: ExtractionField with plugin configuration
            context: Additional context (project_id, tenant_id, user_id)
            
        Returns:
            Dict with validation results:
            {
                'is_valid': bool,
                'validation_status': str (valid | invalid | corrected),
                'errors': [str],
                'suggestions': [str],
                'corrections': [str],
                'plugin_results': [{plugin_name, is_valid, message, ...}],
                'final_value': str,
                'confidence': float,
            }
        """
        if context is None:
            context = {}

        validation_results = []
        errors = []
        suggestions = []
        corrections = []
        final_value = field_value.extracted_value
        is_valid = True

        try:
            # Get configured validators for this field
            validators = field.get_plugin_validators()

            if not validators:
                logger.debug(f"No validators configured for field {field.field_name}")
                return {
                    'is_valid': True,
                    'validation_status': 'valid',
                    'errors': [],
                    'suggestions': [],
                    'corrections': [],
                    'plugin_results': [],
                    'final_value': final_value,
                    'confidence': field_value.confidence_score,
                }

            # Execute each plugin validator
            for validator_config in validators:
                plugin_name = validator_config.get('plugin_name')
                validator_method = validator_config.get('validator_method')
                fail_on_error = validator_config.get('fail_on_error', False)
                suggest_corrections = validator_config.get('suggest_corrections', True)

                result = await self._execute_validator(
                    plugin_name=plugin_name,
                    validator_method=validator_method,
                    field_name=field.field_name,
                    field_value=final_value,
                    field_type=field.field_type,
                    context=context,
                    suggest_corrections=suggest_corrections,
                )

                validation_results.append(result)

                if result['success']:
                    if not result['is_valid']:
                        is_valid = False
                        errors.extend(result.get('errors', []))

                        if result.get('correction'):
                            correction = result['correction']
                            final_value = correction
                            corrections.append(f"Auto-corrected to: {correction}")

                        if fail_on_error:
                            break

                    suggestions.extend(result.get('suggestions', []))
                else:
                    # Plugin execution error
                    error_msg = result.get('error_message', 'Unknown error')
                    if fail_on_error:
                        is_valid = False
                        errors.append(f"Validator error: {error_msg}")
                        break
                    else:
                        logger.warning(f"Validator {plugin_name} error: {error_msg}")

            # Save validation results to database
            field_value.validation_status = 'valid' if is_valid else 'invalid'
            if corrections:
                field_value.validation_status = 'corrected'
            
            field_value.extracted_value = final_value
            field_value.validation_errors_json = json.dumps(errors)
            field_value.suggested_values_json = json.dumps(suggestions)
            field_value.corrections_applied_json = json.dumps(corrections)
            field_value.plugin_executions_json = json.dumps(validation_results)

            # Store individual validation results
            for result in validation_results:
                if result.get('plugin_id'):
                    val_result = ExtractionValidationResult(
                        field_value_id=field_value.id,
                        plugin_id=result['plugin_id'],
                        is_valid=result.get('is_valid', False),
                        validation_message=result.get('message', ''),
                        correction_applied=result.get('correction'),
                        suggestions_json=json.dumps(result.get('suggestions', [])),
                        execution_time_ms=result.get('execution_time_ms', 0.0),
                    )
                    db.session.add(val_result)

            db.session.add(field_value)
            db.session.commit()

            return {
                'is_valid': is_valid,
                'validation_status': field_value.validation_status,
                'errors': errors,
                'suggestions': suggestions,
                'corrections': corrections,
                'plugin_results': validation_results,
                'final_value': final_value,
                'confidence': field_value.confidence_score,
            }

        except Exception as e:
            logger.error(f"Error validating field {field.field_name}: {e}")
            field_value.validation_status = 'invalid'
            db.session.add(field_value)
            db.session.commit()

            return {
                'is_valid': False,
                'validation_status': 'invalid',
                'errors': [str(e)],
                'suggestions': [],
                'corrections': [],
                'plugin_results': [],
                'final_value': final_value,
                'confidence': field_value.confidence_score,
            }

    async def _execute_validator(self, plugin_name: str, validator_method: str,
                                 field_name: str, field_value: str,
                                 field_type: str, context: Dict[str, Any],
                                 suggest_corrections: bool = True) -> Dict[str, Any]:
        """Execute a single plugin validator.
        
        Args:
            plugin_name: Name of plugin
            validator_method: Method to call on plugin
            field_name: Field being validated
            field_value: Value to validate
            field_type: Field type
            context: Validation context
            suggest_corrections: Whether to request corrections
            
        Returns:
            Validation result dict
        """
        try:
            # Get plugin instance
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return {
                    'success': False,
                    'plugin_name': plugin_name,
                    'error_message': f"Plugin {plugin_name} not loaded",
                }

            # Get plugin record for ID
            plugin_record = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin_record:
                plugin_id = None
            else:
                plugin_id = plugin_record.id

            # Execute validator
            start_time = time.time()
            try:
                if hasattr(plugin, validator_method):
                    handler = getattr(plugin, validator_method)
                    result = await asyncio.wait_for(
                        handler(field_name, field_value, {
                            'field_type': field_type,
                            'context': context,
                            'suggest_corrections': suggest_corrections,
                        }),
                        timeout=30.0
                    )
                else:
                    # Fallback to validate_field method
                    result = await asyncio.wait_for(
                        plugin.validate_field(field_name, field_value, {
                            'field_type': field_type,
                            'context': context,
                        }),
                        timeout=30.0
                    )

                execution_time = (time.time() - start_time) * 1000

                return {
                    'success': True,
                    'plugin_name': plugin_name,
                    'plugin_id': plugin_id,
                    'validator_method': validator_method,
                    'is_valid': result.success,
                    'message': result.error_message or '',
                    'errors': [result.error_message] if not result.success else [],
                    'suggestions': result.suggestions or [],
                    'correction': None,  # Plugins return suggestions not corrections
                    'execution_time_ms': execution_time,
                }

            except asyncio.TimeoutError:
                execution_time = (time.time() - start_time) * 1000
                return {
                    'success': False,
                    'plugin_name': plugin_name,
                    'plugin_id': plugin_id,
                    'error_message': f"Validator timeout (>30s)",
                    'execution_time_ms': execution_time,
                }

        except Exception as e:
            logger.error(f"Error executing validator {plugin_name}: {e}")
            return {
                'success': False,
                'plugin_name': plugin_name,
                'error_message': str(e),
                'execution_time_ms': 0.0,
            }

    async def resolve_field_value(self, field: ExtractionField, 
                                  partial_value: str = None,
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use plugins to resolve and suggest values for a field.
        
        Args:
            field: ExtractionField to resolve
            partial_value: Partial value to use for resolution
            context: Resolution context
            
        Returns:
            Dict with resolution results:
            {
                'suggestions': [
                    {'value': str, 'plugin_name': str, 'confidence': float, ...}
                ],
                'best_match': {'value': str, 'plugin_name': str, ...},
            }
        """
        if context is None:
            context = {}

        suggestions = []
        resolvers = field.get_plugin_resolvers()

        if not resolvers:
            logger.debug(f"No resolvers configured for field {field.field_name}")
            return {
                'suggestions': [],
                'best_match': None,
            }

        # Execute each plugin resolver
        for resolver_config in resolvers:
            plugin_name = resolver_config.get('plugin_name')
            resolver_method = resolver_config.get('resolver_method', 'resolve_field')

            try:
                plugin = self.plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    logger.warning(f"Plugin {plugin_name} not loaded for resolver")
                    continue

                if not hasattr(plugin, resolver_method):
                    logger.warning(f"Plugin {plugin_name} does not have {resolver_method}")
                    continue

                # Execute resolver
                start_time = time.time()
                handler = getattr(plugin, resolver_method)
                result = await asyncio.wait_for(
                    handler(field.field_name, partial_value or '', {
                        'field_type': field.field_type,
                        'context': context,
                    }),
                    timeout=30.0
                )

                execution_time = (time.time() - start_time) * 1000

                # Extract suggestions from result
                if hasattr(result, 'suggestions') and result.suggestions:
                    for suggestion in result.suggestions:
                        suggestions.append({
                            'value': suggestion,
                            'plugin_name': plugin_name,
                            'confidence': 0.8,  # Default confidence
                            'execution_time_ms': execution_time,
                        })

            except asyncio.TimeoutError:
                logger.warning(f"Resolver {plugin_name} timed out")
            except Exception as e:
                logger.warning(f"Error executing resolver {plugin_name}: {e}")

        # Sort by confidence (if available)
        suggestions.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        return {
            'suggestions': suggestions,
            'best_match': suggestions[0] if suggestions else None,
        }

    async def validate_schema(self, schema_id: int, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate all configured validators for a schema.
        
        Args:
            schema_id: ExtractionSchema ID
            context: Validation context
            
        Returns:
            Dict with validation status for all fields
        """
        from app.models.researcher.researcher_extraction import ExtractionSchema

        schema = db.session.query(ExtractionSchema).filter(ExtractionSchema.id == schema_id).first()
        if not schema:
            return {'success': False, 'error': f"Schema {schema_id} not found"}

        validation_status = {
            'schema_id': schema_id,
            'schema_name': schema.name,
            'fields': [],
        }

        for field in schema.fields:
            # Check if field has validators configured
            validators = field.get_plugin_validators()
            resolvers = field.get_plugin_resolvers()

            field_status = {
                'field_name': field.field_name,
                'has_validators': len(validators) > 0,
                'validator_count': len(validators),
                'has_resolvers': len(resolvers) > 0,
                'resolver_count': len(resolvers),
                'validators': validators,
                'resolvers': resolvers,
            }

            validation_status['fields'].append(field_status)

        return {
            'success': True,
            'validation_status': validation_status,
        }
