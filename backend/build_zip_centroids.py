"""Build data/zip_centroids.json from the U.S. Census Bureau's ZIP code file.

Run once from the project folder:
    python backend/build_zip_centroids.py

It downloads the 2020 Census "ZCTA Gazetteer" (~1 MB, public domain) and
keeps only ZIP codes in and around Collin and Denton County. Each ZIP gets
its "internal point": a spot the Census picks inside the ZIP area.
"""

import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
              "2020_Gazetteer/2020_Gaz_zcta_national.zip")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "zip_centroids.json"

# A box around Collin + Denton County, with some margin for neighbors
# like Carrollton and Wylie that appear in our pantry list.
MIN_LAT, MAX_LAT = 32.85, 33.50
MIN_LNG, MAX_LNG = -97.45, -96.25


def main():
    print(f"Downloading {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))

    text = archive.read(archive.namelist()[0]).decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    reader.fieldnames = [name.strip() for name in reader.fieldnames]  # last header has trailing spaces

    centroids = {}
    for row in reader:
        lat, lng = float(row["INTPTLAT"]), float(row["INTPTLONG"])
        if MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG:
            centroids[row["GEOID"]] = {"lat": lat, "lng": lng}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(centroids.items())), f, indent=1)
        f.write("\n")
    print(f"Saved {len(centroids)} ZIP codes to {OUTPUT_PATH.name}")


if __name__ == "__main__":
    main()
