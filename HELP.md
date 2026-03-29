# Retrocore Help

Retrocore by Hivemind Studio  
Turn your terminal into a CRT.  
[hivemindstudio.art](https://hivemindstudio.art)

## Usage

```powershell
retrocore <command> [options]
```

## Core

```text
status
apply
manager
help
```

## Config

```text
get
set
config
preset
```

## Targeting

```text
profiles
target
```

## Power

```text
on / off
enable / disable
```

## Effects

```text
effect
```

## Global Options

```text
--config PATH
-h, --help
```

## Examples

```powershell
retrocore
retrocore help preset use
retrocore on
retrocore target only "PowerShell"
retrocore effect glow_horizontal 0.12
retrocore manager
```

## Notes

- `retrocore help` shows grouped top-level help
- `retrocore help <topic>` shows help for one command path, such as `retrocore help target only`
- `on` and `off` are the preferred toggle verbs
- `effect` is the preferred effect-editing command
- `enable`, `disable`, and `set-effect` remain available as compatibility aliases
