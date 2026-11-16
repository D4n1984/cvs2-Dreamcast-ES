"""Package a Spanish DCP against original Japanese resources, never a ROM."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from disco import Disc
from preparar_base import DCP_SHA256, ORIGINAL_MD5, PREFIX, digest

ROOT = Path(__file__).resolve().parents[1]


def add_entry(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compresslevel=9)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xdelta", required=True, type=Path)
    parser.add_argument("--version", default="v0.1.0-alpha.1")
    parser.add_argument("--original-track3", type=Path)
    args = parser.parse_args()
    original = args.original_track3 or next((ROOT / "roms/original").glob("*Track 3*.bin"))
    upstream = ROOT / "parches" / f"{PREFIX}.dcp"
    if digest(original, "md5") != ORIGINAL_MD5 or digest(upstream, "sha256") != DCP_SHA256:
        raise ValueError("Original image or upstream patch checksum mismatch")
    work = ROOT / "build/dcp"
    work.mkdir(parents=True, exist_ok=True)
    built = ROOT / "build/es"
    replacements = {}
    verified = []
    with zipfile.ZipFile(upstream) as archive:
        entries = {item.filename.replace("\\", "/"): archive.read(item) for item in archive.infolist() if not item.is_dir()}
    with Disc(original) as disc:
        for path in sorted(built.rglob("*")):
            if not path.is_file() or path.suffix.upper() not in (".BIN", ".HTML"):
                continue
            name = path.relative_to(built).as_posix()
            data = path.read_bytes()
            if name in disc.entries:
                source = work / "original" / name
                delta = work / "deltas" / f"{name}.xdelta"
                decoded = work / "verificacion" / name
                for folder in (source.parent, delta.parent, decoded.parent):
                    folder.mkdir(parents=True, exist_ok=True)
                source.write_bytes(disc.read_file(name))
                subprocess.run([str(args.xdelta), "-f", "-e", "-s", str(source), str(path), str(delta)], check=True)
                subprocess.run([str(args.xdelta), "-f", "-d", "-s", str(source), str(delta), str(decoded)], check=True)
                if decoded.read_bytes() != data:
                    raise ValueError(f"Delta roundtrip failed: {name}")
                entries.pop(name, None)
                entries[f"{name}.xdelta"] = delta.read_bytes()
            else:
                entries.pop(f"{name}.xdelta", None)
                entries[name] = data
            verified.append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})
    dist = ROOT / "dist" / args.version
    dist.mkdir(parents=True, exist_ok=True)
    patch = dist / f"Capcom_vs_SNK_2_Dreamcast_ES_{args.version}.dcp"
    with zipfile.ZipFile(patch, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            add_entry(archive, name, data)
    with zipfile.ZipFile(patch) as archive:
        if archive.testzip() is not None:
            raise ValueError("DCP ZIP integrity check failed")
    report = {"version": args.version, "original_track3_md5": ORIGINAL_MD5, "upstream_dcp_sha256": DCP_SHA256,
              "patch_sha256": digest(patch, "sha256"), "patch_bytes": patch.stat().st_size,
              "new_resources_verified": verified, "dcp_entries": len(entries), "status": "prerelease"}
    (dist / "verificacion.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    release_notes = ROOT / "docs" / f"RELEASE-{args.version}.md"
    readme = dist / "LEEME.txt"
    readme.write_text(release_notes.read_text(encoding="utf-8"), encoding="utf-8")
    sums = dist / "SHA256SUMS.txt"
    sums.write_text("\n".join(f"{digest(p, 'sha256')}  {p.name}" for p in [patch, readme, dist / "verificacion.json"]) + "\n", encoding="ascii")
    bundle = dist / f"CvS2_Dreamcast_ES_{args.version}.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in [patch, readme, dist / "verificacion.json", sums]:
            add_entry(archive, path.name, path.read_bytes())
    print(f"DCP verified: {patch.name} ({patch.stat().st_size} bytes)")
    print(f"Release bundle: {bundle}")


if __name__ == "__main__":
    main()
