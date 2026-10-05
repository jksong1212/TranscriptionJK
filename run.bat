@echo off
cd /d "%~dp0"
set "UV_PROJECT_ENVIRONMENT=C:\uv_envs\Transcription_py"
uv run .\main.py %*
