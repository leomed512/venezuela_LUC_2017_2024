#!/usr/bin/env python3
"""
============================================================
ANÁLISIS DE COBERTURA Y CAMBIO - VENEZUELA 2017-2024
Sentinel-2 10m Land Use/Land Cover (ESRI Living Atlas)
============================================================
Entrada: rasters reproyectados a Albers (output del script .sh)
============================================================
"""

import numpy as np
import pandas as pd
import rasterio
from collections import Counter
from pathlib import Path

# --- CONFIGURACIÓN ---
BASE = Path.home() / "Documents/data_analysis/venezuela_landcover/output"
RASTER_2017 = BASE / "venezuela_landcover_2017.tif"
RASTER_2024 = BASE / "venezuela_landcover_2024.tif"
OUTPUT_DIR = BASE / "resultados"
OUTPUT_DIR.mkdir(exist_ok=True)

# Clases ESRI Sentinel-2 Land Use/Land Cover
CLASES = {
    0: "Sin dato",
    1: "Water",
    2: "Trees",
    3: "No data",
    4: "Flooded Vegetation",
    5: "Crops",
    6: "No data",
    7: "Built Area",
    8: "Bare Ground",
    9: "Snow/Ice",  
    10: "Clouds",  
    11: "Rangeland"
}

# Resolución del píxel en la proyección Albers (metros)
RESOLUCION_M = 10


def calcular_cobertura(ruta_raster):
    """
    Cuenta píxeles por clase leyendo el raster por bloques.
    No carga todo en RAM — apto para rasters de varios GB.
    """
    conteo = Counter()

    with rasterio.open(ruta_raster) as src:
        print(f"  Raster: {src.width} x {src.height} píxeles")
        print(f"  CRS: {src.crs}")
        print(f"  Resolución: {src.res[0]:.2f} x {src.res[1]:.2f} m")

        nodata = src.nodata
        total_bloques = len(list(src.block_windows(1)))

        for i, (ji, window) in enumerate(src.block_windows(1)):
            bloque = src.read(1, window=window)

            # Excluir NoData
            if nodata is not None:
                bloque = bloque[bloque != nodata]

            valores, conteos = np.unique(bloque, return_counts=True)
            for val, cnt in zip(valores, conteos):
                conteo[int(val)] += int(cnt)

            # Progreso cada 500 bloques
            if (i + 1) % 500 == 0 or (i + 1) == total_bloques:
                print(f"  Procesados {i + 1}/{total_bloques} bloques...")

    return conteo


def conteo_a_dataframe(conteo, año, resolucion_m=RESOLUCION_M):
    """Convierte conteo de píxeles a DataFrame con áreas en km² y hectáreas."""
    area_pixel_km2 = (resolucion_m ** 2) / 1e6  # 0.0001 km² por píxel
    area_pixel_ha = (resolucion_m ** 2) / 1e4    # 0.01 ha por píxel

    filas = []
    for clase_id, pixeles in sorted(conteo.items()):
        nombre = CLASES.get(clase_id, f"Clase {clase_id}")
        filas.append({
            "clase_id": clase_id,
            "clase": nombre,
            "pixeles": pixeles,
            "area_km2": round(pixeles * area_pixel_km2, 2),
            "area_ha": round(pixeles * area_pixel_ha, 2),
        })

    df = pd.DataFrame(filas)
    total_area = df["area_km2"].sum()
    df["porcentaje"] = round(df["area_km2"] / total_area * 100, 2)
    df["año"] = año

    return df


def calcular_matriz_transicion(ruta_2017, ruta_2024, resolucion_m=RESOLUCION_M):
    """
    Calcula la matriz de transición entre 2017 y 2024.
    Lee ambos rasters por bloques simultáneamente.
    """
    area_pixel_km2 = (resolucion_m ** 2) / 1e6
    transiciones = Counter()

    with rasterio.open(ruta_2017) as src17, rasterio.open(ruta_2024) as src24:
        # Verificar que las grillas coincidan
        assert src17.shape == src24.shape, \
            f"Las dimensiones no coinciden: {src17.shape} vs {src24.shape}"
        assert src17.transform == src24.transform, \
            "Los transforms no coinciden — los rasters no están alineados"

        nodata_17 = src17.nodata
        nodata_24 = src24.nodata
        total_bloques = len(list(src17.block_windows(1)))

        for i, (ji, window) in enumerate(src17.block_windows(1)):
            bloque_17 = src17.read(1, window=window)
            bloque_24 = src24.read(1, window=window)

            # Crear máscara combinada de datos válidos
            mascara = np.ones(bloque_17.shape, dtype=bool)
            if nodata_17 is not None:
                mascara &= (bloque_17 != nodata_17)
            if nodata_24 is not None:
                mascara &= (bloque_24 != nodata_24)

            v17 = bloque_17[mascara]
            v24 = bloque_24[mascara]

            for val17, val24 in zip(v17, v24):
                transiciones[(int(val17), int(val24))] += 1

            if (i + 1) % 500 == 0 or (i + 1) == total_bloques:
                print(f"  Procesados {i + 1}/{total_bloques} bloques...")

    # Construir la matriz como DataFrame
    clases_presentes = sorted(set(
        [k[0] for k in transiciones.keys()] +
        [k[1] for k in transiciones.keys()]
    ))

    matriz = pd.DataFrame(0.0, index=clases_presentes, columns=clases_presentes)
    for (c17, c24), conteo in transiciones.items():
        matriz.loc[c17, c24] = round(conteo * area_pixel_km2, 2)

    # Renombrar índices con nombres de clase
    nombres = {cid: CLASES.get(cid, f"Clase {cid}") for cid in clases_presentes}
    matriz.index = [nombres[c] for c in clases_presentes]
    matriz.columns = [nombres[c] for c in clases_presentes]

    return matriz


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ANÁLISIS DE COBERTURA - VENEZUELA")
    print("=" * 60)

    # --- Fase 3: Calcular áreas por clase ---
    print("\n--- Calculando cobertura 2017 ---")
    conteo_2017 = calcular_cobertura(RASTER_2017)
    df_2017 = conteo_a_dataframe(conteo_2017, 2017)

    print("\n--- Calculando cobertura 2024 ---")
    conteo_2024 = calcular_cobertura(RASTER_2024)
    df_2024 = conteo_a_dataframe(conteo_2024, 2024)

    # Tabla comparativa
    comp = df_2017[["clase_id", "clase", "area_km2", "porcentaje"]].merge(
        df_2024[["clase_id", "area_km2", "porcentaje"]],
        on="clase_id",
        suffixes=("_2017", "_2024"),
        how="outer"
    ).fillna(0)

    comp["cambio_km2"] = comp["area_km2_2024"] - comp["area_km2_2017"]
    comp["cambio_pct"] = round(
        (comp["area_km2_2024"] - comp["area_km2_2017"]) /
        comp["area_km2_2017"].replace(0, np.nan) * 100, 2
    )

    # Mostrar resultados
    print("\n" + "=" * 60)
    print("COBERTURA 2017")
    print("=" * 60)
    print(df_2017[["clase", "area_km2", "area_ha", "porcentaje"]]
          .to_string(index=False))

    print("\n" + "=" * 60)
    print("COBERTURA 2024")
    print("=" * 60)
    print(df_2024[["clase", "area_km2", "area_ha", "porcentaje"]]
          .to_string(index=False))

    print("\n" + "=" * 60)
    print("CAMBIOS 2017 → 2024")
    print("=" * 60)
    print(comp[["clase", "area_km2_2017", "area_km2_2024", "cambio_km2", "cambio_pct"]]
          .to_string(index=False))

    # Guardar CSVs
    df_2017.to_csv(OUTPUT_DIR / "cobertura_2017.csv", index=False)
    df_2024.to_csv(OUTPUT_DIR / "cobertura_2024.csv", index=False)
    comp.to_csv(OUTPUT_DIR / "comparacion_2017_2024.csv", index=False)
    print(f"\nTablas guardadas en {OUTPUT_DIR}/")

    # --- Fase 4: Matriz de transición ---
    print("\n" + "=" * 60)
    print("CALCULANDO MATRIZ DE TRANSICIÓN")
    print("=" * 60)
    matriz = calcular_matriz_transicion(RASTER_2017, RASTER_2024)

    matriz.to_csv(OUTPUT_DIR / "matriz_transicion_km2.csv")
    print(f"\nMatriz guardada en {OUTPUT_DIR}/matriz_transicion_km2.csv")

    print("\n" + "=" * 60)
    print("PROCESO COMPLETO")
    print("=" * 60)
    print(f"\nArchivos generados en {OUTPUT_DIR}/:")
    print("  - cobertura_2017.csv")
    print("  - cobertura_2024.csv")
    print("  - comparacion_2017_2024.csv")
    print("  - matriz_transicion_km2.csv")