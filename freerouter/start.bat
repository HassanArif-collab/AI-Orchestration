@echo off
REM FreeRouter v3 startup script for Windows
REM Usage: start.bat

REM Check for .env file
if not exist .env (
    echo Warning: .env file not found.
    if exist .env.example (
        copy .env.example .env >nul
        echo Created .env from .env.example
        echo Please edit .env and add your API keys (OPENROUTER_API_KEY, GROQ_API_KEY).
    )
)

echo.
echo Starting FreeRouter v3...
echo.
echo Endpoints:
echo   API:    http://localhost:4000/v1
echo   Models: http://localhost:4000/v1/models
echo   Health: http://localhost:4000/health
echo.

python -m freerouter
