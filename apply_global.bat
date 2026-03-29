@echo off
setlocal
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0apply_global.ps1" %*
