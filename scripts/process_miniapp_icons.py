from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
ASSETS = ROOT / "apps/miniapp/src/assets/icons"
TABBAR = ROOT / "apps/miniapp/src/assets/tabbar"

SOURCES = {
    "mic": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_20 (1).png",
    "upload": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_21 (2).png",
    "image": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_21 (3).png",
    "ai": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_22 (4).png",
    "send": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_22 (5).png",
    "mic_circle": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_23 (6).png",
    "record": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_23 (7).png",
    "me": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_24 (8).png",
    "camera": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_25 (9).png",
    "todos": DOWNLOADS / "ChatGPT Image 2026年7月18日 12_00_25 (10).png",
}

TODO_SOURCES = [
    DOWNLOADS / "ChatGPT Image 2026年7月18日 14_13_05 (1).png",
    DOWNLOADS / "ChatGPT Image 2026年7月18日 14_13_05 (2).png",
    DOWNLOADS / "ChatGPT Image 2026年7月18日 14_13_06 (3).png",
    DOWNLOADS / "ChatGPT Image 2026年7月18日 14_13_06 (4).png",
    DOWNLOADS / "ChatGPT Image 2026年7月18日 14_13_07 (5).png",
]

ME_MENU_SOURCES = {
    "favorite": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_35 (1).png",
    "recent": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_35 (2).png",
    "ai-preference": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_36 (3).png",
    "notification": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_38 (4).png",
    "help": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_38 (5).png",
    "about": DOWNLOADS / "ChatGPT Image 2026年7月18日 14_14_39 (6).png",
}


def isolate_icon(path: Path, size: int = 192) -> Image.Image:
    source = Image.open(path).convert("RGB")
    pixels = source.load()
    alpha = Image.new("L", source.size, 0)
    alpha_pixels = alpha.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue = pixels[x, y]
            darkest, lightest = min(red, green, blue), max(red, green, blue)
            saturation = lightest - darkest
            darkness = 232 - (red + green + blue) / 3
            strength = max(saturation * 2.5, darkness * 2.2)
            alpha_pixels[x, y] = max(0, min(255, round((strength - 8) * 2.2)))
    bbox = alpha.getbbox()
    if not bbox:
        raise RuntimeError(f"No icon content found in {path}")
    left, top, right, bottom = bbox
    padding = max(right - left, bottom - top) // 12
    crop_box = (
        max(0, left - padding),
        max(0, top - padding),
        min(source.width, right + padding),
        min(source.height, bottom + padding),
    )
    rgba = source.convert("RGBA")
    rgba.putalpha(alpha)
    cropped = rgba.crop(crop_box)
    cropped.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    canvas.alpha_composite(cropped, ((size - cropped.width) // 2, (size - cropped.height) // 2))
    return canvas


def recolor(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    result = Image.new("RGBA", image.size, (*color, 0))
    # Remove the soft baked-in shadow from the supplied tab icons while
    # preserving a narrow antialiased edge on the actual glyph.
    alpha = image.getchannel("A").point(
        lambda value: 0 if value < 92 else min(255, round((value - 92) * 255 / 163))
    )
    result.putalpha(alpha)
    return result


def normalize_glyph(image: Image.Image, visual_size: int = 88) -> Image.Image:
    """Give differently shaped tab glyphs the same visible outer dimension."""
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image
    glyph = image.crop(bbox)
    glyph.thumbnail((visual_size, visual_size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    canvas.alpha_composite(glyph, ((image.width - glyph.width) // 2, (image.height - glyph.height) // 2))
    return canvas


ASSETS.mkdir(parents=True, exist_ok=True)
for name in ("mic", "upload", "image", "ai", "send", "mic_circle", "camera"):
    isolate_icon(SOURCES[name]).save(ASSETS / f"{name}.png", optimize=True)

for index, source in enumerate(TODO_SOURCES):
    isolate_icon(source).save(ASSETS / f"todo-{index}.png", optimize=True)

for name, source in ME_MENU_SOURCES.items():
    isolate_icon(source, size=128).save(ASSETS / f"menu-{name}.png", optimize=True)

tab_sources = {"record": "record", "todos": "todos", "me": "me"}
for tab_name, source_name in tab_sources.items():
    icon = isolate_icon(SOURCES[source_name], size=96)
    normalize_glyph(recolor(icon, (139, 150, 146))).save(TABBAR / f"{tab_name}.png", optimize=True)
    normalize_glyph(recolor(icon, (22, 155, 122))).save(TABBAR / f"{tab_name}-active.png", optimize=True)
