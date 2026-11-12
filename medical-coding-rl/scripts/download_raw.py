#!/usr/bin/env python3
"""Download the raw CMS source files (data/raw/) from Google Drive and unpack them.

data/raw/ is not in git (326 MB of CMS zips and PDFs). It is only needed to rebuild the reference
bundle with scripts/build_reference.py; running the benchmarks does not need it.

    uv run --with gdown python scripts/download_raw.py            # download + unzip into data/raw/
    uv run --with gdown python scripts/download_raw.py --force    # re-download, replace data/raw/
    uv run --with gdown python scripts/download_raw.py --keep-zip # keep data/raw.zip afterwards

If the download fails, open RAW_URL in a browser, save the file as data/raw.zip and run this
script again: it uses an existing data/raw.zip instead of downloading.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

FILE_ID = "1iPkcG5_32G3CTYEuiZi-OCIYVhgAJ1Uw"
RAW_URL = f"https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
ZIP_PATH = DATA_DIR / "raw.zip"


def manual_help() -> str:
    return (
        "\nManual download:\n"
        f"  1. Open {RAW_URL}\n"
        f"  2. Save the file as {ZIP_PATH}\n"
        "  3. Run this script again (it will unzip the file you saved)\n"
    )


def download() -> None:
    try:
        import gdown
    except ImportError:
        sys.exit("gdown is not installed. Run: uv run --with gdown python scripts/download_raw.py"
                 + manual_help())
    print(f"Downloading raw.zip from Google Drive -> {ZIP_PATH}")
    try:
        out = gdown.download(id=FILE_ID, output=str(ZIP_PATH), quiet=False)
    except Exception as exc:  # gdown raises several exception types (quota, permission, network)
        out = None
        print(f"gdown failed: {exc}", file=sys.stderr)
    if not out or not ZIP_PATH.exists():
        ZIP_PATH.unlink(missing_ok=True)
        sys.exit("Download failed." + manual_help())


def extract() -> None:
    if not zipfile.is_zipfile(ZIP_PATH):
        sys.exit(f"{ZIP_PATH} is not a valid zip file (Google Drive may have returned an HTML "
                 "page instead). Delete it and try again." + manual_help())

    with zipfile.ZipFile(ZIP_PATH) as zf:
        members = [m for m in zf.infolist()
                   if not m.filename.startswith("__MACOSX/") and Path(m.filename).name != ".DS_Store"]
        names = [m.filename for m in members]
        # The zip holds the raw/ folder itself; also accept a zip of raw/'s contents.
        target = DATA_DIR if names and all(n.startswith("raw/") for n in names) else RAW_DIR
        target.mkdir(parents=True, exist_ok=True)
        root = target.resolve()
        for m in members:
            dest = (target / m.filename).resolve()
            if not dest.is_relative_to(root):
                sys.exit(f"Refusing to extract {m.filename!r}: path escapes {target}")
        print(f"Extracting {len(members)} entries -> {RAW_DIR}")
        zf.extractall(target, members=members)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="replace an existing data/raw/")
    ap.add_argument("--keep-zip", action="store_true", help="keep data/raw.zip after extracting")
    args = ap.parse_args()

    if RAW_DIR.is_dir() and any(RAW_DIR.iterdir()) and not args.force:
        print(f"{RAW_DIR} already exists; nothing to do (use --force to replace it).")
        return
    if args.force and RAW_DIR.exists():
        shutil.rmtree(RAW_DIR)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists() and zipfile.is_zipfile(ZIP_PATH):
        print(f"Using existing {ZIP_PATH}")
    else:
        ZIP_PATH.unlink(missing_ok=True)
        download()

    extract()
    if not args.keep_zip:
        ZIP_PATH.unlink()
    print(f"Done: {RAW_DIR}")


if __name__ == "__main__":
    main()
