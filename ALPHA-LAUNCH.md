# Retrocore Alpha Launch

Retrocore `v0.1-alpha` is the first packaged build of the project for early testers.

## What this version is for

- proving the end-to-end Windows Terminal shader workflow
- validating the preset and profile-targeting model
- collecting feedback on CLI ergonomics before adding a richer manager UI
- collecting feedback on the first Retrocore Manager surface
- confirming install and uninstall behavior on real machines

## What testers should expect

- Retrocore is usable, but not polished
- Windows Terminal settings are backed up before Retrocore writes changes
- Retrocore supports common Windows Terminal `settings.json` files that include comments or trailing commas
- when Retrocore writes the file back, it normalizes the file to plain JSON formatting

## Recommended tester flow

```powershell
python .\tests\smoke_test.py
.\retrocore.cmd status
.\retrocore.cmd preset list
.\retrocore.cmd on
.\retrocore.cmd profiles
```

## Feedback to collect during alpha

- whether the install flow is clear enough
- whether profile targeting behaves as expected
- whether presets feel distinct and worth keeping
- whether the CLI output is readable enough
- any cases where Windows Terminal settings fail to load or are rewritten unexpectedly

## Not in scope yet

- richer terminal UI styling for the CLI itself
- a dedicated Retrocore manager surface
- packaged installer output
- signed `.exe` distribution
- GitHub release automation
