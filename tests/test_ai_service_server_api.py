import json

from app.config_manager import config_manager
from app.services import ai_service


class _FakeResponse:
    def __init__(self, payload=None, lines=None, status_code=200):
        self._payload = payload or {}
        self._lines = lines or []
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload

    def iter_lines(self):
        for line in self._lines:
            yield line


def test_generate_with_llm_non_stream_uses_application_token(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')
    ai_service._ai_service = None

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        captured['stream'] = stream
        return _FakeResponse(
            payload={
                'choices': [
                    {'message': {'content': 'Generated answer'}}
                ]
            }
        )

    monkeypatch.setattr(ai_service.requests, 'post', fake_post)

    result = list(ai_service.generate_with_llm('Explain the results', stream=False))

    assert result == [{'token': 'Generated answer'}]
    assert captured['url'] == 'http://localhost:5000/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured['headers']['Content-Type'] == 'application/json'
    assert captured['json']['stream'] is False



def test_generate_with_llm_stream_uses_application_token_and_parses_sse(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')
    ai_service._ai_service = None

    captured = {}
    lines = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b'data: {"choices":[{"delta":{"content":" world"}}]}',
        b'data: [DONE]',
    ]

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        captured['stream'] = stream
        return _FakeResponse(lines=lines)

    monkeypatch.setattr(ai_service.requests, 'post', fake_post)

    result = list(ai_service.generate_with_llm('Stream this', stream=True))

    assert result == [{'token': 'Hello'}, {'token': ' world'}]
    assert captured['url'] == 'http://localhost:5000/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured['headers']['Content-Type'] == 'application/json'
    assert captured['json']['stream'] is True
    assert captured['stream'] is True
