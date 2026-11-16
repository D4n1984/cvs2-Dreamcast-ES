"""Insert rebuilt resources into a separate copy of the English v1.2 GDI."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from disco import Disc, checksums
from fuente_es import encode_spanish

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", action="store_true", help="replace an initial system message with a glyph diagnostic")
    args = parser.parse_args()
    baseline = ROOT / "build/ingles"
    source = ROOT / "build/es"
    folder = ROOT / "build" / ("prueba-glifos" if args.proof else "es-disc")
    folder.mkdir(parents=True, exist_ok=True)
    track = folder / "track03.bin"
    shutil.copyfile(baseline / "track03.bin", track)
    for name in ("track01.bin", "track02.bin"):
        shutil.copyfile(baseline / name, folder / name)
    replacements = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file() and p.suffix.upper() in (".BIN", ".HTML")}
    if args.proof:
        exe = bytearray(replacements["1ST_READ.BIN"])
        position = 0x185FD4
        end = exe.index(0, position)
        text = encode_spanish("¡ÁÉÍÓÚ ÜÑ áéíóú üñ! ¿Qué tal?")
        if len(text) > end - position:
            raise ValueError("Diagnostic does not fit")
        exe[position:end + 1] = text + bytes(end + 1 - position - len(text))
        replacements["1ST_READ.BIN"] = bytes(exe)
    report = []
    with Disc(track, writable=True) as disc:
        for name, payload in replacements.items():
            entry = disc.entries[name]
            old_lba = entry.lba
            lba = disc.replace(name, payload)
            report.append({"path": name, "bytes": len(payload), "old_lba": old_lba, "lba": lba, "sha256": hashlib.sha256(payload).hexdigest()})
    with Disc(track) as disc:
        for name, payload in replacements.items():
            if disc.read_file(name) != payload:
                raise ValueError(f"Resource readback failed: {name}")
            entry = disc.entries[name]
            for offset in range((entry.size + 2047) // 2048):
                raw = disc.raw_sector(entry.lba + offset)
                if checksums(raw) != raw:
                    raise ValueError(f"Invalid sector parity: {name}")
    (folder / "cvs2-es.gdi").write_text("3\n1 0 4 2352 track01.bin 0\n2 450 0 2352 track02.bin 352800\n3 45000 4 2352 track03.bin 0\n", encoding="ascii")
    (folder / "informe-insercion.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Inserted and verified {len(report)} resources in {folder}")


if __name__ == "__main__":
    main()
