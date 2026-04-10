@echo off
REM Minimal viewer: 3D view only (no scene tree / toolbar). For full SOFA UI use run_physical_imgui.bat
set ROOT=%~dp0..
cd /d "%ROOT%"
start "" "%ROOT%\bin\runSofa.exe" -l SofaPython3 -g glfw "%~dp0tdcr_physical.py"

