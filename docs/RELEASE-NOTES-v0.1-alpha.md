# Release Notes: v0.1-alpha

## Summary

`v0.1-alpha` establishes the first end-to-end Retrocore workflow for Windows Terminal:

- local or shim-based CLI usage
- preset-driven CRT shader generation
- profile-default or profile-specific targeting
- standalone PowerShell apply and removal scripts
- automatic settings backups before writes

## Included in this release

- `retrocore.py` CLI for status, apply, presets, config editing, and targeting
- `retrocore manager` dark desktop UI for core controls and effect editing
- `retrocore.cmd` wrapper for local project execution
- `manager.ps1` and `manager.bat` direct launchers
- `install_dependencies.ps1` guided setup flow
- standalone global apply and remove scripts
- built-in presets: `subtle`, `warm`, `arcade`, `amber`, `phosphor-green`, `ice`
- JSONC-tolerant Windows Terminal settings parsing for comments and trailing commas
- smoke-test script at `tests/smoke_test.py`

## Known limitations

- Windows-only target
- no formal automated test suite beyond smoke coverage
- CLI output is functional but still visually plain
- writing Terminal settings back normalizes formatting to standard JSON
- no packaged installer or GitHub release flow yet

## Recommended verification

```powershell
python .\tests\smoke_test.py
.\retrocore.cmd status
.\retrocore.cmd on
.\retrocore.cmd off
```

## Next planned work

- stronger CLI presentation
- a dedicated Retrocore manager surface
- installer packaging
- GitHub publishing and release assets
