"""Resolve font family names to font files, fontconfig-style.

OpenSCAD finds fonts via fontconfig, which matches on the family name in
the font's name table. build123d delegates to OCCT's Font_FontMgr, which
registers fonts with nonstandard subfamilies (e.g. "Plain") under a
combined name, so lookups by plain family name silently fall back to
Arial. This module scans the system font directories with fontTools and
resolves an OpenSCAD-style ``"Family"`` or ``"Family:style=Style"`` spec
to a concrete font file path.
"""

import sys
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

_FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc")
_DEFAULT_STYLES = ("regular", "plain", "normal", "book", "roman", "medium")


def _font_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ]
    if sys.platform.startswith("win"):
        dirs = [Path(r"C:\Windows\Fonts")]
        local = home / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        return dirs + [local]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        home / ".local" / "share" / "fonts",
        home / ".fonts",
    ]


def _faces_in_file(path: Path) -> list[tuple[str, str]]:
    """Return (family, subfamily) for each face in a font file."""
    faces: list[tuple[str, str]] = []
    try:
        if path.suffix.lower() in (".ttc", ".otc"):
            fonts = TTCollection(path, lazy=True).fonts
        else:
            fonts = [TTFont(path, lazy=True)]
        for font in fonts:
            family = font["name"].getDebugName(1)
            subfamily = font["name"].getDebugName(2) or ""
            if family:
                faces.append((family, subfamily))
            font.close()
    except Exception:
        pass
    return faces


@lru_cache(maxsize=1)
def _font_index() -> dict[str, dict[str, Path]]:
    """Map lowercase family name -> {lowercase style: file path}."""
    index: dict[str, dict[str, Path]] = {}
    for directory in _font_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in _FONT_SUFFIXES:
                continue
            for family, subfamily in _faces_in_file(path):
                styles = index.setdefault(family.lower(), {})
                styles.setdefault(subfamily.lower(), path)
    return index


def parse_font_spec(spec: str) -> tuple[str, str | None]:
    """Split OpenSCAD's ``"Family:style=Style"`` syntax."""
    family, _, rest = spec.partition(":")
    style: str | None = None
    for part in rest.split(":"):
        key, _, value = part.partition("=")
        if key.strip().lower() == "style" and value.strip():
            style = value.strip()
    return family.strip(), style


def find_font_path(spec: str) -> str | None:
    """Resolve a font spec to a file path, or None if no family matches."""
    family, style = parse_font_spec(spec)
    styles = _font_index().get(family.lower())
    if not styles:
        return None
    if style is not None:
        path = styles.get(style.lower())
        return str(path) if path is not None else None
    for preferred in _DEFAULT_STYLES:
        if preferred in styles:
            return str(styles[preferred])
    return str(next(iter(styles.values())))
