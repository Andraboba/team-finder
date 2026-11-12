"""Генерация аватара по умолчанию: первая буква имени на мягком однотонном фоне."""
import random
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

AVATAR_SIZE = 256

# Приглушённые пастельные цвета: буква на них хорошо читается,
# а сам фон не режет глаз.
BACKGROUND_COLORS = (
    (244, 199, 195),
    (248, 215, 170),
    (250, 236, 170),
    (200, 230, 201),
    (178, 223, 219),
    (179, 229, 252),
    (197, 202, 233),
    (225, 190, 231),
    (215, 204, 200),
    (207, 216, 220),
)
TEXT_COLOR = (55, 55, 55)

# Шрифты с поддержкой кириллицы, которые ищутся по порядку.
FONT_CANDIDATES = (
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def _load_font(size):
    candidates = []
    if getattr(settings, "AVATAR_FONT_PATH", ""):
        candidates.append(settings.AVATAR_FONT_PATH)
    candidates.extend(FONT_CANDIDATES)
    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Встроенный шрифт Pillow (кириллицу может не поддерживать).
    return ImageFont.load_default(size=size)


def generate_avatar(name):
    """Возвращает ContentFile с PNG-аватаром для переданного имени."""
    letter = (name or "?").strip()[:1].upper() or "?"
    background = random.choice(BACKGROUND_COLORS)
    image = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), background)
    draw = ImageDraw.Draw(image)
    font = _load_font(int(AVATAR_SIZE * 0.5))
    draw.text(
        (AVATAR_SIZE / 2, AVATAR_SIZE / 2),
        letter,
        fill=TEXT_COLOR,
        font=font,
        anchor="mm",
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue())
