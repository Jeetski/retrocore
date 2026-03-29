// Subtle CRT shader for Windows Terminal.
// Aims for realistic restraint rather than obvious retro gimmicks.

Texture2D shaderTexture : register(t0);
SamplerState samplerState : register(s0);

cbuffer PixelShaderSettings : register(b0)
{
    float Time;
    float Scale;
    float2 Resolution;
    float4 Background;
};

struct PSInput
{
    float4 pos : SV_POSITION;
    float2 uv : TEXCOORD0;
};

static const float PI = 3.14159265359;

float rand(float2 n)
{
    return frac(sin(dot(n, float2(12.9898, 78.233))) * 43758.5453);
}

float2 barrel(float2 uv, float amount)
{
    float2 p = uv * 2.0 - 1.0;
    float r2 = dot(p, p);
    p *= 1.0 + amount * r2;
    return p * 0.5 + 0.5;
}

float3 sample_rgb(float2 uv, float2 aberration)
{
    float r = shaderTexture.Sample(samplerState, uv + aberration).r;
    float g = shaderTexture.Sample(samplerState, uv).g;
    float b = shaderTexture.Sample(samplerState, uv - aberration).b;
    return float3(r, g, b);
}

float3 horizontal_glow(float2 uv, float2 aberration)
{
    float2 px = float2(1.0 / Resolution.x, 0.0);

    float3 c0 = sample_rgb(uv, aberration) * 0.44;
    float3 c1 = sample_rgb(uv + px * 1.0, aberration) * 0.18;
    float3 c2 = sample_rgb(uv - px * 1.0, aberration) * 0.18;
    float3 c3 = sample_rgb(uv + px * 2.0, aberration) * 0.10;
    float3 c4 = sample_rgb(uv - px * 2.0, aberration) * 0.10;

    return c0 + c1 + c2 + c3 + c4;
}

float3 vertical_glow(float2 uv, float2 aberration)
{
    float2 py = float2(0.0, 1.0 / Resolution.y);

    float3 c0 = sample_rgb(uv + py * 1.0, aberration) * 0.10;
    float3 c1 = sample_rgb(uv - py * 1.0, aberration) * 0.10;
    float3 c2 = sample_rgb(uv + py * 2.0, aberration) * 0.04;
    float3 c3 = sample_rgb(uv - py * 2.0, aberration) * 0.04;

    return c0 + c1 + c2 + c3;
}

float scanline_mask(float y, float beam)
{
    float scanPhase = sin(y * Resolution.y * PI);
    float beamResponse = saturate((beam - 0.72) / 0.45);
    float darkFloor = lerp(0.60, 0.70, beamResponse);
    float brightPeak = lerp(1.02, 1.10, beamResponse);
    float brightRow = pow(0.5 + 0.5 * scanPhase, lerp(1.25, 0.95, beamResponse));

    return lerp(darkFloor, brightPeak, brightRow);
}

float3 shadow_mask(float x)
{
    float triad = frac(x * Resolution.x / 3.0);
    float3 mask = float3(
        saturate(1.0 - abs(triad - 1.0 / 6.0) * 6.0),
        saturate(1.0 - abs(triad - 3.0 / 6.0) * 6.0),
        saturate(1.0 - abs(triad - 5.0 / 6.0) * 6.0)
    );
    float grille = 0.99 + 0.01 * sin(x * Resolution.x * 2.0 * PI);

    return (0.955 + mask * 0.045) * grille;
}

float edge_falloff(float2 uv)
{
    float2 p = uv * (1.0 - uv);
    float vig = p.x * p.y * 18.0;
    return saturate(pow(vig, 0.22));
}

float beam_profile(float3 color)
{
    return 0.78 + saturate(max(color.r, max(color.g, color.b))) * 0.38;
}

float3 phosphor_dot_glow(float2 uv, float3 baseColor)
{
    float2 grid = frac(uv * Resolution.xy);
    float dotGlow = exp(-18.0 * dot(grid - 0.5, grid - 0.5));
    return baseColor * dotGlow * 0.028;
}

float4 main(PSInput input) : SV_TARGET
{
    float2 uv = input.uv;
    float2 warped = barrel(uv, 0.055);

    if (warped.x < 0.0 || warped.x > 1.0 || warped.y < 0.0 || warped.y > 1.0)
    {
        return float4(Background.rgb * 0.02, 1.0);
    }

    float2 edgeVec = warped - 0.5;
    float edgeAmount = dot(edgeVec, edgeVec);
    float2 aberration = float2(0.00055 + edgeAmount * 0.00075, 0.0);

    float3 base = sample_rgb(warped, aberration);
    float3 glow = horizontal_glow(warped, aberration);
    float3 scanGlow = vertical_glow(warped, aberration);

    float beam = beam_profile(base);
    float scan = scanline_mask(warped.y, beam);
    float3 mask = shadow_mask(warped.x + 0.00015 * sin(Time * 1.13));
    float vignette = edge_falloff(warped);

    float noise = (rand(float2(warped.y * 241.13, Time * 2.7)) - 0.5) * 0.014;
    float flicker = 1.0 + sin(Time * 59.7) * 0.0035 + sin(Time * 121.3) * 0.0015;
    float verticalJitter = (rand(float2(floor(Time * 2.0), 8.0)) - 0.5) * 0.00045;

    float3 persistence =
        shaderTexture.Sample(samplerState, warped + float2(0.0, verticalJitter + 1.0 / Resolution.y)).rgb * 0.022 +
        shaderTexture.Sample(samplerState, warped + float2(0.0, verticalJitter - 1.0 / Resolution.y)).rgb * 0.022;

    float3 color = base;
    color += glow * 0.16;
    color += scanGlow * 0.10;
    color += persistence;
    color += phosphor_dot_glow(warped, base);

    color *= scan;
    color *= mask;
    color *= flicker;
    color += noise;

    // Slight convergence imperfection, stronger toward the edges.
    color.r *= 1.0 + edgeAmount * 0.018;
    color.b *= 1.0 - edgeAmount * 0.012;

    // Gentle bloom rolloff.
    color = color / (1.0 + color * 0.22);
    color *= vignette;

    return float4(saturate(color), 1.0);
}
