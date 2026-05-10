# Generates XYZ raster tiles from land cover GeoTIFFs and packages
# them into single PMTiles files for efficient serving with MapLibre.
#
# Requires: gdal2tiles.py (GDAL), pmtiles CLI (pip install pmtiles)
#
# Usage:
#   chmod +x scripts/generate_pmtiles.sh
#   ./scripts/generate_pmtiles.sh

set -euo pipefail

INPUT_DIR="data/processed/cover"
OUTPUT_DIR="src/maplibre/data/rasters"
TMP_DIR="data/processed/pmtiles_tmp"

ZOOM_LEVELS="5-12"
PROCESSES=4

mkdir -p "$OUTPUT_DIR"
mkdir -p "$TMP_DIR"

generate_pmtiles() {
  local input_file="$1"
  local layer_name="$2"

  local rgba_vrt="$TMP_DIR/${layer_name}_rgba.vrt"
  local tiles_dir="$TMP_DIR/${layer_name}_tiles"
  local output_file="$OUTPUT_DIR/${layer_name}.pmtiles"

  if [ -f "$output_file" ]; then
    echo "Skipping $layer_name — PMTiles already exists"
    return
  fi

  echo "Processing $layer_name..."

  # Expand categorical raster palette to RGBA for tile rendering
  gdal_translate \
    -of VRT \
    -expand rgba \
    "$input_file" \
    "$rgba_vrt"

  # Generate XYZ tiles 
  rm -rf "$tiles_dir"
  gdal2tiles.py \
    --profile=mercator \
    --zoom="$ZOOM_LEVELS" \
    --resampling=near \
    --processes="$PROCESSES" \
    --xyz \
    --exclude \
    --webviewer=none \
    "$rgba_vrt" \
    "$tiles_dir"

  # Package all tiles into a single PMTiles file
  # pmtiles convert "$tiles_dir" "$output_file" --- NO FUNCIONÓ

  # Package tiles into MBTiles, then convert to PMTiles
  mb-util "$tiles_dir" "$TMP_DIR/${layer_name}.mbtiles" --image_format=png --scheme=xyz
  pmtiles convert "$TMP_DIR/${layer_name}.mbtiles" "$output_file"

  # Clean up
  rm -f "$rgba_vrt"
  rm -rf "$tiles_dir"
  rm -f "$TMP_DIR/${layer_name}.mbtiles"



  echo "Created: $output_file ($(du -h "$output_file" | cut -f1))"
}

generate_pmtiles \
  "$INPUT_DIR/venezuela_landcover_2017.tif" \
  "lc2017"

generate_pmtiles \
  "$INPUT_DIR/venezuela_landcover_2024.tif" \
  "lc2024"

echo "Done. PMTiles saved in $OUTPUT_DIR"
