@echo off
set ROOT=%~dp0..
cd /d "%ROOT%"
start "" "%ROOT%\bin\runSofa.exe" -l SofaPython3 "%~dp0tdcr_physical.py"

