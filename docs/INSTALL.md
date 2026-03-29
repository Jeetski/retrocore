# Install Guide

Retrocore currently supports two setup paths on Windows.

## Option 1: Guided setup

Use the guided installer if you want Python detection, an optional Python install via `winget`, and a `retrocore` command added to your user PATH.

```powershell
.\install_dependencies.ps1
```

Or:

```bat
install_dependencies.bat
```

The guided flow can:

- detect Python 3
- install Python 3.11 with `winget` if Python is missing
- create a user-level command shim at `%LOCALAPPDATA%\Retrocore\bin\retrocore.cmd`
- add that shim directory to your user PATH
- run a quick `retrocore status` check at the end
- work against Windows Terminal settings files that contain comments or trailing commas

Important:

- The shim points at the current project folder
- if you move the project folder later, rerun the installer
- PATH changes usually require a new terminal window

## Option 2: No install, project-local use

You can also run Retrocore directly from the project folder without setting up a global command:

```powershell
.\retrocore.cmd status
.\retrocore.cmd preset list
.\retrocore.cmd on
```
