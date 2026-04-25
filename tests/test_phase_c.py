"""Phase C tests — PHI redaction, domain plugins, sector models."""
import pytest
import json


# ══════════════════════════════════════════════════════════════════════════════
#  TestPhiService  —  unit tests for phi_redaction_service (no HTTP)
# ══════════════════════════════════════════════════════════════════════════════

class TestPhiService:
    """Tests for the PHI redaction service functions."""

    def _svc(self):
        from app.services.phi_redaction_service import scan_text, redact_text, phi_report
        return scan_text, redact_text, phi_report

    def test_scan_ssn(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("Patient SSN: 123-45-6789 was admitted.")
        types = [f.entity_type for f in findings]
        assert 'SSN' in types

    def test_scan_email(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("Contact patient at john.doe@hospital.org today.")
        types = [f.entity_type for f in findings]
        assert 'EMAIL' in types

    def test_scan_phone(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("Call (555) 867-5309 for appointment.")
        types = [f.entity_type for f in findings]
        assert 'PHONE' in types

    def test_scan_date(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("Admitted on 01/15/2023.")
        types = [f.entity_type for f in findings]
        assert any(t in types for t in ('DATE', 'DOB'))

    def test_scan_empty_text(self):
        scan_text, _, _ = self._svc()
        assert scan_text('') == []
        assert scan_text(None) == []

    def test_scan_no_phi(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("The weather is sunny today in Colorado.")
        # Should find zero PHI
        assert findings == []

    def test_redact_text_replaces_ssn(self):
        _, redact_text, _ = self._svc()
        redacted, redaction_map = redact_text("SSN: 123-45-6789", replacement='[PHI]')
        assert '123-45-6789' not in redacted
        assert '[PHI]' in redacted
        # redaction_map is a list of finding dicts
        assert isinstance(redaction_map, list)

    def test_redact_text_entity_type_filter(self):
        _, redact_text, _ = self._svc()
        text = "Call (555) 867-5309. Email: a@b.com."
        redacted, _ = redact_text(text, entity_types=['PHONE'])
        # Phone should be redacted, email should remain
        assert '(555) 867-5309' not in redacted
        assert 'a@b.com' in redacted

    def test_phi_report_structure(self):
        _, _, phi_report = self._svc()
        report = phi_report("Patient SSN: 123-45-6789, phone (555) 123-4567.")
        assert 'phi_found' in report
        assert 'total_findings' in report
        assert 'entity_type_counts' in report
        assert 'findings' in report
        assert report['phi_found'] is True

    def test_phi_report_clean_text(self):
        _, _, phi_report = self._svc()
        report = phi_report("The system runs on Linux servers with 99.9% uptime.")
        assert report['phi_found'] is False
        assert report['total_findings'] == 0

    def test_finding_to_dict(self):
        scan_text, _, _ = self._svc()
        findings = scan_text("Email: patient@clinic.org here.")
        assert findings
        d = findings[0].to_dict()
        assert 'entity_type' in d
        assert 'start' in d
        assert 'end' in d
        assert 'matched_text' in d


# ══════════════════════════════════════════════════════════════════════════════
#  TestPhiRoutes  —  HTTP endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TestPhiRoutes:
    """Tests for GET/POST/DELETE phi-report and redact endpoints."""

    PHI_TEXT = 'Patient SSN: 123-45-6789, contact at patient@hospital.org. DOB 01/15/1980.'

    def _create_phi_doc(self, app_context, project_id):
        """Create a document with PHI text directly via ORM and return its id."""
        from app.database import db
        from app.models.researcher import ResearcherDocument
        doc = ResearcherDocument(
            project_id=project_id,
            filename='phi_test.txt',
            file_path='/tmp/phi_test.txt',
            mime_type='text/plain',
            text_content=self.PHI_TEXT,
            file_size=len(self.PHI_TEXT),
            source_type='test',
        )
        db.session.add(doc)
        db.session.commit()
        return doc.id

    def _create_clean_doc(self, app_context, project_id):
        """Create a document with no PHI directly via ORM and return its id."""
        from app.database import db
        from app.models.researcher import ResearcherDocument
        doc = ResearcherDocument(
            project_id=project_id,
            filename='clean.txt',
            file_path='/tmp/clean.txt',
            mime_type='text/plain',
            text_content='The experiment produced interesting results.',
            file_size=50,
            source_type='test',
        )
        db.session.add(doc)
        db.session.commit()
        return doc.id

    def test_phi_report_returns_findings(self, app_context, client, test_project):
        doc_id = self._create_phi_doc(app_context, test_project.id)
        resp = client.get(f'/projects/{test_project.id}/documents/{doc_id}/phi-report')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'phi_found' in data
        assert 'total_findings' in data
        assert data['document_id'] == doc_id

    def test_phi_report_does_not_modify_document(self, app_context, client, test_project):
        doc_id = self._create_phi_doc(app_context, test_project.id)
        # Run PHI report — should NOT change text
        client.get(f'/projects/{test_project.id}/documents/{doc_id}/phi-report')
        # Read document directly from DB to verify text unchanged
        from app.models.researcher import ResearcherDocument
        from app.database import db as _db
        doc = _db.session.get(ResearcherDocument, doc_id)
        assert doc.text_content == self.PHI_TEXT

    def test_redact_document_removes_phi(self, app_context, client, test_project):
        doc_id = self._create_phi_doc(app_context, test_project.id)
        resp = client.post(
            f'/projects/{test_project.id}/documents/{doc_id}/redact',
            json={'replacement': '[REDACTED]'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'ok'

    def test_redact_document_prevents_double_redaction(self, app_context, client, test_project):
        doc_id = self._create_phi_doc(app_context, test_project.id)
        client.post(
            f'/projects/{test_project.id}/documents/{doc_id}/redact',
            json={'replacement': '[REDACTED]'},
        )
        # Second attempt should be blocked
        resp2 = client.post(
            f'/projects/{test_project.id}/documents/{doc_id}/redact',
            json={'replacement': '[REDACTED]'},
        )
        assert resp2.status_code == 409

    def test_restore_after_redaction(self, app_context, client, test_project):
        doc_id = self._create_phi_doc(app_context, test_project.id)
        # Redact first
        client.post(
            f'/projects/{test_project.id}/documents/{doc_id}/redact',
            json={'replacement': '[REDACTED]'},
        )
        # Restore
        resp = client.delete(f'/projects/{test_project.id}/documents/{doc_id}/redact')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('ok') is True

    def test_restore_without_backup_returns_404(self, app_context, client, test_project):
        """Document that was never redacted should return 404 on restore."""
        doc_id = self._create_clean_doc(app_context, test_project.id)
        resp = client.delete(f'/projects/{test_project.id}/documents/{doc_id}/redact')
        assert resp.status_code == 404

    def test_bulk_phi_report(self, app_context, client, test_project):
        # Create two documents with PHI
        self._create_phi_doc(app_context, test_project.id)
        self._create_phi_doc(app_context, test_project.id)
        resp = client.get(f'/projects/{test_project.id}/phi-report')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total_documents' in data
        assert 'documents_with_phi' in data

    def test_phi_report_404_bad_project(self, client):
        resp = client.get('/projects/999999/documents/1/phi-report')
        assert resp.status_code == 404

    def test_phi_report_404_bad_document(self, app_context, client, test_project):
        resp = client.get(f'/projects/{test_project.id}/documents/999999/phi-report')
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
#  TestRealEstatePlugin
# ══════════════════════════════════════════════════════════════════════════════

class TestRealEstatePlugin:
    """Unit tests for RealEstatePlugin helpers (no Flask context needed)."""

    def _plugin(self):
        from app.plugins.real_estate import RealEstatePlugin
        from app.services.plugin_base import PluginMetadata
        meta = PluginMetadata(
            name='real_estate_test', display_name='Real Estate Test',
            version='1.0', description='test',
            author='test', plugin_type='domain',
        )
        return RealEstatePlugin(meta)

    def test_classify_zoning_known_code(self):
        plugin = self._plugin()
        result = plugin.classify_zoning('R1')
        assert result['code'] == 'R1'
        assert 'Single-Family' in result['description']

    def test_classify_zoning_unknown_code(self):
        plugin = self._plugin()
        result = plugin.classify_zoning('ZZ')
        assert result['code'] == 'ZZ'
        assert result['description'] == ''

    def test_calculate_cap_rate(self):
        plugin = self._plugin()
        # Returns a float percentage directly
        result = plugin.calculate_cap_rate(noi=100_000, property_value=1_000_000)
        assert result == pytest.approx(10.0)

    def test_calculate_cap_rate_zero_value(self):
        plugin = self._plugin()
        # Returns None when property_value is 0
        result = plugin.calculate_cap_rate(noi=50_000, property_value=0)
        assert result is None

    def test_detect_title_defects_found(self):
        plugin = self._plugin()
        text = "The property has an existing easement and a mechanic lien on record."
        # Returns a list of keyword strings
        defects = plugin.detect_title_defects(text)
        assert len(defects) >= 2
        assert any('easement' in d for d in defects)

    def test_detect_title_defects_none(self):
        plugin = self._plugin()
        defects = plugin.detect_title_defects("Clean title, no issues whatsoever.")
        assert defects == []

    def test_extract_lease_terms_monthly(self):
        plugin = self._plugin()
        text = "The monthly rent is $2,500 per month for a 12-month lease."
        terms = plugin.extract_lease_terms(text)
        assert isinstance(terms, dict)

    def test_normalize_address(self):
        plugin = self._plugin()
        result = plugin.normalize_address("123 Main Street, Suite 4B, Dallas TX 75201")
        assert isinstance(result, str)
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════════════════
#  TestEducationPlugin
# ══════════════════════════════════════════════════════════════════════════════

class TestEducationPlugin:
    """Unit tests for EducationPlugin helpers."""

    def _plugin(self):
        from app.plugins.education import EducationPlugin
        from app.services.plugin_base import PluginMetadata
        meta = PluginMetadata(
            name='education_test', display_name='Education Test',
            version='1.0', description='test',
            author='test', plugin_type='domain',
        )
        return EducationPlugin(meta)

    def test_detect_citation_style_apa(self):
        plugin = self._plugin()
        text = "Smith, J. A. (2020). The nature of things. Journal of Science, 12(3), 45-67."
        style = plugin.detect_citation_style(text)
        assert style == 'APA'

    def test_detect_citation_style_mla(self):
        plugin = self._plugin()
        text = 'Jones, Mary. "The nature of reality." Science Today 12'
        style = plugin.detect_citation_style(text)
        assert style == 'MLA'

    def test_detect_citation_style_chicago(self):
        plugin = self._plugin()
        text = "1. Smith, John. The Big Book of Things. Chicago: University Press, 2020."
        style = plugin.detect_citation_style(text)
        assert style == 'Chicago'

    def test_detect_citation_style_none(self):
        plugin = self._plugin()
        style = plugin.detect_citation_style("This is a random sentence with no citations.")
        assert style is None

    def test_format_citation_apa(self):
        plugin = self._plugin()
        result = plugin.format_citation_apa(
            author='Doe, J.', year=2021, title='A Study', journal='Nature',
            volume='10', issue='2', pages='100-110',
        )
        assert 'Doe, J.' in result
        assert '2021' in result
        assert 'Nature' in result

    def test_detect_ferpa_terms_found(self):
        plugin = self._plugin()
        text = "Student GPA and transcript are confidential under FERPA regulations."
        terms = plugin.detect_ferpa_terms(text)
        assert len(terms) >= 2
        assert any('gpa' in t for t in terms)

    def test_detect_ferpa_terms_none(self):
        plugin = self._plugin()
        text = "The experiment was conducted using a randomized control group."
        terms = plugin.detect_ferpa_terms(text)
        assert terms == []

    def test_classify_methodology_qualitative(self):
        plugin = self._plugin()
        text = "This study used thematic analysis and focus group interviews."
        result = plugin.classify_methodology(text)
        assert result == 'qualitative'

    def test_classify_methodology_quantitative(self):
        plugin = self._plugin()
        text = "We ran a regression analysis with a sample size of 500 using ANOVA."
        result = plugin.classify_methodology(text)
        assert result == 'quantitative'

    def test_classify_methodology_systematic_review(self):
        plugin = self._plugin()
        text = "This is a systematic review following PRISMA guidelines with meta-analysis."
        result = plugin.classify_methodology(text)
        assert result == 'systematic_review'

    def test_classify_methodology_none(self):
        plugin = self._plugin()
        result = plugin.classify_methodology("The weather was warm that summer.")
        assert result is None

    def test_tag_blooms_level_remember(self):
        plugin = self._plugin()
        result = plugin.tag_blooms_level("Students should be able to define and list the key terms.")
        assert result == 'remember'

    def test_tag_blooms_level_analyze(self):
        plugin = self._plugin()
        result = plugin.tag_blooms_level("Analyze and compare the two competing theories by examining their differences.")
        assert result == 'analyze'

    def test_tag_blooms_level_none(self):
        plugin = self._plugin()
        result = plugin.tag_blooms_level("This sentence has no verbs.")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
#  TestGovernmentPlugin
# ══════════════════════════════════════════════════════════════════════════════

class TestGovernmentPlugin:
    """Unit tests for GovernmentPlugin helpers."""

    def _plugin(self):
        from app.plugins.government import GovernmentPlugin
        from app.services.plugin_base import PluginMetadata
        meta = PluginMetadata(
            name='government_test', display_name='Government Test',
            version='1.0', description='test',
            author='test', plugin_type='domain',
        )
        return GovernmentPlugin(meta)

    def test_parse_cfr_citations(self):
        plugin = self._plugin()
        text = "See 45 CFR 164.502 and 21 C.F.R. § 312.23 for details."
        results = plugin.parse_cfr_citations(text)
        assert len(results) == 2
        titles = [r['title_number'] for r in results]
        assert '45' in titles
        assert '21' in titles

    def test_parse_cfr_citations_none(self):
        plugin = self._plugin()
        results = plugin.parse_cfr_citations("No regulatory citations here.")
        assert results == []

    def test_parse_usc_citations(self):
        plugin = self._plugin()
        text = "Under 5 U.S.C. § 552 and 42 USC 1983, the agency must disclose."
        results = plugin.parse_usc_citations(text)
        assert len(results) >= 1
        titles = [r['title_number'] for r in results]
        assert '5' in titles

    def test_extract_agency_mentions(self):
        plugin = self._plugin()
        text = "The EPA and FDA issued a joint statement regarding HHS guidelines."
        agencies = plugin.extract_agency_mentions(text)
        acronyms = [a['acronym'] for a in agencies]
        assert 'EPA' in acronyms
        assert 'FDA' in acronyms
        assert 'HHS' in acronyms

    def test_extract_agency_mentions_none(self):
        plugin = self._plugin()
        agencies = plugin.extract_agency_mentions("No agencies mentioned here at all.")
        assert agencies == []

    def test_match_agency_known(self):
        plugin = self._plugin()
        result = plugin.match_agency('EPA')
        assert 'Environmental Protection' in result

    def test_match_agency_unknown(self):
        plugin = self._plugin()
        result = plugin.match_agency('XYZ')
        assert result is None

    def test_detect_foia_exemptions(self):
        plugin = self._plugin()
        text = "This document qualifies for exemptions (b)(1) and (b)(6) under FOIA."
        exemptions = plugin.detect_foia_exemptions(text)
        assert '(b)(1)' in exemptions
        assert '(b)(6)' in exemptions

    def test_detect_foia_exemptions_none(self):
        plugin = self._plugin()
        exemptions = plugin.detect_foia_exemptions("We support full public disclosure.")
        assert exemptions == []

    def test_classify_sentiment_support(self):
        plugin = self._plugin()
        result = plugin.classify_public_comment_sentiment(
            "We strongly support this regulation and agree with its proposed measures."
        )
        assert result == 'support'

    def test_classify_sentiment_oppose(self):
        plugin = self._plugin()
        result = plugin.classify_public_comment_sentiment(
            "We oppose this rule and object to every aspect of the harmful proposal."
        )
        assert result == 'oppose'

    def test_classify_sentiment_neutral(self):
        plugin = self._plugin()
        result = plugin.classify_public_comment_sentiment(
            "The proposed regulation changes section 4 of the existing code."
        )
        assert result == 'neutral'


# ══════════════════════════════════════════════════════════════════════════════
#  TestSectorModels  —  ORM CRUD in the Flask test DB
# ══════════════════════════════════════════════════════════════════════════════

class TestSectorModels:
    """Basic ORM create / read / delete for Phase C sector models."""

    def test_create_hypothesis(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import Hypothesis
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Sector Test Project',
            description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()

        hyp = Hypothesis(
            project_id=project.id,
            statement='Students with higher engagement score better.',
            hypothesis_type='alternative',
            status='active',
            methodology='quantitative',
        )
        db.session.add(hyp)
        db.session.commit()

        fetched = Hypothesis.query.filter_by(project_id=project.id).first()
        assert fetched is not None
        assert fetched.statement == 'Students with higher engagement score better.'
        d = fetched.to_dict()
        assert d['hypothesis_type'] == 'alternative'

    def test_create_plagiarism_check(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import PlagiarismCheck
        from app.models.researcher import ResearchProject, ResearcherDocument

        project = ResearchProject(
            name='Plagiarism Test Project',
            description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()

        doc = ResearcherDocument(
            project_id=project.id,
            filename='paper.pdf',
            file_path='/tmp/paper.pdf',
            mime_type='application/pdf',
            text_content='Sample text.',
            file_size=100,
            source_type='test',
        )
        db.session.add(doc)
        db.session.flush()

        check = PlagiarismCheck(
            project_id=project.id,
            document_id=doc.id,
            service='internal_rag',
            similarity_score=12.5,
            status='clean',
        )
        db.session.add(check)
        db.session.commit()

        fetched = PlagiarismCheck.query.filter_by(document_id=doc.id).first()
        assert fetched.similarity_score == 12.5
        assert fetched.status == 'clean'

    def test_create_evidence_grade(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import EvidenceGrade
        from app.models.researcher.phase_a_models import EvidenceItem
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Grade Test Project',
            description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()

        ev = EvidenceItem(
            project_id=project.id,
            claim_text='RCT Study on pain management shows positive outcome.',
            evidence_type='RCT',
            strength='high',
            direction='supports',
        )
        db.session.add(ev)
        db.session.flush()

        grade = EvidenceGrade(
            evidence_item_id=ev.id,
            grade='A',
            grading_system='oxford',
            grade_reason='Large RCT, low bias.',
        )
        db.session.add(grade)
        db.session.commit()

        fetched = EvidenceGrade.query.filter_by(evidence_item_id=ev.id).first()
        assert fetched.grade == 'A'
        d = fetched.to_dict()
        assert d['grading_system'] == 'oxford'

    def test_create_clause_template(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import ClauseTemplate
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Legal Project',
            description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()

        clause = ClauseTemplate(
            project_id=project.id,
            name='Force Majeure',
            clause_type='risk',
            jurisdiction='TX',
            risk_level='high',
            reference_text='Neither party shall be liable for...',
        )
        db.session.add(clause)
        db.session.commit()

        fetched = ClauseTemplate.query.filter_by(project_id=project.id).first()
        assert fetched.name == 'Force Majeure'
        assert fetched.risk_level == 'high'
        d = fetched.to_dict()
        assert d['jurisdiction'] == 'TX'

    def test_create_citation_validation(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import CitationValidation
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Citation Test Project',
            description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()

        cit = CitationValidation(
            project_id=project.id,
            citation_text='45 CFR 164.502',
            citation_type='cfr',
            is_valid=True,
            normalized_form='45 C.F.R. § 164.502',
        )
        db.session.add(cit)
        db.session.commit()

        fetched = CitationValidation.query.filter_by(project_id=project.id).first()
        assert fetched.citation_type == 'cfr'
        assert fetched.is_valid is True
        d = fetched.to_dict()
        assert d['normalized_form'] == '45 C.F.R. § 164.502'

    def test_hypothesis_to_dict_fields(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import Hypothesis
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Dict Test', description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()
        hyp = Hypothesis(
            project_id=project.id,
            statement='Test statement.',
            hypothesis_type='null',
            status='draft',
        )
        db.session.add(hyp)
        db.session.commit()

        d = hyp.to_dict()
        for key in ('id', 'project_id', 'statement', 'hypothesis_type', 'status',
                    'methodology', 'literature_support_count', 'created_at'):
            assert key in d, f"Missing key: {key}"

    def test_delete_hypothesis_cascade(self, app_context):
        from app.database import db
        from app.models.researcher.sector_models import Hypothesis
        from app.models.researcher import ResearchProject

        project = ResearchProject(
            name='Cascade Test', description='test',
            owner_id=1,
        )
        db.session.add(project)
        db.session.flush()
        hyp = Hypothesis(
            project_id=project.id,
            statement='Will be deleted.',
        )
        db.session.add(hyp)
        db.session.commit()
        hyp_id = hyp.id

        db.session.delete(hyp)
        db.session.commit()

        assert db.session.get(Hypothesis, hyp_id) is None
