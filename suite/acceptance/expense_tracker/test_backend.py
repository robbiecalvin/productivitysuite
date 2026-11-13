"""Suite-owned acceptance checks derived from the agreed expense contract."""
import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    with create_app({"TESTING": True, "DATABASE": str(tmp_path / "nested" / "expenses.db")}).test_client() as client:
        yield client


def expense(**changes):
    return {"date": "2024-02-29", "category": "Food", "description": "Lunch", "amount_cents": 10, **changes}


def test_home_and_empty(client):
    assert client.get('/').status_code == 200
    assert client.get('/api/expenses').get_json() == {"expenses": [], "total_cents": 0}


def test_create_filter_and_exact_total(client):
    records = []
    for payload in [expense(category=' Food '), expense(amount_cents=20), expense(category='Travel', amount_cents=50)]:
        result = client.post('/api/expenses', json=payload)
        assert result.status_code == 201
        record = result.get_json()['expense']
        assert type(record['id']) is int
        assert record == {**payload, 'category': payload['category'].strip(), 'id': record['id']}
        records.append(record)
    assert len({r['id'] for r in records}) == 3
    assert client.get('/api/expenses').get_json() == {'expenses': records, 'total_cents': 80}
    assert client.get('/api/expenses?category=%20Food%20').get_json() == {'expenses': records[:2], 'total_cents': 30}
    for category in ('food', 'Missing'):
        assert client.get('/api/expenses', query_string={'category': category}).get_json() == {'expenses': [], 'total_cents': 0}
    for category in ('', '  '):
        assert client.get('/api/expenses', query_string={'category': category}).get_json()['expenses'] == records


@pytest.mark.parametrize('payload', [None, [], 'text', {},
    expense(date='2023-02-29'), expense(date='2024-2-01'), expense(date='2024-01-01T00:00:00'),
    expense(date=None), expense(date=123), expense(category=None), expense(category=42),
    expense(category=' '), expense(category='x'*61), expense(description=None),
    expense(description=1), expense(description='x'*1001), expense(amount_cents=True),
    expense(amount_cents=0), expense(amount_cents=-1), expense(amount_cents=1.5),
    expense(amount_cents='10'), expense(amount_cents=100000001), expense(extra='bad')])
def test_invalid_creates_are_json_and_do_not_write(client, payload):
    result = client.post('/api/expenses', json=payload)
    assert result.status_code == 400
    assert result.is_json and isinstance(result.get_json().get('error'), str) and result.get_json()['error'].strip()
    assert client.get('/api/expenses').get_json() == {'expenses': [], 'total_cents': 0}


def test_malformed_json(client):
    result = client.post('/api/expenses', data='{', content_type='application/json')
    assert result.status_code == 400 and result.is_json


def test_limits_default_description_and_literal_html(client):
    payload = expense(category='x'*60, description='x'*1000, amount_cents=100000000)
    assert client.post('/api/expenses', json=payload).status_code == 201
    payload = expense(category='<script>alert(1)</script>')
    del payload['description']
    result = client.post('/api/expenses', json=payload)
    assert result.status_code == 201
    assert result.get_json()['expense']['description'] == ''
    assert result.get_json()['expense']['category'] == payload['category']


def test_persistence_and_defaults(tmp_path):
    config = {'TESTING': True, 'DATABASE': str(tmp_path / 'nested' / 'persist.db')}
    first = create_app(config)
    record = first.test_client().post('/api/expenses', json=expense()).get_json()['expense']
    second = create_app(config)
    assert second.test_client().get('/api/expenses').get_json() == {'expenses': [record], 'total_cents': 10}
    # Defaults must survive partial configuration overrides.
    assert 'DATABASE' in first.config


def test_partial_configuration_keeps_database_default(tmp_path, monkeypatch):
    import app as application
    original_flask = application.Flask
    monkeypatch.setattr(application, 'Flask', lambda name: original_flask(name, instance_path=str(tmp_path)))
    configured = application.create_app({'TESTING': True})
    assert configured.config['DATABASE'] == str(tmp_path / 'expenses.sqlite3')
    assert configured.test_client().post('/api/expenses', json=expense()).status_code == 201
