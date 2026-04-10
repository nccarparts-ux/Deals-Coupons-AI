"""
run_migrations.py -- Apply schema/migrations.sql to Supabase.

Requires ONE of these in marketing-system/.env:
  SUPABASE_DB_PASSWORD  -- database password (Settings > Database > Connection string)
  SUPABASE_PAT          -- personal access token (app.supabase.com/account/tokens)

SUPABASE_URL + SUPABASE_KEY are always read from .env.
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

import requests

SUPABASE_URL  = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY  = os.environ["SUPABASE_KEY"]
DB_PASSWORD   = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
PAT           = os.environ.get("SUPABASE_PAT", "").strip()

ref_match = re.match(r"https://([^.]+)\.supabase\.co", SUPABASE_URL)
if not ref_match:
    print("ERROR: Could not parse project ref from SUPABASE_URL")
    sys.exit(1)
PROJECT_REF = ref_match.group(1)

SQL_FILE = Path(__file__).parent / "schema" / "migrations.sql"
raw_sql = SQL_FILE.read_text(encoding="utf-8")

# Strip line comments, then split on semicolons, keep non-empty statements
def _strip_comments(sql: str) -> str:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return "\n".join(lines)

clean_sql = _strip_comments(raw_sql)
statements = [s.strip() for s in clean_sql.split(";") if s.strip()]


def run_via_pat(sql_block: str) -> tuple[bool, str]:
    """Supabase Management API -- requires SUPABASE_PAT."""
    if not PAT:
        return False, "SUPABASE_PAT not set"
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={"query": sql_block},
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return True, "OK"
    return False, f"HTTP {resp.status_code}: {resp.text[:200]}"


def run_via_psycopg2(statements_list: list) -> tuple[int, int]:
    """Direct psycopg2 via session pooler -- requires SUPABASE_DB_PASSWORD."""
    if not DB_PASSWORD:
        return 0, len(statements_list)
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed -- pip install psycopg2-binary")
        return 0, len(statements_list)

    ok = fail = 0
    conn = None
    try:
        conn = psycopg2.connect(
            host="aws-0-us-east-1.pooler.supabase.com",
            port=5432,
            dbname="postgres",
            user=f"postgres.{PROJECT_REF}",
            password=DB_PASSWORD,
            sslmode="require",
            connect_timeout=15,
        )
        conn.autocommit = True
        cur = conn.cursor()
        for i, stmt in enumerate(statements_list, 1):
            preview = stmt.replace("\n", " ")[:70]
            print(f"  [{i}/{len(statements_list)}] {preview}")
            try:
                cur.execute(stmt)
                print(f"    OK")
                ok += 1
            except Exception as e:
                err = str(e).strip()
                if "already exists" in err:
                    print(f"    SKIP (already exists)")
                    ok += 1
                else:
                    print(f"    FAIL: {err[:100]}")
                    fail += 1
        cur.close()
    except Exception as e:
        print(f"Connection failed: {e}")
        fail = len(statements_list)
    finally:
        if conn:
            conn.close()
    return ok, fail


# ── Main ──────────────────────────────────────────────────────────────────────

print(f"Project ref : {PROJECT_REF}")
print(f"SQL file    : {SQL_FILE}")
print(f"Statements  : {len(statements)}")

if not DB_PASSWORD and not PAT:
    print("\nERROR: No credentials for DDL execution.")
    print("Add one of these to marketing-system/.env:")
    print("  SUPABASE_DB_PASSWORD=<your db password>")
    print("  SUPABASE_PAT=<personal access token from app.supabase.com/account/tokens>")
    print(f"\nOr run manually: https://supabase.com/dashboard/project/{PROJECT_REF}/sql")
    sys.exit(1)

ok = fail = 0

if PAT:
    print("\nUsing Management API (PAT)...")
    for i, stmt in enumerate(statements, 1):
        preview = stmt.replace("\n", " ")[:70]
        print(f"[{i}/{len(statements)}] {preview}")
        success, msg = run_via_pat(stmt)
        if success:
            print(f"  OK")
            ok += 1
        else:
            if "already exists" in msg:
                print(f"  SKIP (already exists)")
                ok += 1
            else:
                print(f"  FAIL: {msg}")
                fail += 1

elif DB_PASSWORD:
    print("\nUsing psycopg2 session pooler (DB password)...")
    ok, fail = run_via_psycopg2(statements)

print(f"\nDone: {ok} succeeded, {fail} failed")
if fail:
    print(f"\nFor any failures, run schema/migrations.sql in the Supabase SQL Editor:")
    print(f"  https://supabase.com/dashboard/project/{PROJECT_REF}/sql")
    sys.exit(1)
else:
    print("All tables ready.")
