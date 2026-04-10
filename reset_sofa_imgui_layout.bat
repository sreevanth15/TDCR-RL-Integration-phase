@echo off
REM If runSofa shows a black 3D view or "invalid window position", ImGui saved a bad layout.
REM This backs up and removes the saved docking/window files so SOFA recreates defaults.
set CFG=%LOCALAPPDATA%\SOFA\config\imgui
if not exist "%CFG%" (
  echo No folder: %CFG%
  pause
  exit /b 1
)
echo Backing up and removing ImGui layout in:
echo   %CFG%
if exist "%CFG%\imgui.ini" move /Y "%CFG%\imgui.ini" "%CFG%\imgui.ini.bak"
if exist "%CFG%\settings.ini" move /Y "%CFG%\settings.ini" "%CFG%\settings.ini.bak"
echo Done. Start runSofa again — the 3D viewport should be a normal size.
pause

