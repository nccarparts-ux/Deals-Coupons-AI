@echo off
REM Usage:
REM   start_marketing.bat                         (normal start - run pipeline then schedule)
REM   start_marketing.bat --once                  (run pipeline once and exit)
REM   start_marketing.bat --new-domain example.com  (update SITE_URL and rebuild all pages)

cd /d "%~dp0"

:: ── Handle --new-domain flag ───────────────────────────────────────────────
set NEW_DOMAIN=
set ONCE=

:parse_args
if "%~1"=="" goto done_args
if /i "%~1"=="--new-domain" (
    set NEW_DOMAIN=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--once" (
    set ONCE=1
    shift
    goto parse_args
)
shift
goto parse_args
:done_args

if not "%NEW_DOMAIN%"=="" (
    echo Switching domain to: %NEW_DOMAIN%
    venv\Scripts\python.exe -c "import re; env=open('marketing-system/.env',encoding='utf-8').read(); env=re.sub(r'SITE_URL=.*','SITE_URL=https://%NEW_DOMAIN%',env); open('marketing-system/.env','w',encoding='utf-8').write(env); print('SITE_URL updated.')"
    echo Rebuilding all deal pages with new domain...
    venv\Scripts\python.exe marketing-system\agents\website_publisher.py --rebuild-all
    echo Done. All pages now use https://%NEW_DOMAIN%
    echo Remember to also update your Vercel project to use this domain.
    pause
    exit /b 0
)

:: ── Normal start ──────────────────────────────────────────────────────────
echo.
echo  =====================================================
echo    Coupons, Deals ^& Steals -- Marketing Pipeline
echo  =====================================================
echo.

:: Check venv exists
if not exist "venv\Scripts\python.exe" (
    echo [FAIL] venv not found. Run: python -m venv venv ^&^& venv\Scripts\pip install -r marketing-system\requirements.txt
    pause
    exit /b 1
)

:: Quick env check
echo Checking configuration...
venv\Scripts\python.exe -c "import sys,os; sys.path.insert(0,'marketing-system'); from dotenv import load_dotenv; from pathlib import Path; load_dotenv(Path('marketing-system/.env')); missing=[k for k in ['SUPABASE_URL','SUPABASE_KEY','RESEND_API_KEY','ANTHROPIC_API_KEY'] if not os.environ.get(k,'').strip() or os.environ.get(k,'').startswith('#')]; print('[WARN] Missing:',missing) if missing else print('[OK] All required env vars set.'); print('[OK] Site URL:',os.environ.get('SITE_URL','(not set)'))"
echo.

if "%ONCE%"=="1" (
    echo Running pipeline once...
    start "Marketing Pipeline" cmd /k "cd /d %~dp0 && venv\Scripts\python.exe marketing-system\run_all.py --agent telegram && venv\Scripts\python.exe marketing-system\run_all.py --agent content && venv\Scripts\python.exe marketing-system\run_all.py --agent website && venv\Scripts\python.exe marketing-system\run_all.py --stats && echo Done. && pause"
) else (
    echo Starting marketing pipeline scheduler...
    echo This will sync deals, generate AI content, publish pages, and send emails automatically.
    echo.
    start "Marketing Pipeline" cmd /k "cd /d %~dp0 && venv\Scripts\python.exe marketing-system\run_all.py"
    ping 127.0.0.1 -n 2 >nul
    echo.
    echo  Marketing pipeline is running in a separate window.
    echo.
    echo  What it does automatically:
    echo    Every 15 min  -- Syncs new deals from main pipeline
    echo    Every 15 min  -- Generates SEO + social copy (DeepSeek AI)
    echo    Every 15 min  -- Publishes deal pages to GitHub/Vercel
    echo    Daily  8am UTC -- Sends email digest to subscribers
    echo    Sunday 9am UTC -- Sends weekly top-10 email
    echo    Daily  6am UTC -- Learning engine updates AI prompts
    echo.
    echo  Website: https://bidyarddeals.com
    echo.
    echo  To change domain later:  start_marketing.bat --new-domain yourdomain.com
    echo  To run once and exit:    start_marketing.bat --once
    echo.
)

pause
