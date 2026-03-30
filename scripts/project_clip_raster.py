"""
Reproject Sentinel-2 LULC tiles to Albers Equal-Area, build virtual
mosaics, and clip to the Venezuelan national boundary.

Outputs:
    data/processed/cover/venezuela_landcover_2017.tif
    data/processed/cover/venezuela_landcover_2024.tif
"""

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("process_tiles")

# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

TILES_2017 = PROJECT_ROOT / "data/raw/venezuela_landcover_2017"
TILES_2024 = PROJECT_ROOT / "data/raw/venezuela_land_cover_2024"
BOUNDARY   = PROJECT_ROOT / "data/raw/venezuela.geojson"

PROCESSED  = PROJECT_ROOT / "data/processed/cover"
REPROJ_DIR = PROCESSED / "reprojected"

RASTER_2017 = PROCESSED / "venezuela_landcover_2017.tif"
RASTER_2024 = PROCESSED / "venezuela_landcover_2024.tif"

# Albers Equal-Area Conic — standard parallels at 2°N and 10°N
# ---------------------------------------------------------------------------
ALBERS = (
    "+proj=aea +lat_1=2 +lat_2=10 +lat_0=6 +lon_0=-66 "
    "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)

TILES = {
    2017: [
        "18N_20170101-20180101.tif", "18P_20170101-20180101.tif",
        "19N_20170101-20180101.tif", "19P_20170101-20180101.tif",
        "20N_20170101-20180101.tif", "20P_20170101-20180101.tif",
        "21N_20170101-20180101.tif", "21P_20170101-20180101.tif",
    ],
    2024: [
        "18N_20240101-20241231.tif", "18P_20240101-20241231.tif",
        "19N_20240101-20241231.tif", "19P_20240101-20241231.tif",
        "20N_20240101-20241231.tif", "20P_20240101-20241231.tif",
        "21N_20240101-20241231.tif", "21P_20240101-20241231.tif",
    ],
}

# Common GeoTIFF creation options for all outputs
GTIFF_OPTS = [
    "-co", "COMPRESS=LZW",
    "-co", "TILED=YES",
    "-co", "BIGTIFF=YES",
]


# Helpers
# ---------------------------------------------------------------------------
def run_gdal(cmd: list[str]) -> None:
    """Execute a GDAL CLI command; raise on non-zero exit."""
    log.debug(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("GDAL stderr:\n%s", result.stderr)
        raise RuntimeError(f"Failed: {cmd[0]}")


def check_inputs() -> None:
    """Verify that raw tiles and boundary file exist before processing."""
    missing = []
    src_dirs = {2017: TILES_2017, 2024: TILES_2024}

    for year, tile_list in TILES.items():
        for name in tile_list:
            path = src_dirs[year] / name
            if not path.exists():
                missing.append(str(path))

    if not BOUNDARY.exists():
        missing.append(str(BOUNDARY))

    if missing:
        log.error("Missing input files:")
        for m in missing:
            log.error("  %s", m)
        sys.exit(1)


#  Reproject tiles
# ---------------------------------------------------------------------------
def reproject_tiles() -> None:
    """Reproject each tile from its native UTM zone to Albers."""
    log.info(" Reprojecting tiles to Albers Equal-Area")

    src_dirs = {2017: TILES_2017, 2024: TILES_2024}

    for year, tile_list in TILES.items():
        out_dir = REPROJ_DIR / str(year)
        out_dir.mkdir(parents=True, exist_ok=True)

        for name in tile_list:
            src = src_dirs[year] / name
            dst = out_dir / name

            if dst.exists():
                log.info("  [skip] %d/%s — already reprojected", year, name)
                continue

            log.info("  %d/%s", year, name)
            run_gdal([
                "gdalwarp",
                "-t_srs", ALBERS,
                "-r", "near",
                "-of", "GTiff",
                *GTIFF_OPTS,
                "-overwrite",
                str(src), str(dst),
            ])

    log.info("Reprojection complete.")


# VRT mosaic + clip
# ---------------------------------------------------------------------------
def build_vrt_and_clip() -> None:
    """Build virtual mosaics from reprojected tiles, clip to boundary."""
    log.info(" Building mosaics and clipping to national boundary")

    PROCESSED.mkdir(parents=True, exist_ok=True)

    for year, out_raster in [(2017, RASTER_2017), (2024, RASTER_2024)]:
        tile_dir = REPROJ_DIR / str(year)
        tiles = sorted(tile_dir.glob("*.tif"))

        if not tiles:
            raise FileNotFoundError(f"No reprojected tiles in {tile_dir}")

        vrt = PROCESSED / f"mosaic_{year}.vrt"

        log.info("  VRT %d — %d tiles", year, len(tiles))
        run_gdal(["gdalbuildvrt", str(vrt)] + [str(t) for t in tiles])

        if out_raster.exists():
            log.info("  [skip] %s — already clipped", out_raster.name)
            continue

        log.info("  Clipping %d...", year)
        run_gdal([
            "gdalwarp",
            "-cutline", str(BOUNDARY),
            "-crop_to_cutline",
            "-r", "near",
            "-of", "GTiff",
            *GTIFF_OPTS,
            "-wm", "2048",
            "-multi",
            "-overwrite",
            str(vrt), str(out_raster),
        ])

    log.info("Mosaic and clip complete.")


# Main
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("Project root: %s", PROJECT_ROOT)
    check_inputs()
    reproject_tiles()
    build_vrt_and_clip()

    log.info("Done. Output rasters:")
    log.info("  %s", RASTER_2017)
    log.info("  %s", RASTER_2024)


if __name__ == "__main__":
    main()