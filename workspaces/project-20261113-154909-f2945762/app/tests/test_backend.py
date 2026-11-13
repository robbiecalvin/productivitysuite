import pytest
from app import create_app, db
from datetime import datetime

@pytest.fixture
def client():
    app = create_app(test_config={'DATABASE': 'instance/test_expenses.sqlite3'})
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()

@pytest.fixture
def expense_data():
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'category': 'Groceries',
        'description': 'Weekly grocery shopping',
        'amount_cents': 1500
    }

def test_add_expense(client, expense_data):
    response = client.post('/api/expenses', json=expense_data)
    assert response.status_code == 201
    data = response.json()
    assert 'expense' in data
    assert data['expense']['date'] == expense_data['date']
    assert data['expense']['category'] == expense_data['category']
    assert data['expense']['description'] == expense_data['description']
    assert data['expense']['amount_cents'] == expense_data['amount_cents']

def test_get_expenses(client, expense_data):
    client.post('/api/expenses', json=expense_data)
    response = client.get('/api/expenses')
    assert response.status_code == 200
    data = response.json()
    assert 'expenses' in data
    assert len(data['expenses']) == 1
    assert data['total_cents'] == expense_data['amount_cents']

def test_get_expenses_by_category(client, expense_data):
    client.post('/api/expenses', json=expense_data)
    response = client.get(f'/api/expenses?category={expense_data['category']}')
    assert response.status_code == 200
    data = response.json()
    assert 'expenses' in data
    assert len(data['expenses']) == 1
    assert data['total_cents'] == expense_data['amount_cents']

def test_get_expenses_empty_category(client, expense_data):
    client.post('/api/expenses', json=expense_data)
    response = client.get('/api/expenses?category=')
    assert response.status_code == 200
    data = response.json()
    assert 'expenses' in data
    assert len(data['expenses']) == 1
    assert data['total_cents'] == expense_data['amount_cents']

def test_get_expenses_no_results(client):
    response = client.get('/api/expenses?category=Utilities')
    assert response.status_code == 200
    data = response.json()
    assert 'expenses' in data
    assert len(data['expenses']) == 0
    assert data['total_cents'] == 0
