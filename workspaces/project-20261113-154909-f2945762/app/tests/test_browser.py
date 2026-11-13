import pytest
from playwright.sync_api import sync_playwright
from app import create_app, db
from datetime import datetime

@pytest.fixture
def server():
    app = create_app(test_config={'DATABASE': 'instance/test_expenses_browser.sqlite3'})
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()

@pytest.fixture
def page(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        server_url = 'http://127.0.0.1:5000'
        server.run(port=5000, use_reloader=False)
        page = browser.new_page()
        yield page
        page.close()
        browser.close()

@pytest.fixture
def expense_data():
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'category': 'Groceries',
        'description': 'Weekly grocery shopping',
        'amount_cents': 1500
    }

def test_add_expense(page, expense_data):
    page.goto('http://127.0.0.1:5000')
    page.fill('#expense-date', expense_data['date'])
    page.fill('#expense-category', expense_data['category'])
    page.fill('#expense-description', expense_data['description'])
    page.fill('#expense-amount', str(expense_data['amount_cents'] / 100))
    page.click('button[type="submit"]')
    page.wait_for_selector('#error-message.visible', state='hidden')
    page.reload()
    page.wait_for_selector('#expense-list li')
    expenses = page.query_selector_all('#expense-list li')
    assert len(expenses) == 1
    expense_text = expenses[0].text_content()
    assert expense_data['date'] in expense_text
    assert expense_data['category'] in expense_text
    assert f'${(expense_data['amount_cents'] / 100):.2f}' in expense_text

def test_filter_expenses(page, expense_data):
    page.goto('http://127.0.0.1:5000')
    page.fill('#expense-date', expense_data['date'])
    page.fill('#expense-category', expense_data['category'])
    page.fill('#expense-description', expense_data['description'])
    page.fill('#expense-amount', str(expense_data['amount_cents'] / 100))
    page.click('button[type="submit"]')
    page.wait_for_selector('#error-message.visible', state='hidden')
    page.fill('#filter-category', expense_data['category'])
    page.click('button[data-testid="apply-filter"]')
    page.wait_for_selector('#expense-list li')
    expenses = page.query_selector_all('#expense-list li')
    assert len(expenses) == 1
    expense_text = expenses[0].text_content()
    assert expense_data['date'] in expense_text
    assert expense_data['category'] in expense_text
    assert f'${(expense_data['amount_cents'] / 100):.2f}' in expense_text

def test_clear_filter(page, expense_data):
    page.goto('http://127.0.0.1:5000')
    page.fill('#expense-date', expense_data['date'])
    page.fill('#expense-category', expense_data['category'])
    page.fill('#expense-description', expense_data['description'])
    page.fill('#expense-amount', str(expense_data['amount_cents'] / 100))
    page.click('button[type="submit"]')
    page.wait_for_selector('#error-message.visible', state='hidden')
    page.fill('#filter-category', expense_data['category'])
    page.click('button[data-testid="apply-filter"]')
    page.wait_for_selector('#expense-list li')
    expenses = page.query_selector_all('#expense-list li')
    assert len(expenses) == 1
    page.fill('#filter-category', '')
    page.click('button[data-testid="apply-filter"]')
    page.wait_for_selector('#expense-list li')
    expenses = page.query_selector_all('#expense-list li')
    assert len(expenses) == 1
