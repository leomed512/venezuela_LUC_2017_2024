from pathlib import Path
import zipfile
import subprocess
import shutil

import earthaccess
import geopandas as gpd

# =========================
# Rutas
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data/vectors/venezuela.geojson"
RAW_DIR = BASE_DIR / "data/raw"
EXTRACT_DIR = BASE_DIR / "data/raw_extracted"
PROCESSED_DIR = BASE_DIR / "data/processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

VRT_PATH = PROCESSED_DIR / "venezuela.vrt"
DEM_PATH = PROCESSED_DIR / "venezuela_dem.tif"

# =========================
# Verificar GDAL
# =========================
for tool in ["gdalbuildvrt", "gdalwarp", "gdalinfo"]:
    if shutil.which(tool) is None:
        raise RuntimeError(
            f"No se encontró '{tool}' en el PATH. "
            "Instala GDAL en tu entorno conda."
        )

# =========================
# Leer GeoJSON
# =========================
gdf = gpd.read_file(GEOJSON_PATH)

if gdf.empty:
    raise RuntimeError("El GeoJSON está vacío.")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
elif gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

bbox = tuple(gdf.total_bounds)
print("BBOX:", bbox)

# =========================
# Login Earthdata
# =========================
earthaccess.login(strategy="interactive")

# =========================
# Buscar granules NASADEM
# =========================
granules = earthaccess.search_data(
    short_name="NASADEM_HGT",
    version="001",
    bounding_box=bbox
)

print(f"Tiles encontrados: {len(granules)}")

# =========================
# Descargar solo ZIP faltantes
# =========================
existing_zips = {p.name for p in RAW_DIR.glob("*.zip")}
granules_to_download = []

for g in granules:
    links = g.data_links()
    if not links:
        continue

    filename = links[0].split("/")[-1]
    if filename not in existing_zips:
        granules_to_download.append(g)

print(f"Granules nuevos a descargar: {len(granules_to_download)}")

if granules_to_download:
    downloaded_files = earthaccess.download(
        granules_to_download,
        local_path=str(RAW_DIR)
    )
    print(f"Archivos descargados: {len(downloaded_files)}")
else:
    print("Todos los ZIP ya existen, se omite descarga.")

# =========================
# Extraer ZIP faltantes
# =========================
zip_files = sorted(RAW_DIR.glob("*.zip"))
print(f"ZIP encontrados: {len(zip_files)}")

for zip_path in zip_files:
    expected_hgt = EXTRACT_DIR / zip_path.name.replace(".zip", ".hgt")
    if expected_hgt.exists():
        continue

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(EXTRACT_DIR)

print("Extracción completada")

hgt_files = sorted(EXTRACT_DIR.rglob("*.hgt"))
print(f"HGT extraídos: {len(hgt_files)}")

if not hgt_files:
    raise RuntimeError("No se encontraron archivos .hgt después de extraer los ZIP.")

# =========================
# Crear VRT si no existe
# =========================
if VRT_PATH.exists():
    print("VRT ya existe, se reutiliza.")
else:
    cmd_vrt = ["gdalbuildvrt", str(VRT_PATH)] + [str(fp) for fp in hgt_files]
    print("Creando VRT...")
    subprocess.run(cmd_vrt, check=True)
    print("VRT creado:", VRT_PATH)

# =========================
# Crear DEM recortado si no existe
# =========================
if DEM_PATH.exists():
    print("DEM final ya existe, se reutiliza.")
else:
    cmd_warp = [
        "gdalwarp",
        "-cutline", str(GEOJSON_PATH),
        "-crop_to_cutline",
        "-dstnodata", "-9999",
        "-of", "GTiff",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
        str(VRT_PATH),
        str(DEM_PATH),
    ]
    print("Recortando DEM con GDAL...")
    subprocess.run(cmd_warp, check=True)
    print("DEM final listo:", DEM_PATH)

# =========================
# Validación rápida
# =========================
print("Inspección final:")
subprocess.run(["gdalinfo", str(DEM_PATH)], check=True)

# =========================
# Recorte eficiente por ventana + mask
# =========================

"""
Esta parte del script no funcionó rasterio.mask.mask() crea una máscara rasterizada con el 
tamaño del raster de entrada, y geometry_mask/rasterize termina reservando un array del tamaño
 de out_shape; por eso vuelve a intentar crear ~19.7 GiB en memoria.

Rasterio documenta que el trabajo por ventanas ayuda con rasters mayores que la RAM, 
pero aquí el problema es que la propia ventana sigue siendo demasiado grande para que mask() 
rasterice la geometría completa de una sola vez.

Flujo actual hace esto:
-descarga ZIP,
-extrae .hgt,
-crea un mosaico TIFF grande,
-intenta recortarlo con rasterio.mask(). - se rompe todo

Solución

Usar GDAL para el recorte

Para este caso, es la salida más práctica y robusta. En flujos GIS grandes, gdalwarp con -cutline 
suele manejar mejor el recorte de rasters grandes que rasterio.mask.mask() en memoria. Rasterio existe 
sobre GDAL, pero aquí el binding de alto nivel te está llevando a una operación demasiado pesada en RAM.

El flujo sería:

-conservar tus ZIP y HGT,
-crear un VRT o mantener el mosaico,
-recortar con gdalwarp -cutline venezuela.geojson -crop_to_cutline.

Eso suele evitar esta explosión de memoria porque GDAL procesa por bloques.

Código
CREAR VRT
gdalbuildvrt data/processed/venezuela.vrt data/raw_extracted/*.hgt
RECORTAR VRT CON GEOJSON
gdalwarp \
  -cutline data/vectors/venezuela.geojson \
  -crop_to_cutline \
  -dstnodata -9999 \
  -of GTiff \
  data/processed/venezuela.vrt \
  data/processed/venezuela_dem.tif
REVISAR LA SALIDA
gdalinfo data/processed/venezuela_dem.tif | head -40


Este codigo funciona y fue integrado al script principal
"""
