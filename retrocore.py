from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "retrocore.json"
PRESETS_PATH = PROJECT_ROOT / "presets.json"
TEMPLATE_PATH = PROJECT_ROOT / "shaders" / "retrocore.template.hlsl"
GENERATED_PROJECT_SHADER_PATH = PROJECT_ROOT / "shaders" / "retrocore.generated.hlsl"
SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"
BRANDING_DIR = PROJECT_ROOT / "branding"
LOGO_PNG_PATH = BRANDING_DIR / "retrocore.png"
LOGO_ICO_PATH = BRANDING_DIR / "retrocore.ico"
HIVEMIND_STUDIO_PNG_PATH = BRANDING_DIR / "hivemind_studio.png"
HIVEMIND_STUDIO_URL = "https://hivemindstudio.art"
HELP_DOC_PATH = PROJECT_ROOT / "HELP.md"
SETTING_KEY = "experimental.pixelShaderPath"
BUILTIN_PRESET_NAMES = {
    "subtle",
    "warm",
    "arcade",
    "amber",
    "phosphor-green",
    "ice",
}

EFFECT_KEYS = {
    "curvature": "__CURVATURE__",
    "aberration_base": "__ABERRATION_BASE__",
    "aberration_edge": "__ABERRATION_EDGE__",
    "glow_horizontal": "__GLOW_HORIZONTAL__",
    "glow_vertical": "__GLOW_VERTICAL__",
    "noise_amount": "__NOISE_AMOUNT__",
    "flicker_primary": "__FLICKER_PRIMARY__",
    "flicker_secondary": "__FLICKER_SECONDARY__",
    "vertical_jitter": "__VERTICAL_JITTER__",
    "persistence_amount": "__PERSISTENCE_AMOUNT__",
    "dot_glow_amount": "__DOT_GLOW_AMOUNT__",
    "red_gain": "__RED_GAIN__",
    "green_gain": "__GREEN_GAIN__",
    "blue_gain": "__BLUE_GAIN__",
    "saturation": "__SATURATION__",
}


def expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def strip_json_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and text[index] not in "\r\n":
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


def strip_trailing_json_commas(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < length and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < length and text[lookahead] in "]}":
                index += 1
                continue

        result.append(char)
        index += 1

    return "".join(result)


def parse_json_document(path: Path, *, allow_jsonc: bool = False) -> dict:
    text = read_text_file(path)
    if allow_jsonc:
        text = strip_trailing_json_commas(strip_json_comments(text))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        hint = " after JSONC normalization" if allow_jsonc else ""
        raise SystemExit(f"Failed to parse JSON{hint} in {path}: {exc}") from exc


def load_json(path: Path) -> dict:
    return parse_json_document(path)


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def format_number(value: float) -> str:
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text if text else "0"


def load_config(config_path: Path) -> dict:
    config = load_json(config_path)
    missing = sorted(set(EFFECT_KEYS) - set(config.get("effects", {})))
    if missing:
        raise SystemExit(f"Config is missing effect keys: {', '.join(missing)}")
    return config


def load_presets() -> dict:
    presets = load_json(PRESETS_PATH)
    for name, preset in presets.items():
        missing = sorted(set(EFFECT_KEYS) - set(preset.get("effects", {})))
        if missing:
            raise SystemExit(f"Preset '{name}' is missing effect keys: {', '.join(missing)}")
    return presets


def save_presets(presets: dict) -> None:
    save_json(PRESETS_PATH, presets)


def is_builtin_preset(name: str) -> bool:
    return name in BUILTIN_PRESET_NAMES


def get_config_value(config: dict, dotted_path: str) -> Any:
    current: Any = config
    for key in dotted_path.split("."):
        if not isinstance(current, dict):
            raise SystemExit(f"Config path '{dotted_path}' is invalid at '{key}'")
        if key not in current:
            raise SystemExit(f"Unknown config path: {dotted_path}")
        current = current[key]
    return current


def set_config_value(config: dict, dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current: Any = config
    for key in parts[:-1]:
        if not isinstance(current, dict):
            raise SystemExit(f"Config path '{dotted_path}' is invalid at '{key}'")
        if key not in current:
            raise SystemExit(f"Unknown config path: {dotted_path}")
        current = current[key]

    last_key = parts[-1]
    if not isinstance(current, dict) or last_key not in current:
        raise SystemExit(f"Unknown config path: {dotted_path}")
    current[last_key] = value


def parse_bool(raw: str) -> bool:
    lowered = raw.strip().lower()
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}
    if lowered in truthy:
        return True
    if lowered in falsy:
        return False
    raise SystemExit(f"Cannot parse boolean value: {raw}")


def coerce_config_value(raw: str, value_type: str, existing_value: Any) -> Any:
    if value_type == "string":
        return raw
    if value_type == "bool":
        return parse_bool(raw)
    if value_type == "number":
        return int(raw) if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()) else float(raw)
    if value_type == "json":
        return json.loads(raw)
    if value_type != "auto":
        raise SystemExit(f"Unsupported value type: {value_type}")

    if isinstance(existing_value, bool):
        return parse_bool(raw)
    if isinstance(existing_value, int) and not isinstance(existing_value, bool):
        return int(raw)
    if isinstance(existing_value, float):
        return float(raw)
    if isinstance(existing_value, (list, dict)):
        return json.loads(raw)
    return raw


def settings_path_from_config(config: dict) -> Path:
    return expand_path(config["terminal"]["settings_path"])


def terminal_shader_path_from_config(config: dict) -> Path:
    return expand_path(config["terminal"]["shader_output_path"])


def managed_shader_values(config: dict) -> set[str]:
    output_path = terminal_shader_path_from_config(config)
    return {output_path.name, str(output_path)}


def shader_setting_value(config: dict) -> str:
    settings_path = settings_path_from_config(config)
    output_path = terminal_shader_path_from_config(config)
    if output_path.parent == settings_path.parent:
        return output_path.name
    return str(output_path)


def render_shader(config: dict) -> str:
    shader = TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, token in EFFECT_KEYS.items():
        shader = shader.replace(token, format_number(float(config["effects"][key])))
    return shader


def write_generated_shader(config: dict) -> tuple[Path, Path]:
    shader_text = render_shader(config)
    GENERATED_PROJECT_SHADER_PATH.parent.mkdir(parents=True, exist_ok=True)
    GENERATED_PROJECT_SHADER_PATH.write_text(shader_text, encoding="utf-8")

    terminal_shader_path = terminal_shader_path_from_config(config)
    terminal_shader_path.parent.mkdir(parents=True, exist_ok=True)
    terminal_shader_path.write_text(shader_text, encoding="utf-8")
    return GENERATED_PROJECT_SHADER_PATH, terminal_shader_path


def load_terminal_settings(config: dict) -> tuple[Path, dict]:
    path = settings_path_from_config(config)
    if not path.exists():
        raise SystemExit(f"Windows Terminal settings file not found: {path}")
    return path, parse_json_document(path, allow_jsonc=True)


def list_profiles(settings: dict) -> list[dict]:
    profiles = settings.setdefault("profiles", {})
    profiles.setdefault("defaults", {})
    return profiles.setdefault("list", [])


def terminal_profiles_summary(config: dict) -> list[dict[str, str]]:
    _, settings = load_terminal_settings(config)
    profiles = []
    for profile in list_profiles(settings):
        profiles.append(
            {
                "name": profile.get("name", "<unnamed>"),
                "guid": profile.get("guid", ""),
            }
        )
    return profiles


def profile_matches(profile: dict, identifiers: set[str]) -> bool:
    profile_name = profile.get("name")
    profile_guid = profile.get("guid")
    return profile_name in identifiers or profile_guid in identifiers


def remove_managed_shader(obj: dict, managed_values: set[str]) -> bool:
    if obj.get(SETTING_KEY) in managed_values:
        del obj[SETTING_KEY]
        return True
    return False


def apply_shader_target(settings: dict, config: dict) -> dict:
    profiles_root = settings.setdefault("profiles", {})
    defaults = profiles_root.setdefault("defaults", {})
    profiles = profiles_root.setdefault("list", [])
    managed_values = managed_shader_values(config)
    desired_value = shader_setting_value(config)
    target = config["target"]
    enabled = bool(config["enabled"])
    changed = {
        "defaults_set": False,
        "defaults_removed": False,
        "profiles_set": [],
        "profiles_removed": [],
    }

    if not enabled:
        changed["defaults_removed"] = remove_managed_shader(defaults, managed_values)
        for profile in profiles:
            if remove_managed_shader(profile, managed_values):
                changed["profiles_removed"].append(profile.get("name", "<unnamed>"))
        return changed

    mode = target.get("mode", "defaults")
    clear_non_target = bool(target.get("clear_non_target_profiles", True))

    if mode == "defaults":
        if defaults.get(SETTING_KEY) != desired_value:
            defaults[SETTING_KEY] = desired_value
            changed["defaults_set"] = True
        if clear_non_target:
            for profile in profiles:
                if remove_managed_shader(profile, managed_values):
                    changed["profiles_removed"].append(profile.get("name", "<unnamed>"))
        return changed

    if mode != "specific":
        raise SystemExit("target.mode must be either 'defaults' or 'specific'")

    identifiers = {value for value in target.get("profile_ids", []) if value}
    if not identifiers:
        raise SystemExit("target.profile_ids must contain at least one profile name or GUID when mode is 'specific'")

    changed["defaults_removed"] = remove_managed_shader(defaults, managed_values)
    matched = set()
    available = []

    for profile in profiles:
        name = profile.get("name", "<unnamed>")
        guid = profile.get("guid")
        available.append(name if guid is None else f"{name} ({guid})")
        if profile_matches(profile, identifiers):
            matched.add(profile.get("name") or profile.get("guid"))
            if profile.get(SETTING_KEY) != desired_value:
                profile[SETTING_KEY] = desired_value
                changed["profiles_set"].append(name)
        elif clear_non_target and remove_managed_shader(profile, managed_values):
            changed["profiles_removed"].append(name)

    unresolved = []
    for identifier in identifiers:
        if not any(profile_matches(profile, {identifier}) for profile in profiles):
            unresolved.append(identifier)

    if unresolved:
        available_text = ", ".join(available) if available else "<none>"
        raise SystemExit(
            "Unknown profile id(s): "
            + ", ".join(unresolved)
            + "\nAvailable profiles: "
            + available_text
        )

    return changed


def backup_settings(settings_path: Path) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = SNAPSHOTS_DIR / f"settings.backup.{timestamp}.json"
    shutil.copy2(settings_path, backup_path)
    return backup_path


def maybe_apply(config_path: Path, should_apply: bool, prompt: str) -> int:
    if should_apply:
        return cmd_apply(config_path)
    print(prompt)
    return 0


def should_apply_changes(args: argparse.Namespace, default: bool = True) -> bool:
    value = getattr(args, "apply", None)
    if value is None:
        return default
    return bool(value)


def cmd_status(config_path: Path) -> int:
    config = load_config(config_path)
    settings_path, settings = load_terminal_settings(config)
    terminal_shader_path = terminal_shader_path_from_config(config)
    defaults_shader = settings.get("profiles", {}).get("defaults", {}).get(SETTING_KEY)

    print(f"Project: {config.get('project_name', 'retrocore')}")
    print(f"Config: {config_path}")
    print(f"Preset: {config.get('preset', 'custom')}")
    print(f"Enabled: {config['enabled']}")
    print(f"Target mode: {config['target'].get('mode', 'defaults')}")
    profile_ids = config["target"].get("profile_ids", [])
    print(f"Target profiles: {', '.join(profile_ids) if profile_ids else '(all via defaults)'}")
    print(f"Terminal settings: {settings_path}")
    print(f"Managed shader output: {terminal_shader_path}")
    print(f"Live defaults shader: {defaults_shader or '(none)'}")
    print(f"Managed setting value: {shader_setting_value(config)}")
    return 0


def cmd_config_show(config_path: Path) -> int:
    config = load_config(config_path)
    print_json(config)
    return 0


def cmd_config_get(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    value = get_config_value(config, args.path)
    if isinstance(value, (dict, list)):
        print_json(value)
    else:
        print(value)
    return 0


def cmd_config_set(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    existing = get_config_value(config, args.path)
    new_value = coerce_config_value(args.value, args.type, existing)
    set_config_value(config, args.path, new_value)
    if args.path.startswith("effects."):
        config["preset"] = "custom"
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    print(f"Set {args.path}={json.dumps(new_value) if isinstance(new_value, (dict, list, bool)) else new_value}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=False),
        "Run 'retrocore.cmd apply' to push the config change into Windows Terminal.",
    )


def cmd_preset_list(config_path: Path) -> int:
    config = load_config(config_path)
    presets = load_presets()
    active = config.get("preset", "custom")
    for name, preset in presets.items():
        marker = "*" if name == active else " "
        kind = "built-in" if is_builtin_preset(name) else "user"
        print(f"{marker} {name} [{kind}]: {preset.get('description', '')}")
    return 0


def cmd_preset_show(_: Path, args: argparse.Namespace) -> int:
    presets = load_presets()
    if args.name not in presets:
        raise SystemExit(f"Unknown preset '{args.name}'. Use 'retrocore.cmd preset list' to see available presets.")
    payload = {"name": args.name, "builtin": is_builtin_preset(args.name), **presets[args.name]}
    print_json(payload)
    return 0


def cmd_preset_apply(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    presets = load_presets()
    if args.name not in presets:
        raise SystemExit(f"Unknown preset '{args.name}'. Use 'retrocore.cmd preset list' to see available presets.")
    config["preset"] = args.name
    config["effects"] = copy.deepcopy(presets[args.name]["effects"])
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    print(f"Applied preset: {args.name}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to regenerate the shader and update Terminal.",
    )


def cmd_preset_save(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    presets = load_presets()
    existing = presets.get(args.name)

    if is_builtin_preset(args.name):
        raise SystemExit(f"Preset '{args.name}' is built in and cannot be overwritten.")

    if existing is not None and not args.force:
        raise SystemExit(
            f"Preset '{args.name}' already exists. Re-run with '--force' to overwrite it."
        )

    if args.description:
        description = args.description
    elif existing is not None and existing.get("description"):
        description = existing["description"]
    else:
        description = "User-defined preset saved from the current Retrocore effect values."

    presets[args.name] = {
        "description": description,
        "effects": copy.deepcopy(config["effects"]),
    }
    save_presets(presets)

    config["preset"] = args.name
    save_json(config_path, config)

    print(f"Saved preset: {args.name}")
    print(f"Preset catalog updated: {PRESETS_PATH}")
    print(f"Config updated: {config_path}")
    return 0


def cmd_preset_rename(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    presets = load_presets()

    if args.old_name not in presets:
        raise SystemExit(f"Unknown preset '{args.old_name}'. Use 'retrocore.cmd preset list' to see available presets.")
    if is_builtin_preset(args.old_name):
        raise SystemExit(f"Preset '{args.old_name}' is built in and cannot be renamed.")
    if is_builtin_preset(args.new_name):
        raise SystemExit(f"Preset name '{args.new_name}' is reserved for a built-in preset.")
    if args.new_name in presets:
        raise SystemExit(f"Preset '{args.new_name}' already exists.")

    presets[args.new_name] = presets.pop(args.old_name)
    save_presets(presets)

    if config.get("preset") == args.old_name:
        config["preset"] = args.new_name
        save_json(config_path, config)
        print(f"Config updated: {config_path}")

    print(f"Renamed preset: {args.old_name} -> {args.new_name}")
    print(f"Preset catalog updated: {PRESETS_PATH}")
    return 0


def cmd_preset_delete(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    presets = load_presets()

    if args.name not in presets:
        raise SystemExit(f"Unknown preset '{args.name}'. Use 'retrocore.cmd preset list' to see available presets.")
    if is_builtin_preset(args.name):
        raise SystemExit(f"Preset '{args.name}' is built in and cannot be deleted.")

    del presets[args.name]
    save_presets(presets)

    if config.get("preset") == args.name:
        config["preset"] = "custom"
        save_json(config_path, config)
        print(f"Config updated: {config_path}")
        print("Active preset reference cleared; current effect values were kept.")

    print(f"Deleted preset: {args.name}")
    print(f"Preset catalog updated: {PRESETS_PATH}")
    return 0


def cmd_profiles(config_path: Path) -> int:
    config = load_config(config_path)
    _, settings = load_terminal_settings(config)
    defaults_shader = settings.get("profiles", {}).get("defaults", {}).get(SETTING_KEY)
    profiles = list_profiles(settings)

    if not profiles:
        print("No Windows Terminal profiles found.")
        return 0

    print(f"Defaults shader: {defaults_shader or '(none)'}")
    for profile in profiles:
        name = profile.get("name", "<unnamed>")
        guid = profile.get("guid", "<no-guid>")
        direct = profile.get(SETTING_KEY)
        effective = direct or defaults_shader or "(none)"
        print(f"- {name} | {guid} | direct={direct or '(inherits)'} | effective={effective}")
    return 0


def cmd_apply(config_path: Path) -> int:
    config = load_config(config_path)
    project_shader_path, terminal_shader_path = write_generated_shader(config)
    settings_path, settings = load_terminal_settings(config)
    backup_path = backup_settings(settings_path)
    changed = apply_shader_target(settings, config)
    save_json(settings_path, settings)

    print(f"Generated shader written to: {project_shader_path}")
    print(f"Terminal shader written to: {terminal_shader_path}")
    print(f"Windows Terminal settings backup: {backup_path}")
    print(f"Windows Terminal settings updated: {settings_path}")
    print(f"Enabled: {config['enabled']}")
    print(f"Target mode: {config['target'].get('mode', 'defaults')}")
    if changed['defaults_set']:
        print("Defaults shader: set")
    if changed['defaults_removed']:
        print("Defaults shader: removed")
    if changed["profiles_set"]:
        print("Profiles shader set: " + ", ".join(changed["profiles_set"]))
    if changed["profiles_removed"]:
        print("Profiles shader removed: " + ", ".join(changed["profiles_removed"]))
    print("Restart Windows Terminal to see the change.")
    return 0


def cmd_enable(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["enabled"] = True
    if args.all:
        config["target"]["mode"] = "defaults"
        config["target"]["profile_ids"] = []
    elif args.profile:
        config["target"]["mode"] = "specific"
        config["target"]["profile_ids"] = list(dict.fromkeys(args.profile))
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to push the change into Windows Terminal.",
    )


def cmd_disable(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["enabled"] = False
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to remove the managed shader from Windows Terminal.",
    )


def cmd_set_effect(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    if args.key not in EFFECT_KEYS:
        valid = ", ".join(sorted(EFFECT_KEYS))
        raise SystemExit(f"Unknown effect key '{args.key}'. Valid keys: {valid}")
    config["effects"][args.key] = float(args.value)
    config["preset"] = "custom"
    save_json(config_path, config)
    print(f"Set {args.key}={format_number(float(args.value))} in {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to regenerate the shader and update Terminal.",
    )


def cmd_target_defaults(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["target"]["mode"] = "defaults"
    config["target"]["profile_ids"] = []
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to target all profiles through defaults.",
    )


def cmd_target_specific(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["target"]["mode"] = "specific"
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=False),
        "Run 'retrocore.cmd apply' after choosing one or more profiles.",
    )


def cmd_target_add_profile(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    profile_ids = list(config["target"].get("profile_ids", []))
    if args.profile not in profile_ids:
        profile_ids.append(args.profile)
    config["target"]["mode"] = "specific"
    config["target"]["profile_ids"] = profile_ids
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    print("Target profiles: " + ", ".join(profile_ids))
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to scope Retrocore to the selected profiles.",
    )


def cmd_target_remove_profile(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    profile_ids = [profile for profile in config["target"].get("profile_ids", []) if profile != args.profile]
    config["target"]["profile_ids"] = profile_ids
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    print("Target profiles: " + (", ".join(profile_ids) if profile_ids else "(none)"))
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to update Windows Terminal profile targeting.",
    )


def cmd_target_clear_profiles(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["target"]["profile_ids"] = []
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' after choosing a new target mode or new profiles.",
    )


def cmd_target_only(config_path: Path, args: argparse.Namespace) -> int:
    config = load_config(config_path)
    config["target"]["mode"] = "specific"
    config["target"]["profile_ids"] = list(dict.fromkeys(args.profiles))
    save_json(config_path, config)
    print(f"Updated config: {config_path}")
    print("Target profiles: " + ", ".join(config["target"]["profile_ids"]))
    return maybe_apply(
        config_path,
        should_apply_changes(args, default=True),
        "Run 'retrocore.cmd apply' to scope Retrocore to the selected profiles.",
    )


def add_apply_flags(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(apply=None)
    parser.add_argument("--apply", dest="apply", action="store_true", help="Apply immediately after updating config")
    parser.add_argument("--no-apply", dest="apply", action="store_false", help="Update config without applying immediately")


class RetrocoreManagerApp:
    def __init__(self, root: Any, config_path: Path):
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.root = root
        self.config_path = config_path
        self.presets = load_presets()
        self.profile_rows: list[dict[str, str]] = []
        self.profile_vars: list[tuple[str, str, Any]] = []
        self.effect_vars: dict[str, Any] = {}
        self.logo_image: Any | None = None
        self.studio_icon_image: Any | None = None
        self.help_window: Any | None = None
        self.fonts = {
            "title": ("Consolas", 22, "bold"),
            "body": ("Consolas", 10),
            "small": ("Consolas", 9),
            "studio": ("Consolas", 10, "bold"),
            "link": ("Consolas", 10, "underline"),
            "help_h1": ("Consolas", 18, "bold"),
            "help_h2": ("Consolas", 13, "bold"),
            "help_body": ("Consolas", 10),
            "help_code": ("Consolas", 10),
        }
        self.status_var = tk.StringVar(value="Ready.")
        self.enabled_var = tk.BooleanVar()
        self.preset_var = tk.StringVar()
        self.target_mode_var = tk.StringVar()
        self.clear_non_target_var = tk.BooleanVar()

        self.root.title("Retrocore Manager")
        self.root.geometry("1180x760")
        self.root.minsize(1020, 680)
        self.configure_theme()
        self.configure_branding()
        self.build_ui()
        try:
            self.root.state("zoomed")
        except self.tk.TclError:
            pass
        self.reload_from_disk()

    def configure_theme(self) -> None:
        palette = {
            "bg": "#000000",
            "panel": "#000000",
            "panel_alt": "#000000",
            "border": "#1aff1a",
            "text": "#1aff1a",
            "muted": "#1aff1a",
            "accent": "#1aff1a",
            "accent_text": "#000000",
            "entry": "#000000",
        }
        self.palette = palette
        style = self.ttk.Style()
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass

        self.root.configure(bg=palette["bg"])
        style.configure(".", background=palette["bg"], foreground=palette["text"], fieldbackground=palette["entry"], font=self.fonts["body"])
        style.configure("Retro.TFrame", background=palette["panel"])
        style.configure("RetroAlt.TFrame", background=palette["panel_alt"])
        style.configure("Retro.TLabel", background=palette["panel"], foreground=palette["text"], font=self.fonts["body"])
        style.configure("RetroAlt.TLabel", background=palette["panel_alt"], foreground=palette["text"], font=self.fonts["body"])
        style.configure("Muted.TLabel", background=palette["panel"], foreground=palette["muted"], font=self.fonts["body"])
        style.configure("Retro.TCheckbutton", background=palette["panel"], foreground=palette["text"], font=self.fonts["body"])
        style.map("Retro.TCheckbutton", background=[("active", palette["panel"])], foreground=[("active", palette["text"])])
        style.configure("Retro.TRadiobutton", background=palette["panel"], foreground=palette["text"], font=self.fonts["body"])
        style.map("Retro.TRadiobutton", background=[("active", palette["panel"])], foreground=[("active", palette["text"])])
        style.configure("Retro.TLabelframe", background=palette["panel"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("Retro.TLabelframe.Label", background=palette["panel"], foreground=palette["text"], font=self.fonts["body"])
        style.configure(
            "Retro.Vertical.TScrollbar",
            background=palette["bg"],
            troughcolor=palette["bg"],
            bordercolor=palette["border"],
            arrowcolor=palette["text"],
            darkcolor=palette["border"],
            lightcolor=palette["border"],
            gripcount=0,
        )
        style.map(
            "Retro.Vertical.TScrollbar",
            background=[("active", palette["text"]), ("pressed", palette["text"])],
            troughcolor=[("active", palette["bg"])],
            arrowcolor=[("active", palette["bg"]), ("pressed", palette["bg"])],
            bordercolor=[("active", palette["border"]), ("pressed", palette["border"])],
        )
        style.configure(
            "Retro.TEntry",
            fieldbackground=palette["entry"],
            foreground=palette["text"],
            insertcolor=palette["text"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["border"],
            font=self.fonts["body"],
        )
        style.map(
            "Retro.TEntry",
            fieldbackground=[("readonly", palette["entry"]), ("focus", palette["entry"])],
            foreground=[("readonly", palette["text"]), ("focus", palette["text"])],
            bordercolor=[("focus", palette["border"])],
            lightcolor=[("focus", palette["border"])],
            darkcolor=[("focus", palette["border"])],
        )
        style.configure(
            "Retro.TCombobox",
            fieldbackground=palette["entry"],
            foreground=palette["text"],
            background=palette["entry"],
            arrowcolor=palette["text"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["border"],
            arrowsize=15,
            font=self.fonts["body"],
        )
        style.map(
            "Retro.TCombobox",
            fieldbackground=[("readonly", palette["entry"]), ("focus", palette["entry"])],
            foreground=[("readonly", palette["text"]), ("focus", palette["text"])],
            background=[("readonly", palette["entry"]), ("active", palette["entry"])],
            arrowcolor=[("readonly", palette["text"]), ("active", palette["text"]), ("focus", palette["text"])],
            bordercolor=[("focus", palette["border"])],
            lightcolor=[("focus", palette["border"])],
            darkcolor=[("focus", palette["border"])],
            selectbackground=[("readonly", palette["entry"])],
            selectforeground=[("readonly", palette["text"])],
        )
        style.configure(
            "Retro.TButton",
            background=palette["panel_alt"],
            foreground=palette["text"],
            bordercolor=palette["border"],
            lightcolor=palette["border"],
            darkcolor=palette["border"],
            focusthickness=1,
            focuscolor=palette["border"],
            font=self.fonts["body"],
        )
        style.map(
            "Retro.TButton",
            background=[("active", palette["panel"]), ("pressed", palette["panel"])],
            foreground=[("active", palette["text"]), ("pressed", palette["text"])],
            bordercolor=[("active", palette["border"]), ("focus", palette["border"])],
            lightcolor=[("active", palette["border"]), ("focus", palette["border"])],
            darkcolor=[("active", palette["border"]), ("focus", palette["border"])],
        )
        style.configure("Accent.TButton", background=palette["accent"], foreground=palette["accent_text"], bordercolor=palette["accent"])
        style.map(
            "Accent.TButton",
            background=[("active", palette["accent"]), ("pressed", palette["accent"])],
            foreground=[("active", palette["accent_text"]), ("pressed", palette["accent_text"])],
            bordercolor=[("active", palette["accent"]), ("focus", palette["accent"])],
            lightcolor=[("active", palette["accent"]), ("focus", palette["accent"])],
            darkcolor=[("active", palette["accent"]), ("focus", palette["accent"])],
        )

    def configure_branding(self) -> None:
        if LOGO_ICO_PATH.exists():
            try:
                self.root.iconbitmap(default=str(LOGO_ICO_PATH))
            except self.tk.TclError:
                pass

        if LOGO_PNG_PATH.exists():
            try:
                source_image = self.tk.PhotoImage(file=str(LOGO_PNG_PATH))
                width = source_image.width()
                height = source_image.height()
                crop_x = min(max(14, width // 44), max(14, width // 9))
                crop_y = min(max(6, height // 90), max(6, height // 14))
                cropped_image = self.tk.PhotoImage()
                cropped_image.tk.call(
                    cropped_image,
                    "copy",
                    source_image,
                    "-from",
                    crop_x,
                    crop_y,
                    width - crop_x,
                    height - crop_y,
                )
                self.logo_image = cropped_image
                width = self.logo_image.width()
                if width > 180:
                    scale = max(1, width // 150)
                    self.logo_image = self.logo_image.subsample(scale, scale)
            except self.tk.TclError:
                self.logo_image = None

        if HIVEMIND_STUDIO_PNG_PATH.exists():
            try:
                if Image is not None and ImageTk is not None:
                    source_image = Image.open(HIVEMIND_STUDIO_PNG_PATH)
                    target_size = (34, 34)
                    resized_image = source_image.resize(target_size, Image.Resampling.LANCZOS)
                    self.studio_icon_image = ImageTk.PhotoImage(resized_image)
                else:
                    self.studio_icon_image = self.tk.PhotoImage(file=str(HIVEMIND_STUDIO_PNG_PATH))
            except self.tk.TclError:
                self.studio_icon_image = None

    def build_ui(self) -> None:
        tk = self.tk
        ttk = self.ttk

        shell = ttk.Frame(self.root, style="Retro.TFrame", padding=18)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(1, weight=1)

        header = ttk.Frame(shell, style="Retro.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)
        brand_frame = ttk.Frame(header, style="Retro.TFrame")
        brand_frame.grid(row=0, column=0, sticky="w")
        brand_frame.columnconfigure(1, weight=1)
        if self.logo_image is not None:
            logo_label = tk.Label(
                brand_frame,
                image=self.logo_image,
                bg=self.palette["bg"],
                activebackground=self.palette["bg"],
                borderwidth=0,
                highlightthickness=0,
            )
            logo_label.grid(row=0, column=0, sticky="nw", padx=(0, 14))
        title_frame = ttk.Frame(brand_frame, style="Retro.TFrame")
        title_frame.grid(row=0, column=1, sticky="nw")
        ttk.Label(title_frame, text="RETROCORE MANAGER", style="Retro.TLabel", font=self.fonts["title"]).pack(anchor="w")
        ttk.Label(
            title_frame,
            text="Turn your terminal into a CRT.",
            style="Muted.TLabel",
            font=self.fonts["body"],
        ).pack(anchor="w")
        ttk.Label(
            title_frame,
            text="Control surface for presets, targeting, and CRT effect tuning.",
            style="Muted.TLabel",
            font=self.fonts["body"],
        ).pack(anchor="w")
        studio_frame = ttk.Frame(header, style="Retro.TFrame")
        studio_frame.grid(row=0, column=1, sticky="nw", padx=(18, 0))
        if self.studio_icon_image is not None:
            studio_icon_label = tk.Label(
                studio_frame,
                image=self.studio_icon_image,
                bg=self.palette["bg"],
                activebackground=self.palette["bg"],
                borderwidth=0,
                highlightthickness=0,
            )
            studio_icon_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 8))
        ttk.Label(
            studio_frame,
            text="Hivemind Studio",
            style="Muted.TLabel",
            font=self.fonts["studio"],
        ).grid(row=0, column=1, sticky="w", pady=(2, 0))
        studio_link = tk.Label(
            studio_frame,
            text="hivemindstudio.art",
            fg=self.palette["text"],
            bg=self.palette["bg"],
            cursor="hand2",
            font=self.fonts["link"],
            borderwidth=0,
            highlightthickness=0,
            activeforeground=self.palette["text"],
            activebackground=self.palette["bg"],
        )
        studio_link.grid(row=1, column=1, sticky="w", pady=(4, 0))
        studio_link.bind("<Button-1>", lambda _event: webbrowser.open(HIVEMIND_STUDIO_URL))
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel", font=self.fonts["body"]).grid(row=0, column=2, sticky="e")

        left = ttk.Frame(shell, style="Retro.TFrame")
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 14))
        right = ttk.Frame(shell, style="Retro.TFrame")
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(left, text="Core Controls", style="Retro.TLabelframe", padding=14)
        controls.pack(fill="x")
        ttk.Checkbutton(controls, text="Retrocore enabled", variable=self.enabled_var, style="Retro.TCheckbutton").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(controls, text="Preset", style="Retro.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 4))
        self.preset_combo = ttk.Combobox(controls, textvariable=self.preset_var, state="readonly", style="Retro.TCombobox")
        self.preset_combo.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)
        ttk.Label(controls, text="Target mode", style="Retro.TLabel").grid(row=3, column=0, sticky="w", pady=(12, 4))
        self.target_combo = ttk.Combobox(controls, textvariable=self.target_mode_var, state="readonly", style="Retro.TCombobox", values=["defaults", "specific"])
        self.target_combo.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Checkbutton(
            controls,
            text="Clear non-target Retrocore profile assignments",
            variable=self.clear_non_target_var,
            style="Retro.TCheckbutton",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        actions = ttk.LabelFrame(left, text="Actions", style="Retro.TLabelframe", padding=14)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Reload", command=self.reload_from_disk, style="Retro.TButton").grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Save Config", command=self.save_config_only, style="Retro.TButton").grid(row=0, column=1, sticky="ew", padx=(10, 0))
        ttk.Button(actions, text="Apply to Terminal", command=self.apply_changes, style="Accent.TButton").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Help", command=self.open_help_window, style="Retro.TButton").grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Open Snapshots Folder", command=self.open_snapshots_dir, style="Retro.TButton").grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        target_frame = ttk.LabelFrame(right, text="Profile Targeting", style="Retro.TLabelframe", padding=14)
        target_frame.grid(row=0, column=0, sticky="ew")
        target_frame.columnconfigure(0, weight=1)
        ttk.Label(
            target_frame,
            text="Choose which Windows Terminal profiles Retrocore should target when mode is set to specific.",
            style="Muted.TLabel",
            font=self.fonts["small"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.profile_canvas = tk.Canvas(target_frame, height=170, bg=self.palette["panel_alt"], highlightthickness=1, highlightbackground=self.palette["border"])
        self.profile_canvas.grid(row=1, column=0, sticky="ew")
        profile_scroll = ttk.Scrollbar(target_frame, orient="vertical", command=self.profile_canvas.yview, style="Retro.Vertical.TScrollbar")
        profile_scroll.grid(row=1, column=1, sticky="ns")
        self.profile_canvas.configure(yscrollcommand=profile_scroll.set)
        self.profile_inner = ttk.Frame(self.profile_canvas, style="RetroAlt.TFrame")
        self.profile_canvas_window = self.profile_canvas.create_window((0, 0), window=self.profile_inner, anchor="nw")
        self.profile_inner.bind(
            "<Configure>",
            lambda _event: self.profile_canvas.configure(scrollregion=self.profile_canvas.bbox("all")),
        )
        self.profile_canvas.bind(
            "<Configure>",
            lambda event: self.profile_canvas.itemconfigure(self.profile_canvas_window, width=event.width),
        )

        effects_frame = ttk.LabelFrame(right, text="Effect Settings", style="Retro.TLabelframe", padding=14)
        effects_frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        effects_frame.columnconfigure(0, weight=1)
        effects_frame.rowconfigure(1, weight=1)
        ttk.Label(
            effects_frame,
            text="Edit effect values directly. Numbers are saved back to retrocore.json.",
            style="Muted.TLabel",
            font=self.fonts["small"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.effects_canvas = tk.Canvas(
            effects_frame,
            bg=self.palette["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.palette["border"],
        )
        self.effects_canvas.grid(row=1, column=0, sticky="nsew")
        effects_scroll = ttk.Scrollbar(effects_frame, orient="vertical", command=self.effects_canvas.yview, style="Retro.Vertical.TScrollbar")
        effects_scroll.grid(row=1, column=1, sticky="ns")
        self.effects_canvas.configure(yscrollcommand=effects_scroll.set)
        self.effects_inner = ttk.Frame(self.effects_canvas, style="RetroAlt.TFrame", padding=10)
        self.effects_canvas_window = self.effects_canvas.create_window((0, 0), window=self.effects_inner, anchor="nw")
        self.effects_inner.bind(
            "<Configure>",
            lambda _event: self.effects_canvas.configure(scrollregion=self.effects_canvas.bbox("all")),
        )
        self.effects_canvas.bind(
            "<Configure>",
            lambda event: self.effects_canvas.itemconfigure(self.effects_canvas_window, width=event.width),
        )

        for index, key in enumerate(EFFECT_KEYS):
            column = index % 2
            row = (index // 2) * 2
            ttk.Label(self.effects_inner, text=key, style="RetroAlt.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 10))
            var = tk.StringVar()
            self.effect_vars[key] = var
            entry = ttk.Entry(self.effects_inner, textvariable=var, style="Retro.TEntry")
            entry.grid(row=row + 1, column=column, sticky="ew", padx=(0, 14), pady=(2, 10))
        self.effects_inner.columnconfigure(0, weight=1)
        self.effects_inner.columnconfigure(1, weight=1)

        self.root.option_add("*TCombobox*Listbox.background", self.palette["bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", self.palette["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.palette["text"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.palette["bg"])
        self.root.option_add("*TCombobox*Listbox.highlightBackground", self.palette["border"])
        self.root.option_add("*TCombobox*Listbox.highlightColor", self.palette["border"])

    def reload_from_disk(self) -> None:
        self.config = load_config(self.config_path)
        self.presets = load_presets()
        self.profile_rows = terminal_profiles_summary(self.config)
        self.preset_combo.configure(values=list(self.presets))
        active_preset = self.config.get("preset", "custom")
        preset_values = list(self.presets)
        if active_preset not in preset_values:
            preset_values = ["custom", *preset_values]
            self.preset_combo.configure(values=preset_values)
        self.preset_var.set(active_preset)
        self.enabled_var.set(bool(self.config["enabled"]))
        self.target_mode_var.set(self.config["target"].get("mode", "defaults"))
        self.clear_non_target_var.set(bool(self.config["target"].get("clear_non_target_profiles", True)))
        for key, var in self.effect_vars.items():
            var.set(format_number(float(self.config["effects"][key])))
        self.rebuild_profiles()
        self.status_var.set(f"Loaded {self.config_path.name}")

    def rebuild_profiles(self) -> None:
        for child in self.profile_inner.winfo_children():
            child.destroy()
        self.profile_vars = []
        selected = set(self.config["target"].get("profile_ids", []))
        if not self.profile_rows:
            self.ttk.Label(self.profile_inner, text="No Windows Terminal profiles found.", style="RetroAlt.TLabel").grid(row=0, column=0, sticky="w")
            return
        for index, profile in enumerate(self.profile_rows):
            identifier = profile["name"] or profile["guid"]
            var = self.tk.BooleanVar(value=profile["name"] in selected or profile["guid"] in selected)
            label = profile["name"] if not profile["guid"] else f'{profile["name"]}  {profile["guid"]}'
            self.ttk.Checkbutton(self.profile_inner, text=label, variable=var, style="Retro.TCheckbutton").grid(row=index, column=0, sticky="w", pady=2)
            self.profile_vars.append((profile["name"], profile["guid"], var))

    def on_preset_selected(self, _event: Any = None) -> None:
        selected_preset = self.preset_var.get()
        preset = self.presets.get(selected_preset)
        if not preset:
            return
        for key, value in preset["effects"].items():
            if key in self.effect_vars:
                self.effect_vars[key].set(format_number(float(value)))
        self.status_var.set(f"Preset loaded: {selected_preset}")

    def collect_config_from_form(self) -> dict:
        config = load_config(self.config_path)
        config["enabled"] = bool(self.enabled_var.get())
        selected_preset = self.preset_var.get() or "custom"
        config["target"]["mode"] = self.target_mode_var.get() or "defaults"
        config["target"]["clear_non_target_profiles"] = bool(self.clear_non_target_var.get())
        selected_profiles = []
        for name, guid, var in self.profile_vars:
            if var.get():
                selected_profiles.append(name or guid)
        config["target"]["profile_ids"] = selected_profiles if config["target"]["mode"] == "specific" else []
        for key, var in self.effect_vars.items():
            raw = var.get().strip()
            if not raw:
                raise SystemExit(f"Effect '{key}' cannot be blank.")
            config["effects"][key] = float(raw)
        preset_effects = self.presets.get(selected_preset, {}).get("effects")
        if preset_effects and all(float(config["effects"][key]) == float(preset_effects[key]) for key in EFFECT_KEYS):
            config["preset"] = selected_preset
        else:
            config["preset"] = "custom"
        return config

    def save_current_state(self) -> None:
        config = self.collect_config_from_form()
        save_json(self.config_path, config)
        self.config = config

    def save_config_only(self) -> None:
        try:
            self.save_current_state()
        except Exception as exc:
            self.messagebox.showerror("Retrocore Manager", str(exc))
            self.status_var.set("Save failed.")
            return
        self.status_var.set("Config saved.")

    def apply_changes(self) -> None:
        try:
            self.save_current_state()
            cmd_apply(self.config_path)
        except Exception as exc:
            self.messagebox.showerror("Retrocore Manager", str(exc))
            self.status_var.set("Apply failed.")
            return
        self.status_var.set("Applied to Windows Terminal.")
        self.messagebox.showinfo("Retrocore Manager", "Retrocore settings were applied.\nRestart Windows Terminal to see the change.")

    def open_snapshots_dir(self) -> None:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(SNAPSHOTS_DIR)

    def open_help_window(self) -> None:
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.lift()
            self.help_window.focus_force()
            return

        if not HELP_DOC_PATH.exists():
            self.messagebox.showerror("Retrocore Manager", f"Help document not found: {HELP_DOC_PATH}")
            return

        help_window = self.tk.Toplevel(self.root)
        help_window.title("Retrocore Help")
        help_window.configure(bg=self.palette["bg"])
        help_window.geometry("920x720")
        try:
            help_window.iconbitmap(default=str(LOGO_ICO_PATH))
        except self.tk.TclError:
            pass
        self.help_window = help_window
        help_window.protocol("WM_DELETE_WINDOW", self.close_help_window)

        container = self.ttk.Frame(help_window, style="Retro.TFrame", padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        text = self.tk.Text(
            container,
            wrap="word",
            bg=self.palette["bg"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.palette["border"],
            padx=16,
            pady=16,
            font=self.fonts["help_body"],
        )
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = self.ttk.Scrollbar(container, orient="vertical", command=text.yview, style="Retro.Vertical.TScrollbar")
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        self.configure_help_text_tags(text)
        self.render_markdown_into_text(text, HELP_DOC_PATH.read_text(encoding="utf-8"))
        text.configure(state="disabled")

    def close_help_window(self) -> None:
        if self.help_window is not None and self.help_window.winfo_exists():
            self.help_window.destroy()
        self.help_window = None

    def configure_help_text_tags(self, text: Any) -> None:
        text.tag_configure("h1", font=self.fonts["help_h1"], spacing1=4, spacing3=8)
        text.tag_configure("h2", font=self.fonts["help_h2"], spacing1=6, spacing3=6)
        text.tag_configure("body", font=self.fonts["help_body"], spacing1=0, spacing3=2)
        text.tag_configure("bullet", lmargin1=14, lmargin2=28, spacing3=2)
        text.tag_configure("code", font=self.fonts["help_code"], background="#001400", lmargin1=14, lmargin2=14, spacing1=4, spacing3=6)
        text.tag_configure("inline_code", font=self.fonts["help_code"], background="#001400")
        text.tag_configure("link", foreground=self.palette["text"], underline=True)

    def render_markdown_into_text(self, text: Any, markdown: str) -> None:
        in_code_block = False
        link_index = 0

        for raw_line in markdown.splitlines():
            line = raw_line.rstrip("\n")

            if line.startswith("```"):
                in_code_block = not in_code_block
                if not in_code_block:
                    text.insert("end", "\n")
                continue

            if in_code_block:
                text.insert("end", line + "\n", ("code",))
                continue

            stripped = line.strip()
            if not stripped:
                text.insert("end", "\n")
                continue

            if stripped.startswith("# "):
                text.insert("end", stripped[2:] + "\n", ("h1",))
                continue

            if stripped.startswith("## "):
                text.insert("end", stripped[3:] + "\n", ("h2",))
                continue

            if stripped.startswith("- "):
                self.insert_markdown_inline(text, "• " + stripped[2:], link_index_prefix=f"link_{link_index}_")
                link_index += 1
                text.insert("end", "\n", ("bullet",))
                start = text.index("end-2c linestart")
                end = text.index("end-2c lineend")
                text.tag_add("bullet", start, end)
                continue

            self.insert_markdown_inline(text, stripped, link_index_prefix=f"link_{link_index}_")
            link_index += 1
            text.insert("end", "\n", ("body",))

    def insert_markdown_inline(self, text: Any, content: str, link_index_prefix: str) -> None:
        index = 0
        segment = 0
        while index < len(content):
            if content[index] == "`":
                end = content.find("`", index + 1)
                if end != -1:
                    text.insert("end", content[index + 1 : end], ("inline_code",))
                    index = end + 1
                    continue

            if content[index] == "[":
                mid = content.find("](", index)
                end = content.find(")", mid + 2) if mid != -1 else -1
                if mid != -1 and end != -1:
                    label = content[index + 1 : mid]
                    url = content[mid + 2 : end]
                    tag_name = f"{link_index_prefix}{segment}"
                    start = text.index("end")
                    text.insert("end", label, ("link", tag_name))
                    finish = text.index("end")
                    text.tag_add(tag_name, start, finish)
                    text.tag_bind(tag_name, "<Button-1>", lambda _event, target=url: webbrowser.open(target))
                    text.tag_bind(tag_name, "<Enter>", lambda _event: text.configure(cursor="hand2"))
                    text.tag_bind(tag_name, "<Leave>", lambda _event: text.configure(cursor="xterm"))
                    index = end + 1
                    segment += 1
                    continue

            text.insert("end", content[index], ("body",))
            index += 1


def cmd_manager(config_path: Path) -> int:
    try:
        import tkinter as tk
    except ImportError as exc:
        raise SystemExit("Tkinter is required for 'retrocore manager' but is not available in this Python install.") from exc

    root = tk.Tk()
    app = RetrocoreManagerApp(root, config_path)
    root.mainloop()
    return 0


def print_top_level_help() -> None:
    left = "Retrocore by Hivemind Studio"
    right = "https://hivemindstudio.art"
    width = 80
    spacing = max(2, width - len(left) - len(right))
    print(left + (" " * spacing) + right)
    print("Turn your terminal into a CRT.")
    print("")
    print("Usage:")
    print("  retrocore <command> [options]")
    print("")
    print("Core:")
    print("  status")
    print("  apply")
    print("  manager")
    print("  help")
    print("")
    print("Config:")
    print("  get")
    print("  set")
    print("  config")
    print("  preset")
    print("")
    print("Targeting:")
    print("  profiles")
    print("  target")
    print("")
    print("Power:")
    print("  on / off")
    print("  enable / disable")
    print("")
    print("Effects:")
    print("  effect")
    print("")
    print("Global options:")
    print("  --config PATH")
    print("  -h, --help")
    print("")
    print("Examples:")
    print("  retrocore")
    print("  retrocore help preset use")
    print("  retrocore on")
    print('  retrocore target only "PowerShell"')
    print("  retrocore effect glow_horizontal 0.12")


def cmd_help(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if not args.topic:
        print_top_level_help()
        return 0

    command_parts = list(args.topic)
    current_parser = parser

    for index, part in enumerate(command_parts):
        action = next(
            (
                candidate
                for candidate in current_parser._actions
                if isinstance(candidate, argparse._SubParsersAction) and part in candidate.choices
            ),
            None,
        )
        if action is None:
            joined = " ".join(command_parts[: index + 1])
            raise SystemExit(f"Unknown help topic: {joined}")
        current_parser = action.choices[part]

    current_parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retrocore Windows Terminal shader manager")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to retrocore config JSON",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    help_parser = subparsers.add_parser("help", help="Show help for Retrocore or one command")
    help_parser.add_argument("topic", nargs="*", help="Optional command path such as preset use or target only")

    subparsers.add_parser("status", help="Show config and live Windows Terminal shader state")
    subparsers.add_parser("profiles", help="List Windows Terminal profiles and current shader attachment")
    subparsers.add_parser("apply", help="Generate the shader and update Windows Terminal settings")
    subparsers.add_parser("manager", help="Launch the Retrocore Manager desktop UI")

    get_parser = subparsers.add_parser("get", help="Read one config value by dotted path")
    get_parser.add_argument("path", help="Config path such as target.mode or effects.glow_horizontal")

    set_parser = subparsers.add_parser("set", help="Update one config value by dotted path")
    set_parser.add_argument("path", help="Config path such as target.mode or terminal.shader_output_path")
    set_parser.add_argument("value", help="New value")
    set_parser.add_argument(
        "--type",
        choices=["auto", "string", "number", "bool", "json"],
        default="auto",
        help="How to parse the new value",
    )
    add_apply_flags(set_parser)

    preset_parser = subparsers.add_parser("preset", help="List, inspect, save, and apply Retrocore presets")
    preset_subparsers = preset_parser.add_subparsers(dest="preset_command", required=True)
    preset_subparsers.add_parser("list", help="List available presets")
    preset_show_parser = preset_subparsers.add_parser("show", help="Show one preset definition")
    preset_show_parser.add_argument("name", help="Preset name")
    preset_apply_parser = preset_subparsers.add_parser("use", aliases=["apply"], help="Use one preset and apply it by default")
    preset_apply_parser.add_argument("name", help="Preset name")
    add_apply_flags(preset_apply_parser)
    preset_save_parser = preset_subparsers.add_parser("save", help="Save the current effect values as a preset")
    preset_save_parser.add_argument("name", help="Preset name")
    preset_save_parser.add_argument("--description", help="Optional preset description")
    preset_save_parser.add_argument("--force", action="store_true", help="Overwrite an existing preset")
    preset_rename_parser = preset_subparsers.add_parser("rename", help="Rename a user preset")
    preset_rename_parser.add_argument("old_name", help="Existing preset name")
    preset_rename_parser.add_argument("new_name", help="New preset name")
    preset_delete_parser = preset_subparsers.add_parser("delete", help="Delete a user preset")
    preset_delete_parser.add_argument("name", help="Preset name")

    config_parser = subparsers.add_parser("config", help="Read or edit retrocore.json through the CLI")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("show", help="Print the full config JSON")
    config_get_parser = config_subparsers.add_parser("get", help="Read one config value by dotted path")
    config_get_parser.add_argument("path", help="Config path such as target.mode or effects.glow_horizontal")
    config_set_parser = config_subparsers.add_parser("set", help="Update one config value by dotted path")
    config_set_parser.add_argument("path", help="Config path such as target.mode or terminal.shader_output_path")
    config_set_parser.add_argument("value", help="New value")
    config_set_parser.add_argument(
        "--type",
        choices=["auto", "string", "number", "bool", "json"],
        default="auto",
        help="How to parse the new value",
    )
    add_apply_flags(config_set_parser)

    target_parser = subparsers.add_parser("target", help="Manage which Windows Terminal profiles Retrocore affects")
    target_subparsers = target_parser.add_subparsers(dest="target_command", required=True)
    target_defaults_parser = target_subparsers.add_parser("all", aliases=["defaults"], help="Target all profiles through profiles.defaults")
    add_apply_flags(target_defaults_parser)
    target_specific_parser = target_subparsers.add_parser("specific", help="Use explicit target.profile_ids instead of defaults")
    add_apply_flags(target_specific_parser)
    target_only_parser = target_subparsers.add_parser("only", help="Target only the named profiles and apply by default")
    target_only_parser.add_argument("profiles", nargs="+", help="One or more profile names or GUIDs")
    add_apply_flags(target_only_parser)
    target_add_parser = target_subparsers.add_parser("add-profile", help="Add one profile name or GUID to target.profile_ids")
    target_add_parser.add_argument("profile", help="Profile name or GUID")
    add_apply_flags(target_add_parser)
    target_remove_parser = target_subparsers.add_parser("remove-profile", help="Remove one profile name or GUID from target.profile_ids")
    target_remove_parser.add_argument("profile", help="Profile name or GUID")
    add_apply_flags(target_remove_parser)
    target_clear_parser = target_subparsers.add_parser("clear", aliases=["clear-profiles"], help="Clear target.profile_ids")
    add_apply_flags(target_clear_parser)

    enable_parser = subparsers.add_parser("enable", help="Compatibility alias for 'on'")
    enable_parser.add_argument("--all", action="store_true", help="Target all profiles through profiles.defaults")
    enable_parser.add_argument("--profile", action="append", help="Profile name or GUID to target; repeat as needed")
    add_apply_flags(enable_parser)

    on_parser = subparsers.add_parser("on", help="Alias for enable")
    on_parser.add_argument("--all", action="store_true", help="Target all profiles through profiles.defaults")
    on_parser.add_argument("--profile", action="append", help="Profile name or GUID to target; repeat as needed")
    add_apply_flags(on_parser)

    disable_parser = subparsers.add_parser("disable", help="Compatibility alias for 'off'")
    add_apply_flags(disable_parser)

    off_parser = subparsers.add_parser("off", help="Alias for disable")
    add_apply_flags(off_parser)

    set_effect_parser = subparsers.add_parser("effect", aliases=["set-effect"], help="Update one effect value and apply it by default")
    set_effect_parser.add_argument("key", help="Effect key to update")
    set_effect_parser.add_argument("value", help="New numeric value")
    add_apply_flags(set_effect_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv or argv in [["-h"], ["--help"]]:
        print_top_level_help()
        return 0
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()

    if args.command == "help":
        return cmd_help(parser, args)
    if args.command == "status":
        return cmd_status(config_path)
    if args.command == "preset":
        if args.preset_command == "list":
            return cmd_preset_list(config_path)
        if args.preset_command == "show":
            return cmd_preset_show(config_path, args)
        if args.preset_command in {"use", "apply"}:
            return cmd_preset_apply(config_path, args)
        if args.preset_command == "save":
            return cmd_preset_save(config_path, args)
        if args.preset_command == "rename":
            return cmd_preset_rename(config_path, args)
        if args.preset_command == "delete":
            return cmd_preset_delete(config_path, args)
        parser.error(f"Unsupported preset command: {args.preset_command}")
    if args.command == "config":
        if args.config_command == "show":
            return cmd_config_show(config_path)
        if args.config_command == "get":
            return cmd_config_get(config_path, args)
        if args.config_command == "set":
            return cmd_config_set(config_path, args)
        parser.error(f"Unsupported config command: {args.config_command}")
    if args.command == "get":
        return cmd_config_get(config_path, args)
    if args.command == "set":
        return cmd_config_set(config_path, args)
    if args.command == "profiles":
        return cmd_profiles(config_path)
    if args.command == "apply":
        return cmd_apply(config_path)
    if args.command == "manager":
        return cmd_manager(config_path)
    if args.command == "target":
        if args.target_command in {"all", "defaults"}:
            return cmd_target_defaults(config_path, args)
        if args.target_command == "specific":
            return cmd_target_specific(config_path, args)
        if args.target_command == "only":
            return cmd_target_only(config_path, args)
        if args.target_command == "add-profile":
            return cmd_target_add_profile(config_path, args)
        if args.target_command == "remove-profile":
            return cmd_target_remove_profile(config_path, args)
        if args.target_command in {"clear", "clear-profiles"}:
            return cmd_target_clear_profiles(config_path, args)
        parser.error(f"Unsupported target command: {args.target_command}")
    if args.command == "enable":
        return cmd_enable(config_path, args)
    if args.command == "on":
        return cmd_enable(config_path, args)
    if args.command == "disable":
        return cmd_disable(config_path, args)
    if args.command == "off":
        return cmd_disable(config_path, args)
    if args.command in {"effect", "set-effect"}:
        return cmd_set_effect(config_path, args)
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
