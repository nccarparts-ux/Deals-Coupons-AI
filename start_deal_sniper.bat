@echo off
REM Usage:
REM   start_deal_sniper.bat              (normal start)
REM   start_deal_sniper.bat --dry-run    (test mode - no real posts on new platforms)
REM   start_deal_sniper.bat --social-only (new platforms only)
REM   start_deal_sniper.bat --kill-social (pause all new platform tasks)
cd /d "%~dp0"
echo Starting Deal Sniper AI...

:: Load .env so Python can find credentials during the check phase
if exist .env (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
    )
)

:: Run startup checks and handle special flags (--kill-social exits here)
venv\Scripts\activate
python scripts\start_sniper.py check %*
if errorlevel 1 (
    echo [FAIL] Startup checks failed. Aborting.
    pause
    exit /b 1
)

:: If --kill-social was passed, start_sniper.py already exited cleanly.

:: ── Kill any existing processes (by title AND by port/process) ──────────────
echo Stopping existing processes...

:: Kill by window title (handles windows still open)
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Celery Beat*"   >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq API Server*"    >nul 2>&1

:: Kill the process occupying port 8001 (handles detached/orphaned uvicorn)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    echo Releasing port 8001 (PID %%P)...
    taskkill /F /PID %%P >nul 2>&1
)

:: Kill any lingering celery beat processes (prevents "already running" errors)
for /f "tokens=2" %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO list 2^>nul ^| findstr "PID"') do (
    wmic process where "ProcessId=%%P and CommandLine like '%%celery%%beat%%'" delete >nul 2>&1
)

:: Give OS a moment to release resources
ping 127.0.0.1 -n 3 >nul

:: ── Start components ─────────────────────────────────────────────────────────
echo Starting Celery Worker...
start "Celery Worker" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python -m celery -A deal_sniper_ai.scheduler.celery_app worker --loglevel=info --pool=solo --queues=default,monitoring,coupons,analytics,glitches,affiliate,scoring,community,posting,growth,maintenance --hostname=worker@deals-sniper"

:: Wait for worker to initialize
ping 127.0.0.1 -n 6 >nul

echo Starting Celery Beat Scheduler...
start "Celery Beat" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python -m celery -A deal_sniper_ai.scheduler.celery_app beat --loglevel=info --schedule=celerybeat-schedule"

:: Wait then start API server
ping 127.0.0.1 -n 4 >nul

echo Starting API Server...
start "API Server" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python -m uvicorn deal_sniper_ai.api.main:app --host 127.0.0.1 --port 8001 --reload"

echo.
echo Deal Sniper AI is running!
echo - Celery Worker: monitors deals and posts to Telegram
echo - Celery Beat:   schedules crawls + SEO blog (every 3h)
echo - API Server:    http://127.0.0.1:8001/dashboard
echo - Social panel:  http://127.0.0.1:8001/social
echo.
echo Close those three windows to stop the bot.
pause
