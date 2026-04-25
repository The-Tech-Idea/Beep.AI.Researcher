"""Phase B tests.

Covers:
  B.1 — Research Lifecycle Routes (briefs, claims, evidence, reviews)
  B.2 — Compliance Policy & Templates (RetentionPolicy, CompliancePolicyTemplate)
  B.3 — Threaded Comments (parent_id, mentions, replies)
  B.4 — Observability Routes (project health, cache stats, job queue)
"""
import json
import pytest


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _json(r):
    return r.get_json()


def _make_project(client, name="B-Test Project"):
    r = client.post('/projects/', json={'name': name, 'description': 'Phase B test'})
    assert r.status_code in (200, 201), r.data
    return _json(r)['id']


def _make_brief(client, pid, title="Brief Alpha"):
    r = client.post(f'/projects/{pid}/briefs',
                    json={'title': title, 'sector': 'medical', 'status': 'draft'})
    assert r.status_code == 201, r.data
    return _json(r)


def _make_claim(client, pid, text="Claim One"):
    r = client.post(f'/projects/{pid}/claims',
                    json={'claim_text': text, 'claim_type': 'factual', 'verdict': 'unclear'})
    assert r.status_code == 201, r.data
    return _json(r)


def _make_evidence(client, pid, text="Evidence A"):
    r = client.post(f'/projects/{pid}/evidence',
                    json={'claim_text': text, 'strength': 'high', 'direction': 'supports'})
    assert r.status_code == 201, r.data
    return _json(r)


# ─────────────────────────────────────────────────────────────
#  B.1 — Research Lifecycle: Briefs
# ─────────────────────────────────────────────────────────────

class TestBriefs:
    def test_create_brief(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/briefs',
                        json={'title': 'My Brief', 'sector': 'legal', 'status': 'draft'})
        assert r.status_code == 201
        d = _json(r)
        assert d['title'] == 'My Brief'
        assert d['sector'] == 'legal'
        assert d['status'] == 'draft'

    def test_create_brief_missing_title(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/briefs', json={'sector': 'legal'})
        assert r.status_code == 400

    def test_list_briefs(self, client):
        pid = _make_project(client)
        _make_brief(client, pid, "B1")
        _make_brief(client, pid, "B2")
        r = client.get(f'/projects/{pid}/briefs')
        assert r.status_code == 200
        assert len(_json(r)['briefs']) == 2

    def test_list_briefs_filter_sector(self, client):
        pid = _make_project(client)
        client.post(f'/projects/{pid}/briefs', json={'title': 'Legal Brief', 'sector': 'legal'})
        client.post(f'/projects/{pid}/briefs', json={'title': 'Med Brief', 'sector': 'medical'})
        r = client.get(f'/projects/{pid}/briefs?sector=legal')
        assert r.status_code == 200
        briefs = _json(r)['briefs']
        assert all(b['sector'] == 'legal' for b in briefs)

    def test_get_brief(self, client):
        pid = _make_project(client)
        brief = _make_brief(client, pid)
        r = client.get(f'/projects/{pid}/briefs/{brief["id"]}')
        assert r.status_code == 200
        assert _json(r)['id'] == brief['id']

    def test_update_brief(self, client):
        pid = _make_project(client)
        brief = _make_brief(client, pid)
        r = client.put(f'/projects/{pid}/briefs/{brief["id"]}',
                       json={'status': 'final', 'title': 'Updated'})
        assert r.status_code == 200
        d = _json(r)
        assert d['status'] == 'final'
        assert d['title'] == 'Updated'

    def test_delete_brief(self, client):
        pid = _make_project(client)
        brief = _make_brief(client, pid)
        r = client.delete(f'/projects/{pid}/briefs/{brief["id"]}')
        assert r.status_code == 204
        r2 = client.get(f'/projects/{pid}/briefs/{brief["id"]}')
        assert r2.status_code == 404

    def test_brief_wrong_project(self, client):
        pid1 = _make_project(client, "P1")
        pid2 = _make_project(client, "P2")
        brief = _make_brief(client, pid1)
        r = client.get(f'/projects/{pid2}/briefs/{brief["id"]}')
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
#  B.1 — Research Lifecycle: Claims
# ─────────────────────────────────────────────────────────────

class TestClaims:
    def test_create_claim(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/claims',
                        json={'claim_text': 'Drug X is effective.', 'claim_type': 'factual'})
        assert r.status_code == 201
        d = _json(r)
        assert d['claim_text'] == 'Drug X is effective.'
        assert d['verdict'] == 'unclear'

    def test_create_claim_missing_text(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/claims', json={'claim_type': 'factual'})
        assert r.status_code == 400

    def test_list_claims(self, client):
        pid = _make_project(client)
        _make_claim(client, pid, "C1")
        _make_claim(client, pid, "C2")
        r = client.get(f'/projects/{pid}/claims')
        assert r.status_code == 200
        assert len(_json(r)['claims']) == 2

    def test_update_claim_verdict(self, client):
        pid = _make_project(client)
        claim = _make_claim(client, pid)
        r = client.put(f'/projects/{pid}/claims/{claim["id"]}',
                       json={'verdict': 'supported', 'confidence_score': 0.9})
        assert r.status_code == 200
        d = _json(r)
        assert d['verdict'] == 'supported'
        assert d['confidence_score'] == pytest.approx(0.9)

    def test_delete_claim(self, client):
        pid = _make_project(client)
        claim = _make_claim(client, pid)
        r = client.delete(f'/projects/{pid}/claims/{claim["id"]}')
        assert r.status_code == 204

    def test_link_evidence_to_claim(self, client):
        pid = _make_project(client)
        claim = _make_claim(client, pid)
        ev = _make_evidence(client, pid)
        r = client.post(f'/projects/{pid}/claims/{claim["id"]}/evidence',
                        json={'evidence_id': ev['id'], 'role': 'supporting'})
        assert r.status_code == 201
        d = _json(r)
        assert d['claim_id'] == claim['id']
        assert d['evidence_id'] == ev['id']
        assert d['role'] == 'supporting'

    def test_link_evidence_idempotent(self, client):
        pid = _make_project(client)
        claim = _make_claim(client, pid)
        ev = _make_evidence(client, pid)
        client.post(f'/projects/{pid}/claims/{claim["id"]}/evidence',
                    json={'evidence_id': ev['id'], 'role': 'supporting'})
        # Second link — should update role, not duplicate
        r = client.post(f'/projects/{pid}/claims/{claim["id"]}/evidence',
                        json={'evidence_id': ev['id'], 'role': 'refuting'})
        assert r.status_code == 200
        assert _json(r)['role'] == 'refuting'

    def test_get_claim_includes_evidence_links(self, client):
        pid = _make_project(client)
        claim = _make_claim(client, pid)
        ev = _make_evidence(client, pid)
        client.post(f'/projects/{pid}/claims/{claim["id"]}/evidence',
                    json={'evidence_id': ev['id']})
        r = client.get(f'/projects/{pid}/claims/{claim["id"]}')
        assert r.status_code == 200
        d = _json(r)
        assert len(d['evidence_links']) == 1


# ─────────────────────────────────────────────────────────────
#  B.1 — Research Lifecycle: Evidence
# ─────────────────────────────────────────────────────────────

class TestEvidence:
    def test_create_evidence(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/evidence', json={
            'claim_text': 'Found in study',
            'verbatim_quote': '"The results were significant"',
            'strength': 'high',
            'direction': 'supports',
        })
        assert r.status_code == 201
        d = _json(r)
        assert d['strength'] == 'high'
        assert d['direction'] == 'supports'

    def test_create_evidence_missing_claim_text(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/evidence', json={'strength': 'low'})
        assert r.status_code == 400

    def test_list_evidence_filter_strength(self, client):
        pid = _make_project(client)
        client.post(f'/projects/{pid}/evidence', json={'claim_text': 'HighEv', 'strength': 'high'})
        client.post(f'/projects/{pid}/evidence', json={'claim_text': 'LowEv', 'strength': 'low'})
        r = client.get(f'/projects/{pid}/evidence?strength=high')
        assert r.status_code == 200
        items = _json(r)['evidence']
        assert all(i['strength'] == 'high' for i in items)

    def test_update_evidence(self, client):
        pid = _make_project(client)
        ev = _make_evidence(client, pid)
        r = client.put(f'/projects/{pid}/evidence/{ev["id"]}',
                       json={'strength': 'very_low', 'direction': 'refutes'})
        assert r.status_code == 200
        d = _json(r)
        assert d['strength'] == 'very_low'
        assert d['direction'] == 'refutes'

    def test_delete_evidence(self, client):
        pid = _make_project(client)
        ev = _make_evidence(client, pid)
        r = client.delete(f'/projects/{pid}/evidence/{ev["id"]}')
        assert r.status_code == 204
        r2 = client.get(f'/projects/{pid}/evidence/{ev["id"]}')
        assert r2.status_code == 404


# ─────────────────────────────────────────────────────────────
#  B.1 — Research Lifecycle: ReviewSteps
# ─────────────────────────────────────────────────────────────

class TestReviews:
    def test_create_review(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/reviews', json={
            'stage': 'screening',
            'decision': 'pass',
            'notes': 'Looks relevant',
        })
        assert r.status_code == 201
        d = _json(r)
        assert d['stage'] == 'screening'
        assert d['decision'] == 'pass'

    def test_create_review_invalid_stage(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/reviews', json={'stage': 'nonsense'})
        assert r.status_code == 400

    def test_list_reviews(self, client):
        pid = _make_project(client)
        client.post(f'/projects/{pid}/reviews', json={'stage': 'screening', 'decision': 'pass'})
        client.post(f'/projects/{pid}/reviews', json={'stage': 'eligibility', 'decision': 'exclude'})
        r = client.get(f'/projects/{pid}/reviews')
        assert r.status_code == 200
        assert len(_json(r)['reviews']) == 2

    def test_filter_reviews_by_stage(self, client):
        pid = _make_project(client)
        client.post(f'/projects/{pid}/reviews', json={'stage': 'screening'})
        client.post(f'/projects/{pid}/reviews', json={'stage': 'eligibility'})
        r = client.get(f'/projects/{pid}/reviews?stage=screening')
        assert r.status_code == 200
        assert all(s['stage'] == 'screening' for s in _json(r)['reviews'])

    def test_sign_off_review(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/reviews', json={'stage': 'included', 'decision': 'uncertain'})
        rid = _json(r)['id']
        r2 = client.put(f'/projects/{pid}/reviews/{rid}/sign-off',
                        json={'decision': 'pass', 'notes': 'Approved by lead'})
        assert r2.status_code == 200
        assert _json(r2)['decision'] == 'pass'

    def test_sign_off_invalid_decision(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/reviews', json={'stage': 'screening'})
        rid = _json(r)['id']
        r2 = client.put(f'/projects/{pid}/reviews/{rid}/sign-off',
                        json={'decision': 'bad_value'})
        assert r2.status_code == 400


# ─────────────────────────────────────────────────────────────
#  B.2 — Compliance Policy Templates & RetentionPolicy
# ─────────────────────────────────────────────────────────────

class TestComplianceTemplates:
    def test_list_templates_includes_builtins(self, client):
        r = client.get('/projects/compliance-templates')
        assert r.status_code == 200
        templates = _json(r)['templates']
        names = {t['name'] for t in templates}
        assert 'hipaa' in names
        assert 'gdpr' in names
        assert 'ferpa' in names
        assert 'soc2' in names
        assert 'foia' in names

    def test_get_specific_template(self, client):
        r = client.get('/projects/compliance-templates/hipaa')
        assert r.status_code == 200
        d = _json(r)
        assert d['name'] == 'hipaa'
        assert d['requires_encryption'] is True
        assert d['retention_days'] == 2190

    def test_template_not_found(self, client):
        r = client.get('/projects/compliance-templates/nonexistent')
        assert r.status_code == 404


class TestRetentionPolicy:
    def test_set_policy_from_template(self, client):
        pid = _make_project(client)
        r = client.put(f'/projects/{pid}/compliance-policy',
                       json={'template_name': 'hipaa'})
        assert r.status_code == 200
        d = _json(r)
        assert d['template_name'] == 'hipaa'
        assert d['requires_encryption'] is True
        assert d['retention_days'] == 2190

    def test_get_policy(self, client):
        pid = _make_project(client)
        client.put(f'/projects/{pid}/compliance-policy',
                   json={'template_name': 'gdpr', 'retention_days': 730})
        r = client.get(f'/projects/{pid}/compliance-policy')
        assert r.status_code == 200
        policy = _json(r)['policy']
        assert policy['retention_days'] == 730  # Override applied

    def test_legal_hold_place_and_release(self, client):
        pid = _make_project(client)
        # Place hold
        r = client.post(f'/projects/{pid}/compliance-policy/hold',
                        json={'hold_reason': 'Litigation matter XYZ'})
        assert r.status_code == 201
        d = _json(r)
        assert d['is_legal_hold'] is True
        assert d['auto_destroy'] is False

        # Release hold
        r2 = client.delete(f'/projects/{pid}/compliance-policy/hold')
        assert r2.status_code == 200
        assert _json(r2)['policy']['is_legal_hold'] is False

    def test_release_hold_when_none_active(self, client):
        pid = _make_project(client)
        # Create a policy without a hold first
        client.put(f'/projects/{pid}/compliance-policy', json={'retention_days': 365})
        r = client.delete(f'/projects/{pid}/compliance-policy/hold')
        assert r.status_code == 409

    def test_destruction_cert_blocked_by_hold(self, client):
        pid = _make_project(client)
        client.post(f'/projects/{pid}/compliance-policy/hold',
                    json={'hold_reason': 'Active litigation'})
        r = client.post(f'/projects/{pid}/compliance-policy/destruction-certificate',
                        json={'issued_by': 1})
        assert r.status_code == 409

    def test_destruction_cert_ok(self, client):
        pid = _make_project(client)
        client.put(f'/projects/{pid}/compliance-policy', json={'retention_days': 30})
        r = client.post(f'/projects/{pid}/compliance-policy/destruction-certificate',
                        json={'issued_by': 1, 'method': 'secure_erase'})
        assert r.status_code == 200
        cert = _json(r)['certificate']
        assert cert['method'] == 'secure_erase'

    def test_backward_compat_retention_get(self, client):
        pid = _make_project(client)
        client.put(f'/projects/{pid}/compliance-policy', json={'retention_days': 90})
        r = client.get(f'/projects/{pid}/retention')
        assert r.status_code == 200
        assert _json(r)['retention_days'] == 90

    def test_backward_compat_retention_put(self, client):
        pid = _make_project(client)
        r = client.put(f'/projects/{pid}/retention', json={'retention_days': 180})
        assert r.status_code == 200
        assert _json(r)['retention_days'] == 180

    def test_retention_put_persists_action(self, client):
        pid = _make_project(client)
        r = client.put(f'/projects/{pid}/retention', json={'retention_days': 180, 'action': 'archive'})
        assert r.status_code == 200
        payload = _json(r)
        assert payload['retention_days'] == 180
        assert payload['action'] == 'archive'

        r = client.get(f'/projects/{pid}/retention')
        assert r.status_code == 200
        payload = _json(r)
        assert payload['retention_days'] == 180
        assert payload['action'] == 'archive'


# ─────────────────────────────────────────────────────────────
#  B.3 — Threaded Comments
# ─────────────────────────────────────────────────────────────

class TestThreadedComments:
    def test_create_top_level_comment(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/comments',
                        json={'content': 'Top-level comment', 'user_id': 1})
        assert r.status_code == 201
        d = _json(r)
        assert d['content'] == 'Top-level comment'
        assert d['parent_id'] is None

    def test_create_reply(self, client):
        pid = _make_project(client)
        parent = _json(client.post(f'/projects/{pid}/comments',
                                   json={'content': 'Parent comment', 'user_id': 1}))
        r = client.post(f'/projects/{pid}/comments',
                        json={'content': 'Reply comment', 'user_id': 2, 'parent_id': parent['id']})
        assert r.status_code == 201
        d = _json(r)
        assert d['parent_id'] == parent['id']

    def test_list_comments_top_level_only(self, client):
        pid = _make_project(client)
        parent = _json(client.post(f'/projects/{pid}/comments',
                                   json={'content': 'Root', 'user_id': 1}))
        client.post(f'/projects/{pid}/comments',
                    json={'content': 'Reply', 'user_id': 2, 'parent_id': parent['id']})
        r = client.get(f'/projects/{pid}/comments')
        assert r.status_code == 200
        # Only root-level comments returned
        comments = _json(r)['comments']
        assert all(c['parent_id'] is None for c in comments)
        assert len(comments) == 1

    def test_get_comment_includes_replies(self, client):
        pid = _make_project(client)
        parent = _json(client.post(f'/projects/{pid}/comments',
                                   json={'content': 'Root', 'user_id': 1}))
        client.post(f'/projects/{pid}/comments',
                    json={'content': 'Reply 1', 'user_id': 2, 'parent_id': parent['id']})
        client.post(f'/projects/{pid}/comments',
                    json={'content': 'Reply 2', 'user_id': 3, 'parent_id': parent['id']})
        r = client.get(f'/projects/{pid}/comments/{parent["id"]}')
        assert r.status_code == 200
        d = _json(r)
        assert len(d['replies']) == 2

    def test_mentions_stored(self, client):
        pid = _make_project(client)
        mentions = [{'user_id': 5, 'username': 'alice'}]
        r = client.post(f'/projects/{pid}/comments',
                        json={'content': '@alice great point', 'user_id': 1, 'mentions': mentions})
        assert r.status_code == 201
        d = _json(r)
        assert len(d['mentions']) == 1
        assert d['mentions'][0]['username'] == 'alice'

    def test_edit_comment(self, client):
        pid = _make_project(client)
        c = _json(client.post(f'/projects/{pid}/comments',
                              json={'content': 'Original', 'user_id': 1}))
        r = client.put(f'/projects/{pid}/comments/{c["id"]}',
                       json={'content': 'Edited'})
        assert r.status_code == 200
        assert _json(r)['content'] == 'Edited'

    def test_delete_comment(self, client):
        pid = _make_project(client)
        c = _json(client.post(f'/projects/{pid}/comments',
                              json={'content': 'To delete', 'user_id': 1}))
        r = client.delete(f'/projects/{pid}/comments/{c["id"]}')
        assert r.status_code == 204

    def test_reply_invalid_parent(self, client):
        pid = _make_project(client)
        r = client.post(f'/projects/{pid}/comments',
                        json={'content': 'Reply', 'user_id': 1, 'parent_id': 999999})
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
#  B.4 — Observability Routes
# ─────────────────────────────────────────────────────────────

class TestObservability:
    def test_project_health(self, client):
        pid = _make_project(client)
        r = client.get(f'/projects/{pid}/health')
        assert r.status_code == 200
        d = _json(r)
        assert d['project_id'] == pid
        assert 'total_documents' in d
        assert 'cache_entries_total' in d

    def test_project_health_with_hours_param(self, client):
        pid = _make_project(client)
        r = client.get(f'/projects/{pid}/health?hours=48')
        assert r.status_code == 200
        assert _json(r)['window_hours'] == 48

    def test_project_health_nonexistent(self, client):
        r = client.get('/projects/999999/health')
        assert r.status_code == 404

    def test_cache_stats(self, client):
        pid = _make_project(client)
        r = client.get(f'/projects/{pid}/cache-stats')
        assert r.status_code == 200
        d = _json(r)
        assert d['project_id'] == pid
        assert 'total_cache_entries' in d
        assert 'by_provider' in d

    def test_job_queue_stats(self, client):
        r = client.get('/projects/job-queue-stats')
        assert r.status_code == 200
        d = _json(r)
        assert 'queue_depth' in d
        assert 'by_status' in d
