# Phase 2: Deployment Guide

**Version**: 1.0 | **Last Updated**: February 7, 2026  
**Scope**: Deploying Phase 2 (2.1-2.5) to production environments

## Overview

This guide provides step-by-step procedures for deploying the Phase 2 search and document management system to production. It covers database migration, configuration, testing, and rollout procedures.

## Prerequisites

### System Requirements

- Python 3.8+
- PostgreSQL 12+ or SQLite 3.30+
- 4GB RAM minimum (8GB recommended)
- 50GB disk space (for document storage)
- Network access to external APIs (PubMed, arXiv)

### Software Requirements

- Flask 2.0+
- SQLAlchemy 1.4+
- Requests 2.25+
- pytest for testing
- Git for version control

### Knowledge Requirements

- Basic Flask/Python knowledge
- Database administration
- Linux/Windows command line
- API key management

### Pre-Deployment Checklist

- [ ] Phase 1 fully deployed and verified
- [ ] Backup of existing database completed
- [ ] All team members notified of deployment plan
- [ ] Staging environment available for testing
- [ ] Production database access verified
- [ ] API keys obtained (PubMed, arXiv, etc)
- [ ] SSL/TLS certificates in place
- [ ] Monitoring tools configured

## Step 1: Database Migration

### 1.1 Create Backup

**Protect existing data before any changes:**

```bash
# PostgreSQL
pg_dump -h localhost -U researcher_user -d beep_researcher > backup_before_phase2.sql

# SQLite
cp data/researcher.db data/researcher.db.backup
```

### 1.2 Create New Tables

Run migration scripts to create Phase 2 tables:

```bash
# In project root
python -m flask db upgrade

# Or manually:
python scripts/create_phase2_tables.py
```

**Tables created**:
- `search_results` - Phase 2.1 search caching
- `library_sources` - Phase 2.2 custom sources
- `search_sessions` - Phase 2.3 workflow tracking
- `search_cache` - Phase 2.5 query caching
- `search_index` - Phase 2.5 result analytics

### 1.3 Add Columns to Existing Tables

Researcher documents table extended with:

```sql
ALTER TABLE researcher_documents ADD COLUMN source_type VARCHAR(50);
ALTER TABLE researcher_documents ADD COLUMN source_id VARCHAR(255);
ALTER TABLE researcher_documents ADD COLUMN source_url VARCHAR(2048);
ALTER TABLE researcher_documents ADD COLUMN imported_at TIMESTAMP;
```

### 1.4 Create Indexes

Optimize query performance:

```sql
-- Search cache indexes
CREATE INDEX idx_search_cache_project_provider ON search_cache(project_id, provider);
CREATE INDEX idx_search_cache_query_hash ON search_cache(query_hash);
CREATE INDEX idx_search_cache_expires ON search_cache(expires_at);

-- Library sources indexes
CREATE INDEX idx_library_sources_project ON library_sources(project_id);
CREATE INDEX idx_library_sources_type ON library_sources(provider_type);

-- Search index indexes
CREATE INDEX idx_search_index_project_provider ON search_index(project_id, provider);
CREATE INDEX idx_search_index_publication_date ON search_index(publication_date);
CREATE FULLTEXT INDEX idx_search_index_full_text ON search_index(title, authors);
```

### 1.5 Verify Migration

```bash
# Check tables exist
python -c "from app.database import db; from app.models import *; db.inspect()"

# Run test queries
python scripts/verify_migration.py
```

**Expected output**:
```
✓ search_results table exists
✓ library_sources table exists
✓ search_cache table exists
✓ search_index table exists
✓ All indexes created
✓ Migration complete
```

## Step 2: Configuration

### 2.1 Environment Variables

Create `.env` file with Phase 2 settings:

```bash
# Search Configuration (Phase 2.1)
PUBMED_EMAIL=your-email@example.com
PUBMED_API_KEY=                  # Optional, increases rate limit
ARXIV_EMAIL=your-email@example.com

# Library Source Configuration (Phase 2.2)
DEFAULT_LIBRARY_SOURCES_ENABLED=true
CUSTOM_SOURCE_VALIDATION=true

# Document Import Configuration (Phase 2.4)
PDF_DOWNLOAD_TIMEOUT=30
PDF_DOWNLOAD_RETRIES=3
PDF_STORAGE_PATH=data/projects/{project_id}/documents/
PDF_MAX_SIZE_MB=500

# Cache Configuration (Phase 2.5)
SEARCH_CACHE_ENABLED=true
SEARCH_CACHE_TTL_HOURS=24
SEARCH_CACHE_LRU_SIZE=100
SEARCH_CACHE_CLEANUP_INTERVAL_HOURS=6

# Event Configuration (Phase 1.1)
EVENT_BUS_ENABLED=true
CACHE_INVALIDATION_ENABLED=true

# Logging
PHASE2_LOG_LEVEL=INFO
PHASE2_LOG_FILE=logs/phase2.log
```

### 2.2 Load Configuration

Ensure configuration loads in app startup:

```python
# app/__init__.py
import os
from dotenv import load_dotenv

load_dotenv()

# Verify critical settings
required_settings = [
    'PUBMED_EMAIL',
    'SEARCH_CACHE_ENABLED'
]

for setting in required_settings:
    if not os.getenv(setting):
        print(f"WARNING: {setting} not configured")
```

### 2.3 Create Configuration Reference

Document all settings used:

```bash
python scripts/generate_config_reference.py
# Generates docs/CONFIGURATION_USED.md with actual values (sanitized)
```

## Step 3: Testing in Staging

### 3.1 Deploy to Staging

```bash
# Clone and setup
git clone <repo> /opt/staging/beep-researcher
cd /opt/staging/beep-researcher
git checkout phase-2.5

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Setup database
python -m flask db upgrade
python scripts/seed_staging_data.py
```

### Startup Dependency and Schema Bootstrap

`run.py`, `run.bat`, and `run.sh` start the application from the active Python environment. On Windows, `run.bat` downloads Python Embedded only to create and run the local `.venv`; runtime packages are installed into that `.venv`, not into the Python Embedded directory and not into the system Python.

At app startup, `startup_dependency_bootstrap.py` reads `requirements.txt`, checks installed distributions, and installs missing packages with the active interpreter (`sys.executable -m pip install <requirement>`). The default is enabled through `auto_install_requirements_on_startup=true`; set `AUTO_INSTALL_REQUIREMENTS_ON_STARTUP=0` to disable it. If required packages remain missing or an install fails, startup exits instead of running with a partial document-management stack.

Database startup is handled by `app/services/startup/database_bootstrap.py`. It imports all SQLAlchemy models, runs `db.create_all()` for missing tables, applies additive startup migrations for quota, document extraction, RAG sync, and ingestion tracking columns, and seeds the default plan tiers. Alembic migrations remain the production migration path, but the startup bootstrap protects fresh local installs and older development databases.

### 3.2 Run Full Test Suite

Verify all Phase 2 functionality:

```bash
# Run all tests
pytest tests/ -v --tb=short

# Expected: 318 tests pass
# Tests should include: 
# - 37 Phase 2.1 search tests
# - 20 Phase 2.2 library source tests
# - 62 Phase 2.3 extended search tests
# - 2 Phase 2.4 import tests
# - 22 Phase 2.5 cache tests
```

### 3.3 Performance Testing

Verify caching performance:

```bash
# Run performance tests
pytest tests/test_search_caching.py::TestCachePerformance -v

# Expected results:
# Cache miss (uncached): 1-5 seconds
# Cache hit (LRU): <1 millisecond
# Cache hit (DB): 10-50 milliseconds
# Improvement: 100-5000x
```

### 3.4 Load Testing

Test concurrent request handling:

```bash
# Install load testing tools
pip install locust

# Run load test
locust -f tests/load_test_search.py -u 100 -r 10 --run-time 60s

# Expected: Handles 100 concurrent users, P95 latency <5s
```

### 3.5 Integration Testing

Test Phase 1 + Phase 2 integration:

```bash
# Test EventBus integration
python tests/test_integration_eventbus.py -v

# Test JobQueue integration (PDF downloads)
python tests/test_integration_jobqueue.py -v

# Test Hooks integration (extraction on import)
python tests/test_integration_hooks.py -v
```

### 3.6 Staging Sign-off

Verify staging meets requirements:

```bash
# Checklist
python scripts/staging_checklist.py

Expected output:
✓ All 318 tests passing
✓ Database migration successful
✓ Configuration loaded
✓ EventBus initialized
✓ PDF download handler registered
✓ Cache manager initialized
✓ API endpoints responding
✓ Performance benchmarks met
✓ No errors in logs
→ READY FOR PRODUCTION
```

## Step 4: Production Rollout

### 4.1 Pre-Rollout Verification

**24 hours before rollout:**

```bash
# Final backup
pg_dump -h prod-db -U researcher_user -d beep_researcher > \
  backup_before_phase2_$(date +%Y%m%d).sql

# System capacity check
df -h /data/projects/                    # Disk space
free -h                                  # Memory
ps aux | grep flask                      # Running processes
```

### 4.2 Deployment Steps

**For zero-downtime deployment:**

1. **Deploy new code** (while old system running)

```bash
cd /opt/production/beep-researcher
git fetch origin
git checkout phase-2.5
git pull

# Install new dependencies
source venv/bin/activate
pip install -r requirements.txt
```

2. **Run database migration** (may cause brief lock)

```bash
# Create migration checkpoint
python -m flask db branch phase-2-checkpoint

# Run migration
python -m flask db upgrade

# Verify migration
python scripts/verify_migration.py
```

3. **Validate configuration**

```bash
# Check all required settings present
python -c "from app import app; print('Configuration valid')"
```

4. **Restart application** (brief downtime ~10 seconds)

```bash
# Stop old process gracefully
kill -TERM $(pgrep -f 'flask run')
sleep 5

# Start new process
PORT=5000 python -m flask run &

# Verify startup
sleep 5
curl http://localhost:5000/health
```

5. **Verify services**

```bash
# Check API endpoints
curl http://localhost:5000/projects/1/search?query=test
curl http://localhost:5000/projects/1/library-sources
curl http://localhost:5000/projects/1/cache/stats

# Check database
python scripts/health_check.py
```

### 4.3 Health Checks

**Monitor system during rollout:**

```bash
# Real-time monitoring
watch 'ps aux | grep flask; curl http://localhost:5000/health'

# Log monitoring
tail -f logs/phase2.log
tail -f logs/app.log

# Database monitoring
python scripts/monitor_db.py
```

**Expected output**:
```
API Status: ✓ OK
Database: ✓ Connected
Cache: ✓ Initialized
EventBus: ✓ Running
PDFHandler: ✓ Registered
Response time: 150ms avg
Memory: 45% used
Disk: 30% used
```

### 4.4 Phased Rollout (Recommended)

For high-traffic production, use phased approach:

**Phase 1: 5% Traffic (1 hour)**
```
- Route 5% of search requests to Phase 2
- Monitor error rate (should be <0.1%)
- Check response times
```

**Phase 2: 25% Traffic (2 hours)**
```
- Increase to 25% if Phase 1 successful
- Monitor cache hit ratio (should be >40%)
- Check import success rate
```

**Phase 3: 100% Traffic (immediate)**
```
- If 25% phase successful, go full
- Run smoke tests
- Verify all users can access
```

## Step 5: Post-Deployment

### 5.1 Validation

Verify Phase 2 working correctly:

```bash
# API validation
python scripts/api_validation.py

# Expected: All 50+ endpoints responding

# Data validation
python scripts/data_validation.py

# Expected: No orphaned records, data integrity

# Performance validation
python scripts/performance_validation.py

# Expected: Cache hit ratio >40%, avg response <500ms
```

### 5.2 Monitoring Setup

Configure alerts and dashboards:

```bash
# Metrics to monitor
- Search cache hit ratio (target: >40%)
- PDF download success rate (target: >95%)
- API response time P95 (target: <5s)
- Database size (alert if >90GB)
- Error rate (alert if >1%)

# Setup alerts
python scripts/setup_monitoring.py

# View dashboards
Open: http://localhost:8080/grafana (or your monitoring tool)
```

### 5.3 Documentation Update

Update operational documentation:

- [ ] Update README with Phase 2 features
- [ ] Document any custom configurations
- [ ] Update runbook with Phase 2 procedures
- [ ] Create on-call guide for common issues
- [ ] Document API keys locations and access

### 5.4 Team Notification

Communicate deployment to stakeholders:

**Email Template**:
```
Subject: Phase 2 Deployment Complete - New Features Available

Team,

Phase 2 (Search & Document Management) is now live in production.

NEW CAPABILITIES:
✓ Multi-source search (PubMed, arXiv, custom)
✓ Advanced filtering and faceting
✓ Automatic document import from search results
✓ Intelligent result caching (100-5000x faster)

USAGE:
- See PHASE_2_COMPLETE.md for overview
- API docs: /docs/api/phase-2
- Support: dev-team@example.com

PERFORMANCE IMPROVEMENTS:
- Repeat searches: 1-5s → <1ms (100-5000x faster)
- Cache hit ratio: ~40%
- Document import: Automatic PDF download

Please test and provide feedback.

---
Deployment Team
```

## Step 6: Rollback Procedure

In case of critical issues, rollback to Phase 1:

### 6.1 Identify Issues

```bash
# Check error rate
curl http://localhost:5000/health
# If response indicates errors, proceed with rollback

# Check logs
grep ERROR logs/phase2.log
grep CRITICAL logs/app.log
```

### 6.2 Rollback Steps

```bash
# 1. Stop current process
kill -TERM $(pgrep -f 'flask run')

# 2. Restore code to Phase 1
cd /opt/production/beep-researcher
git checkout phase-1.5
git pull

# 3. Restore database (if needed)
psql -h prod-db -U researcher_user -d beep_researcher < backup_before_phase2_*.sql

# 4. Restart application
source venv/bin/activate
python -m flask run &

# 5. Verify rollback
sleep 5
curl http://localhost:5000/health
```

### 6.3 Post-Rollback

- Document what failed
- Create incident report
- Plan fixes for re-deployment
- Notify stakeholders

## Common Issues & Solutions

### Issue 1: PDF Download Failing

**Symptoms**: import.completed not firing, PDFs not saved

**Diagnosis**:
```bash
# Check PDF handler registered
python -c "from app.jobs import pdf_download_handler; print('OK')"

# Check logs
grep pdf_download logs/phase2.log

# Test PDF download
curl -I https://www.example.com/sample.pdf
```

**Solutions**:
1. Verify PDF URLs are accessible
2. Check PDF_DOWNLOAD_TIMEOUT setting
3. Verify storage directory writable
4. Check network connectivity

### Issue 2: Cache Not Working

**Symptoms**: Every search takes 1-5 seconds, cache stats show 0%

**Diagnosis**:
```bash
# Check cache enabled
python -c "from app.config import SEARCH_CACHE_ENABLED; print(SEARCH_CACHE_ENABLED)"

# Check cache table exists
python -c "from app.models import SearchCache; print(SearchCache.__tablename__)"

# Check cache stats
curl http://localhost:5000/projects/1/cache/stats
```

**Solutions**:
1. Verify SEARCH_CACHE_ENABLED=true
2. Check database migration completed
3. Restart application
4. Clear cache: POST /projects/1/cache/clear

### Issue 3: High Memory Usage

**Symptoms**: Memory increasing, no cache cleanup

**Diagnosis**:
```bash
# Check memory
free -h

# Check cache size
curl http://localhost:5000/projects/1/cache/stats | jq '.total_entries'

# Check process memory
ps aux | grep flask | grep -v grep
```

**Solutions**:
1. Reduce SEARCH_CACHE_LRU_SIZE
2. Reduce SEARCH_CACHE_TTL_HOURS
3. Run cache cleanup: POST /projects/1/cache/expired/clean
4. Increase server RAM

### Issue 4: EventBus Not Triggering

**Symptoms**: Cache not invalidating, PDFs not triggering hooks

**Diagnosis**:
```bash
# Check EventBus initialized
python -c "from app.core.event_bus import EventBus; print('OK')"

# Check handlers registered
grep "register_cache_invalidation_handlers" app/__init__.py

# Check logs for event processing
grep -i event logs/phase2.log
```

**Solutions**:
1. Restart application (handlers re-register)
2. Verify EVENT_BUS_ENABLED=true
3. Check Python error logs
4. Verify event types match (see EVENT_BUS_GUIDE.md)

## Performance Tuning

### Optimize Cache

```python
# In settings
SEARCH_CACHE_LRU_SIZE = 100      # Increase for more hot queries
SEARCH_CACHE_TTL_HOURS = 24      # Decrease for fresher data
SEARCH_CACHE_CLEANUP_INTERVAL_HOURS = 6
```

### Optimize Database

```sql
-- Add more indexes for common queries
CREATE INDEX idx_search_index_type_provider ON search_index(result_type, provider);
ANALYZE search_cache;
ANALYZE search_index;
```

### Optimize PDF Downloads

```python
# Increase parallel downloads
PDF_DOWNLOAD_CONCURRENCY = 10    # default

# Increase timeout for large PDFs
PDF_DOWNLOAD_TIMEOUT = 60        # seconds
```

## Security Considerations

### API Keys

- [ ] Store all API keys in environment variables (not code)
- [ ] Rotate API keys every 90 days
- [ ] Use separate keys for staging/production
- [ ] Audit API key usage logs monthly

### Database Access

- [ ] Use separate database credentials for production
- [ ] Enable database audit logging
- [ ] Restrict access to backup files
- [ ] Use TLS for database connections

### PDF Storage

- [ ] Store PDFs outside web root
- [ ] Use read-only access where possible
- [ ] Scan PDFs for malware
- [ ] Audit access logs

## Support & Troubleshooting

### Getting Help

**For deployment issues**:
1. Check this guide's troubleshooting section
2. Review logs in `logs/phase2.log`
3. Run health check: `python scripts/health_check.py`
4. Contact dev-team@example.com with:
   - Error log excerpts
   - Health check output
   - System information

### Escalation Path

- Level 1: Check logs and health
- Level 2: Review recent changes
- Level 3: Consult deployment guide
- Level 4: Rollback and investigate

## Appendix: Scripts Reference

### Migration and Deployment Scripts

```bash
# Setup
python scripts/create_phase2_tables.py      # Create tables
python scripts/verify_migration.py          # Verify migration
python scripts/seed_staging_data.py        # Add test data

# Validation
python scripts/api_validation.py            # Test all endpoints
python scripts/data_validation.py          # Check data integrity
python scripts/performance_validation.py   # Verify performance

# Monitoring
python scripts/health_check.py             # Quick health check
python scripts/monitor_db.py               # Database monitoring
python scripts/staging_checklist.py        # Pre-rollout checklist
```

### Configuration Scripts

```bash
# Generate reference
python scripts/generate_config_reference.py  # List all settings
python scripts/setup_monitoring.py           # Setup monitoring

# Database
python scripts/backup_database.py            # Create backup
python scripts/restore_database.py <file>   # Restore backup
```

---

**Related Documentation**:
- [Phase 2 Complete Guide](PHASE_2_COMPLETE.md)
- [Phase 2.5 Caching Guide](CACHING_INDEXING_GUIDE.md)
- [Configuration Reference](CONFIGURATION_REFERENCE.md)

**Last Updated**: February 7, 2026  
**Version**: 1.0  
**Status**: COMPLETE
