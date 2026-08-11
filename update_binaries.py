#!/usr/bin/env python3

import io
import json
import os
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/slendidev/libvinput/releases/latest"
SAVE_DIR = Path(__file__).resolve().parent / "vinput" / "lib"
TARGETS = {
    "linux-x86_64.tar.gz": "libvinput.so",
    "macos-universal.tar.gz": "libvinput.dylib",
    "windows-x86_64.zip": "libvinput.dll",
}


def download(url, timeout):
    request = Request(url)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def find_asset(assets, suffix):
    matches = [asset for asset in assets if asset["name"].endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one release asset ending in {suffix!r}, found {len(matches)}"
        )
    return matches[0]


def read_binary(archive_name, archive_data, binary_name):
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            matches = [
                name
                for name in archive.namelist()
                if PurePosixPath(name).name == binary_name
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Expected one {binary_name!r} in {archive_name}, found {len(matches)}"
                )
            return archive.read(matches[0])

    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as archive:
        matches = [
            member
            for member in archive.getmembers()
            if member.isfile() and PurePosixPath(member.name).name == binary_name
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one {binary_name!r} in {archive_name}, found {len(matches)}"
            )
        extracted = archive.extractfile(matches[0])
        if extracted is None:
            raise RuntimeError(f"Could not read {binary_name!r} from {archive_name}")
        return extracted.read()


def save_binary(binary_name, data):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    destination = SAVE_DIR / f"{binary_name}.dat"
    with tempfile.NamedTemporaryFile(dir=SAVE_DIR, delete=False) as temporary:
        temporary.write(data)
        temporary_path = temporary.name
    os.replace(temporary_path, destination)


def main():
    print("Downloading libvinput libraries")
    release = json.loads(download(RELEASE_URL, timeout=30))
    assets = release["assets"]

    binaries = {}
    for suffix, binary_name in TARGETS.items():
        asset = find_asset(assets, suffix)
        print(f"Downloading {asset['name']}")
        archive_data = download(asset["browser_download_url"], timeout=60)
        binaries[binary_name] = read_binary(
            asset["name"], archive_data, binary_name
        )

    for binary_name, data in binaries.items():
        save_binary(binary_name, data)
        print(f"Updated {binary_name} successfully.")


if __name__ == "__main__":
    main()
