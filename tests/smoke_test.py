from __future__ import annotations

import contextlib
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import retrocore


@contextlib.contextmanager
def patched_retrocore_paths(temp_root: Path):
    original = {
        "PROJECT_ROOT": retrocore.PROJECT_ROOT,
        "DEFAULT_CONFIG_PATH": retrocore.DEFAULT_CONFIG_PATH,
        "PRESETS_PATH": retrocore.PRESETS_PATH,
        "TEMPLATE_PATH": retrocore.TEMPLATE_PATH,
        "GENERATED_PROJECT_SHADER_PATH": retrocore.GENERATED_PROJECT_SHADER_PATH,
        "SNAPSHOTS_DIR": retrocore.SNAPSHOTS_DIR,
    }
    try:
        retrocore.PROJECT_ROOT = temp_root
        retrocore.DEFAULT_CONFIG_PATH = temp_root / "retrocore.json"
        retrocore.PRESETS_PATH = temp_root / "presets.json"
        retrocore.TEMPLATE_PATH = temp_root / "shaders" / "retrocore.template.hlsl"
        retrocore.GENERATED_PROJECT_SHADER_PATH = temp_root / "shaders" / "retrocore.generated.hlsl"
        retrocore.SNAPSHOTS_DIR = temp_root / "snapshots"
        yield
    finally:
        for key, value in original.items():
            setattr(retrocore, key, value)


def run_cli(argv: list[str]) -> str:
    buffer = StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = retrocore.main(argv)
    if exit_code != 0:
        raise AssertionError(f"retrocore returned non-zero exit code {exit_code} for argv={argv}")
    return buffer.getvalue()


def build_fixture(temp_root: Path) -> tuple[Path, Path]:
    shaders_dir = temp_root / "shaders"
    snapshots_dir = temp_root / "snapshots"
    shaders_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    (shaders_dir / "retrocore.template.hlsl").write_text(
        (REPO_ROOT / "shaders" / "retrocore.template.hlsl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (temp_root / "presets.json").write_text(
        (REPO_ROOT / "presets.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    terminal_dir = temp_root / "terminal"
    terminal_dir.mkdir(parents=True, exist_ok=True)
    settings_path = terminal_dir / "settings.json"
    settings_path.write_text(
        """{
  // Windows Terminal fixture with comments and trailing commas
  "profiles": {
    "defaults": {},
    "list": [
      {
        "name": "PowerShell",
        "guid": "{574e775e-4f2a-5b96-ac1e-a2962a402336}",
      },
    ],
  },
}
""",
        encoding="utf-8",
    )

    config = json.loads((REPO_ROOT / "retrocore.json").read_text(encoding="utf-8"))
    config["terminal"]["settings_path"] = str(settings_path)
    config["terminal"]["shader_output_path"] = str(terminal_dir / "retrocore.generated.hlsl")
    config_path = temp_root / "retrocore.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return config_path, settings_path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="retrocore-smoke-") as temp_dir:
        temp_root = Path(temp_dir)
        config_path, settings_path = build_fixture(temp_root)

        with patched_retrocore_paths(temp_root):
            status_output = run_cli(["--config", str(config_path), "status"])
            assert "Project: retrocore" in status_output
            assert "Managed setting value: retrocore.generated.hlsl" in status_output

            get_output = run_cli(["--config", str(config_path), "get", "target.mode"])
            assert "defaults" in get_output

            set_output = run_cli(["--config", str(config_path), "set", "target.clear_non_target_profiles", "false", "--no-apply"])
            assert "Set target.clear_non_target_profiles=false" in set_output

            apply_output = run_cli(["--config", str(config_path), "apply"])
            assert "Windows Terminal settings updated" in apply_output
            assert (temp_root / "shaders" / "retrocore.generated.hlsl").exists()
            assert list((temp_root / "snapshots").glob("settings.backup.*.json"))

            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            defaults_shader = settings["profiles"]["defaults"]["experimental.pixelShaderPath"]
            assert defaults_shader == "retrocore.generated.hlsl"

            preset_output = run_cli(["--config", str(config_path), "preset", "use", "warm"])
            assert "Applied preset: warm" in preset_output

            target_output = run_cli(["--config", str(config_path), "target", "only", "PowerShell"])
            assert "Target profiles: PowerShell" in target_output

            effect_output = run_cli(["--config", str(config_path), "effect", "glow_horizontal", "0.12"])
            assert "Set glow_horizontal=0.12" in effect_output

            off_output = run_cli(["--config", str(config_path), "off"])
            assert "Enabled: False" in off_output or "Defaults shader: removed" in off_output

            updated_settings = json.loads(settings_path.read_text(encoding="utf-8"))
            assert "experimental.pixelShaderPath" not in updated_settings["profiles"]["defaults"]

    print("retrocore smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
