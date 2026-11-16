"""Rebuild Spanish message resources from the verified English v1.2 assets."""
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import struct

from fuente_es import encode_spanish, extend_font

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "analisis/ingles"
OUTPUT = ROOT / "build/es"
OUTPUT.mkdir(parents=True, exist_ok=True)


def catalog(name):
    with (ROOT / "traduccion" / name).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if any(not row["espanol"] for row in rows):
        raise ValueError(f"Incomplete translation: {name}")
    return rows


def message_parts(data, win):
    start = 5108 if win else 260
    end = struct.unpack_from("<I", data)[0] - (58784 if win else 2016)
    parts = []
    position = start
    while position < end:
        if data[position] == 0:
            position += 1
            continue
        stop = data.index(0, position, end)
        parts.append((position, data[position:stop]))
        position = stop + 1
    return start, end, parts


def rebuild_message(data, raw_strings, win):
    start, end, old = message_parts(data, win)
    if len(old) != len(raw_strings):
        raise ValueError("Mismatched physical string count")
    payload = bytearray()
    remap = {}
    for (offset, _), raw in zip(old, raw_strings, strict=True):
        remap[offset] = start + len(payload)
        if b"\0" in raw:
            raise ValueError("A translation contains an embedded terminator")
        payload += raw + b"\0"
        if not win:
            payload += bytes((-len(payload)) % 4)
    if win:
        payload += bytes((-len(payload)) % 4)
    difference = start + len(payload) - end
    prefix = bytearray(data[:start])
    for offset in ([0, 4] if win else [0]):
        pointer = struct.unpack_from("<I", data, offset)[0]
        struct.pack_into("<I", prefix, offset, pointer + difference)
    tail = bytearray(data[end:])
    if len(tail) % 4:
        raise ValueError("Unaligned pointer table")
    for offset in range(0, len(tail), 4):
        pointer = struct.unpack_from("<I", tail, offset)[0]
        if pointer in remap:
            replacement = remap[pointer]
        elif end <= pointer <= len(data):
            replacement = pointer + difference
        elif start <= pointer < end:
            raise ValueError(f"Unmapped pointer inside text: {pointer:#x}")
        else:
            replacement = pointer
        struct.pack_into("<I", tail, offset, replacement)
    return bytes(prefix + payload + tail)


def build_messages():
    victories = catalog("dialogos-victoria.csv")
    endings = catalog("finales.csv")
    result = {}
    for name in ("MESJ_WIN.BIN", "MESE_WIN.BIN", "MESE_DM.BIN"):
        data = (SOURCE / name).read_bytes()
        win = "WIN" in name
        _, _, old = message_parts(data, win)
        # A byte-identical no-op roundtrip checks alignment and pointer handling.
        if rebuild_message(data, [raw for _, raw in old], win) != data:
            raise ValueError(f"No-op roundtrip failed: {name}")
        rows = victories if win else endings
        strings = []
        for (_, raw), row in zip(old, rows, strict=True):
            if row["accion"].startswith("CONSERVAR_") or (win and row["archivo"] != name):
                strings.append(raw)
            else:
                text = encode_spanish(row["espanol"].strip())
                if win:
                    text += b" " * (len(raw) - len(raw.rstrip(b" ")))
                strings.append(text)
        built = rebuild_message(data, strings, win)
        maximum = 358400 if win else 19844
        if len(built) > maximum:
            raise ValueError(f"Message buffer limit exceeded: {name} {len(built)}/{maximum}")
        (OUTPUT / name).write_bytes(built)
        result[name] = {"bytes": len(built), "original_bytes": len(data), "buffer_limit": maximum, "roundtrip": True}
    return result


def build_descriptions():
    exe = bytearray((SOURCE / "1ST_READ.BIN").read_bytes())
    rows = catalog("descripciones-juego.csv")
    # The upstream patch relocates Command List from this Japanese data block
    # to 0x1A5260. Reuse only the abandoned original block, after verifying that
    # no executable pointer still addresses it. The active English list is intact.
    region_start, region_end = 1597992, 1597992 + 11354
    for position in range(0, len(exe) - 3, 4):
        pointer = struct.unpack_from("<I", exe, position)[0]
        if 0x8C010000 + region_start <= pointer < 0x8C010000 + region_end:
            raise ValueError(f"Abandoned command data is still referenced at {position:#x}")
    active_commands = bytes(exe[0x1A5260:0x1A5260 + 12032])
    cursor = region_start
    report = []
    for row in rows:
        payload = encode_spanish(row["espanol"].strip()) + b"\0"
        if cursor + len(payload) > region_end:
            raise ValueError("No abandoned command-list space for descriptions")
        old_offset = int(row["offset"], 16)
        old_pointer = struct.pack("<I", 0x8C010000 + old_offset)
        new_pointer = struct.pack("<I", 0x8C010000 + cursor)
        references = [match.start() for match in re.finditer(re.escape(old_pointer), exe)]
        if not references:
            raise ValueError(f"No description pointer found: {row['id']}")
        for position in references:
            exe[position:position + 4] = new_pointer
        exe[cursor:cursor + len(payload)] = payload
        report.append({"id": row["id"], "new_offset": hex(cursor), "references": references})
        cursor = (cursor + len(payload) + 3) & ~3
    if bytes(exe[0x1A5260:0x1A5260 + 12032]) != active_commands:
        raise ValueError("Active English Command List changed")
    return exe, report


def build_bonus():
    rows = catalog("bonus-mode.csv")
    pages = {}
    for row in rows:
        pages.setdefault(row["archivo"], []).append(row)
    changes = {}
    for name, expected in pages.items():
        source = (SOURCE / name).read_bytes().decode("shift_jis")
        sequence = 0
        in_head = False

        def substitute(match):
            nonlocal sequence, in_head
            raw = match.group()
            if raw.startswith("<!--"):
                return raw
            if raw.startswith("<"):
                if re.match(r"<head\b", raw, re.I):
                    in_head = True
                elif re.match(r"</head\b", raw, re.I):
                    in_head = False
                return raw
            if in_head:
                return raw
            text = re.sub(r"\s+", " ", html.unescape(raw)).strip()
            if not re.search(r"[A-Za-z0-9]", text):
                return raw
            row = expected[sequence]
            sequence += 1
            if text != row["ingles"]:
                raise ValueError(f"HTML segment drift: {row['id']}")
            if row["espanol"] == text:
                return raw
            escaped = html.escape(row["espanol"], quote=False).encode("ascii", "xmlcharrefreplace").decode("ascii")
            return re.match(r"\s*", raw).group() + escaped + re.search(r"\s*$", raw).group()

        updated = re.sub(r"<!--.*?-->|<[^>]+>|[^<]+", substitute, source, flags=re.S)
        if sequence != len(expected):
            raise ValueError(f"Wrong HTML segment count: {name}")
        updated = re.sub(r"charset=Shift_JIS", "charset=iso-8859-1", updated, flags=re.I)
        destination = OUTPUT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(updated.encode("ascii"))
        changes[name] = {"segments": sequence, "bytes": destination.stat().st_size}
    return changes


def main():
    messages = build_messages()
    extend_font(ROOT / "analisis/original/S20RM04.BIN", OUTPUT / "S20RM04.BIN", ROOT / "analisis/fuentes/es-glifos.png")
    exe, descriptions = build_descriptions()
    # Update the game's independent file-size allocation table. Preserve larger
    # upstream allocations, especially the message buffers used by both banks.
    table_start = 0x182DF4
    updated = []
    for index in range(623):
        offset = table_start + index * 20
        allocation = struct.unpack_from("<I", exe, offset)[0]
        name = bytes(exe[offset + 4:offset + 20]).split(b"\0", 1)[0].decode("ascii")
        resource = OUTPUT / name
        if name and resource.is_file() and resource.stat().st_size > allocation:
            size = resource.stat().st_size
            struct.pack_into("<I", exe, offset, size)
            updated.append({"file": name, "old": allocation, "new": size})
    (OUTPUT / "1ST_READ.BIN").write_bytes(exe)
    bonus = build_bonus()
    report = {"messages": messages, "descriptions": descriptions, "bonus": bonus, "allocation_changes": updated,
              "note": "Build resources only. In-game verification remains required."}
    (OUTPUT / "informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(messages, indent=2))
    print(f"Built {len(descriptions)} description lines and {len(bonus)} HTML pages")


if __name__ == "__main__":
    main()
