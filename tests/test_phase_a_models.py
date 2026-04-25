"""Tests for Phase A enhancement models (ResearchBrief, EvidenceItem, Claim, ReviewStep, SourceProvenance)."""
import pytest
from datetime import datetime


class TestResearchBriefModel:
    def test_create_minimal_brief(self, app_context, test_project, test_user):
        from app.database import db
        from app.models.researcher.phase_a_models import ResearchBrief
        brief = ResearchBrief(
            project_id=test_project.id,
            sector='medical',
            title='COVID-19 Treatment Review',
        )
        db.session.add(brief)
        db.session.commit()
        assert brief.id is not None
        assert brief.status == 'draft'

    def test_brief_to_dict(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import ResearchBrief
        brief = ResearchBrief(
            project_id=test_project.id,
            sector='law',
            title='Contract Law Brief',
            compliance_frameworks=['GDPR', 'SOX'],
            key_findings={'section1': 'Finding A'},
        )
        db.session.add(brief)
        db.session.commit()
        d = brief.to_dict()
        assert d['sector'] == 'law'
        assert d['title'] == 'Contract Law Brief'
        assert 'GDPR' in d['compliance_frameworks']
        assert 'created_at' in d

    def test_brief_default_sector_is_general(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import ResearchBrief
        brief = ResearchBrief(project_id=test_project.id, title='Untitled')
        db.session.add(brief)
        db.session.commit()
        assert brief.sector == 'general'

    def test_brief_status_transitions(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import ResearchBrief
        brief = ResearchBrief(project_id=test_project.id, title='X', sector='education')
        db.session.add(brief)
        db.session.commit()
        brief.status = 'final'
        db.session.commit()
        assert db.session.get(ResearchBrief, brief.id).status == 'final'

    @pytest.mark.parametrize('sector', ['law', 'medical', 'real_estate', 'education', 'government'])
    def test_all_sectors_valid(self, app_context, test_project, sector):
        from app.database import db
        from app.models.researcher.phase_a_models import ResearchBrief
        brief = ResearchBrief(project_id=test_project.id, title=f'{sector} brief', sector=sector)
        db.session.add(brief)
        db.session.commit()
        assert brief.sector == sector


class TestEvidenceItemModel:
    def test_create_evidence_item(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import EvidenceItem
        ev = EvidenceItem(
            project_id=test_project.id,
            document_id=test_document.id,
            claim_text='Drug X reduces blood pressure significantly.',
            strength='high',
            direction='supports',
            evidence_type='RCT',
        )
        db.session.add(ev)
        db.session.commit()
        assert ev.id is not None

    def test_evidence_to_dict(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import EvidenceItem
        ev = EvidenceItem(
            project_id=test_project.id,
            document_id=test_document.id,
            claim_text='Test claim.',
            strength='moderate',
            direction='refutes',
            verbatim_quote='The study found no effect.',
        )
        db.session.add(ev)
        db.session.commit()
        d = ev.to_dict()
        assert d['claim_text'] == 'Test claim.'
        assert d['strength'] == 'moderate'
        assert d['direction'] == 'refutes'
        assert d['verbatim_quote'] == 'The study found no effect.'

    def test_default_strength_is_low(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import EvidenceItem
        ev = EvidenceItem(project_id=test_project.id, claim_text='Simple claim.')
        db.session.add(ev)
        db.session.commit()
        assert ev.strength == 'low'

    @pytest.mark.parametrize('strength', ['high', 'moderate', 'low', 'very_low'])
    def test_all_strength_levels(self, app_context, test_project, strength):
        from app.database import db
        from app.models.researcher.phase_a_models import EvidenceItem
        ev = EvidenceItem(project_id=test_project.id, claim_text='Claim.', strength=strength)
        db.session.add(ev)
        db.session.commit()
        assert ev.strength == strength

    def test_evidence_with_tags(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import EvidenceItem
        ev = EvidenceItem(
            project_id=test_project.id,
            claim_text='Tagged claim.',
            tags=['cardiology', 'hypertension'],
        )
        db.session.add(ev)
        db.session.commit()
        assert 'cardiology' in db.session.get(EvidenceItem, ev.id).tags


class TestClaimModel:
    def test_create_claim(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import Claim
        claim = Claim(
            project_id=test_project.id,
            claim_text='Higher education increases earning potential.',
            claim_type='factual',
            sector='education',
        )
        db.session.add(claim)
        db.session.commit()
        assert claim.id is not None
        assert claim.verdict == 'unclear'

    def test_claim_to_dict(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import Claim
        claim = Claim(
            project_id=test_project.id,
            claim_text='Policy X is effective.',
            verdict='supported',
            confidence_score=0.87,
        )
        db.session.add(claim)
        db.session.commit()
        d = claim.to_dict()
        assert d['verdict'] == 'supported'
        assert d['confidence_score'] == pytest.approx(0.87)


class TestClaimEvidenceLink:
    def test_link_claim_to_evidence(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import Claim, EvidenceItem, ClaimEvidence
        claim = Claim(project_id=test_project.id, claim_text='Test claim.')
        ev = EvidenceItem(project_id=test_project.id, claim_text='Supporting fact.')
        db.session.add_all([claim, ev])
        db.session.flush()
        link = ClaimEvidence(claim_id=claim.id, evidence_id=ev.id, role='supporting')
        db.session.add(link)
        db.session.commit()
        assert link.id is not None
        assert link.role == 'supporting'

    def test_unique_constraint_prevents_duplicate_link(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import Claim, EvidenceItem, ClaimEvidence
        claim = Claim(project_id=test_project.id, claim_text='Unique claim.')
        ev = EvidenceItem(project_id=test_project.id, claim_text='Unique evidence.')
        db.session.add_all([claim, ev])
        db.session.flush()
        link1 = ClaimEvidence(claim_id=claim.id, evidence_id=ev.id, role='supporting')
        db.session.add(link1)
        db.session.commit()
        # Duplicate
        db.session.add(ClaimEvidence(claim_id=claim.id, evidence_id=ev.id, role='refuting'))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()

    def test_claim_evidence_to_dict(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.phase_a_models import Claim, EvidenceItem, ClaimEvidence
        claim = Claim(project_id=test_project.id, claim_text='C.')
        ev = EvidenceItem(project_id=test_project.id, claim_text='E.')
        db.session.add_all([claim, ev])
        db.session.flush()
        link = ClaimEvidence(claim_id=claim.id, evidence_id=ev.id, role='neutral')
        db.session.add(link)
        db.session.commit()
        d = link.to_dict()
        assert d['role'] == 'neutral'
        assert d['claim_id'] == claim.id


class TestReviewStepModel:
    def test_create_review_step(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import ReviewStep
        step = ReviewStep(
            project_id=test_project.id,
            document_id=test_document.id,
            stage='screening',
            decision='pass',
        )
        db.session.add(step)
        db.session.commit()
        assert step.id is not None

    def test_review_step_to_dict(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import ReviewStep
        step = ReviewStep(
            project_id=test_project.id,
            document_id=test_document.id,
            stage='eligibility',
            decision='exclude',
            exclusion_reason='off_topic',
            is_automated=True,
            automation_confidence=0.95,
        )
        db.session.add(step)
        db.session.commit()
        d = step.to_dict()
        assert d['stage'] == 'eligibility'
        assert d['decision'] == 'exclude'
        assert d['exclusion_reason'] == 'off_topic'
        assert d['is_automated'] is True
        assert d['automation_confidence'] == pytest.approx(0.95)

    @pytest.mark.parametrize('stage', ['identification', 'screening', 'eligibility', 'included', 'excluded'])
    def test_all_prisma_stages(self, app_context, test_project, stage):
        from app.database import db
        from app.models.researcher.phase_a_models import ReviewStep
        step = ReviewStep(project_id=test_project.id, stage=stage, decision='uncertain')
        db.session.add(step)
        db.session.commit()
        assert step.stage == stage


class TestSourceProvenanceModel:
    def test_create_provenance_record(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import SourceProvenance
        prov = SourceProvenance(
            document_id=test_document.id,
            project_id=test_project.id,
            event_type='imported',
            tool_name='pubmed_importer',
            tool_version='1.0',
            content_hash='a' * 64,
        )
        db.session.add(prov)
        db.session.commit()
        assert prov.id is not None

    def test_provenance_to_dict(self, app_context, test_project, test_document):
        from app.database import db
        from app.models.researcher.phase_a_models import SourceProvenance
        prov = SourceProvenance(
            document_id=test_document.id,
            project_id=test_project.id,
            event_type='redacted',
            event_detail={'phi_count': 3, 'method': 'phi_redact'},
            tool_name='phi_redactor',
        )
        db.session.add(prov)
        db.session.commit()
        d = prov.to_dict()
        assert d['event_type'] == 'redacted'
        assert d['event_detail']['phi_count'] == 3

    @pytest.mark.parametrize('event_type', [
        'imported', 'transformed', 'chunked', 'extracted', 'redacted', 'exported',
    ])
    def test_all_event_types(self, app_context, test_project, test_document, event_type):
        from app.database import db
        from app.models.researcher.phase_a_models import SourceProvenance
        prov = SourceProvenance(
            document_id=test_document.id,
            project_id=test_project.id,
            event_type=event_type,
        )
        db.session.add(prov)
        db.session.commit()
        assert prov.event_type == event_type

    def test_provenance_lineage_chain(self, app_context, test_project, test_document):
        """A redacted copy can reference its parent document."""
        from app.database import db
        from app.models.researcher import ResearcherDocument
        from app.models.researcher.phase_a_models import SourceProvenance
        redacted = ResearcherDocument(
            project_id=test_project.id,
            filename='redacted.pdf',
            file_path='',
            file_size=100, source_type='test',
        )
        db.session.add(redacted)
        db.session.flush()
        prov = SourceProvenance(
            document_id=redacted.id,
            project_id=test_project.id,
            event_type='redacted',
            parent_document_id=test_document.id,
        )
        db.session.add(prov)
        db.session.commit()
        assert prov.parent_document_id == test_document.id


class TestPhaseAModelsRegistration:
    def test_all_models_in_init(self):
        from app.models.researcher import (
            ResearchBrief, EvidenceItem, Claim, ClaimEvidence,
            ReviewStep, SourceProvenance,
        )
        for cls in [ResearchBrief, EvidenceItem, Claim, ClaimEvidence, ReviewStep, SourceProvenance]:
            assert cls is not None
            assert hasattr(cls, '__tablename__')

    def test_tablenames_correct(self):
        from app.models.researcher.phase_a_models import (
            ResearchBrief, EvidenceItem, Claim, ClaimEvidence,
            ReviewStep, SourceProvenance,
        )
        assert ResearchBrief.__tablename__ == 'research_briefs'
        assert EvidenceItem.__tablename__ == 'evidence_items'
        assert Claim.__tablename__ == 'claims'
        assert ClaimEvidence.__tablename__ == 'claim_evidence'
        assert ReviewStep.__tablename__ == 'review_steps'
        assert SourceProvenance.__tablename__ == 'source_provenance'
