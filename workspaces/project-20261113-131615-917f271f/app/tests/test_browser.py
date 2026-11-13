import threading

import pytest
from playwright.sync_api import expect
from werkzeug.serving import make_server

from app import create_app


@pytest.fixture
def app_url(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "browser.sqlite3"),
    })
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture
def opened_page(page, app_url):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(app_url)
    expect(page.get_by_test_id("add-task")).to_be_enabled()
    yield page
    assert not errors, f"Uncaught JavaScript errors: {errors}"


def add_task(page, title, description="Details"):
    page.get_by_test_id("task-title").fill(title)
    page.get_by_test_id("task-description").fill(description)
    page.get_by_test_id("add-task").click()
    expect(page.get_by_test_id("add-task")).to_be_enabled()


@pytest.mark.parametrize("viewport", [
    {"width": 1280, "height": 800},
    {"width": 390, "height": 844},
])
def test_task_lifecycle(opened_page, viewport):
    page = opened_page
    page.set_viewport_size(viewport)
    items = page.get_by_test_id("task-item")

    add_task(page, "First task")
    expect(items).to_have_count(1)
    add_task(page, "Second task")
    expect(items).to_have_count(2)

    first = items.filter(has_text="First task")
    toggle = first.get_by_test_id("task-toggle")

    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_be_enabled()

    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(toggle).to_be_enabled()

    page.reload()
    expect(items).to_have_count(2)
    expect(
        items.filter(has_text="First task").get_by_test_id("task-toggle")
    ).to_have_attribute("aria-pressed", "false")

    items.filter(has_text="First task").get_by_test_id("task-delete").click()
    expect(items).to_have_count(1)
    expect(items).to_contain_text("Second task")

    page.reload()
    expect(items).to_have_count(1)
    expect(items).to_contain_text("Second task")


def test_user_html_is_literal(opened_page):
    page = opened_page
    title = '<img src=x onerror="window.injected=true">'
    add_task(page, title)

    item = page.get_by_test_id("task-item")
    expect(item).to_contain_text(title)
    expect(item.locator("img")).to_have_count(0)
    assert page.evaluate("window.injected === true") is False


def test_api_error_is_visible_and_recoverable(opened_page):
    page = opened_page

    def fail_create(route):
        if route.request.method == "POST":
            route.fulfill(
                status=500,
                content_type="application/json",
                body='{"error": "Simulated save failure"}',
            )
        else:
            route.continue_()

    page.route("**/api/tasks", fail_create)
    add_task(page, "Retry this task")

    error = page.get_by_test_id("error-message")
    expect(error).to_be_visible()
    expect(error).to_contain_text("Simulated save failure")
    expect(page.get_by_test_id("task-item")).to_have_count(0)
    expect(page.get_by_test_id("task-title")).to_have_value("Retry this task")

    page.unroute("**/api/tasks", fail_create)
    page.get_by_test_id("add-task").click()
    expect(page.get_by_test_id("task-item")).to_have_count(1)
    expect(error).to_be_hidden()
