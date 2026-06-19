"""Download and safely extract the UCI Online Retail II dataset."""

from __future__ import annotations

import argparse
import shutil
import urllib.request
import zipfile
from pathlib import Path


DATASET_URL = (
    "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
)
WORKBOOK_NAME = "online_retail_II.xlsx"


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if destination not in target.parents and target != destination:
                raise ValueError(f"Unsafe archive member: {member.filename}")
        archive.extractall(destination)


def download_dataset(output_directory: str | Path) -> Path:
    output_directory = Path(output_directory).resolve()
    archive_path = output_directory / "online_retail_ii.zip"
    extract_directory = output_directory / "online_retail_ii"
    workbook_path = extract_directory / WORKBOOK_NAME

    if workbook_path.is_file():
        return workbook_path

    output_directory.mkdir(parents=True, exist_ok=True)
    if not archive_path.is_file() or not zipfile.is_zipfile(archive_path):
        temporary_path = archive_path.with_suffix(".download")
        with urllib.request.urlopen(DATASET_URL, timeout=180) as response:
            with temporary_path.open("wb") as output_file:
                shutil.copyfileobj(response, output_file, length=1024 * 1024)
        temporary_path.replace(archive_path)

    extract_directory.mkdir(parents=True, exist_ok=True)
    _safe_extract(archive_path, extract_directory)
    if not workbook_path.is_file():
        raise FileNotFoundError(
            f"Expected workbook was not found after extraction: {workbook_path}"
        )
    return workbook_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download UCI Online Retail II.")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("data/raw"),
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    workbook_path = download_dataset(arguments.output_directory)
    print(workbook_path)


if __name__ == "__main__":
    main()

