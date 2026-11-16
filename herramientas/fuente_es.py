"""Extend CvS2's narrow S20RM04 font using its existing halfwidth-kana path.

Only sixteen glyph bitmap payloads change. Original headers and file length stay
identical. A6..B5 are single-byte input codes; no executable patch is required by
the direct dialogue parser at 0x8c06894c. Other text paths require separate tests.
"""
import argparse
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LETTERS = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
ENCODING = {char: bytes([0xA6 + index]) for index, char in enumerate(LETTERS)}
BASE_LETTERS = "aeiouunAEIOUUN?!"
RECORD_SIZE = 116
HEADER_SIZE = 16


def read_glyph(data, index):
    raw = data[index * RECORD_SIZE + HEADER_SIZE:(index + 1) * RECORD_SIZE]
    image = Image.new("L", (20, 20))
    image.putdata([((raw[p // 4] >> (6 - p % 4 * 2)) & 3) * 85 for p in range(400)])
    return image


def pack_glyph(image):
    pixels = [min(3, (v + 42) // 85) for v in image.get_flattened_data()]
    return bytes((pixels[p] << 6) | (pixels[p + 1] << 4) | (pixels[p + 2] << 2) | pixels[p + 3] for p in range(0, 400, 4))


def latin_index(letter):
    return (0x29 - 0x21) * 94 + ord(letter) - 0x21


def encode_spanish(text):
    # Normalize typography, never discard Spanish accents or punctuation.
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "«": '"', "»": '"', "—": "-", "–": "-", "\u00a0": " "}))
    return b"".join(ENCODING[char] if char in ENCODING else char.encode("shift_jis", errors="strict") for char in text)


def extend_font(source, destination, preview):
    original = source.read_bytes()
    if len(original) != RECORD_SIZE * 7808:
        raise ValueError("Unexpected S20RM04 font structure")
    output = bytearray(original)
    sheet = Image.new("RGB", (len(LETTERS) * 60, 140), (28, 28, 28))
    labels = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    mapping = {}
    for number, (letter, base) in enumerate(zip(LETTERS, BASE_LETTERS, strict=True)):
        image = read_glyph(original, latin_index(base))
        narrow = image.crop((0, 0, 10, 20))
        if letter in "¿¡":
            narrow = narrow.transpose(Image.Transpose.ROTATE_180)
        else:
            if base.isupper():
                box = narrow.getbbox()
                body = narrow.crop((0, box[1], 10, box[3]))
                height = min(15, body.height)
                body = body.resize((10, height), Image.Resampling.LANCZOS)
                narrow = Image.new("L", (10, 20))
                narrow.paste(body, (0, 19 - height))
            draw = ImageDraw.Draw(narrow)
            if letter == "í":
                draw.rectangle((0, 0, 9, 4), fill=0)  # replace i's original dot
            if letter in "üÜ":
                draw.rectangle((2, 1, 3, 2), fill=255)
                draw.rectangle((7, 1, 8, 2), fill=255)
            elif letter in "ñÑ":
                for x, y, value in [(2, 2, 170), (3, 1, 255), (4, 1, 170), (5, 2, 255), (6, 2, 170), (7, 1, 255)]:
                    draw.point((x, y), fill=value)
            else:
                draw.line((4, 2, 6, 0), fill=255, width=1)
                draw.line((5, 2, 7, 0), fill=170, width=1)
        image = Image.new("L", (20, 20))
        image.paste(narrow, (0, 0))
        # A6 => internal SJIS85A4 => JIS2A26; consecutive entries follow.
        index = (0x2A - 0x21) * 94 + (0x26 - 0x21) + number
        start = index * RECORD_SIZE
        jis = struct.unpack_from("<H", original, start)[0]
        if jis != 0x2A26 + number:
            raise ValueError(f"Unexpected glyph at record {index}: {jis:#x}")
        output[start + HEADER_SIZE:start + RECORD_SIZE] = pack_glyph(image)
        sheet.paste(narrow.resize((50, 100), Image.Resampling.NEAREST), (number * 60, 30))
        labels.text((number * 60, 3), letter, font=label_font, fill="white")
        mapping[letter] = {"input_hex": f"{0xA6 + number:02X}", "jis": f"{jis:04X}", "record": index}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    preview.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(preview)
    preview.with_suffix(".json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return mapping


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "analisis/original/S20RM04.BIN")
    parser.add_argument("--output", type=Path, default=ROOT / "build/es/S20RM04.BIN")
    parser.add_argument("--preview", type=Path, default=ROOT / "analisis/fuentes/es-glifos.png")
    args = parser.parse_args()
    extend_font(args.source, args.output, args.preview)
    print(f"Wrote {args.output}; 16 narrow glyphs; size preserved")
