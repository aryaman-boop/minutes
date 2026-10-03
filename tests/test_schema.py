from pathlib import Path

from strawberry.printer import print_schema

from meetings.schema import schema


def test_schema_matches_snapshot():
    snapshot = Path(__file__).resolve().parent.parent / "schema.graphql"
    assert print_schema(schema) == snapshot.read_text()
