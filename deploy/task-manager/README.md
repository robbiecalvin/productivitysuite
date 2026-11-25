# Deploy the task manager demo

This image serves the reference task manager with Gunicorn and stores its
SQLite database at `/var/data/task-manager/tasks.sqlite3`. It serves the
existing app and runs independently of the desktop suite and Ollama.

## Local Docker

Run from the repository root. Set `DEMO_PASSWORD` in your environment first
and use a disposable password for local testing.

```sh
docker build -f deploy/task-manager/Dockerfile -t productivity-task-demo .
docker run -d --name productivity-task-demo \
  --publish 127.0.0.1:8000:8000 \
  --mount type=volume,source=productivity-task-demo,target=/var/data \
  --env DEMO_PASSWORD productivity-task-demo
```

Open [localhost:8000](http://localhost:8000) and sign in as `demo`. Create
a synthetic task, mark it complete, run `docker restart productivity-task-demo`,
and reload the page to confirm its saved state.

## Render

1. Create a paid Docker web service from this repository. Use the repository
   root as the build context and `./deploy/task-manager/Dockerfile` as the
   Dockerfile path. Leave the Docker command at its image default.
2. Add a persistent disk at `/var/data`. Run a single service instance.
3. Set `DEMO_PASSWORD` as a secret environment variable and set the HTTP
   health check path to `/healthz`. Render supplies `PORT`.
4. Open the service's HTTPS URL and sign in as `demo`. Create and complete a
   synthetic task, restart the service, and check that the task and its
   completion state are still present.

The demo has one shared task list. Share the password with intended testers
and use synthetic data. The health endpoint is open for platform probes.

[Render Docker services](https://render.com/docs/docker) ·
[Render persistent disks](https://render.com/docs/disks)
