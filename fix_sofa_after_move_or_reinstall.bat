@echo off
REM After copying SOFA to a new folder or installing a second copy, SOFA may still read
REM %LOCALAPPDATA%\SOFA\config\loadedPlugins.ini with OLD absolute DLL paths. That causes
REM thousands of error 123 / "Plugin not found" lines and broken paths like:
REM   ...Win64_MAIN\bin\C:\Users\...\SOFA_v25.12.00_Win64\bin\Sofa.X.dll
REM This script backs up and removes that cache so SOFA uses plugin_list.conf from bin again.

set "CFG=%LOCALAPPDATA%\SOFA\config"
if not exist "%CFG%" (
  echo No folder: %CFG%
  pause
  exit /b 0
)

echo SOFA user config: %CFG%
echo.

if exist "%CFG%\loadedPlugins.ini" (
  echo Backing up and removing stale loadedPlugins.ini ...
  move /Y "%CFG%\loadedPlugins.ini" "%CFG%\loadedPlugins.ini.bak"
  echo Done. Restart runSofa from your current SOFA folder.
) else (
  echo loadedPlugins.ini not found - nothing to fix.
)

echo.
echo If ImGui window position is wrong or viewport is black, also run: reset_sofa_imgui_layout.bat
pause
