# CLI Reference

## Core commands

```powershell
retrocore help
retrocore help preset use
retrocore status
retrocore profiles
retrocore apply
retrocore on
retrocore off
retrocore get target.mode
retrocore set target.clear_non_target_profiles false --no-apply
retrocore manager
```

`on` and `off` are the preferred toggle verbs. `enable` and `disable` are still supported as compatibility aliases.

`retrocore manager` launches the local Retrocore Manager desktop UI for preset selection, profile targeting, and direct effect editing.

For everyday use, Retrocore now applies common state-changing commands immediately by default. Use `--no-apply` when you want to update config without writing to Windows Terminal right away.

## Targeting

```powershell
retrocore target all
retrocore target only "PowerShell"
retrocore target only "PowerShell" "Command Prompt"
retrocore target specific
retrocore target add-profile "PowerShell"
retrocore target remove-profile "Command Prompt"
retrocore target clear
```

## Presets

```powershell
retrocore preset list
retrocore preset show warm
retrocore preset use amber
retrocore preset save my-tube --description "My preferred look"
retrocore preset rename my-tube my-daily-tube
retrocore preset delete my-daily-tube
```

Built-in presets are protected. They can be applied, but not overwritten, renamed, or deleted.

## Fine-grained config editing

```powershell
retrocore config show
retrocore get target.mode
retrocore set target.clear_non_target_profiles false --no-apply
retrocore effect glow_horizontal 0.12
retrocore effect curvature 0.04
```

`retrocore get` and `retrocore set` are the preferred short forms. `retrocore config get` and `retrocore config set` still work for compatibility.
