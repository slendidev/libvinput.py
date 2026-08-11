#!/usr/bin/env python3
"""Download the libvinput shared libraries from a libvinput GitHub release and
place them in ``vinput/lib`` as the ``*.dat`` files the binding loads.

The libvinput release publishes one archive per platform (see
libvinput/.github/workflows/release.yml), e.g.::

    libvinput-v1.3.0-linux-x86_64.tar.gz     -> lib/libvinput.so
    libvinput-v1.3.0-macos-universal.tar.gz  -> lib/libvinput.dylib
    libvinput-v1.3.0-windows-x86_64.zip      -> lib/libvinput.dll

This script resolves a release (the latest by default, or ``LIBVINPUT_TAG``),
downloads each archive, extracts the shared library, and writes it to
``vinput/lib/<name>.dat``. The resolved version (tag without a leading ``v``) is
printed and, when running in GitHub Actions, written to ``$GITHUB_OUTPUT`` as
``version=<x.y.z>`` so a workflow can sync the package version.

Only the standard library is used so this runs in CI without dependencies.
"""

import io
import json
import os
import sys
import tarfile
import urllib.request
import zipfile

# Repository that publishes the libvinput binaries. Override with LIBVINPUT_REPO.
REPO = os.environ.get("LIBVINPUT_REPO", "slendidev/libvinput")
# Specific release tag to fetch (e.g. "v1.3.0"). Defaults to the latest release.
TAG = os.environ.get("LIBVINPUT_TAG", "").strip()

SAVE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "vinput", "lib")

# Map a substring found in the release asset name -> (library filename, output .dat)
PLATFORMS = [
    ("linux", "libvinput.so", "libvinput.so.dat"),
    ("macos", "libvinput.dylib", "libvinput.dylib.dat"),
    ("windows", "libvinput.dll", "libvinput.dll.dat"),
]


def _api_get(url: str) -> dict:
    """GET a GitHub API URL as JSON, using GITHUB_TOKEN if available."""
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "libvinput.py-update-binaries",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "libvinput.py-update-binaries"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _extract_member(data: bytes, asset_name: str, library: str) -> bytes:
    """Return the bytes of ``library`` from a downloaded archive."""
    if asset_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.replace("\\", "/").endswith("/" + library) or name == library:
                    return zf.read(name)
    else:  # assume a (gzipped) tarball
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for member in tf.getmembers():
                if member.isfile() and os.path.basename(member.name) == library:
                    f = tf.extractfile(member)
                    if f is not None:
                        return f.read()
    raise RuntimeError(f"Could not find {library} inside asset {asset_name}")


def main() -> int:
    if TAG:
        release = _api_get(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}")
    else:
        release = _api_get(f"https://api.github.com/repos/{REPO}/releases/latest")

    tag = release["tag_name"]
    version = tag[1:] if tag.startswith("v") else tag
    assets = release.get("assets", [])
    print(f"libvinput release {tag} ({len(assets)} assets)")

    os.makedirs(SAVE_DIR, exist_ok=True)

    updated = 0
    for needle, library, out_name in PLATFORMS:
        asset = next(
            (a for a in assets if needle in a["name"].lower()
             and a["name"].lower().endswith((".tar.gz", ".tgz", ".zip"))),
            None,
        )
        if asset is None:
            print(f"  WARNING: no asset matching '{needle}', skipping {out_name}")
            continue

        print(f"  {asset['name']} -> {out_name}")
        data = _download(asset["browser_download_url"])
        lib_bytes = _extract_member(data, asset["name"], library)

        out_path = os.path.join(SAVE_DIR, out_name)
        with open(out_path, "wb") as f:
            f.write(lib_bytes)
        updated += 1

    if updated == 0:
        print("ERROR: no binaries were updated", file=sys.stderr)
        return 1

    # Expose the resolved version to a GitHub Actions workflow.
    print(f"version={version}")
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"version={version}\n")
            f.write(f"tag={tag}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
