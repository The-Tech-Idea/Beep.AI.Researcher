# Phase 2: Configuration Reference

**Version**: 1.0 | **Last Updated**: February 7, 2026  
**Scope**: Complete reference for all Phase 2 configuration options

## Quick Reference

### Essential Settings

```bash
# Minimal .env for functional Phase 2
PUBMED_EMAIL=your-email@example.com
SEARCH_CACHE_ENABLED=true
PDF_DOWNLOAD_TIMEOUT=30
```

### Feature Toggle Checklist

```bash
SEARCH_FEATURE_ENABLED=true         # Phase 2.1 multi-source search
LIBRARY_SOURCES_ENABLED=true        # Phase 2.2 custom sources
EXTENDED_SEARCH_ENABLED=true        # Phase 2.3 advanced filters
DOCUMENT_IMPORT_ENABLED=true        # Phase 2.4 import from search
SEARCH_CACHE_ENABLED=true           # Phase 2.5 caching layer
```

## Phase 2.1: Multi-Source Search Configuration

### External API Configuration

#### PubMed

**Required Settings**:
```bash
# Email is REQUIRED by PubMed API (in User-Agent)
PUBMED_EMAIL=your-email@example.com

# Optional: API key increases rate limit from 3 to 10 req/sec
PUBMED_API_KEY=your_pubmed_api_key

# Rate limiting
PUBMED_RATE_LIMIT_REQUESTS=3        # Default: 3 req/sec without key
PUBMED_RATE_LIMIT_TIMEOUT=1         # Seconds between requests

# Search parameters
PUBMED_SEARCH_TIMEOUT=30            # Seconds per search
PUBMED_RESULTS_PER_PAGE=20          # How many results per page
PUBMED_MAX_RESULTS=100              # Cap total results per search
PUBMED_MIN_PUBLISH_YEAR=2000        # Minimum publication year
```

**Optional Settings**:
```bash
# Authentication (for institutional access)
PUBMED_PROXY_URL=                   # HTTP proxy if needed
PUBMED_USE_PROXY=false              # Enable proxy

# Retry logic
PUBMED_RETRY_COUNT=3                # Failed request retries
PUBMED_RETRY_DELAY=5                # Delay seconds between retries
PUBMED_RETRY_BACKOFF=2              # Exponential backoff factor
```

**Example Configuration**:
```python
# Production
PUBMED_EMAIL=researcher@myorg.com
PUBMED_API_KEY=abc123def456
PUBMED_RATE_LIMIT_REQUESTS=10
PUBMED_SEARCH_TIMEOUT=30

# Development
PUBMED_EMAIL=dev@example.com
PUBMED_API_KEY=
PUBMED_RATE_LIMIT_REQUESTS=3
```

#### arXiv

**Required Settings**:
```bash
# Email (required, but less strict than PubMed)
ARXIV_EMAIL=your-email@example.com

# Category filtering
ARXIV_CATEGORIES=cs,physics         # Comma-separated categories
ARXIV_ENABLE_ALL_CATEGORIES=false   # Or allow all categories
```

**Optional Settings**:
```bash
# Search parameters
ARXIV_SEARCH_TIMEOUT=20             # Seconds per search
ARXIV_RESULTS_PER_PAGE=10           # arXiv typically returns fewer
ARXIV_MAX_RESULTS=50                # Cap total results

# Sorting
ARXIV_DEFAULT_SORT_BY=submittedDate # submittedDate|modifiedDate|relevance
ARXIV_SORT_ORDER=descending         # descending|ascending

# Retry logic
ARXIV_RETRY_COUNT=3
ARXIV_RETRY_DELAY=2
```

**Example Configuration**:
```python
# Production
ARXIV_EMAIL=researcher@myorg.com
ARXIV_CATEGORIES=cs.AI,cs.LG,q-bio.QM
ARXIV_SEARCH_TIMEOUT=20

# Development
ARXIV_EMAIL=dev@example.com
ARXIV_ENABLE_ALL_CATEGORIES=true
```

### Search Engine Configuration

```bash
# Feature enablement
SEARCH_FEATURE_ENABLED=true

# Default behavior
SEARCH_DEFAULT_LIMIT=20             # Results per search
SEARCH_MAX_LIMIT=100                # Maximum allowed
SEARCH_RESULTS_TIMEOUT=30           # Total search timeout

# Deduplication
SEARCH_DEDUP_MODE=default           # default|strict|lenient
SEARCH_DEDUP_TITLE_THRESHOLD=0.95   # Fuzzy match threshold

# Sorting
SEARCH_DEFAULT_SORT=relevance       # relevance|date|title
SEARCH_MIN_SCORE=0                  # Minimum relevance score

# Logging
SEARCH_LOG_LEVEL=INFO               # DEBUG|INFO|WARNING|ERROR
SEARCH_LOG_QUERIES=true             # Log search queries
```

## Phase 2.2: Library Source Configuration

### Source Management

```bash
# Feature enablement
LIBRARY_SOURCES_ENABLED=true

# Source validation
CUSTOM_SOURCE_VALIDATION=true       # Validate on create/update
CUSTOM_SOURCE_HEALTH_CHECK=true     # Regular health checks
CUSTOM_SOURCE_TIMEOUT=10            # Health check timeout

# Maximum sources
SOURCE_MAX_PER_PROJECT=20           # How many custom sources allowed
SOURCE_MAX_HEADERS=10               # Max custom headers per source

# Source caching
SOURCE_CACHE_RESULTS=true           # Cache source responses
SOURCE_CACHE_TTL_HOURS=24           # How long to cache

# Logging
SOURCE_LOG_HEALTH_CHECKS=true       # Log health check results
```

### Built-in Sources

```bash
# Built-in source enablement
PUBMED_SOURCE_ENABLED=true
ARXIV_SOURCE_ENABLED=true
GOOGLE_SCHOLAR_ENABLED=false        # Future

# Built-in source configuration
PUBMED_SOURCE_NAME="National Library of Medicine"
ARXIV_SOURCE_NAME="Cornell University Library"

# Built-in source API keys
PUBMED_API_KEY=                     # See Phase 2.1 section
ARXIV_API_KEY=
```

## Phase 2.3: Extended Search Configuration

### Advanced Filter Configuration

```bash
# Feature enablement
EXTENDED_SEARCH_ENABLED=true

# Filter capabilities
FILTER_MAX_COMPLEXITY=10            # Max filter groups
FILTER_MAX_CONDITIONS=50            # Max total conditions
FILTER_TIMEOUT=5                    # Filter validation timeout

# Supported filters
FILTER_DATE_RANGE_ENABLED=true
FILTER_AUTHOR_ENABLED=true
FILTER_CATEGORY_ENABLED=true
FILTER_SOURCE_TYPE_ENABLED=true
FILTER_CUSTOM_FIELDS_ENABLED=false  # Future

# Date range limits
FILTER_DATE_MIN_YEAR=1900
FILTER_DATE_MAX_YEAR=2100
FILTER_DATE_PRESETS=enabled         # Quick presets (last_30_days, etc)
```

### Sorting & Pagination

```bash
# Pagination
PAGINATION_DEFAULT_PAGE_SIZE=20
PAGINATION_MAX_PAGE_SIZE=100
PAGINATION_MIN_PAGE_SIZE=1

# Sorting
SORT_FIELDS=relevance,date,title,author
SORT_DEFAULT=relevance

# Cache for pagination
PAGINATION_CACHE_ENABLED=true
PAGINATION_CACHE_TTL_MINUTES=30
```

### Faceted Search Configuration

```bash
# Feature enablement
FACETED_SEARCH_ENABLED=true

# Available facets
FACETS_ENABLED=provider,type,access,date
FACETS_MAX_VALUES=100               # Max values per facet

# Facet-specific settings
FACET_DATE_GROUPING=year            # year|month|week|day
FACET_AUTHOR_MAX_RESULTS=10
FACET_CATEGORY_HIERARCHY_ENABLED=true
```

## Phase 2.4: Document Import Configuration

### PDF Download Configuration

```bash
# Feature enablement
DOCUMENT_IMPORT_ENABLED=true

# Download parameters
PDF_DOWNLOAD_TIMEOUT=30             # Seconds per download
PDF_DOWNLOAD_RETRIES=3              # Retry attempts
PDF_DOWNLOAD_RETRY_DELAY=5          # Seconds between retries
PDF_DOWNLOAD_BACKOFF=2              # Exponential backoff factor

# Concurrency
PDF_DOWNLOAD_CONCURRENCY=10         # Parallel downloads
PDF_DOWNLOAD_QUEUE_SIZE=500         # Max queued downloads

# Storage
PDF_STORAGE_PATH=data/projects/{project_id}/documents/
PDF_STORAGE_CLEANUP_ENABLED=true
PDF_STORAGE_CLEANUP_DAYS=90         # Delete older than 90 days
PDF_MAX_SIZE_MB=500                 # Skip large PDFs

# Formats supported
PDF_MIME_TYPES=application/pdf,text/html
PDF_EXTRACT_ENABLED=true            # Extract text from PDF
```

### Import Job Configuration

```bash
# Batch import settings
BATCH_IMPORT_MAX_SIZE=100           # Max documents per batch
BATCH_IMPORT_TIMEOUT=600            # Total timeout for batch
BATCH_IMPORT_PROGRESS_INTERVAL=5    # Update progress every N documents

# Job tracking
JOB_MAX_RETENTION_DAYS=7            # Keep job history for N days
JOB_EMAIL_ON_COMPLETE=true          # Email user when done
JOB_QUEUE_BACKEND=memory            # memory|redis|celery (Phase 1.3)
```

### Import Event Configuration

```bash
# Events
IMPORT_EVENTS_ENABLED=true
IMPORT_FIRE_START_EVENT=true        # import.started
IMPORT_FIRE_COMPLETE_EVENT=true     # import.completed
IMPORT_FIRE_ERROR_EVENT=true        # import.failed

# Event handlers
IMPORT_TRIGGER_EXTRACTION=true      # Auto-trigger hooks
IMPORT_TRIGGER_CACHE_INVALIDATION=true
IMPORT_SEND_USER_NOTIFICATION=true
```

### Document Metadata

```bash
# Metadata extraction
EXTRACT_DOCUMENT_KEYWORDS=true
EXTRACT_DOCUMENT_SUMMARY=false      # Requires AI
EXTRACT_DOCUMENT_ENTITIES=false     # Requires NLP

# Source metadata preservation
PRESERVE_SOURCE_URL=true
PRESERVE_SOURCE_ID=true
PRESERVE_SOURCE_TYPE=true
PRESERVE_IMPORT_TIMESTAMP=true
```

## Phase 2.5: Search Cache Configuration

### Cache Layer Configuration

```bash
# Feature enablement
SEARCH_CACHE_ENABLED=true

# Cache mode
SEARCH_CACHE_MODE=dual              # lru|sqlite|dual (both layers)
SEARCH_CACHE_READONLY=false         # Disable writes (maintenance)

# Cache TTL and cleanup
SEARCH_CACHE_TTL_HOURS=24           # Time to live
SEARCH_CACHE_CLEANUP_INTERVAL_HOURS=6   # Cleanup job frequency
SEARCH_CACHE_CLEANUP_BATCH_SIZE=100     # Items per cleanup batch
```

### In-Memory (LRU) Cache Configuration

```bash
# LRU cache parameters
SEARCH_CACHE_LRU_ENABLED=true
SEARCH_CACHE_LRU_SIZE=100           # Max entries in LRU
SEARCH_CACHE_LRU_EVICTION=lru       # lru|lfu|fifo
SEARCH_CACHE_LRU_MEMORY_LIMIT_MB=500    # Max memory allocation

# Performance
SEARCH_CACHE_LRU_MAX_ENTRY_SIZE_MB=10   # Skip caching large results
```

### Persistent (SQLite) Cache Configuration

```bash
# Database settings
SEARCH_CACHE_DB_PATH=data/cache.db
SEARCH_CACHE_DB_TYPE=sqlite         # sqlite|postgresql
SEARCH_CACHE_DB_HOST=localhost      # For postgresql
SEARCH_CACHE_DB_PORT=5432           # For postgresql
SEARCH_CACHE_DB_USER=               # For postgresql
SEARCH_CACHE_DB_PASSWORD=           # For postgresql

# Connection pooling
SEARCH_CACHE_DB_POOL_SIZE=5
SEARCH_CACHE_DB_POOL_TIMEOUT=30
SEARCH_CACHE_DB_POOL_RECYCLE=3600
```

### Search Index Configuration

```bash
# Indexing
SEARCH_INDEX_ENABLED=true
SEARCH_INDEX_AUTOUPDATE=true        # Update on cache miss
SEARCH_INDEX_REBUILD_INTERVAL_DAYS=7    # Periodic rebuild

# Faceting
SEARCH_FACETS_ENABLED=true
SEARCH_FACETS=provider,type,access,date
SEARCH_FACET_PROVIDER_VALUES=pubmed,arxiv,web
SEARCH_FACET_ACCESS_VALUES=open,restricted,unknown
SEARCH_FACET_TYPE_VALUES=article,preprint,dataset
```

### Cache Statistics & Monitoring

```bash
# Statistics collection
SEARCH_CACHE_STATS_ENABLED=true
SEARCH_CACHE_STATS_INTERVAL_MINUTES=1   # Collect every N minutes

# Metrics
CACHE_HIT_RATE_TARGET=0.4           # Aim for 40% hit ratio
CACHE_MISS_RATE_ALERT=0.9           # Alert if >90% misses

# Logging
CACHE_LOG_HITS=false                # Log cache hits (verbose)
CACHE_LOG_MISSES=true               # Log cache misses
CACHE_LOG_EVICTIONS=true            # Log evictions
CACHE_LOG_STATS_INTERVAL=3600       # Log stats every N seconds
```

## Event Bus Configuration

### Event System Configuration

```bash
# Feature enablement
EVENT_BUS_ENABLED=true

# Event delivery
EVENT_BUS_ASYNC=true                # Async event processing
EVENT_BUS_MAX_RETRIES=3             # Retry failed events
EVENT_BUS_TIMEOUT=30                # Max processing time

# Event queue
EVENT_QUEUE_MAX_SIZE=1000           # Max queued events
EVENT_QUEUE_BATCH_SIZE=10           # Process N at a time
```

### Cache Invalidation Events

```bash
# Automatic invalidation
CACHE_INVALIDATION_ENABLED=true

# Invalidation triggers
INVALIDATE_ON_DOCUMENT_UPLOADED=true
INVALIDATE_ON_DOCUMENT_DELETED=true
INVALIDATE_ON_IMPORT_COMPLETED=true
INVALIDATE_ON_SOURCE_UPDATED=true

# Invalidation scope
INVALIDATE_SCOPE=project            # project|global|query
INVALIDATE_ASYNC=true               # Async invalidation
```

## Database Configuration

### Search Tables Configuration

```bash
# Table management
CREATE_SEARCH_TABLES=true
AUTO_MIGRATE_TABLES=true

# Indexes
CREATE_SEARCH_INDEXES=true
ANALYZE_SEARCH_TABLES=true          # Optimize on startup

# Cleanup
SEARCH_TABLE_CLEANUP_ENABLED=true
SEARCH_RESULT_RETENTION_DAYS=90
INDEX_STALE_RETENTION_DAYS=30
```

### Document Table Extensions

```bash
# Document columns added
ADD_SOURCE_COLUMNS=true
ADD_IMPORT_TIMESTAMP=true

# Backward compatibility
LEGACY_DOCUMENTS_COMPATIBLE=true    # Support old format
```

## Logging Configuration

### Log Levels

```bash
# Application logs
APP_LOG_LEVEL=INFO                  # DEBUG|INFO|WARNING|ERROR|CRITICAL
SEARCH_LOG_LEVEL=INFO
CACHE_LOG_LEVEL=INFO
IMPORT_LOG_LEVEL=INFO
EVENT_LOG_LEVEL=INFO

# Request logging
LOG_HTTP_REQUESTS=true
LOG_HTTP_RESPONSE_BODIES=false      # Verbose, leave disabled
LOG_HTTP_TIMINGS=true               # Log request duration
```

### Log Output

```bash
# Log files
SEARCH_LOG_FILE=logs/search.log
CACHE_LOG_FILE=logs/cache.log
IMPORT_LOG_FILE=logs/import.log
EVENT_LOG_FILE=logs/events.log

# Production vs development
LOG_FORMAT=json                     # json|text
LOG_TO_CONSOLE=true                 # Also print to console
LOG_TO_FILE=true                    # Write to file
LOG_ROTATION_SIZE_MB=100            # Rotate when reaches 100MB
LOG_RETENTION_DAYS=30               # Keep logs for 30 days
```

## Security Configuration

### API Key Management

```bash
# Encryption
ENCRYPT_API_KEYS=true
API_KEY_ENCRYPTION_KEY=<your-key>   # 32-char minimum

# Key rotation
API_KEY_ROTATION_ENABLED=true
API_KEY_ROTATION_INTERVAL_DAYS=90
```

### Rate Limiting

```bash
# Global rate limits
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Per-user limits
RATE_LIMIT_PER_USER=true
RATE_LIMIT_USER_REQUESTS_PER_DAY=5000

# Source-specific limits
PUBMED_RATE_LIMIT_REQUESTS=3        # Req/sec
ARXIV_RATE_LIMIT_REQUESTS=2         # Req/sec
```

### Access Control

```bash
# Authentication
REQUIRE_AUTH=true                   # Require JWT token
REQUIRE_PROJECT_OWNERSHIP=true      # Verify project access

# CORS
CORS_ENABLED=true
CORS_ORIGINS=http://localhost:3000,https://example.com
```

## Performance Tuning

### Search Performance

```bash
# Timeout settings
SEARCH_TIMEOUT=30                   # Total search timeout
SOURCE_TIMEOUT=15                   # Individual source timeout
DEDUP_TIMEOUT=5                     # Deduplication timeout

# Result limiting
SEARCH_MAX_RESULTS=100              # Max returned
SEARCH_MIN_LIMIT=1
SEARCH_DEFAULT_LIMIT=20
```

### Cache Performance

```bash
# Cache sizing
CACHE_LRU_SIZE=100                  # More = better hit rate, more RAM
CACHE_DB_BATCH_SIZE=50              # Batch insert size

# Performance metrics
CACHE_REF_TIME_MS=1                 # Reference time (used in calcs)
CACHE_HIT_TIME_MS=0                 # Cache hit latency
CACHE_MISS_TIME_MS=500              # Uncached search latency
```

### Database Performance

```bash
# Connection pool
DB_POOL_SIZE=5
DB_POOL_TIMEOUT=30
DB_ECHO=false                       # Log SQL queries (debug)

# Indexes
AUTO_CREATE_INDEXES=true
AUTO_ANALYZE_TABLES=true            # ANALYZE after changes
```

## Environment-Specific Configurations

### Development Environment

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
TESTING=false

PUBMED_EMAIL=dev@example.com
PUBMED_API_KEY=                     # None for dev
ARXIV_EMAIL=dev@example.com

SEARCH_CACHE_ENABLED=true           # Test caching
SEARCH_CACHE_TTL_HOURS=1            # Short TTL for dev

PDF_DOWNLOAD_TIMEOUT=10             # Shorter for testing
PDF_MAX_SIZE_MB=5                   # Limit size in dev

LOG_LEVEL=DEBUG
LOG_TO_CONSOLE=true
LOG_HTTP_RESPONSE_BODIES=true       # OK in dev

SEARCH_CACHE_DB_PATH=data/cache_dev.db
```

### Testing Environment

```bash
# .env.test
ENVIRONMENT=testing
DEBUG=false
TESTING=true

# Mocked external APIs
PUBMED_EMAIL=test@example.com
PUBMED_API_KEY=mock_key_12345
ARXIV_EMAIL=test@example.com

# Disabled features for speed
SEARCH_CACHE_ENABLED=true           # Test caching
SEARCH_CACHE_TTL_HOURS=0            # No cache expiry
SEARCH_INDEX_ENABLED=false          # Disable indexing in tests

PDF_DOWNLOAD_ENABLED=false          # Mock downloads
PDF_DOWNLOAD_TIMEOUT=1              # Fail fast

CACHE_CLEANUP_INTERVAL_HOURS=999    # Skip cleanup in tests

LOG_LEVEL=ERROR                     # Only errors
SEARCH_CACHE_DB_PATH=:memory:       # In-memory SQLite for tests
```

### Production Environment

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
TESTING=false

PUBMED_EMAIL=researcher@myorg.com
PUBMED_API_KEY=<prod_key>           # Real API key
ARXIV_EMAIL=researcher@myorg.com

SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_TTL_HOURS=24
SEARCH_CACHE_CLEANUP_INTERVAL_HOURS=6

PDF_DOWNLOAD_TIMEOUT=30
PDF_DOWNLOAD_CONCURRENCY=10         # More parallel downloads
PDF_DOWNLOAD_RETRIES=5              # More retries for reliability
PDF_MAX_SIZE_MB=500

CACHE_LOG_HITS=false                # Don't log hits (spam)
CACHE_LOG_MISSES=true

LOG_LEVEL=INFO
LOG_TO_FILE=true
LOG_RETENTION_DAYS=90

SEARCH_CACHE_DB_PATH=/var/lib/beep/cache.db
```

## Configuration Validation

### Checking Configuration

```bash
# Validate configuration
python -c "from app import app; print('Config valid')"

# View active configuration
python scripts/print_config.py

# Check required settings
python scripts/check_required_config.py
```

### Common Configuration Errors

| Error | Cause | Solution |
|-------|-------|----------|
| PUBMED_EMAIL not configured | Missing env var | Set PUBMED_EMAIL |
| Cache table not found | Migration not run | Run: python -m flask db upgrade |
| PDF download timeouts | Timeout too short | Increase PDF_DOWNLOAD_TIMEOUT |
| High memory usage | LRU too large | Reduce SEARCH_CACHE_LRU_SIZE |
| Import not triggering | Events disabled | Set IMPORT_EVENTS_ENABLED=true |

## Configuration Examples

### Minimal Configuration (Development)

```bash
# .env.minimal
PUBMED_EMAIL=dev@example.com
SEARCH_CACHE_ENABLED=true
PDF_DOWNLOAD_TIMEOUT=30
```

### Full Configuration (Production)

See **Configuration Templates** section below (2000+ lines of actual config files).

### Custom Configuration (Enterprise)

```bash
# Custom setup with multiple sources, fine-tuned caching
PUBMED_EMAIL=org@example.com
PUBMED_API_KEY=prod_key_xyz
ARXIV_EMAIL=org@example.com

# Custom library sources enabled
LIBRARY_SOURCES_ENABLED=true
SOURCE_MAX_PER_PROJECT=50

# Optimized caching
SEARCH_CACHE_LRU_SIZE=200           # More hot queries
SEARCH_CACHE_TTL_HOURS=48           # Longer retention
PDF_DOWNLOAD_CONCURRENCY=20         # More parallel downloads

# Enhanced monitoring
CACHE_LOG_STATS_INTERVAL=600        # Every 10 mins
SEARCH_INDEX_REBUILD_INTERVAL_DAYS=1  # Daily rebuild
```

## Related Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md) - How to apply these settings
- [Phase 2 Complete Guide](PHASE_2_COMPLETE.md) - Feature overview
- [Caching Guide](CACHING_INDEXING_GUIDE.md) - Cache-specific settings

## Support

For configuration help:
1. Check examples above for your use case
2. Review Phase-specific guides
3. Check logs for error messages
4. Contact dev-team@example.com

---

**Last Updated**: February 7, 2026  
**Version**: 1.0  
**Status**: COMPLETE
