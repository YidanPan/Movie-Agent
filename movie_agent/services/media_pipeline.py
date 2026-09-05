"""Encoding policy for the source, mezzanine, preview, and delivery tiers.

The policy deliberately keeps lossy H.264 out of the editorial chain.  Real
source media is normalized into a ProRes 422 LT mezzanine when the local
FFmpeg build supports it.  The fallback is a high-quality CRF 13 H.264
mezzanine, which is still materially safer than repeatedly encoding at CRF
18.  Proxy, screening, and delivery encodes are never used as edit sources.
"""

from __future__ import annotations

from typing import Literal


MEZZANINE_CODEC = "prores_ks"
MEZZANINE_PROFILE = "1"  # ProRes 422 LT
MEZZANINE_PIX_FMT = "yuv422p10le"
MEZZANINE_FALLBACK_CODEC = "libx264"
MEZZANINE_FALLBACK_CRF = "13"
PROXY_CRF = "30"
SCREENING_CRF = "22"
DELIVERY_CRF = "18"

PreviewTier = Literal["working_proxy", "screening_preview"]


def mezzanine_video_args(*, fallback: bool = False) -> list[str]:
    """Return video/audio arguments for an editorial mezzanine encode."""

    if fallback:
        return [
            "-c:v",
            MEZZANINE_FALLBACK_CODEC,
            "-preset",
            "slow",
            "-crf",
            MEZZANINE_FALLBACK_CRF,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ar",
            "48000",
        ]
    return [
        "-c:v",
        MEZZANINE_CODEC,
        "-profile:v",
        MEZZANINE_PROFILE,
        "-pix_fmt",
        MEZZANINE_PIX_FMT,
        "-c:a",
        "pcm_s16le",
        "-ar",
        "48000",
    ]


def preview_video_args(tier: PreviewTier) -> list[str]:
    """Return intentionally disposable preview settings."""

    crf = PROXY_CRF if tier == "working_proxy" else SCREENING_CRF
    preset = "veryfast" if tier == "working_proxy" else "fast"
    return [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
    ]


def delivery_video_args(container: str = "mp4") -> list[str]:
    """Return the one final delivery encode for a selected container."""

    if container == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]
    if container == "mov":
        return [
            "-c:v",
            "prores_ks",
            "-profile:v",
            MEZZANINE_PROFILE,
            "-pix_fmt",
            MEZZANINE_PIX_FMT,
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        DELIVERY_CRF,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
    ]


def combine_video_filters(*filters: str | None) -> str | None:
    """Combine scale/timing/crop/color filters into one FFmpeg graph."""

    values = [str(value).strip() for value in filters if str(value or "").strip()]
    return ",".join(values) if values else None
