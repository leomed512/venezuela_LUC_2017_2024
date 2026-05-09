"""
prepare_web_data.py

Prepare optimized vector and tabular outputs

Input files:
- data/processed/abrae_change_indicators.gpkg
- data/raw/venezuela.geojson

Generated outputs:
- src/data/abrae_web.geojson
- src/data/venezuela_boundary.geojson
- src/data/summaries_by_abrae.csv
- src/data/summary_by_type.csv
- src/data/rankings.csv
"""

from pathlib import Path
import logging
import geopandas as gpd
import pandas as pd


# Paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_GPKG = PROJECT_ROOT / "outputs" / "zonal" / "abrae_change_indicators.gpkg"
INPUT_GPKG_LAYER = "change_indicators"

INPUT_VENEZUELA = PROJECT_ROOT / "data" / "raw" / "venezuela.geojson"

OUTPUT_DATA_DIR = PROJECT_ROOT / "src" / "data"

OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)



# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# Configuration

WEB_CRS = "EPSG:4326"

SIMPLIFY_TOLERANCE = 0.001

TOP_N = 10

VECTOR_COLUMNS = [
    "SITE_ID",
    "NAME_ENG",
    "DESIG",
    "forest_loss_ha",
    "agriculture_gain_ha",
    "urban_gain_ha",
    "forest_2017_ha",
    "forest_2024_ha",
    "total_area_ha",
    "forest_loss_pct",
    "geometry",
]

METRIC_COLUMNS = [
    "forest_loss_ha",
    "agriculture_gain_ha",
    "urban_gain_ha",
    "forest_2017_ha",
    "forest_2024_ha",
    "total_area_ha",
    "forest_loss_pct",
]

CHANGE_METRIC_COLUMNS = [
    "forest_loss_ha",
    "agriculture_gain_ha",
    "urban_gain_ha",
    "forest_loss_pct",
]
# Utility functions

def require_file(path: Path) -> None:
    """Validate that a required file exists."""
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")


# Load source data

def load_vectors() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load ABRAE indicators and Venezuela boundary."""
    require_file(INPUT_GPKG)
    require_file(INPUT_VENEZUELA)

    abrae = gpd.read_file(
        INPUT_GPKG,
        layer=INPUT_GPKG_LAYER,
    )

    venezuela = gpd.read_file(INPUT_VENEZUELA)

    if abrae.crs is None:
        raise ValueError(
            "ABRAE layer has no CRS."
        )

    if venezuela.crs is None:
        raise ValueError(
            "Venezuela boundary has no CRS."
        )

    abrae = abrae.to_crs(WEB_CRS)
    venezuela = venezuela.to_crs(WEB_CRS)

    return abrae, venezuela


# Vector optimization

def optimize_vectors(
    abrae: gpd.GeoDataFrame,
    venezuela: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Create simplified GeoJSON layers for web display."""

    missing = [
        col
        for col in VECTOR_COLUMNS
        if col not in abrae.columns
    ]

    if missing:
        raise KeyError(
            f"Missing columns in ABRAE layer: {missing}"
        )

    abrae_web = abrae[VECTOR_COLUMNS].copy()

    # Normalize metrics for visualization.
    for col in METRIC_COLUMNS:
        abrae_web[col] = (
            abrae_web[col]
            .fillna(0)
            .round(2)
        )

    # Simplify geometries for faster rendering.
    abrae_web["geometry"] = (
        abrae_web.geometry.simplify(
            tolerance=SIMPLIFY_TOLERANCE,
            preserve_topology=True,
        )
    )

    # Remove invalid geometries after simplification.
    abrae_web = abrae_web[
        abrae_web.geometry.notna()
        & ~abrae_web.geometry.is_empty
    ].copy()

    abrae_web.to_file(
        OUTPUT_DATA_DIR / "abrae_web.geojson",
        driver="GeoJSON",
    )

    venezuela_web = venezuela.copy()

    venezuela_web["geometry"] = (
        venezuela_web.geometry.simplify(
            tolerance=SIMPLIFY_TOLERANCE,
            preserve_topology=True,
        )
    )

    venezuela_web.to_file(
        OUTPUT_DATA_DIR / "venezuela_boundary.geojson",
        driver="GeoJSON",
    )

    return abrae_web


# Tabular outputs

def build_tables(
    abrae_web: gpd.GeoDataFrame,
) -> None:
    """Generate CSV summaries and rankings."""

    tabular = abrae_web.drop(
        columns="geometry"
    ).copy()

    tabular.sort_values(
        "forest_loss_ha",
        ascending=False,
    ).to_csv(
        OUTPUT_DATA_DIR / "summaries_by_abrae.csv",
        index=False,
    )

    summary_by_type = (
        tabular
        .groupby("DESIG", as_index=False)
        .agg({
            "SITE_ID": "nunique",
            "forest_loss_ha": "sum",
            "agriculture_gain_ha": "sum",
            "urban_gain_ha": "sum",
        })
        .rename(columns={
            "SITE_ID": "n_abrae"
        })
    )

    summary_by_type.to_csv(
        OUTPUT_DATA_DIR / "summary_by_type.csv",
        index=False,
    )

    ranking_frames = []

    # Create national and per-type rankings.
    for metric in CHANGE_METRIC_COLUMNS:
        national = (
            tabular[
                tabular[metric] > 0
            ]
            .sort_values(
                metric,
                ascending=False,
            )
            .head(TOP_N)
            .copy()
        )

        national["metric"] = metric
        national["rank_scope"] = "national"

        ranking_frames.append(national)

        for abrae_type in (
            tabular["DESIG"]
            .dropna()
            .unique()
        ):

            by_type = (
                tabular[
                    (
                        tabular["DESIG"]
                        == abrae_type
                    )
                    & (
                        tabular[metric]
                        > 0
                    )
                ]
                .sort_values(
                    metric,
                    ascending=False,
                )
                .head(TOP_N)
                .copy()
            )

            by_type["metric"] = metric
            by_type["rank_scope"] = abrae_type

            ranking_frames.append(by_type)

    rankings = pd.concat(
        ranking_frames,
        ignore_index=True,
    )

    rankings.to_csv(
        OUTPUT_DATA_DIR / "rankings.csv",
        index=False,
    )



# Main workflow

def main() -> None:
    """Run the full data preparation workflow."""

    logger.info(
        "Starting web data preparation."
    )

    abrae, venezuela = load_vectors()

    abrae_web = optimize_vectors(
        abrae,
        venezuela,
    )

    build_tables(abrae_web)


if __name__ == "__main__":
    main()
