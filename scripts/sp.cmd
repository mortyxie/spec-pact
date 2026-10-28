@echo off
rem spec-pact launcher for Windows cmd / PowerShell. ASCII-only on purpose:
rem cmd.exe parses this file in the OEM codepage, non-ASCII breaks it.
rem ladder: SP_PYTHON -> py -3 -> python -> common install dirs -> agent runtimes -> exit 6
rem delayed expansion is required to carry %errorlevel% out of blocks: use !RC!
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT=%~dp0sp.py"
set "VC=import sys;sys.exit(0 if sys.version_info[:2]>=(3,8) else 1)"
set "RC=0"
set "FOUND="

if not exist "%SCRIPT%" (
  echo ERR sp: missing "%SCRIPT%" 1>&2
  exit /b 1
)

if defined SP_PYTHON (
  call :try "%SP_PYTHON%"
  if defined FOUND exit /b !RC!
)

where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "%VC%" >nul 2>&1
  if not errorlevel 1 (
    py -3 "%SCRIPT%" %*
    set "RC=!errorlevel!"
    set "FOUND=1"
  )
)
if defined FOUND exit /b !RC!

rem 4) common install dirs: found even when not on PATH (the "agent downloads
rem    another copy of python" trap). system installs win over PATH lookups.
for %%D in ("C:\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*" "%LOCALAPPDATA%\Programs\Python\Python3*") do (
  for /d %%P in (%%D) do (
    if exist "%%~fP\python.exe" (
      call :try "%%~fP\python.exe"
      if defined FOUND exit /b !RC!
    )
  )
)

rem 5) PATH python, skipping agent-managed dirs (last resort, reuse only)
for /f "delims=" %%P in ('where python 2^>nul') do (
  echo %%P | findstr /i /c:".workbuddy\" /c:".cursor\" /c:".claude\" /c:".codex\" /c:"WindowsApps" >nul || (
    call :try "%%P"
    if defined FOUND exit /b !RC!
  )
)

for %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*" "%USERPROFILE%\.local\share\uv\python\*" "%USERPROFILE%\.pyenv\pyenv-win\versions\*") do (
  for /d %%P in (%%D) do (
    if exist "%%~fP\python.exe" (
      call :try "%%~fP\python.exe"
      if defined FOUND exit /b !RC!
    )
  )
)

echo ERR sp: no-python - no python 3.8+ found, spec-pact state machine cannot start. 1>&2
echo   Nothing is downloaded automatically. Pick one: 1>&2
echo   1) winget install -e --id Python.Python.3.12 1>&2
echo   2) set SP_PYTHON=C:\path\to\python.exe  then re-run 1>&2
echo   3) cannot install: manual mode, prefix status header with degraded, see protocol\bootstrap.md 1>&2
exit /b 6

:try
"%~1" -c "%VC%" >nul 2>&1
if errorlevel 1 exit /b 1
"%~1" "%SCRIPT%" %*
set "RC=!errorlevel!"
set "FOUND=1"
exit /b 0
