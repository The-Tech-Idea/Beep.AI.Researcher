"""Cache invalidation event handlers (Phase 2.5)."""

import logging
from app.core.event_bus import Event, EventType, get_event_bus
from app.services.search_cache_manager import get_cache_manager

logger = logging.getLogger(__name__)


def register_cache_invalidation_handlers():
    """Register all cache invalidation handlers with the EventBus."""
    event_bus = get_event_bus()
    
    # Listen for document uploads (invalidate project cache)
    event_bus.subscribe(
        EventType.DOCUMENT_UPLOADED.value,
        handle_document_uploaded
    )
    
    # Listen for import completion (invalidate and index)
    # Note: Using 'import.completed' event from Phase 2.4
    event_bus.subscribe(
        'import.completed',
        handle_import_completed
    )
    
    # Listen for document deletion (invalidate project cache)
    event_bus.subscribe(
        EventType.DOCUMENT_DELETED.value,
        handle_document_deleted
    )
    
    logger.info("Registered cache invalidation event handlers")


def handle_document_uploaded(event: Event):
    """
    Handle document.uploaded event - invalidate project cache.
    
    Event data:
    {
        'project_id': int,
        'document_id': int,
        'filename': str,
        'mime_type': str,
        ...
    }
    """
    try:
        project_id = event.data.get('project_id')
        if not project_id:
            logger.warning("document.uploaded event missing project_id")
            return
        
        cache_manager = get_cache_manager()
        cache_manager.invalidate_project_cache(project_id)
        
        document_id = event.data.get('document_id', 'unknown')
        filename = event.data.get('filename', 'unknown')
        logger.info(f"Cache invalidated for project {project_id} due to document upload: {filename}")
    
    except Exception as e:
        logger.error(f"Error handling document.uploaded event: {e}")


def handle_import_completed(event: Event):
    """
    Handle import.completed event - invalidate project cache.
    
    Event data from Phase 2.4:
    {
        'project_id': int,
        'job_id': str,
        'document_id': int,
        'source_result_id': str,
        'source_url': str,
        'file_path': str,
        'file_size': int,
        'duration_seconds': float,
        ...
    }
    """
    try:
        project_id = event.data.get('project_id')
        if not project_id:
            logger.warning("import.completed event missing project_id")
            return
        
        cache_manager = get_cache_manager()
        
        # Invalidate project cache since new document was added
        cache_manager.invalidate_project_cache(project_id)
        
        document_id = event.data.get('document_id', 'unknown')
        source_url = event.data.get('source_url', 'unknown')
        logger.info(
            f"Cache invalidated for project {project_id} due to import completion: "
            f"document {document_id} from {source_url}"
        )
    
    except Exception as e:
        logger.error(f"Error handling import.completed event: {e}")


def handle_document_deleted(event: Event):
    """
    Handle document.deleted event - invalidate project cache.
    
    Event data:
    {
        'project_id': int,
        'document_id': int,
        'filename': str,
        ...
    }
    """
    try:
        project_id = event.data.get('project_id')
        if not project_id:
            logger.warning("document.deleted event missing project_id")
            return
        
        cache_manager = get_cache_manager()
        cache_manager.invalidate_project_cache(project_id)
        
        document_id = event.data.get('document_id', 'unknown')
        filename = event.data.get('filename', 'unknown')
        logger.info(f"Cache invalidated for project {project_id} due to document deletion: {filename}")
    
    except Exception as e:
        logger.error(f"Error handling document.deleted event: {e}")
