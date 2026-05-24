# Venezuela Land Cover Change in Protected Areas (2017–2024)

Land use / land cover change analysis for Venezuela using Sentinel-2 10m LULC data from ESRI Living Atlas. Covers the full national extent (~912,000 km²) at 10-meter resolution, with a focused assessment of change within 215 protected areas (ABRAEs). Results are published through an interactive web dashboard.

---

## What this does

### National analysis

- Reprojects 16 satellite tiles (8 per year) from native UTM zones to Albers Equal-Area Conic
- Mosaics and clips the rasters to the Venezuelan national boundary
- Computes area statistics per land-cover class for 2017 and 2024
- Generates transition matrices and net change summaries
- Produces a spatially explicit change raster for exploratory analysis

![2017 LULC map](qgis/2017_LULC_map.png)

### Protected area analysis

- Extracts and filters ABRAE polygons from the World Database on Protected Areas (WDPA)
- Validates geometries, reprojects to Albers Equal-Area, and exports GeoPackages grouped by ABRAE type
- Computes categorical zonal histograms (pixel counts per land-cover class inside each ABRAE)
- Derives change indicators:
  - forest loss
  - agricultural expansion
  - urban expansion
- Generates rankings, summaries by ABRAE type, and comparison tables
- Simplifies and reprojects vectors for web visualization
- Converts rasters into PMTiles archives for browser rendering
- Publishes results through an interactive MapLibre GL JS dashboard

---

## Methodological note

Metrics represent net changes in land-cover area between 2017 and 2024. Values near zero do not necessarily indicate absence of territorial dynamics — losses in one part of an ABRAE may be offset by regeneration elsewhere within the same protected area.

This analysis measures **net composition change**, not pixel-level class transitions. Detailed transition analysis (gross gains, gross losses, and class-to-class flows) is planned as a future extension.

### Cloud-mask validation and correction

During the validation phase of the ABRAE analysis, several protected areas showed unexpectedly stable forest cover or apparent forest gains between 2017 and 2024. A consistency audit revealed that the 2017 and 2024 land-cover composites contained different amounts of cloud/no-data pixels in some ABRAEs.

In multiple cases, areas classified as clouds in 2017 became visible in 2024 and were then classified mainly as forest or rangeland. This produced artificial gains caused by differences in observation conditions rather than real land-cover change.

To correct this issue, all interannual comparisons were recalculated using a **common valid mask** approach. Change indicators are computed only over pixels that represent valid land-cover observations in both years simultaneously. Pixels classified as cloud or no-data in either year are excluded from the comparison.

As a result:

- Per-year zonal histograms (`zonal_2017.csv`, `zonal_2024.csv`) are preserved as yearly inventories of observed land cover.
- Corrected outputs (`zonal_2017_common.csv`, `zonal_2024_common.csv`) are used for all interannual comparisons, rankings, summaries, and dashboard indicators.
- Additional audit variables (`valid_common_pct`, `excluded_pct`, `cloud_contamination_flag`) are included to evaluate temporal comparability and cloud contamination effects inside each ABRAE.

The dashboard and downloadable outputs therefore represent land-cover change over the **comparable observed area** rather than over the full ABRAE surface.

---

## Live dashboard

Available at:

https://leomed512.github.io/venezuela_LUC_2017_2024/

The dashboard includes:

- Interactive ABRAE visualization
- Raster overlays for 2017 and 2024 land cover
- Dynamic charts and rankings
- Filtering by ABRAE category
- Downloadable tabular and geographic outputs

### Stack

- MapLibre GL JS
- PMTiles
- Plotly.js
- Vanilla HTML/CSS/JavaScript
- No backend
- No framework
- No build step

![Web Dashboard](qgis/web_gis_app.png)

---

## Data

### Land cover

Sentinel-2 10m Land Use / Land Cover Time Series produced by Impact Observatory, Microsoft, and Esri.

- Deep-learning classification
- ESA Sentinel-2 imagery
- 9 land-cover classes
- Global annual composites

Source:

https://www.arcgis.com/home/item.html?id=cfcb7609de5f478eb7666240902d4d3d

Reference:

Karra, Kontgis et al.  
*Global land use/land cover with Sentinel-2 and deep learning.*  
IGARSS 2021 — IEEE.

### Protected areas

WDPA polygons filtered for Venezuela.

ABRAE categories included:

- National Park
- Forest Reserve
- Protective Zone
- Natural Monument
- Wildlife Refuge
- Biosphere Reserve

Source:

https://www.protectedplanet.net/

### Elevation

NASADEM HGT v001 (~30m resolution), downloaded through NASA Earthdata. Used as cartographic context.

---

## Project structure

```text
venezuela_landcover/
├── data/
│   ├── raw/
│   │   ├── venezuela.geojson
│   │   ├── venezuela_landcover_2017/
│   │   ├── venezuela_land_cover_2024/
│   │   └── dem/
│   │
│   └── processed/
│       ├── cover/
│       │   ├── venezuela_landcover_2017.tif
│       │   ├── venezuela_landcover_2024.tif
│       │   ├── change_2017_2024.tif
│       │   └── reprojected/
│       │
│       ├── dem/
│       └── web_tiles_tmp/
│
├── outputs/
│   ├── figures/
│   │   ├── donut_final_2017.png
│   │   ├── donut_final_2024.png
│   │   ├── gain_loss.png
│   │   └── sankey.png
│   │
│   ├── results/
│   │   ├── cover_2017.csv
│   │   ├── cover_2024.csv
│   │   ├── comparison_2017_2024.csv
│   │   └── transition_matrix_km2.csv
│   │
│   └── zonal/
│       ├── zonal_2017.csv
│       ├── zonal_2024.csv
│       ├── zonal_2017_common.csv
│       ├── zonal_2024_common.csv
│       ├── zonal_change.csv
│       ├── comparison_2017_2024.csv
│       ├── cloud_audit.csv
│       └── abrae_change_indicators.gpkg
│
├── notebooks/
│   ├── cover_analysis.ipynb
│   ├── abraes_extract.ipynb
│   └── abraes_analysis.ipynb
│
├── scripts/
│   ├── project_clip_raster.py
│   ├── analyze_cover.py
│   ├── prepare_web_data.py
│   ├── generate_pmtiles.sh
│   └── download_dem.py
│
├── docs/
│   ├── index.html
│   ├── css/styles.css
│   ├── js/app.js
│   └── data/
│       ├── abrae_web.geojson
│       ├── rankings.csv
│       ├── summaries_by_abrae.csv
│       ├── summary_by_type.csv
│       ├── venezuela_boundary.geojson
│       └── rasters/
│           ├── lc2017.pmtiles
│           └── lc2024.pmtiles
│
├── qgis/
│   ├── venezuela_cover.qgz
│   ├── LUC_ven_pdf_2.pdf
│   └── *.png
│
├── environment.yml
├── requirements.txt
