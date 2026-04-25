"""Tests for Reference models (Phase 4.1)."""
import pytest
import json
from datetime import datetime
from app.models.researcher import ResearcherDocument
from app.models.researcher.researcher_references import Reference, DocumentReference, ReferenceSourceType


class TestReferenceModel:
    """Tests for Reference model."""
    
    def test_reference_creation_basic(self, app_context, test_project):
        """Test basic Reference creation with required fields."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Machine Learning Fundamentals",
            citation_key="ML2020",
            source="ACM Computing Surveys"
        )
        db.session.add(ref)
        db.session.commit()
        
        assert ref.id is not None
        assert ref.title == "Machine Learning Fundamentals"
        assert ref.citation_key == "ML2020"
        assert ref.source == "ACM Computing Surveys"
        assert ref.source_type == ReferenceSourceType.OTHER.value
        assert ref.citation_count == 0
    
    def test_reference_creation_full(self, app_context, test_project):
        """Test Reference creation with all fields."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            doi="10.1234/example",
            pubmed_id="12345678",
            arxiv_id="1512.03385",
            isbn="978-0-262-03561-3",
            url="https://example.com/paper",
            citation_key="Goodfellow2016",
            abstract="Comprehensive deep learning textbook",
            volume="2",
            issue="1",
            pages="1-800"
        )
        ref.set_authors(["Goodfellow, I.", "Bengio, Y.", "Courville, A."])
        ref.set_keywords(["deep learning", "neural networks", "AI"])
        db.session.add(ref)
        db.session.commit()
        
        assert ref.id is not None
        assert ref.title == "Deep Learning"
        assert ref.year == 2016
        assert ref.doi == "10.1234/example"
        assert len(ref.get_authors()) == 3
        assert "deep learning" in ref.get_keywords()
    
    def test_reference_authors_json_storage(self, app_context, test_project):
        """Test that authors are stored and retrieved correctly as JSON."""
        from app.database import db
        
        authors = ["Smith, J.", "Jones, M.", "Brown, R."]
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        ref.set_authors(authors)
        db.session.add(ref)
        db.session.commit()
        
        # Verify JSON storage
        assert ref.authors_json is not None
        assert json.loads(ref.authors_json) == authors
        
        # Verify getter method
        assert ref.get_authors() == authors
    
    def test_reference_keywords_json_storage(self, app_context, test_project):
        """Test that keywords are stored and retrieved correctly as JSON."""
        from app.database import db
        
        keywords = ["machine learning", "neural networks", "classification"]
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        ref.set_keywords(keywords)
        db.session.add(ref)
        db.session.commit()
        
        assert ref.get_keywords() == keywords
        assert json.loads(ref.keywords_json) == keywords
    
    def test_reference_metadata_json_storage(self, app_context, test_project):
        """Test that metadata dictionary is stored correctly as JSON."""
        from app.database import db
        
        metadata = {"custom_field": "value", "rating": 5, "tags": ["important", "cited"]}
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        ref.set_metadata_dict(metadata)
        db.session.add(ref)
        db.session.commit()
        
        assert ref.get_metadata_dict() == metadata
        assert json.loads(ref.metadata_json) == metadata
    
    def test_reference_to_bibtex(self, app_context, test_project):
        """Test BibTeX format conversion."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            citation_key="Goodfellow2016",
            volume="1",
            issue="2",
            pages="1-800",
            doi="10.1234/example",
            url="https://example.com"
        )
        ref.set_authors(["Goodfellow, I.", "Bengio, Y."])
        db.session.add(ref)
        db.session.commit()
        
        bibtex = ref.to_bibtex()
        
        assert "@book{Goodfellow2016," in bibtex
        assert "title = {Deep Learning}" in bibtex
        assert "author = {Goodfellow, I. and Bengio, Y.}" in bibtex
        assert "year = {2016}" in bibtex
        assert "publisher = {MIT Press}" in bibtex
        assert "doi = {10.1234/example}" in bibtex
    
    def test_reference_to_ris(self, app_context, test_project):
        """Test RIS format conversion."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            citation_key="Goodfellow2016",
            abstract="Test abstract"
        )
        ref.set_authors(["Goodfellow, I.", "Bengio, Y."])
        db.session.add(ref)
        db.session.commit()
        
        ris = ref.to_ris()
        
        assert "TY  - BOOK" in ris
        assert "TI  - Deep Learning" in ris
        assert "AU  - Goodfellow, I." in ris
        assert "AU  - Bengio, Y." in ris
        assert "PY  - 2016" in ris
        assert "AB  - Test abstract" in ris
        assert "ER  -" in ris
    
    def test_reference_to_apa(self, app_context, test_project):
        """Test APA citation format."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            citation_key="Goodfellow2016"
        )
        ref.set_authors(["Goodfellow, I.", "Bengio, Y."])
        db.session.add(ref)
        db.session.commit()
        
        apa = ref.to_apa()
        
        assert "Goodfellow, I. & Bengio, Y." in apa
        assert "(2016)" in apa
        assert "Deep Learning" in apa
        assert "MIT Press" in apa
    
    def test_reference_to_mla(self, app_context, test_project):
        """Test MLA citation format."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            citation_key="Goodfellow2016"
        )
        ref.set_authors(["Goodfellow", "Bengio"])
        db.session.add(ref)
        db.session.commit()
        
        mla = ref.to_mla()
        
        assert "Goodfellow" in mla
        assert "\"Deep Learning.\"" in mla
        assert "2016" in mla
    
    def test_reference_to_chicago(self, app_context, test_project):
        """Test Chicago citation format."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Deep Learning",
            year=2016,
            source="MIT Press",
            source_type=ReferenceSourceType.BOOK.value,
            citation_key="Goodfellow2016"
        )
        ref.set_authors(["Goodfellow, I.", "Bengio, Y."])
        db.session.add(ref)
        db.session.commit()
        
        chicago = ref.to_chicago()
        
        assert "Goodfellow, I." in chicago
        assert "Bengio, Y." in chicago
        assert "Deep Learning" in chicago
        assert "(2016)" in chicago
    
    def test_reference_to_json(self, app_context, test_project):
        """Test JSON serialization."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            year=2020,
            source="Test Journal",
            citation_key="Test2020"
        )
        ref.set_authors(["Author, A."])
        ref.set_keywords(["test", "keyword"])
        db.session.add(ref)
        db.session.commit()
        
        json_data = ref.to_json()
        
        assert json_data["title"] == "Test Paper"
        assert json_data["year"] == 2020
        assert json_data["citation_key"] == "Test2020"
        assert json_data["authors"] == ["Author, A."]
        assert json_data["keywords"] == ["test", "keyword"]
        assert "created_at" in json_data
        assert "updated_at" in json_data
    
    def test_reference_from_json(self, app_context):
        """Test Reference creation from JSON dictionary."""
        data = {
            "title": "Test Paper",
            "authors": ["Smith, J.", "Jones, M."],
            "year": 2020,
            "source": "Test Journal",
            "citation_key": "Smith2020",
            "keywords": ["test", "keyword"],
            "doi": "10.1234/test",
            "project_id": 1
        }
        
        ref = Reference.from_json(data)
        
        assert ref.title == "Test Paper"
        assert ref.year == 2020
        assert len(ref.get_authors()) == 2
        assert ref.doi == "10.1234/test"
        assert "test" in ref.get_keywords()
    
    def test_reference_repr(self, app_context, test_project):
        """Test string representation."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020",
            year=2020
        )
        db.session.add(ref)
        db.session.commit()
        
        repr_str = repr(ref)
        assert "Reference" in repr_str
        assert "Test2020" in repr_str
        assert "2020" in repr_str


class TestDocumentReferenceModel:
    """Tests for DocumentReference model."""
    
    def test_document_reference_creation(self, app_context, test_project, test_document):
        """Test DocumentReference creation."""
        from app.database import db
        from app.models.researcher.researcher_references import Reference, DocumentReference
        
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        db.session.add(ref)
        db.session.commit()
        
        doc_ref = DocumentReference(
            document_id=test_document.id,
            reference_id=ref.id,
            citation_context="This is how the reference was cited.",
            confidence=0.95,
            citation_type="direct"
        )
        db.session.add(doc_ref)
        db.session.commit()
        
        assert doc_ref.id is not None
        assert doc_ref.document_id == test_document.id
        assert doc_ref.reference_id == ref.id
        assert doc_ref.confidence == 0.95
        assert doc_ref.citation_type == "direct"
    
    def test_document_reference_to_json(self, app_context, test_project, test_document):
        """Test DocumentReference JSON serialization."""
        from app.database import db
        from app.models.researcher.researcher_references import Reference, DocumentReference
        
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        db.session.add(ref)
        db.session.commit()
        
        doc_ref = DocumentReference(
            document_id=test_document.id,
            reference_id=ref.id,
            confidence=0.95
        )
        db.session.add(doc_ref)
        db.session.commit()
        
        json_data = doc_ref.to_json()
        
        assert json_data["document_id"] == test_document.id
        assert json_data["reference_id"] == ref.id
        assert json_data["confidence"] == 0.95
        assert "created_at" in json_data
    
    def test_document_reference_repr(self, app_context, test_project, test_document):
        """Test DocumentReference string representation."""
        from app.database import db
        from app.models.researcher.researcher_references import Reference, DocumentReference
        
        ref = Reference(
            project_id=test_project.id,
            title="Test Paper",
            citation_key="Test2020"
        )
        db.session.add(ref)
        db.session.commit()
        
        doc_ref = DocumentReference(
            document_id=test_document.id,
            reference_id=ref.id
        )
        db.session.add(doc_ref)
        db.session.commit()
        
        repr_str = repr(doc_ref)
        assert "DocumentReference" in repr_str
        assert str(test_document.id) in repr_str
        assert str(ref.id) in repr_str


class TestReferenceSourceType:
    """Tests for ReferenceSourceType enum."""
    
    def test_source_type_values(self):
        """Test all ReferenceSourceType enum values."""
        assert ReferenceSourceType.JOURNAL.value == "journal"
        assert ReferenceSourceType.BOOK.value == "book"
        assert ReferenceSourceType.WEBSITE.value == "website"
        assert ReferenceSourceType.CONFERENCE.value == "conference"
        assert ReferenceSourceType.THESIS.value == "thesis"
        assert ReferenceSourceType.REPORT.value == "report"
        assert ReferenceSourceType.ARXIV.value == "arxiv"
        assert ReferenceSourceType.PUBMED.value == "pubmed"
        assert ReferenceSourceType.OTHER.value == "other"


class TestReferenceJournalArticle:
    """Tests for journal article references."""
    
    def test_reference_journal_article_format_conversions(self, app_context, test_project):
        """Test format conversions for journal articles."""
        from app.database import db
        
        ref = Reference(
            project_id=test_project.id,
            title="Neural Networks and Deep Learning",
            year=2015,
            source="Nature",
            source_type=ReferenceSourceType.JOURNAL.value,
            volume="521",
            issue="7553",
            pages="436-444",
            doi="10.1038/nature14539",
            citation_key="LeCun2015"
        )
        ref.set_authors(["LeCun, Y.", "Bengio, Y.", "Hinton, G."])
        db.session.add(ref)
        db.session.commit()
        
        # All formats should include key fields
        bibtex = ref.to_bibtex()
        assert "journal = {Nature}" in bibtex
        assert "volume = {521}" in bibtex
        
        ris = ref.to_ris()
        assert "JO  - Nature" in ris
        assert "VL  - 521" in ris
        assert "IS  - 7553" in ris
        
        apa = ref.to_apa()
        assert "Nature, 521(7553), 436-444" in apa


class TestReferenceDuplicatePrevention:
    """Tests for preventing duplicate references."""
    
    def test_unique_citation_key_per_project(self, app_context, test_project):
        """Test unique constraint on citation_key per project."""
        from app.database import db
        from sqlalchemy.exc import IntegrityError
        
        ref1 = Reference(
            project_id=test_project.id,
            title="Paper 1",
            citation_key="Paper2020"
        )
        db.session.add(ref1)
        db.session.commit()
        
        ref2 = Reference(
            project_id=test_project.id,
            title="Paper 2",
            citation_key="Paper2020"  # Duplicate key
        )
        db.session.add(ref2)
        
        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db.session.commit()


class TestReferenceRoutes:
    """Route-level tests for reference management APIs."""

    def test_create_reference_entry_persists_tags(self, client, app_context, test_project):
        response = client.post(
            f"/projects/{test_project.id}/references",
            json={
                "title": "Tagged Route Reference",
                "citation_key": "TaggedRouteReference",
                "tags": "methods; chapter 2",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["tags"] == ["methods", "chapter 2"]

        created = Reference.query.filter_by(
            project_id=test_project.id,
            citation_key="TaggedRouteReference",
        ).first()
        assert created is not None
        assert created.get_metadata_dict()["tags"] == ["methods", "chapter 2"]

    def test_list_references_supports_collection_tag_and_query_filters(self, client, app_context, test_project):
        from app.database import db

        linked_reference = Reference(
            project_id=test_project.id,
            title="AI Methods",
            citation_key="AiMethods",
            citation_count=1,
        )
        linked_reference.set_metadata_dict({"tags": ["methods", "ai"]})

        notes_reference = Reference(
            project_id=test_project.id,
            title="Field Notes",
            citation_key="FieldNotes",
            notes="Annotated",
        )
        notes_reference.set_metadata_dict({"tags": ["field"]})

        db.session.add_all([linked_reference, notes_reference])
        db.session.commit()

        response = client.get(
            f"/projects/{test_project.id}/references?collection=linked&tag=methods&q=AI"
        )
        assert response.status_code == 200
        data = response.get_json()

        assert data["selected_collection"] == "linked"
        assert data["selected_tag"] == "methods"
        assert data["query"] == "AI"
        assert data["result_count"] == 1
        assert [reference["citation_key"] for reference in data["references"]] == ["AiMethods"]
        assert any(entry["key"] == "linked" for entry in data["collections"])
        assert any(entry["name"] == "methods" for entry in data["tags"])

    def test_zotero_status_route_returns_sync_state(self, client, app_context, test_project, monkeypatch):
        monkeypatch.setattr(
            "app.routes.references.get_project_zotero_sync_status",
            lambda project, user_id: {
                "available": True,
                "connected": True,
                "ready": True,
                "message": "Zotero is ready.",
                "collections": [{"key": "methods", "name": "Methods", "item_count": 1}],
            },
        )

        response = client.get(f"/projects/{test_project.id}/references/zotero/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ready"] is True
        assert data["collections"][0]["key"] == "methods"

    def test_zotero_sync_route_returns_service_summary(self, client, app_context, test_project, monkeypatch):
        monkeypatch.setattr(
            "app.routes.references.sync_project_references_from_zotero",
            lambda project, user_id, collection_key=None, limit=100: {
                "ok": True,
                "created": 2,
                "updated": 1,
                "imported": 3,
                "collection_key": collection_key or "",
            },
        )

        response = client.post(
            f"/projects/{test_project.id}/references/zotero/sync",
            json={"collection_key": "methods"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["created"] == 2
        assert data["collection_key"] == "methods"

    def test_reference_external_attachments_route_returns_service_payload(
        self,
        client,
        app_context,
        test_project,
        monkeypatch,
    ):
        from app.database import db

        reference = Reference(
            project_id=test_project.id,
            title="Attachment route reference",
            citation_key="AttachmentRouteReference2026",
        )
        db.session.add(reference)
        db.session.commit()

        monkeypatch.setattr(
            "app.routes.references.get_project_reference_external_attachments",
            lambda project, ref, user_id: {
                "provider": "zotero",
                "attachments": [{
                    "item_key": "ATT-1",
                    "title": "Supplement",
                    "filename": "supplement.pdf",
                    "content_type": "application/pdf",
                    "open_url": "https://www.zotero.org/users/123/items/ATT-1",
                }],
                "cached": False,
                "refreshed": True,
            },
        )

        response = client.get(
            f"/projects/{test_project.id}/references/{reference.id}/external-attachments"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["provider"] == "zotero"
        assert data["attachments"][0]["filename"] == "supplement.pdf"

    def test_reference_attachment_import_route_returns_created_document_payload(
        self,
        client,
        app_context,
        test_project,
        monkeypatch,
    ):
        from app.database import db

        reference = Reference(
            project_id=test_project.id,
            title="Attachment import route reference",
            citation_key="AttachmentImportRouteReference2026",
        )
        db.session.add(reference)
        db.session.commit()

        monkeypatch.setattr(
            "app.routes.references.import_project_reference_attachment",
            lambda project, ref, attachment_item_key, user_id: {
                "created": True,
                "linked": True,
                "message": "Attachment added to the project files.",
                "rag_sync": {
                    "attempted": False,
                    "synced": False,
                    "message": "File added without indexing.",
                },
                "document": ResearcherDocument(
                    id=91,
                    project_id=project.id,
                    filename="appendix.pdf",
                    file_path="stored/appendix.pdf",
                    mime_type="application/pdf",
                    file_size=2048,
                    source_type="zotero_attachment",
                    source_id=attachment_item_key,
                    source_url="https://www.zotero.org/users/123/items/ATT-9",
                ),
            },
        )

        response = client.post(
            f"/projects/{test_project.id}/references/{reference.id}/external-attachments/ATT-9/import"
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["ok"] is True
        assert data["created"] is True
        assert data["document"]["filename"] == "appendix.pdf"
        assert data["rag_sync"]["attempted"] is False

    def test_bibliography_preview_route_returns_filtered_preview(self, client, app_context, test_project):
        from app.database import db

        matching_reference = Reference(
            project_id=test_project.id,
            title="Review Methods",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="ReviewMethods2026",
            year=2026,
        )
        matching_reference.set_authors(["Smith, A."])
        matching_reference.set_metadata_dict({"tags": ["methods"]})

        other_reference = Reference(
            project_id=test_project.id,
            title="Field Diary",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="FieldDiary2026",
            year=2026,
        )
        other_reference.set_authors(["Jones, B."])
        other_reference.set_metadata_dict({"tags": ["field"]})

        db.session.add_all([matching_reference, other_reference])
        db.session.commit()

        response = client.get(
            f"/projects/{test_project.id}/references/bibliography-preview?style=apa&tag=methods&q=Review"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["style"] == "apa"
        assert data["preview_mode"] == "list"
        assert data["total_count"] == 1
        assert len(data["entries"]) == 1
        assert "Review Methods" in data["entries"][0]

    def test_export_bibtex(self, client, app_context, test_project):
        from app.database import db

        ref = Reference(
            project_id=test_project.id,
            title="Export Test Paper",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="Export2026",
            year=2026,
        )
        ref.set_authors(["Smith, A."])
        db.session.add(ref)
        db.session.commit()

        response = client.get(f"/projects/{test_project.id}/references/export?style=bibtex")
        assert response.status_code == 200
        assert b"@journal{Export2026" in response.data
        assert ".bib" in response.headers.get("Content-Disposition", "")

    def test_export_bibliography_honors_active_filters(self, client, app_context, test_project):
        from app.database import db

        matching_reference = Reference(
            project_id=test_project.id,
            title="Methods Export",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="MethodsExport2026",
            year=2026,
        )
        matching_reference.set_metadata_dict({"tags": ["methods"]})

        other_reference = Reference(
            project_id=test_project.id,
            title="Notes Export",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="NotesExport2026",
            year=2026,
        )
        other_reference.set_metadata_dict({"tags": ["notes"]})

        db.session.add_all([matching_reference, other_reference])
        db.session.commit()

        response = client.get(
            f"/projects/{test_project.id}/references/export?style=json&tag=methods"
        )

        assert response.status_code == 200
        payload = response.get_data(as_text=True)
        assert "MethodsExport2026" in payload
        assert "NotesExport2026" not in payload

    def test_import_references_json(self, client, app_context, test_project):
        payload = [
            {
                "title": "Imported JSON Reference",
                "authors": ["Doe, J.", "Roe, K."],
                "year": 2025,
                "source": "Test Journal",
                "citation_key": "JsonImport2025",
            }
        ]
        response = client.post(
            f"/projects/{test_project.id}/references/import",
            json={"format": "json", "content": json.dumps(payload)},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["created"] == 1
        assert data["skipped"] == 0
        assert data["duplicate_skipped"] == 0
        assert data["invalid_skipped"] == 0

        from app.models.researcher.researcher_references import Reference
        created = Reference.query.filter_by(project_id=test_project.id, citation_key="JsonImport2025").first()
        assert created is not None

    def test_import_references_bibtex(self, client, app_context, test_project):
        bibtex = """
@article{BibImport2025,
  title = {Imported BibTeX Reference},
  author = {Author, A. and Writer, W.},
  year = {2025},
  journal = {Bib Journal},
  doi = {10.1111/example}
}
""".strip()

        response = client.post(
            f"/projects/{test_project.id}/references/import",
            data={"format": "bibtex", "content": bibtex},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["created"] == 1

        created = Reference.query.filter_by(project_id=test_project.id, citation_key="BibImport2025").first()
        assert created is not None
        assert created.title == "Imported BibTeX Reference"

    def test_import_references_reports_duplicate_skip_summary(self, client, app_context, test_project):
        from app.database import db

        existing = Reference(
            project_id=test_project.id,
            title="Duplicate Methods Reference",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="DuplicateMethods2026",
            year=2026,
            doi="10.3000/duplicate-methods",
        )
        db.session.add(existing)
        db.session.commit()

        payload = [
            {
                "title": "Duplicate Methods Reference",
                "citation_key": "DuplicateMethods2026",
                "year": 2026,
            },
            {
                "title": "Different Title Same DOI",
                "citation_key": "FreshKey2026",
                "year": 2026,
                "doi": "doi:10.3000/duplicate-methods",
            },
        ]

        response = client.post(
            f"/projects/{test_project.id}/references/import",
            json={"format": "json", "content": json.dumps(payload)},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["created"] == 0
        assert data["skipped"] == 2
        assert data["duplicate_skipped"] == 2
        assert data["duplicate_reasons"]["citation_key"] == 1
        assert data["duplicate_reasons"]["doi"] == 1

    def test_link_and_unlink_document_reference(self, client, app_context, test_project, test_document):
        from app.database import db

        ref = Reference(
            project_id=test_project.id,
            title="Link Test Reference",
            citation_key="Link2026",
        )
        db.session.add(ref)
        db.session.commit()

        link_response = client.post(
            f"/projects/{test_project.id}/references/{ref.id}/link-document",
            json={
                "document_id": test_document.id,
                "citation_context": "Cited in intro section.",
                "confidence": 0.88,
                "citation_type": "direct",
            },
        )
        assert link_response.status_code == 201
        link_data = link_response.get_json()
        assert link_data["ok"] is True
        assert link_data["link"]["document_id"] == test_document.id

        list_response = client.get(f"/projects/{test_project.id}/references/{ref.id}/documents")
        assert list_response.status_code == 200
        docs_data = list_response.get_json()
        assert len(docs_data["documents"]) == 1
        assert docs_data["documents"][0]["document_id"] == test_document.id

        unlink_response = client.delete(
            f"/projects/{test_project.id}/references/{ref.id}/link-document/{test_document.id}"
        )
        assert unlink_response.status_code == 200
        assert unlink_response.get_json()["ok"] is True

        list_after = client.get(f"/projects/{test_project.id}/references/{ref.id}/documents")
        assert list_after.status_code == 200
        assert len(list_after.get_json()["documents"]) == 0

    def test_reference_detail_page_renders_linked_documents_and_export_actions(
        self,
        client,
        app_context,
        test_project,
        test_document,
    ):
        from app.database import db
        from app.models.researcher import DocumentAnnotation, ResearcherDocument

        linked_document = ResearcherDocument(
            project_id=test_project.id,
            filename="appendix.pdf",
            file_path="/tmp/appendix.pdf",
            mime_type="application/pdf",
            text_content="Appendix material with supporting context.",
            file_size=2048,
            source_type="pdf",
        )
        reference = Reference(
            project_id=test_project.id,
            document_id=test_document.id,
            title="Detail Page Reference",
            source="Journal of Testing",
            publication="Journal of Testing",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="DetailPageReference2026",
            year=2026,
            doi="10.1000/detail-page-reference",
        )
        reference.set_authors(["Smith, A."])
        reference.set_metadata_dict({
            "tags": ["methods"],
            "external_library": {
                "provider": "zotero",
                "item_key": "ITEM-42",
                "library_type": "user",
                "synced_at": "2026-04-12T08:30:00",
                "attachments": [{
                    "item_key": "ATT-42",
                    "title": "Methods appendix",
                    "filename": "appendix.pdf",
                    "content_type": "application/pdf",
                    "link_mode": "imported_file",
                    "item_url": "https://www.zotero.org/users/123/items/ATT-42",
                }],
            },
        })
        db.session.add_all([linked_document, reference])
        db.session.flush()
        db.session.add(
            DocumentReference(
                document_id=linked_document.id,
                reference_id=reference.id,
                citation_context="Used in the appendix.",
                citation_type="supporting",
                confidence=0.8,
            )
        )
        db.session.add(
            DocumentAnnotation(
                document_id=linked_document.id,
                chunk_id="chunk-0",
                start_offset=0,
                end_offset=8,
                note="Supporting note",
                highlight_color="#fef08a",
            )
        )
        db.session.commit()

        response = client.get(f"/researcher/projects/{test_project.id}/references/{reference.id}")

        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert "Detail Page Reference" in page
        assert "Formatted citation" in page
        assert "Download current style" in page
        assert "appendix.pdf" in page
        assert "Open file" in page
        assert "Library sync details" in page
        assert "External attachments" in page
        assert "Open attachment" in page
        assert "Add to project files" in page
        assert "data-reference-remove-document" in page
        assert f"?source_view=reference&amp;reference_id={reference.id}" in page

    def test_export_single_reference_bibtex(self, client, app_context, test_project):
        from app.database import db

        reference = Reference(
            project_id=test_project.id,
            title="Single Export Reference",
            source="Journal of Testing",
            source_type=ReferenceSourceType.JOURNAL.value,
            citation_key="SingleExportReference2026",
            year=2026,
        )
        reference.set_authors(["Smith, A."])
        db.session.add(reference)
        db.session.commit()

        response = client.get(
            f"/projects/{test_project.id}/references/{reference.id}/export?style=bibtex"
        )

        assert response.status_code == 200
        assert b"@journal{SingleExportReference2026" in response.data
        assert response.mimetype == "application/x-bibtex"
        assert ".bib" in response.headers.get("Content-Disposition", "")
