@echo off
set ROOT=%~dp0..
cd /d "%ROOT%"
start "" "%ROOT%\bin\runSofa.exe" -g glfw "%~dp0tdcr_physical.py"

