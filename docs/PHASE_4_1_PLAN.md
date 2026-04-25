# Phase 4.1: References & Citation Management - Implementation Plan

**Date**: February 8, 2026  
**Status**: PLANNING  
**Estimated Duration**: 2-3 weeks  
**Deliverables**: 1,200+ lines of code | 15+ tests | 300+ lines of documentation

---

## 📋 Overview

Phase 4.1 adds comprehensive bibliographic reference management and citation formatting to Beep.AI.Researcher. Enables researchers to:
- Import references from BibTeX, RIS, and JSON formats
- Link documents to references for citation tracking
- Export citations in multiple academic formats (APA, MLA, Chicago, BibTeX, RIS, JSON)
- Monitor research coverage with citation statistics

---

## 🎯 Phase Scope

### Core Models (TBD: ~200 lines)
1. **Reference Model** - Bibliographic reference storage
2. **CitationFormat Model** - Citation formatting templates
3. **DocumentReference Model** - Document-to-reference linking

### Service Layer (TBD: ~300 lines)
1. **ReferenceService** - CRUD and business logic
2. **CitationFormatterService** - Format conversion (APA, MLA, Chicago, BibTeX, RIS)
3. **ReferenceImportService** - Import from external formats

### API Routes (TBD: ~350 lines)
1. **Reference CRUD endpoints** - Create, read, update, delete references
2. **Reference linking endpoints** - Link/unlink documents
3. **Import/export endpoints** - Bulk operations and format conversion
4. **Citation statistics endpoints** - Reference usage and coverage tracking

### Tests (TBD: ~250 lines, 15+ tests)
1. **Model tests** - Reference, CitationFormat, DocumentReference
2. **Service tests** - CRUD, import/export, formatting
3. **Route tests** - Endpoints with auth and validation
4. **Integration tests** - Full workflow scenarios

---

## 📐 Architecture Design

### Database Schema

```
references
├── id (PK)
├── project_id (FK)
├── title (str)
├── authors (JSON)
├── year (int)
├── source (str)
├── doi (str, optional)
├── url (str, optional)
├── source_type (enum: journal, book, website, conference, other)
├── citation_key (str, unique per project)
├── abstract (text)
├── keywords (JSON)
├── metadata (JSON)
├── created_at
├── updated_at

document_references (M2M)
├── id (PK)
├── document_id (FK)
├── reference_id (FK)
├── citation_context (str, optional - where reference is cited)
├── confidence (float, optional - auto-calculated citation strength)
├── created_at
```

### Class Hierarchy

**Reference Model**
```
class Reference(db.Model):
    id : int
    project_id : int
    title : str
    authors : List[str]  # JSON stored
    year : Optional[int]
    source : str
    doi : Optional[str]
    url : Optional[str]
    source_type : ReferenceSourceType  # enum
    citation_key : str
    abstract : Optional[str]
    keywords : List[str]  # JSON stored
    metadata : Dict  # JSON for extensibility
    documents : Relationship  # DocumentReference
    
    methods:
    - to_bibtex() -> str
    - to_ris() -> str
    - to_apa() -> str
    - to_mla() -> str
    - to_chicago() -> str
    - to_json() -> Dict
    - to_dict() -> Dict
    - from_bibtex(str) -> Reference  (static)
    - from_ris(str) -> Reference  (static)
    - from_json(dict) -> Reference  (static)
```

**DocumentReference Model**
```
class DocumentReference(db.Model):
    id : int
    document_id : int
    reference_id : int
    citation_context : Optional[str]
    confidence : Optional[float]  # 0-1
    created_at : datetime
    
    relationships:
    - document : Document
    - reference : Reference
```

---

## 📅 Implementation Schedule

### Stage 1: Models & Database (Day 1-2)
- [ ] Create Reference model with all fields and methods
- [ ] Create DocumentReference linking model
- [ ] Create ReferenceSourceType enum
- [ ] Add database migration for reference tables
- [ ] Write model tests (6 tests)

**Files**: `app/models/researcher/references.py` (200 lines)

### Stage 2: Services (Day 2-3)
- [ ] Create ReferenceService (CRUD, query)
- [ ] Create CitationFormatterService (5 format converters)
- [ ] Create ReferenceImportService (BibTeX, RIS, JSON)
- [ ] Write service tests (6 tests)

**Files**: 
- `app/services/reference.py` (250 lines)
- `app/services/citation_formatter.py` (200 lines)
- `app/services/reference_import.py` (150 lines)

### Stage 3: API Routes (Day 3-4)
- [ ] CRUD endpoints (5 routes)
- [ ] Document linking endpoints (3 routes)
- [ ] Import/export endpoints (4 routes)
- [ ] Citation format endpoints (2 routes)
- [ ] Write route tests (8 tests)

**Files**: `app/routes/references.py` (350 lines)

### Stage 4: Integration & Testing (Day 5)
- [ ] Integration tests (3 tests)
- [ ] Documentation update
- [ ] TODO.md phase completion

---

## 🔌 API Endpoint Specification

### CRUD Operations

**List References**
```
GET /projects/<project_id>/references
Query params: page=1, per_page=20, sort_by=created_at, search=""
Response: {
  references: [...],
  total: int,
  page: int
}
```

**Get Reference Detail**
```
GET /projects/<project_id>/references/<reference_id>
Response: Reference object with linked documents
```

**Create Reference**
```
POST /projects/<project_id>/references
Body: {
  title: str,
  authors: [str],
  year: int,
  source: str,
  source_type: enum,
  citation_key: str,
  abstract: str,
  metadata: dict
}
Response: Created Reference object
```

**Update Reference**
```
PUT /projects/<project_id>/references/<reference_id>
Body: Partial Reference fields
Response: Updated Reference object
```

**Delete Reference**
```
DELETE /projects/<project_id>/references/<reference_id>
Response: 204 No Content or {success: true}
```

### Document Linking

**Link Document to Reference**
```
POST /projects/<project_id>/references/<reference_id>/documents
Body: {
  document_id: int,
  citation_context: str (optional),
  confidence: float (optional)
}
Response: DocumentReference object
```

**Get Documents Citing Reference**
```
GET /projects/<project_id>/references/<reference_id>/documents
Response: [DocumentReference objects with Document data]
```

**Remove Document Link**
```
DELETE /projects/<project_id>/references/<reference_id>/documents/<document_id>
Response: 204 No Content
```

### Import/Export Operations

**Bulk Import References**
```
POST /projects/<project_id>/references/import
Body: {
  format: enum (bibtex, ris, json),
  content: str
}
Response: {
  imported_count: int,
  skipped_count: int,
  errors: [str]
}
```

**Export References**
```
POST /projects/<project_id>/references/export
Body: {
  format: enum (bibtex, ris, apa, mla, chicago, json),
  reference_ids: [int] (optional - all if not provided),
  include_abstracts: bool (optional)
}
Response: Downloaded file or JSON response
```

### Citation Statistics

**Get Citation Statistics**
```
GET /projects/<project_id>/references/statistics
Response: {
  total_references: int,
  total_citations: int,
  avg_citations_per_ref: float,
  source_type_distribution: {enum: count}
}
```

---

## 🧪 Test Strategy

### Model Tests (6 tests)
1. Reference model creation with required fields
2. Reference model with optional fields
3. Reference to_dict() and from_dict()
4. Reference format conversions (to_bibtex, to_ris, to_apa, to_mla, to_chicago, to_json)
5. DocumentReference model creation
6. DocumentReference relationships (document, reference)

### Service Tests (6 tests)
1. ReferenceService CRUD operations
2. ReferenceService search and filtering
3. CitationFormatterService - all format conversions
4. ReferenceImportService - BibTeX parsing
5. ReferenceImportService - RIS parsing
6. ReferenceImportService - JSON parsing

### Route Tests (8 tests)
1. POST /references - Create reference
2. GET /references - List with pagination
3. GET /references/<id> - Get detail
4. PUT /references/<id> - Update reference
5. DELETE /references/<id> - Delete reference
6. POST /references/<id>/documents - Link document
7. GET /references/<id>/documents - Get linked documents
8. POST /references/import - Bulk import

### Integration Tests (3 tests)
1. Full CRUD workflow - Create → Read → Link Document → Update → Delete
2. Import BibTeX → Link to Documents → Export APA
3. Citation statistics calculation after linking multiple documents

**Total Tests**: 15+ unit + integration tests

---

## 🔄 Existing Pattern Adherence

Following established patterns from Phase 3.6-3.7:

1. **Model Structure**
   - Inherit from db.Model base class
   - Include relationships using db.ForeignKey
   - Implement to_dict(), to_json(), from_dict() methods
   - Store complex data as JSON (authors, keywords, metadata)

2. **Service Layer**
   - Single responsibility principle (one service per concern)
   - Use dependency injection for database access
   - Async-ready method signatures
   - Error handling with custom exceptions

3. **Route Structure**
   - Flask blueprint with resource grouping
   - Auth checks via @auth_required decorator
   - Request validation with Joi-like schemas
   - EventBus integration for reference changes
   - Pagination and filtering support

4. **Testing**
   - TDD approach (tests written alongside code)
   - Use app_context fixture from conftest.py
   - Database cleanup between tests
   - Mock external services (reference lookups)

---

## 📦 Dependencies

### Existing (already available)
- Flask, Flask-SQLAlchemy (ORM)
- pytest-asyncio (testing)
- SQLite (database)

### To Install (if needed)
- `bibtexparser` - For BibTeX parsing/generation
- `pyris` - For RIS format support (or custom RIS parser)

### Custom Implementation (no external deps)
- APA/MLA/Chicago formatting (custom parser, ~100 lines)
- Citation key generation (custom function)

---

## 🎯 Success Criteria

- [x] Phase 4.1 plan document created
- [ ] All 3 model files created and tested (6 tests)
- [ ] All 3 service files created and tested (6 tests)
- [ ] Reference routes file created and tested (8 tests)
- [ ] 15+ tests at 100% pass rate
- [ ] 1,200+ lines of production code
- [ ] All API endpoints working with auth and pagination
- [ ] Import/export for BibTeX, RIS, JSON, APA, MLA, Chicago
- [ ] Document linking and citation statistics
- [ ] TODO.md updated with Phase 4.1 completion details

---

## 🚀 Next Steps

1. **Begin Model Implementation** (Stage 1)
   - Create `app/models/researcher/references.py`
   - Define Reference model with format conversion methods
   - Define DocumentReference linking model
   - Write model tests

2. **Implement Services** (Stage 2)
   - Create citation formatting service
   - Create reference import service
   - Create reference CRUD service
   - Write service tests

3. **Build API Routes** (Stage 3)
   - Create reference blueprint
   - Implement all CRUD endpoints
   - Implement document linking endpoints
   - Implement import/export endpoints
   - Write route tests

4. **Validation & Documentation** (Stage 4)
   - Run full test suite (15+ tests at 100%)
   - Update TODO.md
   - Create completion report

---

## 📊 Metrics & Tracking

| Metric | Target | Current |
|--------|--------|---------|
| Models created | 3 | 0 |
| Services created | 3 | 0 |
| Routes created | 1 blueprint | 0 |
| Tests written | 15+ | 0 |
| Test pass rate | 100% | - |
| Code lines | 1,200+ | 0 |
| Documentation | 300+ lines | This plan |

---

**Phase 4.1 Planning Complete** ✅  
Ready to begin Stage 1: Model Implementation
