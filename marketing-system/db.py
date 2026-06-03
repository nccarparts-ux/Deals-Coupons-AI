"""
Supabase DB helpers for the marketing-system.
Loads credentials from marketing-system/.env only.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Load ONLY marketing-system/.env
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

SUPABASE_URL = os.environ["SUPABASE_URL"]
# Use service role key if available (bypasses RLS for backend operations).
# Falls back to SUPABASE_KEY for environments that haven't been updated yet.
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def supabase_insert(table: str, data: dict) -> dict:
    """Insert a row; returns inserted record."""
    response = get_client().table(table).insert(data).execute()
    return response.data[0] if response.data else {}


def supabase_update(table: str, match: dict, data: dict) -> list:
    """Update rows matching all key=value pairs in match; returns updated records."""
    query = get_client().table(table).update(data)
    for col, val in match.items():
        query = query.eq(col, val)
    response = query.execute()
    return response.data or []


def supabase_select(table: str, filters: dict | None = None) -> list:
    """Select rows, optionally filtering by equality on each key in filters."""
    query = get_client().table(table).select("*")
    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)
    response = query.execute()
    return response.data or []


def get_unprocessed(field: str) -> list:
    """Return deals rows where the given boolean field is false."""
    response = (
        get_client()
        .table("deals")
        .select("*")
        .eq(field, False)
        .execute()
    )
    return response.data or []


def mark_done(deal_id: str, field: str) -> None:
    """Set deals.{field} = true for the given deal id."""
    (
        get_client()
        .table("deals")
        .update({field: True})
        .eq("id", deal_id)
        .execute()
    )
