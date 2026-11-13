import pytest
import requests
from suite.llm import OllamaClient


def test_chat_protocol_and_environment(model_server, monkeypatch):
    with model_server(lambda body: (200, {'message': {'content': 'ready'}})) as (url, calls):
        monkeypatch.setenv('OLLAMA_BASE_URL', url)
        monkeypatch.setenv('OLLAMA_MODEL', 'simulated')
        assert OllamaClient().chat('objective', json_mode=True) == 'ready'
        assert calls[0]['model'] == 'simulated'
        assert calls[0]['stream'] is False and calls[0]['format'] == 'json'
        assert calls[0]['messages'][1]['content'] == 'objective'


@pytest.mark.parametrize('status,payload,error', [
    (503, b'unavailable', 'HTTP 503'), (200, b'not-json', 'invalid JSON'),
    (200, [], 'unexpected response'), (200, {'done_reason': 'length'}, 'output limit'),
    (200, {}, 'missing its message'), (200, {'message': {'content': ' '}}, 'no usable text')])
def test_model_errors(model_server, status, payload, error):
    with model_server(lambda body: (status, payload)) as (url, _):
        with pytest.raises(RuntimeError, match=error):
            OllamaClient(base_url=url).chat('test')


@pytest.mark.parametrize('exception,message', [
    (requests.exceptions.ConnectTimeout(), 'timed out'),
    (requests.exceptions.ConnectionError(), 'Cannot connect'),
    (requests.exceptions.RequestException(), 'request failed')])
def test_transport_errors(monkeypatch, exception, message):
    def fail(*args, **kwargs):
        raise exception
    monkeypatch.setattr(requests, 'post', fail)
    with pytest.raises(RuntimeError, match=message):
        OllamaClient().chat('test')


@pytest.mark.parametrize('url', ['file:///tmp/model', 'http://u:p@localhost', 'http://localhost?a=b'])
def test_invalid_service_url(url):
    with pytest.raises(ValueError):
        OllamaClient(base_url=url)
