@echo off
REM FreeRouter startup script for Windows
REM Usage: start.bat [options]

setlocal enabledelayedexpansion

REM Default values
set HOST=0.0.0.0
set PORT=4000
set CONFIG=config\proxy_server_config.yaml

REM Parse arguments
:parse_args
if "%~1"=="" goto :start
if /i "%~1"=="-h" (set HOST=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="--host" (set HOST=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="-p" (set PORT=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="--port" (set PORT=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="-c" (set CONFIG=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="--config" (set CONFIG=%~2& shift & shift & goto :parse_args)
if /i "%~1"=="--help" goto :show_help
echo Unknown option: %~1
exit /b 1

:show_help
echo Usage: start.bat [options]
echo.
echo Options:
echo   -h, --host      Host to bind to (default: 0.0.0.0)
echo   -p, --port      Port to bind to (default: 4000)
echo   -c, --config    Config file path
echo   --help          Show this help message
exit /b 0

:start

REM Print banner
echo.
echo ========================================================
echo   FreeRouter - Smart LLM Proxy - Always Free First
echo ========================================================
echo.

REM Check for .env file
if not exist .env (
    echo Warning: .env file not found.
    if exist .env.example (
        copy .env.example .env >nul
        echo Created .env from .env.example
        echo Please edit .env and add your API keys.
    )
)

REM Check if Ollama is running
echo Checking if Ollama is running...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel%==0 (
    echo [OK] Ollama is running
) else (
    echo [WARN] Ollama is not running
    echo Install Ollama from https://ollama.ai for local models
)

REM Print startup info
echo.
echo Starting FreeRouter...
echo   Host: %HOST%
echo   Port: %PORT%
echo   Config: %CONFIG%
echo.
echo Endpoints:
echo   API: http://localhost:%PORT%/v1
echo   Docs: http://localhost:%PORT%/docs
echo   Health: http://localhost:%PORT%/health
echo.

REM Start the server
python -m litellm --config %CONFIG% --host %HOST% --port %PORT%