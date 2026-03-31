# Venezuela Land Cover Change Analysis (2017–2024)

Land use/land cover change analysis for Venezuela using Sentinel-2 10m LULC data from ESRI Living Atlas. Covers the full national extent (~912,000 km²) at 10-meter resolution.

## What this does

- Reprojects 16 satellite tiles (8 per year) from native UTM zones to Albers Equal-Area Conic
- Mosaics and clips to the Venezuelan national boundary
- Computes area statistics per land cover class for 2017 and 2024
- Generates a transition matrix showing class-to-class change in km²
- Produces a spatially explicit change raster
- Visualizes results through static and interactive charts

## Data

**Land cover:** Sentinel-2 10m Land Use/Land Cover Time Series, produced by Impact Observatory, Microsoft and Esri. Deep learning classification over ESA Sentinel-2 imagery, 9 LULC classes, assessed accuracy >75%.

Source: [ArcGIS Living Atlas](https://www.arcgis.com/home/item.html?id=cfcb7609de5f478eb7666240902d4d3d)

Reference: Karra, Kontgis et al. "Global land use/land cover with Sentinel-2 and deep learning." IGARSS 2021. IEEE.

**Elevation:** NASADEM HGT v001 (~30m resolution), downloaded via NASA Earthdata. Used as a base layer for cartographic context.

## Project structure

```
venezuela_landcover/
├── data/
│   ├── raw/                    # Original tiles, boundary, and DEM zips
│   │   └── dem/                # NASADEM raw .zip and extracted .hgt files
│   └── processed/
│       ├── cover/              # Reprojected, mosaiced, clipped LULC rasters
│       └── dem/                # Clipped DEM (venezuela_dem.tif)
├── outputs/
│   ├── results/                # CSV tables (areas, comparison, transition matrix)
│   └── figures/                # Chart exports (PNG)
├── scripts/
│   ├── process_tiles.py        # GDAL pipeline: reproject, mosaic, clip
│   ├── analyze_cover.py        # Stats, transition matrix, change raster
│   └── download_dem.py         # Download and process NASADEM via Earthdata
└── notebooks/
    └── cover_analysis.ipynb    # Visualization and exploratory analysis
```

## Setup

With conda (recommended):

```bash
conda env create -f environment.yml
conda activate cover_venezuela
```

With pip:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Note: pip users need GDAL installed separately (`sudo apt install gdal-bin libgdal-dev` on Ubuntu).

DEM download requires a [NASA Earthdata](https://urs.earthdata.nasa.gov/) account.

## Usage

```bash
# Step 1: Reproject tiles, build mosaic, clip to boundary
python scripts/process_tiles.py

# Step 2: Compute stats and generate change raster
python scripts/analyze_cover.py

# Step 2 (tables only, skip change raster):
python scripts/analyze_cover.py
python scripts/analyze_cover.py --no-change-raster # If a change raster is not needed

# Download and process DEM (requires Earthdata login)
python scripts/download_dem.py
```

Cartographic output produced in QGIS Print Layout.

## Projection

Albers Equal-Area Conic, custom parameters for Venezuela:
- Standard parallels: 2°N and 10°N
- Central meridian: 66°W
- Datum: WGS84

This projection preserves area measurements across the full national extent. Analysis is done in Albers; cartographic output is presented in WGS84 (EPSG:4326).

## Tools

GDAL, Python (rasterio, numpy, pandas, geopandas, earthaccess), QGIS, matplotlib, seaborn, plotly.

## Author

Leonardo Medina — [LinkedIn](https://www.linkedin.com/in/leomedinast/)