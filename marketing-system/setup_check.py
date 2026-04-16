"""
setup_check.py -- verify all external integrations before running.
"""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

OK   = "[OK]  "
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def check_supabase():
    try:
        from supabase import create_client
        c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        c.table("config").select("key").limit(1).execute()
        print(f"{OK} Supabase")
    except KeyError as e:
        print(f"{FAIL} Supabase -- missing env var: {e}")
    except Exception as e:
        print(f"{FAIL} Supabase -- {e}\n       Fix: check SUPABASE_URL + SUPABASE_KEY in .env")


def check_telegram():
    try:
        import requests
        token = os.environ["TELEGRAM_READER_TOKEN"].strip()
        if not token or token.startswith("#"):
            print(f"{FAIL} Telegram -- TELEGRAM_READER_TOKEN not set\n       Fix: create a NEW bot via @BotFather")
            return
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        d = r.json()
        if d.get("ok"):
            print(f"{OK} Telegram (@{d['result']['username']})")
        else:
            print(f"{FAIL} Telegram -- {d.get('description')}")
    except KeyError:
        print(f"{FAIL} Telegram -- TELEGRAM_READER_TOKEN missing in .env")
    except Exception as e:
        print(f"{FAIL} Telegram -- {e}")


def check_anthropic():
    try:
        import anthropic
        kwargs = {"api_key": os.environ["ANTHROPIC_API_KEY"]}
        base = os.environ.get("ANTHROPIC_BASE_URL")
        if base:
            kwargs["base_url"] = base
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        c = anthropic.Anthropic(**kwargs)
        c.messages.create(model=model, max_tokens=5, messages=[{"role":"user","content":"hi"}])
        print(f"{OK} Anthropic/AI ({model})")
    except KeyError:
        print(f"{FAIL} Anthropic -- ANTHROPIC_API_KEY missing in .env")
    except Exception as e:
        print(f"{FAIL} Anthropic -- {e}")


def check_brevo():
    try:
        import sib_api_v3_sdk
        cfg = sib_api_v3_sdk.Configuration()
        cfg.api_key["api-key"] = os.environ["BREVO_API_KEY"]
        sib_api_v3_sdk.AccountApi(sib_api_v3_sdk.ApiClient(cfg)).get_account()
        print(f"{OK} Brevo")
    except KeyError:
        print(f"{FAIL} Brevo -- BREVO_API_KEY missing in .env")
    except Exception as e:
        print(f"{FAIL} Brevo -- {e}")


def check_vercel():
    try:
        r = subprocess.run(["vercel", "whoami"], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            print(f"{OK} Vercel CLI ({r.stdout.strip()})")
        else:
            print(f"{FAIL} Vercel CLI -- {r.stderr.strip()}\n       Fix: run `vercel login`")
    except FileNotFoundError:
        print(f"{FAIL} Vercel CLI -- not installed\n       Fix: npm i -g vercel")
    except Exception as e:
        print(f"{FAIL} Vercel CLI -- {e}")


def check_github():
    repo_root = Path(__file__).parent.parent
    try:
        r = subprocess.run(["git", "status"], capture_output=True, text=True,
                           timeout=10, cwd=repo_root)
        if r.returncode == 0:
            print(f"{OK} GitHub (git OK in {repo_root.name})")
        else:
            print(f"{FAIL} GitHub -- {r.stderr.strip()}")
    except Exception as e:
        print(f"{FAIL} GitHub -- {e}")


def check_search_console():
    key = os.environ.get("GOOGLE_SEARCH_CONSOLE_KEY", "").strip()
    if not key or key.startswith("#"):
        print(f"{SKIP} Google Search Console -- optional, set GOOGLE_SEARCH_CONSOLE_KEY to enable SEO learning")
    else:
        print(f"{OK} Google Search Console key present")


if __name__ == "__main__":
    print("=== Marketing System Setup Check ===\n")
    check_supabase()
    check_telegram()
    check_anthropic()
    check_brevo()
    check_vercel()
    check_github()
    check_search_console()
    print("\nDone.")
