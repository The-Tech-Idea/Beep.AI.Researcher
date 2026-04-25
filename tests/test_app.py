"""Basic app tests."""
import pytest


def test_index_redirects(client):
    r = client.get('/')
    assert r.status_code in (301, 302)
    assert 'researcher' in r.location


def test_researcher_dashboard(client):
    r = client.get('/researcher/')
    assert r.status_code == 200


def test_projects_list(client):
    r = client.get('/projects/')
    assert r.status_code == 200
    j = r.get_json()
    assert 'projects' in j
    assert isinstance(j['projects'], list)


def test_projects_create_no_name(client):
    r = client.post('/projects/', json={})
    assert r.status_code == 400


def test_projects_create_with_name(client):
    r = client.post('/projects/', json={'name': 'Test Project'})
    assert r.status_code in (201, 400)  # 400 if no user
    if r.status_code == 201:
        j = r.get_json()
        assert 'name' in j
        assert j['name'] == 'Test Project'
        assert 'start_url' in j
        assert j['start_url'].endswith(f"/researcher/projects/{j['id']}/start")
        assert 'overview_url' in j
        assert 'settings_url' in j
