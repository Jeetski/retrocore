@echo off
setlocal
where py >nul 2>nul
if %errorlevel%==0 (
  goto run_py
)

where python >nul 2>nul
if %errorlevel%==0 (
  goto run_python
)

echo Retrocore requires Python 3. Run install_dependencies.bat or install_dependencies.ps1 first.
exit /b 1

:run_py
py -3 "%~dp0retrocore.py" %*
exit /b %errorlevel%

:run_python
python "%~dp0retrocore.py" %*
exit /b %errorlevel%
