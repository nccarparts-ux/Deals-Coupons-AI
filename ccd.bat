@echo off
cd /d "%~dp0"
echo 🚀 Launching Claude Code with DeepSeek (Official Method)...

:: Load .env file
for /f "tokens=* eol=# delims=" %%a in (.env) do set %%a

:: Verify configuration [citation:1]
echo ✅ Base URL: %ANTHROPIC_BASE_URL%
echo ✅ Model: %ANTHROPIC_MODEL%
echo.

:: Launch Claude Code
claude