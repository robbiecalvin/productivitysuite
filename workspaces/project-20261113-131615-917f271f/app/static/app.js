"use strict";

const form = document.getElementById("add-task-form");
const taskList = document.getElementById("task-list");
const errorMessage = document.querySelector('[data-testid="error-message"]');
const titleInput = document.getElementById("task-title");
const descriptionInput = document.getElementById("task-description");

let busy = false;

async function api(path, options = {}) {
    const response = await fetch(path, options);

    if (!response.ok) {
        let message = `Request failed (${response.status}).`;
        try {
            const body = await response.json();
            if (typeof body.error === "string") {
                message = body.error;
            }
        } catch {
            // Keep the status-based error when the response is not JSON.
        }
        throw new Error(message);
    }

    return response.status === 204 ? null : response.json();
}

function showError(error) {
    errorMessage.textContent = error.message || "Something went wrong.";
    errorMessage.hidden = false;
}

function setBusy(value) {
    busy = value;
    document.querySelectorAll("button").forEach(button => {
        button.disabled = value;
    });
}

async function perform(action) {
    if (busy) return;

    setBusy(true);
    errorMessage.hidden = true;
    errorMessage.textContent = "";

    try {
        await action();
    } catch (error) {
        showError(error);
    } finally {
        setBusy(false);
    }
}

function renderTasks(tasks) {
    taskList.replaceChildren();

    for (const task of tasks) {
        const item = document.createElement("li");
        item.dataset.testid = "task-item";
        item.dataset.taskId = String(task.id);
        item.classList.toggle("completed", task.completed);

        const title = document.createElement("span");
        title.textContent = task.title;

        const description = document.createElement("p");
        description.textContent = task.description;

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.dataset.testid = "task-toggle";
        toggle.textContent = task.completed ? "Mark incomplete" : "Mark complete";
        toggle.setAttribute("aria-pressed", String(task.completed));
        toggle.disabled = busy;
        toggle.addEventListener("click", () => perform(async () => {
            await api(`/api/tasks/${task.id}`, {
                method: "PATCH",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({completed: !task.completed}),
            });
            await refreshTasks();
        }));

        const remove = document.createElement("button");
        remove.type = "button";
        remove.dataset.testid = "task-delete";
        remove.textContent = "Delete";
        remove.setAttribute("aria-label", `Delete task: ${task.title}`);
        remove.disabled = busy;
        remove.addEventListener("click", () => perform(async () => {
            await api(`/api/tasks/${task.id}`, {method: "DELETE"});
            await refreshTasks();
        }));

        item.append(title, description, toggle, remove);
        taskList.append(item);
    }
}

async function refreshTasks() {
    const data = await api("/api/tasks");
    renderTasks(data.tasks);
}

form.addEventListener("submit", event => {
    event.preventDefault();

    perform(async () => {
        const title = titleInput.value.trim();
        if (!title) {
            throw new Error("Enter a task title.");
        }

        await api("/api/tasks", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                title,
                description: descriptionInput.value,
            }),
        });

        form.reset();
        await refreshTasks();
    });
});

perform(refreshTasks);
