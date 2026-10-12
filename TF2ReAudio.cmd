@echo off
rem TF2 Re-Audio launcher for Windows. Double-click it, or run it from cmd or PowerShell.
rem Uses Python 3.10+ if installed; otherwise downloads the official embeddable Python
rem from python.org into runtime\ next to this file (no admin rights, no installer).
setlocal EnableExtensions DisableDelayedExpansion

rem Pinned runtime. python.org publishes no SHA-256 for this file; the hash was computed from
rem the download after checking python.org's MD5 and Steve Dower's GPG release signature.
rem 3.12.10 is the last 3.12 release with Windows binaries (later 3.12.x are source-only).
set "PY_VERSION=3.12.10"
set "PY_SHA256=4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-embed-amd64.zip"

set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "RT=%HERE%\runtime"
set "ZIP=%HERE%\runtime-download.zip"

rem pushd (not cd) also works when the folder is on a network share (\\server\share).
pushd "%HERE%" || goto :fail_folder
if not exist "%HERE%\tf2reaudio\__main__.py" goto :fail_unzipped

set "PY="
call :try_python py -3
if not defined PY call :try_python python
if not defined PY call :try_python "%RT%\python.exe"
if not defined PY call :install_runtime
if not defined PY goto :end_fail

%PY% -m tf2reaudio run %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
echo.
echo TF2 Re-Audio stopped with error code %RC%. Read the message above.
echo If you need help, send a screenshot of this window to the group.
pause
exit /b %RC%

rem ---------------------------------------------------------------------------
rem Sets PY to the given command if it runs, is Python 3.10 or newer and can import
rem tf2reaudio from this folder. Running it (not just finding it) skips the Microsoft
rem Store "python" alias, which exits with an error when given arguments. <nul makes any
rem interactive prompt (e.g. "install Python?") fail instead of waiting invisibly.
:try_python
%* -c "import sys; sys.version_info >= (3, 10) or sys.exit(1); import tf2reaudio" <nul >nul 2>&1
if not errorlevel 1 set PY=%*
exit /b 0

:install_runtime
echo Python 3.10 or newer was not found.
echo Downloading Python %PY_VERSION% from python.org (about 11 MB). This happens only once.
if exist "%RT%" rmdir /s /q "%RT%"
if exist "%ZIP%" del /f /q "%ZIP%"
curl.exe -fL --retry 2 -o "%ZIP%" "%PY_URL%"
if not errorlevel 1 goto :downloaded
echo curl.exe failed, trying PowerShell instead...
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = 'Tls12'; Invoke-WebRequest -UseBasicParsing -Uri $env:PY_URL -OutFile $env:ZIP"
if errorlevel 1 goto :fail_download
:downloaded
powershell.exe -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 -LiteralPath $env:ZIP).Hash -ne $env:PY_SHA256) { exit 1 }"
if errorlevel 1 goto :fail_hash
powershell.exe -NoProfile -Command "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; Expand-Archive -LiteralPath $env:ZIP -DestinationPath $env:RT -Force"
if errorlevel 1 goto :fail_extract
del /f /q "%ZIP%"
rem The embeddable Python only searches the folders listed in its ._pth file (it ignores
rem PYTHONPATH and the current folder). ".." is resolved relative to runtime\, i.e. this folder.
for %%F in ("%RT%\python3*._pth") do echo ..>>"%%F"
call :try_python "%RT%\python.exe"
if not defined PY goto :fail_extract
echo Python %PY_VERSION% is ready.
echo.
exit /b 0

rem ---------------------------------------------------------------------------
:fail_download
echo.
echo ERROR: Could not download Python from python.org.
echo Check your internet connection and run TF2ReAudio.cmd again.
echo Or install Python 3.12 yourself from https://www.python.org/downloads/windows/
echo and run TF2ReAudio.cmd again.
exit /b 1

:fail_hash
del /f /q "%ZIP%"
echo.
echo ERROR: The downloaded Python file is corrupted or not the expected file.
echo It was deleted. Run TF2ReAudio.cmd again. If this keeps happening, install
echo Python 3.12 yourself from https://www.python.org/downloads/windows/
exit /b 1

:fail_extract
echo.
echo ERROR: Could not unpack Python into:
echo   "%RT%"
echo Move the TF2ReAudio folder somewhere you can write to, for example your
echo Desktop or Documents, and run TF2ReAudio.cmd again.
exit /b 1

:fail_folder
echo ERROR: Could not open the folder of this launcher:
echo   "%HERE%"
goto :end_fail

:fail_unzipped
echo ERROR: The "tf2reaudio" folder was not found next to TF2ReAudio.cmd.
echo Extract the whole ZIP first (right-click it, then "Extract All..."),
echo then open the extracted folder and run TF2ReAudio.cmd from there.
goto :end_fail

:end_fail
echo.
pause
exit /b 1
