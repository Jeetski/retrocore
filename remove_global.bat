@echo off
setlocal
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0remove_global.ps1" %*
