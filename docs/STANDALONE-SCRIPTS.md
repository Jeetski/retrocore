# Standalone Scripts

Retrocore includes PowerShell and batch wrappers for users who want a simple Windows-native flow without going through the CLI.

## Launch the manager UI

This opens the Retrocore Manager surface directly.

PowerShell:

```powershell
.\manager.ps1
```

Batch:

```bat
manager.bat
```

## Apply globally

This copies a shader into Windows Terminal's `LocalState` folder and enables it globally through `profiles.defaults`.

PowerShell:

```powershell
.\apply_global.ps1
```

Batch:

```bat
apply_global.bat
```

Behavior:

- prefers `shaders\retrocore.generated.hlsl` when it exists
- falls back to `shaders\crt-subtle.hlsl` if no generated shader is available
- backs up the live Windows Terminal settings into `snapshots\`
- updates `settings.json` directly
- tolerates common JSONC-style comments and trailing commas in Windows Terminal settings before writing back normalized JSON

## Remove global standalone settings

This removes only Retrocore-managed shader paths from Windows Terminal settings.

PowerShell:

```powershell
.\remove_global.ps1
```

Batch:

```bat
remove_global.bat
```

It will not remove unrelated custom shader paths.
