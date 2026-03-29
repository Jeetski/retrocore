# Windows Terminal CRT Shader

This folder contains the custom CRT-style pixel shader used by Windows Terminal on this machine.

The current shader is deliberately restrained. It adds scanlines, a light shadow mask, slight barrel distortion, soft glow, small convergence errors, a faint noise/flicker pass, and a minimal phosphor-style bloom without turning the terminal into a heavy retro effect.

## Files

- `crt-subtle.hlsl`: the shader source loaded by Windows Terminal
- `settings.json`: the Windows Terminal settings file that points to the shader
- `state.json`: Windows Terminal runtime state

## Current configuration

The shader is enabled globally through `profiles.defaults`, so it affects every profile unless a profile overrides the setting:

```json
"profiles": {
  "defaults": {
    "experimental.pixelShaderPath": "crt-subtle.hlsl"
  }
}
```

Because the shader file sits beside `settings.json`, Windows Terminal 1.24 and later can resolve it by relative filename alone.

## Install or re-create this setup

1. Place `crt-subtle.hlsl` in the same folder as `settings.json`.
2. Open `settings.json`.
3. Add the shader path under `profiles.defaults`:

```json
"profiles": {
  "defaults": {
    "experimental.pixelShaderPath": "crt-subtle.hlsl"
  }
}
```

4. Save `settings.json`.
5. Fully restart Windows Terminal.

A tab reload is often not enough. Close all Terminal windows and open a new instance after changing either the shader or the shader path.

## What the shader currently does

- Applies mild barrel distortion toward the screen edges
- Adds small horizontal chromatic aberration, stronger near the edges
- Blends a subtle horizontal and vertical glow around bright pixels
- Uses a scanline brightness mask that reacts slightly to pixel intensity
- Applies a restrained RGB shadow mask to suggest CRT phosphor triads
- Adds light vignette and edge falloff
- Introduces very small flicker, noise, and vertical jitter
- Fakes limited phosphor persistence by re-sampling nearby scanlines

## Tuning notes

The easiest places to adjust the look are inside `crt-subtle.hlsl`:

- `barrel(uv, 0.055)`: screen curvature
- `aberration = float2(0.00055 + edgeAmount * 0.00075, 0.0)`: color fringing
- `color += glow * 0.16;`: horizontal bloom strength
- `color += scanGlow * 0.10;`: vertical bloom strength
- `noise ... * 0.014;`: static intensity
- `flicker`: brightness instability
- `persistence ... * 0.022`: phosphor afterglow approximation

If the effect starts to feel obvious instead of ambient, the bloom, curvature, and chromatic aberration values are the first knobs to reduce.

## Version and path notes

- Windows Terminal 1.24 and later resolve `crt-subtle.hlsl` correctly when it is adjacent to `settings.json`.
- On older 1.23 builds on this machine, `ms-appdata:///local/crt-subtle.hlsl` produced `0x8007007b`.
- Upgrading Terminal was a cleaner fix than maintaining a special-case path.

## Troubleshooting

- Shader has no visible effect: fully restart Windows Terminal, not just the shell inside it.
- Shader fails to load: confirm `crt-subtle.hlsl` is in the same folder as `settings.json`.
- JSON edits break Terminal startup: validate `settings.json` for trailing commas or malformed structure.
- Neovim looks different only outside Terminal: this shader only affects apps rendered inside Windows Terminal.
- Persistence does not look like a real CRT: Terminal shaders cannot access previous frames, so persistence is only approximated.

## Scope

This shader affects Windows Terminal rendering only. It changes the appearance of shells and terminal applications running inside Windows Terminal, including Neovim when Neovim is launched there.
