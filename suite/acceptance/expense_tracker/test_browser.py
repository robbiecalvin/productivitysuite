import threading
import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server
from app import create_app


@pytest.fixture
def opened_page(page, tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'browser.db')})
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f'http://127.0.0.1:{server.server_port}')
    expect(page.get_by_test_id('add-expense')).to_be_enabled()
    yield page
    server.shutdown(); thread.join(timeout=5); server.server_close()
    assert not errors


def add(page, category='Food', amount='0.10', description='Lunch'):
    page.get_by_test_id('expense-date').fill('2024-02-29')
    page.get_by_test_id('expense-category').fill(category)
    page.get_by_test_id('expense-description').fill(description)
    page.get_by_test_id('expense-amount').fill(amount)
    page.get_by_test_id('add-expense').click()
    expect(page.get_by_test_id('add-expense')).to_be_enabled()


@pytest.mark.parametrize('viewport', [{'width': 1280, 'height': 800}, {'width': 390, 'height': 844}])
def test_lifecycle_filter_total_reload(opened_page, viewport):
    page = opened_page; page.set_viewport_size(viewport)
    items = page.get_by_test_id('expense-item')
    add(page)
    expect(items).to_have_count(1)
    add(page, category='Travel', amount='0.20')
    expect(items).to_have_count(2)
    expect(page.get_by_test_id('expense-total')).to_have_text('CAD $0.30')
    page.get_by_test_id('category-filter').fill('Food')
    page.get_by_test_id('apply-filter').click()
    expect(items).to_have_count(1)
    expect(page.get_by_test_id('expense-total')).to_have_text('CAD $0.10')
    # Adding while filtered must preserve the filtered view and total.
    add(page, category='Travel', amount='1.00')
    expect(items).to_have_count(1)
    expect(page.get_by_test_id('expense-total')).to_have_text('CAD $0.10')
    page.get_by_test_id('category-filter').fill('')
    page.get_by_test_id('apply-filter').click()
    expect(items).to_have_count(3)
    expect(page.get_by_test_id('expense-total')).to_have_text('CAD $1.30')
    page.reload()
    expect(items).to_have_count(3)
    expect(items.first).to_contain_text('2024-02-29')
    expect(items.first).to_contain_text('Lunch')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_literal_html(opened_page):
    page = opened_page
    text = '<img src=x onerror="window.injected=true">'
    add(page, category=text, description=text)
    item = page.get_by_test_id('expense-item')
    expect(item).to_contain_text(text)
    expect(item.locator('img')).to_have_count(0)
    assert page.evaluate('window.injected === true') is False


@pytest.mark.parametrize('failure', ['api', 'network'])
def test_failure_preserves_form_and_retry(opened_page, failure):
    page = opened_page
    def fail(route):
        if route.request.method != 'POST':
            return route.continue_()
        if failure == 'network':
            route.abort()
        else:
            route.fulfill(status=500, content_type='application/json', body='{"error":"Try again"}')
    page.route('**/api/expenses*', fail)
    add(page, category='Food')
    expect(page.get_by_test_id('error-message')).to_be_visible()
    expect(page.get_by_test_id('expense-category')).to_have_value('Food')
    expect(page.get_by_test_id('expense-amount')).to_have_value('0.10')
    page.unroute('**/api/expenses*', fail)
    page.get_by_test_id('add-expense').click()
    expect(page.get_by_test_id('expense-item')).to_have_count(1)
    expect(page.get_by_test_id('error-message')).to_be_hidden()


@pytest.mark.parametrize('amount', ['0', '-1', '1.005', 'NaN', '1e3', '1000000.01'])
def test_rejects_invalid_dollar_text_without_write(opened_page, amount):
    page = opened_page
    posts = []
    page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
    add(page, amount=amount)
    expect(page.get_by_test_id('error-message')).to_be_visible()
    expect(page.get_by_test_id('expense-item')).to_have_count(0)
    expect(page.get_by_test_id('expense-amount')).to_have_value(amount)
    assert not posts


def test_decimal_conversion_is_exact(opened_page):
    page = opened_page
    payloads = []
    page.on('request', lambda request: payloads.append(request.post_data_json) if request.method == 'POST' else None)
    add(page, amount='0.29')
    expect(page.get_by_test_id('expense-total')).to_have_text('CAD $0.29')
    assert payloads[0]['amount_cents'] == 29
