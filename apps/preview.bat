@echo off
REM Quick preview script for Windows
cd /d %~dp0..
uv run python apps\preview_ppt.py --template standard --open
pause


