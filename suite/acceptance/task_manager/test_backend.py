import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "tasks.sqlite3"),
    })
    with app.test_client() as client:
        yield client


def assert_error(response, status):
    assert response.status_code == status
    assert response.is_json
    body = response.get_json()
    assert isinstance(body, dict)
    assert isinstance(body.get("error"), str)
    assert body["error"].strip()


def add_task(client, title="Example"):
    response = client.post(
        "/api/tasks",
        json={"title": title, "description": "Details"},
    )
    assert response.status_code == 201
    task = response.get_json()["task"]
    assert type(task["id"]) is int
    assert task["title"] == title.strip()
    assert task["description"] == "Details"
    assert task["completed"] is False
    return task


def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"


def test_create_and_list_tasks(client):
    first = add_task(client, "  First  ")
    second = add_task(client, "Second")
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert response.get_json() == {"tasks": [first, second]}


def test_default_description_and_literal_html(client):
    title = "<script>alert(1)</script>"
    response = client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201
    task = response.get_json()["task"]
    assert task["title"] == title
    assert task["description"] == ""
    assert task["completed"] is False


@pytest.mark.parametrize("payload", [
    {},
    {"title": ""},
    {"title": "   "},
    {"title": "x" * 201},
    {"title": None},
    {"title": 123},
    {"title": ["task"]},
    {"title": "Task", "description": None},
    {"title": "Task", "description": 123},
    {"title": "Task", "description": "x" * 5001},
    {"title": "Task", "unexpected": True},
    [],
    "task",
])
def test_invalid_create(client, payload):
    assert_error(client.post("/api/tasks", json=payload), 400)
    assert client.get("/api/tasks").get_json() == {"tasks": []}


def test_malformed_create_json(client):
    response = client.post(
        "/api/tasks",
        data='{"title":',
        content_type="application/json",
    )
    assert_error(response, 400)


def test_completion_can_be_toggled_both_ways(client):
    task = add_task(client)
    for completed in (True, False):
        response = client.patch(
            f"/api/tasks/{task['id']}",
            json={"completed": completed},
        )
        assert response.status_code == 200
        expected = dict(task, completed=completed)
        assert response.get_json() == {"task": expected}
        assert client.get("/api/tasks").get_json() == {"tasks": [expected]}


@pytest.mark.parametrize("payload", [
    {},
    {"completed": None},
    {"completed": "false"},
    {"completed": 1},
    {"completed": False, "unexpected": True},
    [],
])
def test_invalid_update(client, payload):
    task = add_task(client)
    response = client.patch(
        f"/api/tasks/{task['id']}", json=payload
    )
    assert_error(response, 400)
    assert client.get("/api/tasks").get_json() == {"tasks": [task]}


def test_malformed_update_json(client):
    task = add_task(client)
    response = client.patch(
        f"/api/tasks/{task['id']}",
        data='{"completed":',
        content_type="application/json",
    )
    assert_error(response, 400)


def test_delete_preserves_other_tasks(client):
    first = add_task(client, "Delete me")
    second = add_task(client, "Keep me")
    response = client.delete(f"/api/tasks/{first['id']}")
    assert response.status_code == 204
    assert response.data == b""
    assert client.get("/api/tasks").get_json() == {"tasks": [second]}


def test_missing_tasks(client):
    assert_error(
        client.patch("/api/tasks/99999", json={"completed": True}), 404
    )
    assert_error(client.delete("/api/tasks/99999"), 404)


def test_persistence_across_app_instances(tmp_path):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "persistent.sqlite3"),
    }
    first_app = create_app(config)
    with first_app.test_client() as first_client:
        task = add_task(first_client, "Survive restart")

    second_app = create_app(config)
    with second_app.test_client() as second_client:
        response = second_client.get("/api/tasks")
        assert response.status_code == 200
        assert response.get_json() == {"tasks": [task]}
