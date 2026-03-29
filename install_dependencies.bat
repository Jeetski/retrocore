@echo off
setlocal
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0install_dependencies.ps1" %*
