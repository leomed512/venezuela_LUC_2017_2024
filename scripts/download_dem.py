from pathlib import Path
import zipfile
import subprocess
import shutil

import earthaccess
import geopandas as gpd

# Paths
# ----------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "data" / "raw" /"venezuela.geojson"
RAW_DIR = BASE_DIR / "data" / "raw" / "dem" / "raw"
EXTRACT_DIR = BASE_DIR / "data" / "raw" / "dem" / "raw_extracted"
PROCESSED_DIR = BASE_DIR / "data" / "processed" / "dem"

RAW_DIR.mkdir(parents=True, exist_ok=True)
EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

VRT_PATH = PROCESSED_DIR / "venezuela.vrt"
DEM_PATH = PROCESSED_DIR / "venezuela_dem.tif"


# Read GeoJSON
# ----------------------------------------------
gdf = gpd.read_file(GEOJSON_PATH)

if gdf.empty:
    raise RuntimeError("El GeoJSON está vacío.")

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")
elif gdf.crs != "EPSG:4326":
    gdf = gdf.to_crs("EPSG:4326")

bbox = tuple(gdf.total_bounds)
print("BBOX:", bbox)


# Login Earthdata
# ----------------------------------------------
earthaccess.login(strategy="interactive") #Login with earthdata credentials


# Search NASADEM granules
# ----------------------------------------------
granules = earthaccess.search_data(
    short_name="NASADEM_HGT",
    version="001",
    bounding_box=bbox
)

print(f"Tiles found: {len(granules)}")

# Download ZIP files
# ----------------------------------------------

# Check if there's already files
existing_zips = {p.name for p in RAW_DIR.glob("*.zip")}
granules_to_download = []

for g in granules:
    links = g.data_links()
    if not links:
        continue

    filename = links[0].split("/")[-1]
    if filename not in existing_zips:
        granules_to_download.append(g)

if granules_to_download:
    downloaded_files = earthaccess.download(
        granules_to_download,
        local_path=str(RAW_DIR)
    )
    print(f"Downloaded files: {len(downloaded_files)}")
else:
    print("All files already in storage.")


# Unzip files 
# ----------------------------------------------
zip_files = sorted(RAW_DIR.glob("*.zip"))

for zip_path in zip_files:
    expected_hgt = EXTRACT_DIR / zip_path.name.replace(".zip", ".hgt")
    if expected_hgt.exists():
        continue

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(EXTRACT_DIR)

print("Unziping completed")

hgt_files = sorted(EXTRACT_DIR.rglob("*.hgt"))
print(f"Extracted HGT: {len(hgt_files)}")

if not hgt_files:
    raise RuntimeError("No .hgt files found")


# Create VRT 
# ----------------------------------------------

if VRT_PATH.exists():
    print("VRT already exists, will be used.")
else:
    cmd_vrt = ["gdalbuildvrt", str(VRT_PATH)] + [str(fp) for fp in hgt_files]
    subprocess.run(cmd_vrt, check=True)
    print("VRT created:", VRT_PATH)


# Create Clipped DEM
# ----------------------------------------------
if DEM_PATH.exists():
    print("DEM exists, will be used.")
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
    subprocess.run(cmd_warp, check=True)
    print("DEM ready:", DEM_PATH)

# Validation
# ----------------------------------------------
subprocess.run(["gdalinfo", str(DEM_PATH)], check=True)

