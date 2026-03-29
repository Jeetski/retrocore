@echo off
setlocal
powershell -NoLogo -ExecutionPolicy Bypass -File "%~dp0manager.ps1" %*
