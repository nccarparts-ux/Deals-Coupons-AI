@echo off
REM Usage:
REM   start_deal_sniper.bat              (normal start)
REM   start_deal_sniper.bat --dry-run    (simulate new platforms)
REM   start_deal_sniper.bat --social-only
REM   start_deal_sniper.bat --kill-social
cd /d "%~dp0"
echo Starting Deal Sniper AI...

:: Activate venv then run startup checks
call venv\Scripts\activate.bat
python scripts\start_sniper.py check %*
if errorlevel 1 (
    echo [FAIL] Startup checks failed.
    pause
    exit /b 1
)

:: Kill existing processes
echo Stopping existing processes...
taskkill /F /FI "WINDOWTITLE eq Redis*"        >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Celery Beat*"   >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq API Server*"    >nul 2>&1

:: Kill any process holding port 8001 (orphaned uvicorn from previous session)
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /L ":8001" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
ping 127.0.0.1 -n 3 >nul

:: Start Redis if not already running on port 6379
echo Checking Redis...
netstat -ano 2>nul | findstr /L ":6379" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo Starting Redis...
    where redis-server >nul 2>&1
    if errorlevel 1 (
        echo [WARN] redis-server not found in PATH. Trying common install locations...
        if exist "C:\Program Files\Redis\redis-server.exe" (
            start "Redis" "C:\Program Files\Redis\redis-server.exe"
        ) else if exist "C:\tools\redis\redis-server.exe" (
            start "Redis" "C:\tools\redis\redis-server.exe"
        ) else (
            echo [FAIL] Redis not found. Install from https://github.com/tporadowski/redis/releases
            pause
            exit /b 1
        )
    ) else (
        start "Redis" cmd /k "redis-server"
    )
    ping 127.0.0.1 -n 4 >nul
) else (
    echo Redis already running.
)

:: Start components
echo Starting Celery Worker...
start "Celery Worker" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m celery -A deal_sniper_ai.scheduler.celery_app worker --loglevel=info --pool=solo --queues=default,monitoring,coupons,analytics,glitches,affiliate,scoring,community,posting,growth,maintenance --hostname=worker@deals-sniper"
ping 127.0.0.1 -n 6 >nul

echo Starting Celery Beat...
start "Celery Beat" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m celery -A deal_sniper_ai.scheduler.celery_app beat --loglevel=info --schedule=celerybeat-schedule"
ping 127.0.0.1 -n 4 >nul

echo Starting API Server...
start "API Server" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python -m uvicorn deal_sniper_ai.api.main:app --host 127.0.0.1 --port 8001 --reload"

echo.
echo Deal Sniper AI is running!
echo   Dashboard:    http://127.0.0.1:8001/dashboard
echo   Social panel: http://127.0.0.1:8001/social
echo.
echo Close the four windows to stop (Redis, Celery Worker, Celery Beat, API Server).
pause
