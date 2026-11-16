"""Validate local inputs, reconstruct English v1.2, and extract build assets."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

from disco import Disc

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "Capcom.vs.SNK.2.-.Millionaire.Fighting.2001.English.v1.2"
GDI_SHA256 = "80b8b70b28cdf9963d5e403bf0a9c567d43ed97be2d2dc41df50094f652198a9"
DCP_SHA256 = "aa4253537e805b8cf465c9312aee6788c51c6d655457b8c664bb928c7dfd3155"
ORIGINAL_MD5 = "ff8e199324fc11d4f638e5c99315cdbb"


def digest(path, algorithm):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xdelta", required=True, type=Path)
    parser.add_argument("--original-track3", type=Path)
    args = parser.parse_args()
    original = args.original_track3
    if original is None:
        matches = list((ROOT / "roms/original").glob("*Track 3*.bin"))
        if len(matches) != 1:
            raise ValueError("Specify --original-track3 with the unmodified Japanese data track")
        original = matches[0]
    patch = ROOT / "parches" / f"{PREFIX}.GDI.xdelta"
    dcp = ROOT / "parches" / f"{PREFIX}.dcp"
    for path, algorithm, expected in [(original, "md5", ORIGINAL_MD5), (patch, "sha256", GDI_SHA256), (dcp, "sha256", DCP_SHA256)]:
        if digest(path, algorithm) != expected:
            raise ValueError(f"Unexpected input checksum: {path.name}")
    baseline = ROOT / "build/ingles"
    baseline.mkdir(parents=True, exist_ok=True)
    track = baseline / "track03.bin"
    # The digest below is the output of the currently published official xdelta;
    # the upstream README's patched-track MD5 describes a different image build.
    current_md5 = "fffa34923396957f21825aba88f9fe6c"
    if not track.exists() or digest(track, "md5") != current_md5:
        subprocess.run([str(args.xdelta), "-f", "-d", "-s", str(original), str(patch), str(track)], check=True)
    if digest(track, "md5") != current_md5:
        raise ValueError("Unexpected official English output")
    for number in (1, 2):
        matches = list(original.parent.glob(f"*Track {number}*.bin"))
        if len(matches) != 1:
            raise ValueError(f"Expected Redump Track {number} next to the data track")
        shutil.copyfile(matches[0], baseline / f"track0{number}.bin")
    (baseline / "cvs2-ingles.gdi").write_text("3\n1 0 4 2352 track01.bin 0\n2 450 0 2352 track02.bin 352800\n3 45000 4 2352 track03.bin 0\n", encoding="ascii")
    with Disc(original) as disc:
        target = ROOT / "analisis/original/S20RM04.BIN"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(disc.read_file("S20RM04.BIN"))
    with Disc(track) as disc:
        for name, entry in disc.entries.items():
            if name in {"1ST_READ.BIN", "MESJ_WIN.BIN", "MESE_WIN.BIN", "MESE_DM.BIN"} or (name.startswith("DPWWW/") and name.endswith(".HTML")):
                target = ROOT / "analisis/ingles" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(disc.read_file(name))
    print("Original and official patches verified; English build assets prepared")


if __name__ == "__main__":
    main()
