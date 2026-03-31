"""

Land cover area statistics, change comparison, transition matrix,
and (optionally) a spatially explicit change raster.

Outputs:
    outputs/results/cover_2017.csv
    outputs/results/cover_2024.csv
    outputs/results/comparison_2017_2024.csv
    outputs/results/transition_matrix_km2.csv
    data/processed/cover/change_2017_2024.tif  (unless --no-change-raster)

Excution:
    python3 analyze_cover.py                  # full analysis + change raster
    python3 analyze_cover.py --no-change-raster  # tables only, skip raster
"""

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

log = logging.getLogger("analyze_cover")


# Paths 
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RASTER_2017 = PROJECT_ROOT / "data/processed/cover/venezuela_landcover_2017.tif"
RASTER_2024 = PROJECT_ROOT / "data/processed/cover/venezuela_landcover_2024.tif"
CHANGE_RASTER = PROJECT_ROOT / "data/processed/cover/change_2017_2024.tif"
RESULTS = PROJECT_ROOT / "outputs/results"

# Pixel size in Albers projection (metres)
PIXEL_SIZE = 10

# ESRI Sentinel-2 LULC class schema (verified against actual raster values)
LULC_CLASSES = {
    0:  "No data",
    1:  "Water",
    2:  "Trees",
    3:  "No data",
    4:  "Flooded vegetation",
    5:  "Crops",
    6:  "No data",
    7:  "Built area",
    8:  "Bare ground",
    9:  "Snow/Ice",
    10: "Clouds",
    11: "Rangeland",
}

# Classes to exclude from area totals (nodata, clouds)
EXCLUDE_CLASSES = {0, 3, 6, 10}


# Area statistics
# ----------------------------------------------
def count_pixels(raster_path: Path) -> Counter:
    """Count pixels per class, reading block-by-block"""
    counts = Counter()

    with rasterio.open(raster_path) as src:
        nodata = src.nodata
        blocks = list(src.block_windows(1))
        total = len(blocks)

        log.info("  %s — %d x %d px, %d blocks",
                 raster_path.name, src.width, src.height, total)

        for i, (_, window) in enumerate(blocks):
            data = src.read(1, window=window)
            if nodata is not None:
                data = data[data != nodata]

            values, cnts = np.unique(data, return_counts=True)
            for v, c in zip(values, cnts):
                counts[int(v)] += int(c)

            if (i + 1) % 1000 == 0 or (i + 1) == total:
                log.info("    %d / %d blocks", i + 1, total)

    return counts


def counts_to_dataframe(counts: Counter, year: int) -> pd.DataFrame:
    """Convert pixel counts to a DataFrame with area in km² and hectares."""
    px_km2 = (PIXEL_SIZE ** 2) / 1e6
    px_ha  = (PIXEL_SIZE ** 2) / 1e4

    rows = []
    for class_id, n_pixels in sorted(counts.items()):
        rows.append({
            "class_id": class_id,
            "class_name": LULC_CLASSES.get(class_id, f"Class {class_id}"),
            "pixels": n_pixels,
            "area_km2": round(n_pixels * px_km2, 4),
            "area_ha": round(n_pixels * px_ha, 4),
        })

    df = pd.DataFrame(rows)
    # Percentage over valid classes only
    valid = df[~df["class_id"].isin(EXCLUDE_CLASSES)]
    total_valid = valid["area_km2"].sum()
    df["pct"] = round(df["area_km2"] / total_valid * 100, 2)
    df.loc[df["class_id"].isin(EXCLUDE_CLASSES), "pct"] = np.nan
    df["year"] = year

    return df


def compute_comparison(df_2017: pd.DataFrame,
                       df_2024: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side comparison with absolute and relative change."""
    comp = df_2017[["class_id", "class_name", "area_km2", "pct"]].merge(
        df_2024[["class_id", "area_km2", "pct"]],
        on="class_id", suffixes=("_2017", "_2024"), how="outer",
    ).fillna(0)

    comp["change_km2"] = comp["area_km2_2024"] - comp["area_km2_2017"]
    comp["change_pct"] = round(
        (comp["area_km2_2024"] - comp["area_km2_2017"])
        / comp["area_km2_2017"].replace(0, np.nan) * 100, 2
    )

    return comp


def run_cover_stats():
    """Compute per-class areas for both years and comparison table."""
    log.info("Computing land cover statistics")

    df_2017 = counts_to_dataframe(count_pixels(RASTER_2017), 2017)
    df_2024 = counts_to_dataframe(count_pixels(RASTER_2024), 2024)
    comparison = compute_comparison(df_2017, df_2024)

    return df_2017, df_2024, comparison


# Transition matrix
# ----------------------------------------------
def compute_transition_matrix() -> pd.DataFrame:
    """
    Build a class-to-class transition matrix (km²).
    Rows = 2017 classes, columns = 2024 classes.
    """
    log.info("Computing transition matrix")
    px_km2 = (PIXEL_SIZE ** 2) / 1e6
    transitions = Counter()

    with rasterio.open(RASTER_2017) as src17, \
         rasterio.open(RASTER_2024) as src24:

        assert src17.shape == src24.shape, "Raster dimensions do not match"
        assert src17.transform == src24.transform, "Raster grids not aligned"

        blocks = list(src17.block_windows(1))
        total = len(blocks)

        for i, (_, window) in enumerate(blocks):
            b17 = src17.read(1, window=window)
            b24 = src24.read(1, window=window)

            # Combined valid-data mask
            mask = np.ones(b17.shape, dtype=bool)
            if src17.nodata is not None:
                mask &= b17 != src17.nodata
            if src24.nodata is not None:
                mask &= b24 != src24.nodata

            v17 = b17[mask].ravel()
            v24 = b24[mask].ravel()

            for a, b in zip(v17, v24):
                transitions[(int(a), int(b))] += 1

            if (i + 1) % 1000 == 0 or (i + 1) == total:
                log.info("  %d / %d blocks", i + 1, total)

    # Build matrix
    all_classes = sorted({c for pair in transitions for c in pair})
    matrix = pd.DataFrame(0.0, index=all_classes, columns=all_classes)

    for (c17, c24), n in transitions.items():
        matrix.loc[c17, c24] = round(n * px_km2, 4)

    labels = {c: LULC_CLASSES.get(c, f"Class {c}") for c in all_classes}
    matrix.index = [labels[c] for c in all_classes]
    matrix.columns = [labels[c] for c in all_classes]

    return matrix


# Change raster
# ----------------------------------------------
def build_change_raster() -> None:
    """
    Pixel-by-pixel change detection, block-by-block.
    Values: 0 = no change, 1-254 = new class in 2024, 255 = nodata.
    """
    if CHANGE_RASTER.exists():
        log.info("[skip] Change raster already exists: %s", CHANGE_RASTER.name)
        return

    log.info("Generating change raster")
    t0 = time.time()

    with rasterio.open(RASTER_2017) as src17:
        profile = src17.profile.copy()
        profile.update(
            dtype="uint8", count=1, compress="lzw",
            tiled=True, bigtiff="YES", nodata=255,
        )

        blocks = list(src17.block_windows(1))
        total = len(blocks)
        changed_px = 0
        valid_px = 0

        with rasterio.open(RASTER_2024) as src24, \
             rasterio.open(CHANGE_RASTER, "w", **profile) as dst:

            assert src17.shape == src24.shape, "Raster dimensions do not match"

            for i, (_, window) in enumerate(blocks):
                b17 = src17.read(1, window=window)
                b24 = src24.read(1, window=window)

                out = np.where(b17 != b24, b24, 0).astype(np.uint8)

                if src17.nodata is not None:
                    out[b17 == src17.nodata] = 255
                if src24.nodata is not None:
                    out[b24 == src24.nodata] = 255

                dst.write(out, 1, window=window)

                valid = out < 255
                valid_px += valid.sum()
                changed_px += ((out > 0) & valid).sum()

                if (i + 1) % max(1, total // 50) == 0 or (i + 1) == total:
                    elapsed = time.time() - t0
                    eta = (elapsed / (i + 1)) * (total - i - 1)
                    log.info(
                        "  [%5.1f%%] %d/%d blocks | %.1f min | ~%.1f min left",
                        (i + 1) / total * 100, i + 1, total,
                        elapsed / 60, eta / 60,
                    )

    elapsed = time.time() - t0
    log.info("Change raster complete — %.1f min", elapsed / 60)
    if valid_px > 0:
        log.info("  Changed pixels: %s / %s (%.2f%%)",
                 f"{changed_px:,}", f"{valid_px:,}",
                 changed_px / valid_px * 100)


# Output
# ----------------------------------------------
def save_results(df_2017, df_2024, comparison, matrix):
    RESULTS.mkdir(parents=True, exist_ok=True)

    df_2017.to_csv(RESULTS / "cover_2017.csv", index=False)
    df_2024.to_csv(RESULTS / "cover_2024.csv", index=False)
    comparison.to_csv(RESULTS / "comparison_2017_2024.csv", index=False)
    matrix.to_csv(RESULTS / "transition_matrix_km2.csv")

    log.info("CSV tables saved to %s", RESULTS)


def print_summary(df_2017, df_2024, comparison):
    cover_cols = ["class_name", "area_km2", "area_ha", "pct"]
    change_cols = ["class_name", "area_km2_2017", "area_km2_2024",
                   "change_km2", "change_pct"]

    # Filter out excluded classes for display
    valid_2017 = df_2017[~df_2017["class_id"].isin(EXCLUDE_CLASSES)]
    valid_2024 = df_2024[~df_2024["class_id"].isin(EXCLUDE_CLASSES)]
    valid_comp = comparison[~comparison["class_id"].isin(EXCLUDE_CLASSES)]

    print("\n" + "=" * 60)
    print("LAND COVER 2017")
    print("=" * 60)
    print(valid_2017[cover_cols].to_string(index=False))

    print("\n" + "=" * 60)
    print("LAND COVER 2024")
    print("=" * 60)
    print(valid_2024[cover_cols].to_string(index=False))

    print("\n" + "=" * 60)
    print("CHANGE 2017 -> 2024")
    print("=" * 60)
    print(valid_comp[change_cols].to_string(index=False))


# Main
# ----------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Land cover analysis — Venezuela 2017 vs 2024")
    parser.add_argument(
        "--no-change-raster", action="store_true",
        help="Skip change raster generation (tables only)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    # Verify inputs exist
    for f in (RASTER_2017, RASTER_2024):
        if not f.exists():
            log.error("Raster not found: %s", f)
            log.error("Run process_tiles.py first.")
            sys.exit(1)

    # Stats + comparison
    df_2017, df_2024, comparison = run_cover_stats()

    # Transition matrix
    matrix = compute_transition_matrix()

    # Change raster (optional)
    if not args.no_change_raster:
        build_change_raster()
    else:
        log.info("Skipping change raster (--no-change-raster)")

    save_results(df_2017, df_2024, comparison, matrix)
    print_summary(df_2017, df_2024, comparison)
    log.info("Done.")


if __name__ == "__main__":
    main()