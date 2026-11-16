"""Validate editable TSV translations and assemble reviewable CSV catalogs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_tsv(paths):
    translated = {}
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            columns = line.split("\t")
            if len(columns) != 2 or not columns[1].strip():
                raise ValueError(f"{path.name}:{number}: expected ID and nonempty Spanish text")
            key, value = columns
            if key in translated:
                raise ValueError(f"Duplicate translation ID: {key}")
            translated[key] = value
    return translated


def integrate(source, paths, output, english_column="ingles"):
    translations = read_tsv(paths)
    with (ROOT / "analisis" / source).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    expected = {row["id"] for row in rows}
    extra = translations.keys() - expected
    if extra:
        raise ValueError(f"Unexpected IDs in {output}: {sorted(extra)}")
    pending = []
    wide = []
    for row in rows:
        key = row["id"]
        value = translations.get(key, "")
        row["espanol"] = value
        if not value:
            pending.append(key)
        elif row["accion"].startswith("CONSERVAR_"):
            if value.strip() != row[english_column].strip():
                raise ValueError(f"Protected entry changed: {key}")
            row["espanol"] = row[english_column]  # preserve original padding too
        if len(value) > 50 and source != "bonus-mode.csv":
            wide.append({"id": key, "characters": len(value)})
    destination = ROOT / "traduccion" / output
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "total": len(rows),
        "translated": len(rows) - len(pending),
        "pending_ids": pending,
        "over_50_characters": wide,
        "source_sha256": hashlib.sha256((ROOT / "analisis" / source).read_bytes()).hexdigest(),
    }


def main():
    folder = ROOT / "traduccion"
    catalogs = [
        ("dialogos-victoria.csv", sorted(folder.glob("win-*.tsv")), "dialogos-victoria.csv", "ingles"),
        ("finales.csv", [folder / "finales.tsv"], "finales.csv", "ingles_parche"),
        ("descripciones-juego.csv", [folder / "descripciones.tsv"], "descripciones-juego.csv", "ingles"),
    ]
    if (folder / "bonus.tsv").exists():
        catalogs.append(("bonus-mode.csv", [folder / "bonus.tsv"], "bonus-mode.csv", "ingles"))
    status = {output: integrate(source, paths, output, english) for source, paths, output, english in catalogs}
    (folder / "estado.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, result in status.items():
        print(f"{name}: {result['translated']}/{result['total']}; {len(result['over_50_characters'])} lines over 50 characters")


if __name__ == "__main__":
    main()
