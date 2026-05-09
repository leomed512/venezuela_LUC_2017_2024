# ConvertS large raster images (.tif) into web-friendly PNG tiles that Leaflet can dynamically display in the browser.

# EXECUTE
# chmod +x scripts/generate_raster_tiles.sh
# ./scripts/generate_raster_tiles.sh


set -euo pipefail

INPUT_DIR="data/processed/cover"
OUTPUT_DIR="src/data/rasters"
TMP_DIR="data/processed/web_tiles_tmp"

ZOOM_LEVELS="5-10"
PROCESSES=4

mkdir -p "$OUTPUT_DIR"
mkdir -p "$TMP_DIR"

generate_tiles_with_palette() {
  local input_file="$1"
  local output_name="$2"

  local rgba_vrt="$TMP_DIR/${output_name}_rgba.vrt"
  local output_path="$OUTPUT_DIR/$output_name"

  rm -rf "$output_path"
# Convert categorical raster to RGBA

  gdal_translate \
    -of VRT \
    -expand rgba \
    "$input_file" \
    "$rgba_vrt"
# Generate XYZ Tiles

  gdal2tiles.py \
    --profile=mercator \
    --zoom="$ZOOM_LEVELS" \
    --resampling=near \
    --processes="$PROCESSES" \
    "$rgba_vrt" \
    "$output_path"

  rm -f "$rgba_vrt"
}

generate_tiles_with_palette \
  "$INPUT_DIR/venezuela_landcover_2017.tif" \
  "lc2017"

generate_tiles_with_palette \
  "$INPUT_DIR/venezuela_landcover_2024.tif" \
  "lc2024"