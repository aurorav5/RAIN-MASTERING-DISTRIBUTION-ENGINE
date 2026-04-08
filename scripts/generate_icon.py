"""Generate RAIN app icon (R∞N logo) as .ico for the desktop launcher."""
from PIL import Image, ImageDraw, ImageFont
import os

SIZES = [16, 32, 48, 64, 128, 256]
OUT = os.path.join(os.path.dirname(__file__), "..", "rain.ico")

def draw_icon(size: int) -> Image.Image:
    """Draw the RAIN icon at a given size: dark emerald circle with teal 'R' glyph."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle — dark emerald
    pad = max(1, size // 16)
    draw.ellipse([pad, pad, size - pad, size - pad], fill=(10, 15, 10, 255))

    # Border ring — teal accent
    draw.ellipse([pad, pad, size - pad, size - pad], outline=(0, 212, 170, 255), width=max(1, size // 24))

    # "R" letter — teal
    font_size = int(size * 0.55)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    text = "R"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=(0, 212, 170, 255), font=font)

    return img

if __name__ == "__main__":
    icons = [draw_icon(s) for s in SIZES]
    icons[0].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=icons[1:])
    print(f"Icon saved to {os.path.abspath(OUT)}")
