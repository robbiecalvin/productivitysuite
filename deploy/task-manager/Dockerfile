FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY deploy/task-manager/requirements.txt .
RUN mkdir -p /var/data && python -m pip install --no-cache-dir -r requirements.txt

COPY workspaces/project-20261113-131615-917f271f/app/app.py .
COPY workspaces/project-20261113-131615-917f271f/app/templates/ templates/
COPY workspaces/project-20261113-131615-917f271f/app/static/ static/
COPY deploy/task-manager/serve.py .

CMD ["python", "serve.py"]
