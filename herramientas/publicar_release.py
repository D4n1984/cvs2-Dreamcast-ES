"""Publish a built prerelease to this project's GitHub repository.

Uses the existing Git credential helper in memory. Never writes or prints its
credential. The reviewed commit must already be pushed to origin/main.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "D4n1984/cvs2-Dreamcast-ES"


def credential():
    process = subprocess.run(["git", "credential", "fill"], cwd=ROOT,
                             input="protocol=https\nhost=github.com\n\n", text=True, capture_output=True,
                             env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}, check=True)
    values = dict(line.split("=", 1) for line in process.stdout.splitlines() if "=" in line)
    if not values.get("password"):
        raise RuntimeError("No GitHub credential is available from the Git helper")
    return values["password"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    folder = ROOT / "dist" / args.version
    notes = ROOT / "docs" / f"RELEASE-{args.version}.md"
    allowed = [f"Capcom_vs_SNK_2_Dreamcast_ES_{args.version}.dcp", f"CvS2_Dreamcast_ES_{args.version}.zip", "LEEME.txt", "SHA256SUMS.txt", "verificacion.json"]
    assets = [folder / name for name in allowed]
    if any(not path.is_file() for path in [notes, *assets]):
        raise ValueError("Build all release artifacts and notes before publishing")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    remote = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/main"], cwd=ROOT, text=True).split()[0]
    if remote != commit:
        raise ValueError("origin/main must match the reviewed local commit before publishing")
    token = credential()

    def request(url, method="GET", value=None, binary=None, content_type="application/json"):
        data = binary if binary is not None else (json.dumps(value).encode("utf-8") if value is not None else None)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "cvs2-Dreamcast-ES-release", "Content-Type": content_type}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            details = json.loads(error.read())
            raise RuntimeError(f"GitHub HTTP {error.code}: {details.get('message', 'request failed')}") from None

    base = f"https://api.github.com/repos/{REPOSITORY}"
    release = request(f"{base}/releases", method="POST", value={
        "tag_name": args.version, "target_commitish": commit, "name": f"CvS2 Dreamcast ES {args.version}",
        "body": notes.read_text(encoding="utf-8"), "draft": False, "prerelease": True,
    })
    upload = release["upload_url"].split("{")[0]
    for path in assets:
        result = request(upload + "?name=" + urllib.parse.quote(path.name), method="POST", binary=path.read_bytes(), content_type="application/octet-stream")
        print(f"Uploaded {result['name']} ({result['size']} bytes)")
    print(release["html_url"])


if __name__ == "__main__":
    main()
