# Evidence Ledger

This file records verified evidence only. The repository is public at https://github.com/aryaman-boop/minutes (pushed 2026-10-02).

## Continuous integration

- GitHub Actions run [37086678808](https://github.com/aryaman-boop/minutes/actions/runs/37086678808), 2026-10-02 (21:35 EDT), commit `be01a59`: **success**. `ruff check`, `ruff format --check`, `mypy config meetings` and `pytest` (**11 passed**) on **PostgreSQL 16** (service container, `POSTGRES_DB` set so Django uses the PostgreSQL backend) with **Python 3.12.14**.

## Local verification

- `pytest`: 11 passed locally on 2026-10-02 (SQLite development database, Python 3.14), including authorization, constraint, schema-snapshot, migration-data, N+1 query-count and two regression tests.
- `ruff check .`, `ruff format --check .`, `mypy config meetings`, `manage.py check`, and `manage.py makemigrations --check` all passed locally on 2026-10-02. Note: `mypy` is configured with `ignore_errors = true` for `meetings.schema`, so that module is not type-checked yet.
- Database migrations include `0001_initial` and `0002_action_item_status`; the latter has a reversible `RunPython` mapping `done=True` rows to `status="done"`.

## Bugs found during review, each fixed test-first

Both regression tests were added first and confirmed failing before the fix (2026-10-02).

1. **Anonymous `meetings` query crashed.** The membership filter received `AnonymousUser`, and the response leaked Django's `Field 'id' expected a number but got <SimpleLazyObject: ...AnonymousUser...>` instead of returning data. Fix: return an empty connection for unauthenticated users. Test: `test_anonymous_meetings_query_returns_empty_connection`.
2. **Malformed `scheduledAt` escaped as an untyped error.** Django raises `django.core.exceptions.ValidationError` for a malformed datetime at save time; `createMeeting` caught only `TypeError` and `ValueError`, so clients got a top-level error carrying an unformatted `%(value)s` template. Fix: parse the timestamp with `parse_datetime` before touching the ORM and return the typed `ValidationError`. Test: `test_create_meeting_rejects_malformed_timestamp_with_typed_error`.

## N+1 query measurement

| Query | 10 meetings | 100 meetings | Method |
| --- | ---: | ---: | --- |
| Without `select_related` / `prefetch_related` | 71 | 701 | `CaptureQueriesContext`, same nested query, `meeting_queryset` replaced by `Meeting.objects.all()` in a throwaway test (2026-10-02) |
| Optimized nested meetings query | 9 | 9 | `CaptureQueriesContext` integration test |

The original naive implementation was not retained; the "without" row was measured afterwards by removing only the eager loading from the current code, with the same query and data shape. The optimized count is locked in by the integration test.
