# minutes

`minutes` is a portfolio project: a local-only team meeting-notes GraphQL API with no deployment and no users. It is not affiliated with or a clone of any other product.

It models teams, meetings, attendees, ordered agendas, notes, and owned action items. Django session authentication protects every team resource; non-members receive `null` for meeting lookups, avoiding ID-existence leaks.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed
.venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/graphql/`. The seed command creates `demo` / `demo` credentials; create a Django session through the admin or a test client before making authenticated requests.

## API

The Strawberry schema offers `meeting`, cursor-paginated `meetings`, `myActionItems`, and `me` queries. Mutations create meetings, notes and action items; update action status; and reorder an agenda atomically. Mutation outcomes are typed unions: data, `ValidationError`, or `PermissionDenied`.

`schema.graphql` is a committed SDL snapshot. `tests/test_schema.py` fails when an API change is made without deliberately updating it.

## Data and performance

`ActionItem` started with a `done` boolean in migration `0001`. Migration `0002` replaces it with an `open` / `in_progress` / `done` enum via a reversible `RunPython` data migration and adds the database constraint that requires `completed_at` exactly when the status is `done`.

Nested meeting reads explicitly use `select_related` and `prefetch_related`. The query-count test keeps the nested attendees/action-item-owner query at nine SQL statements for both 10 and 100 meetings; `PROOF.md` records the measured baseline.

## Quality

Run `ruff check .`, `ruff format --check .`, `mypy config meetings`, and `pytest`. GitHub Actions runs those commands against PostgreSQL 16 on every push and pull request; `PROOF.md` links the first green run.
