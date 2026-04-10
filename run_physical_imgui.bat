@echo off
REM Full SOFA UI: scene graph, Animate/Step/Reset, menus, docking panels.
REM If the 3D view is black or tiny, run reset_sofa_imgui_layout.bat once, then try again.
set ROOT=%~dp0..
cd /d "%ROOT%"
start "" "%ROOT%\bin\runSofa.exe" -l SofaPython3 -g imgui "%~dp0tdcr_physical.py"
