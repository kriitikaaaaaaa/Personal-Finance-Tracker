# Deploying to Render

This app is configured for Render with `render.yaml`.

## Render settings

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Health check path: `/healthz`

## Required environment variables

Set these in Render before deploying:

- `MYSQL_HOST`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DB`

`SECRET_KEY` is generated automatically by the Render blueprint.

## Database note

The app uses MySQL. A local database host such as `localhost` will not work on Render. Use a MySQL database that is reachable from Render, then run `database.sql` on that database before opening the app.
