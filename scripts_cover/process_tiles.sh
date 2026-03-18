#!/bin/bash
# ============================================================
# PROCESAMIENTO LAND COVER VENEZUELA - 2017 y 2024
# Sentinel-2 10m Land Use/Land Cover (ESRI Living Atlas)
# ============================================================
# Proyección: Albers Equal-Area Conic centrada en Venezuela
# ============================================================
# Ejecutar
# ============================================================
"""
cd ruta/ 
chmod +x process_tiles.sh # permiso de ejecución
./process_tiles.sh # ejecutar el script
"""

# --- CONFIGURACIÓN ---
BASE=~/Documents/data_analysis/venezuela_landcover
TILES_2017="${BASE}/venezuela_landcover_2017"
TILES_2024="${BASE}/venezuela_land_cover_2024"
OUTPUT="${BASE}/output"
REPROJ="${OUTPUT}/reproyectados"

# Ruta al GeoJSON de Venezuela
GEOJSON="${BASE}/venezuela.geojson"

# Proyección Albers Equal-Area para Venezuela
ALBERS="+proj=aea +lat_1=2 +lat_2=10 +lat_0=6 +lon_0=-66 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"

# Crear carpetas
mkdir -p "${REPROJ}/2017"
mkdir -p "${REPROJ}/2024"

# --- PASO 1: Reproyectar cada tile individualmente a Albers ---
echo "============================================"
echo "PASO 1: Reproyectando tiles a Albers"
echo "============================================"

# Tiles 2017
for TILE in \
  18N_20170101-20180101.tif \
  18P_20170101-20180101.tif \
  19N_20170101-20180101.tif \
  19P_20170101-20180101.tif \
  20N_20170101-20180101.tif \
  20P_20170101-20180101.tif \
  21N_20170101-20180101.tif \
  21P_20170101-20180101.tif
do
  echo "  Reproyectando 2017/${TILE}..."
  gdalwarp \
    -t_srs "${ALBERS}" \
    -r near \
    -of GTiff \
    -co COMPRESS=LZW \
    -co TILED=YES \
    -co BIGTIFF=YES \
    -overwrite \
    "${TILES_2017}/${TILE}" \
    "${REPROJ}/2017/${TILE}"
done

echo "Tiles 2017 reproyectados."

# Tiles 2024
for TILE in \
  18N_20240101-20241231.tif \
  18P_20240101-20241231.tif \
  19N_20240101-20241231.tif \
  19P_20240101-20241231.tif \
  20N_20240101-20241231.tif \
  20P_20240101-20241231.tif \
  21N_20240101-20241231.tif \
  21P_20240101-20241231.tif
do
  echo "  Reproyectando 2024/${TILE}..."
  gdalwarp \
    -t_srs "${ALBERS}" \
    -r near \
    -of GTiff \
    -co COMPRESS=LZW \
    -co TILED=YES \
    -co BIGTIFF=YES \
    -overwrite \
    "${TILES_2024}/${TILE}" \
    "${REPROJ}/2024/${TILE}"
done

echo "Tiles 2024 reproyectados."

# --- PASO 2: Crear VRT (ahora todos en el mismo CRS) ---
echo ""
echo "============================================"
echo "PASO 2: Creando mosaicos virtuales"
echo "============================================"

gdalbuildvrt "${OUTPUT}/mosaico_2017.vrt" "${REPROJ}/2017/"*.tif
echo "VRT 2017 creado."

gdalbuildvrt "${OUTPUT}/mosaico_2024.vrt" "${REPROJ}/2024/"*.tif
echo "VRT 2024 creado."

# --- PASO 3: Recortar con contorno de Venezuela ---
echo ""
echo "============================================"
echo "PASO 3: Recortando con contorno de Venezuela"
echo "============================================"

echo "Recortando 2017..."
gdalwarp \
  -cutline "${GEOJSON}" \
  -crop_to_cutline \
  -r near \
  -of GTiff \
  -co COMPRESS=LZW \
  -co TILED=YES \
  -co BIGTIFF=YES \
  -wm 2048 \
  -multi \
  -overwrite \
  "${OUTPUT}/mosaico_2017.vrt" \
  "${OUTPUT}/venezuela_landcover_2017.tif"

echo "2017 listo."

echo "Recortando 2024..."
gdalwarp \
  -cutline "${GEOJSON}" \
  -crop_to_cutline \
  -r near \
  -of GTiff \
  -co COMPRESS=LZW \
  -co TILED=YES \
  -co BIGTIFF=YES \
  -wm 2048 \
  -multi \
  -overwrite \
  "${OUTPUT}/mosaico_2024.vrt" \
  "${OUTPUT}/venezuela_landcover_2024.tif"

echo "2024 listo."


echo "Raster final comprimido generado."
echo ""
echo "============================================"
echo "PROCESO COMPLETO"
echo "============================================"
echo ""
echo "Archivos en: ${OUTPUT}/"
echo "  - reproyectados/2017/*.tif  (tiles individuales en Albers)"
echo "  - reproyectados/2024/*.tif  (tiles individuales en Albers)"
echo "  - mosaico_2017.vrt"
echo "  - mosaico_2024.vrt"
echo "  - venezuela_landcover_2017.tif"
echo "  - venezuela_landcover_2024.tif"
echo ""
