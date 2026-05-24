// app.js — Venezuela ABRAE Land Cover Change Dashboard (MapLibre + PMTiles)

const METRICS = {
  forest_loss_ha: {
    label: "Pérdida de bosque comparable (ha)",
    shortLabel: "Pérdida de bosque",
    unit: "ha",
    colorScale: ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "loss",
  },
  forest_loss_pct: {
    label: "Pérdida de bosque comparable (%)",
    shortLabel: "Pérdida de bosque %",
    unit: "%",
    colorScale: ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"],
    format: v => v.toFixed(2) + "%",
    cssClass: "loss",
  },
  agriculture_gain_ha: {
    label: "Ganancia agrícola comparable (ha)",
    shortLabel: "Ganancia agrícola",
    unit: "ha",
    colorScale: ["#ffffd4", "#fed98e", "#fe9929", "#d95f0e", "#993404"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "gain",
  },
  urban_gain_ha: {
    label: "Expansión urbana comparable (ha)",
    shortLabel: "Expansión urbana",
    unit: "ha",
    colorScale: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "loss",
  },
};

const BASEMAP_TILES = {
  dark: "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
  satellite: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
};

let geojsonData = null;
let boundaryData = null;
let summaryByType = null;
let rankingsData = null;

let map = null;
let popup = null;
let currentMetric = "forest_loss_ha";
let currentType = "all";

const metricSelect = document.getElementById("metric-select");
const typeSelect = document.getElementById("type-select");
const contextCard = document.getElementById("context-summary");
const detailCard = document.getElementById("detail-card");
const legendEl = document.getElementById("map-legend");

async function loadData() {
  const base = getBasePath();

  const [geoRes, boundRes, typeRes, rankRes] = await Promise.all([
    fetch(`${base}data/abrae_web.geojson`).then(r => r.json()),
    fetch(`${base}data/venezuela_boundary.geojson`).then(r => r.json()),
    fetch(`${base}data/summary_by_type.csv`).then(r => r.text()),
    fetch(`${base}data/rankings.csv`).then(r => r.text()),
  ]);

  geojsonData = geoRes;
  boundaryData = boundRes;
  summaryByType = parseCSV(typeRes);
  rankingsData = parseCSV(rankRes);

  populateTypeFilter();
}

function getBasePath() {
  const path = window.location.pathname;
  if (path.includes("/src/")) {
    return path.substring(0, path.indexOf("/src/") + 5);
  }
  return path.endsWith("/") ? path : path.substring(0, path.lastIndexOf("/") + 1);
}

function parseCSV(text) {
  const lines = text.trim().split("\n");
  const headers = lines[0].split(",");

  return lines.slice(1).map(line => {
    const values = line.split(",");
    const obj = {};

    headers.forEach((h, i) => {
      const value = values[i];
      const cleanKey = h.trim();

      if (value === "true") {
        obj[cleanKey] = true;
      } else if (value === "false") {
        obj[cleanKey] = false;
      } else {
        obj[cleanKey] = isNaN(value) || value === "" ? value : parseFloat(value);
      }
    });

    return obj;
  });
}

function initPMTiles() {
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
}

function initMap() {
  map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        basemap: {
          type: "raster",
          tiles: [BASEMAP_TILES.dark],
          tileSize: 256,
          maxzoom: 18,
          attribution: "© CARTO · © Esri",
        },
        labels: {
          type: "raster",
          tiles: ["https://basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png"],
          tileSize: 256,
          maxzoom: 18,
        },
      },
      layers: [
        { id: "basemap", type: "raster", source: "basemap" },
        { id: "labels", type: "raster", source: "labels", layout: { visibility: "none" } },
      ],
    },
    center: [-66, 7.5],
    zoom: 5.5,
    minZoom: 4,
    maxZoom: 14,
    attributionControl: false,
  });

  map.addControl(new maplibregl.NavigationControl(), "top-left");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

  popup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    maxWidth: "280px",
  });

  map.on("load", () => {
    addBoundaryLayer();
    addRasterSources();
    addAbraeLayer();
    setupMapInteractions();
    setupToggleButtons();
    setupLayerControl();
    renderLegend();
    updateContext();
  });
}

function addBoundaryLayer() {
  map.addSource("boundary", {
    type: "geojson",
    data: boundaryData,
  });

  map.addLayer({
    id: "boundary-line",
    type: "line",
    source: "boundary",
    paint: {
      "line-color": "#4a5568",
      "line-width": 1.5,
      "line-dasharray": [3, 2],
    },
  });
}

function addRasterSources() {
  const base = getBasePath();

  ["lc2017", "lc2024"].forEach(name => {
    map.addSource(name, {
      type: "raster",
      url: `pmtiles://${window.location.origin}${base}data/rasters/${name}.pmtiles`,
      tileSize: 256,
    });
  });
}

function addAbraeLayer() {
  const filtered = filterFeatures();
  const colorExpr = buildColorExpression();

  map.addSource("abraes", {
    type: "geojson",
    data: filtered,
  });

  map.addLayer({
    id: "abraes-fill",
    type: "fill",
    source: "abraes",
    paint: {
      "fill-color": colorExpr,
      "fill-opacity": 0.75,
    },
  });

  map.addLayer({
    id: "abraes-outline",
    type: "line",
    source: "abraes",
    paint: {
      "line-color": "#3a4048",
      "line-width": 0.8,
    },
  });

  map.addLayer({
    id: "abraes-highlight",
    type: "line",
    source: "abraes",
    paint: {
      "line-color": "#f0f2f4",
      "line-width": 2,
    },
    filter: ["==", "SITE_ID", ""],
  });
}

function buildColorExpression() {
  const cfg = METRICS[currentMetric];
  const scale = getColorScale(currentMetric);

  if (scale.max === 0) return "#1a1e22";

  const steps = cfg.colorScale.length;
  const interval = scale.max / steps;
  const expr = ["step", ["coalesce", ["get", currentMetric], 0], "#1a1e22"];

  cfg.colorScale.forEach((color, i) => {
    expr.push(i === 0 ? 0.01 : interval * i, color);
  });

  return expr;
}

function filterFeatures() {
  const features = currentType === "all"
    ? geojsonData.features
    : geojsonData.features.filter(f => f.properties.DESIG === currentType);

  return { type: "FeatureCollection", features };
}

function updateAbraeLayer() {
  map.getSource("abraes").setData(filterFeatures());
  map.setPaintProperty("abraes-fill", "fill-color", buildColorExpression());
  renderLegend();
  updateContext();
}

function setupMapInteractions() {
  map.on("mousemove", "abraes-fill", (e) => {
    map.getCanvas().style.cursor = "pointer";

    const p = e.features[0].properties;
    const cfg = METRICS[currentMetric];
    const val = p[currentMetric] || 0;

    popup.setLngLat(e.lngLat).setHTML(
      `<div class="tt-name">${p.NAME_ENG}</div>` +
      `<div class="tt-type">${p.DESIG}</div>` +
      `<div class="tt-metric ${cfg.cssClass}">${cfg.label}: ${cfg.format(val)}</div>` +
      `<div class="tt-quality">Área comparable: ${fmtPct(p.valid_common_pct)}</div>` +
      `${p.cloud_contamination_flag ? `<div class="tt-warning">Revisar: diferencia de nubes/no-data</div>` : ""}`
    ).addTo(map);

    map.setFilter("abraes-highlight", ["==", "SITE_ID", p.SITE_ID]);
  });

  map.on("mouseleave", "abraes-fill", () => {
    map.getCanvas().style.cursor = "";
    popup.remove();
    map.setFilter("abraes-highlight", ["==", "SITE_ID", ""]);
  });

  map.on("click", "abraes-fill", (e) => {
    showDetail(e.features[0].properties);
  });
}

function setupToggleButtons() {
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const layerName = btn.dataset.layer;
      const layerId = `${layerName}-raster`;

      if (map.getLayer(layerId)) {
        const vis = map.getLayoutProperty(layerId, "visibility");
        const newVis = vis === "none" ? "visible" : "none";

        map.setLayoutProperty(layerId, "visibility", newVis);
        btn.classList.toggle("active", newVis === "visible");
      } else {
        map.addLayer({
          id: layerId,
          type: "raster",
          source: layerName,
          paint: { "raster-opacity": 0.7 },
          layout: { visibility: "visible" },
        }, "abraes-fill");

        btn.classList.add("active");
      }

      syncCheckbox(layerName, btn.classList.contains("active"));
      updateRasterLegend();
    });
  });
}

function syncCheckbox(layerName, checked) {
  const year = layerName.replace("lc", "");
  const checkbox = document.getElementById(`lc-${year}`);

  if (checkbox) checkbox.checked = checked;
}

function setupLayerControl() {
  const toggle = document.getElementById("layer-control-toggle");
  const panel = document.getElementById("layer-control-panel");

  toggle.addEventListener("click", () => panel.classList.toggle("hidden"));

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".layer-control")) {
      panel.classList.add("hidden");
    }
  });

  document.querySelectorAll('input[name="basemap"]').forEach(radio => {
    radio.addEventListener("change", () => {
      map.getSource("basemap").setTiles([BASEMAP_TILES[radio.value]]);

      map.setLayoutProperty(
        "labels",
        "visibility",
        radio.value === "satellite" ? "visible" : "none"
      );
    });
  });

  document.getElementById("lc-abraes").addEventListener("change", (e) => {
    const vis = e.target.checked ? "visible" : "none";

    ["abraes-fill", "abraes-outline", "abraes-highlight"].forEach(id => {
      map.setLayoutProperty(id, "visibility", vis);
    });
  });

  ["2017", "2024"].forEach(year => {
    document.getElementById(`lc-${year}`).addEventListener("change", (e) => {
      const layerName = `lc${year}`;
      const layerId = `${layerName}-raster`;
      const btn = document.querySelector(`.toggle-btn[data-layer="${layerName}"]`);

      if (e.target.checked) {
        if (!map.getLayer(layerId)) {
          map.addLayer({
            id: layerId,
            type: "raster",
            source: layerName,
            paint: { "raster-opacity": 0.7 },
            layout: { visibility: "visible" },
          }, "abraes-fill");
        } else {
          map.setLayoutProperty(layerId, "visibility", "visible");
        }

        btn.classList.add("active");
      } else {
        if (map.getLayer(layerId)) {
          map.setLayoutProperty(layerId, "visibility", "none");
        }

        btn.classList.remove("active");
      }

      updateRasterLegend();
    });
  });
}

function getColorScale(metricKey) {
  const values = geojsonData.features
    .map(f => f.properties[metricKey] || 0)
    .filter(v => v > 0);

  if (values.length === 0) return { min: 0, max: 0 };

  const sorted = [...values].sort((a, b) => a - b);
  const max = sorted[Math.floor(sorted.length * 0.95)] || sorted[sorted.length - 1];

  return { min: 0, max };
}

function renderLegend() {
  const cfg = METRICS[currentMetric];
  const scale = getColorScale(currentMetric);
  const gradient = cfg.colorScale.join(", ");

  legendEl.innerHTML = `
    <div class="legend-title">${cfg.label}</div>
    <div class="legend-scale">
      <div class="legend-bar" style="background: linear-gradient(to right, ${gradient})"></div>
    </div>
    <div class="legend-labels">
      <span>${cfg.format(scale.min)}</span>
      <span>${cfg.format(scale.max)}</span>
    </div>
  `;
}

function updateRasterLegend() {
  const anyActive = ["lc2017", "lc2024"].some(name => {
    const layer = map.getLayer(`${name}-raster`);

    return layer && map.getLayoutProperty(`${name}-raster`, "visibility") !== "none";
  });

  document.getElementById("raster-legend").classList.toggle("hidden", !anyActive);
}

function updateContext() {
  const cfg = METRICS[currentMetric];
  const features = filterFeatures().features;
  const values = features.map(f => f.properties[currentMetric] || 0);
  const total = values.reduce((a, b) => a + b, 0);
  const affected = values.filter(v => v > 0).length;
  const flagged = features.filter(f => f.properties.cloud_contamination_flag).length;
  const typeLabel = currentType === "all" ? "todas las ABRAEs" : currentType;

  let text = `<strong>${affected}</strong> de ${features.length} ${typeLabel} registran `;

  if (currentMetric.includes("loss")) {
    text += `pérdida de bosque sobre área comparable, con un total de <span class="metric-highlight">${cfg.format(total)} ha.</span>`;
  } else if (currentMetric.includes("agriculture")) {
    text += `ganancia agrícola sobre área comparable, totalizando <span class="metric-highlight">${cfg.format(total)} ha</span>.`;
  } else if (currentMetric.includes("urban")) {
    text += `expansión urbana sobre área comparable, totalizando <span class="metric-highlight">${cfg.format(total)} ha</span>.`;
  }

  text += `<br><span class="context-note">
    Las métricas se calculan solo con píxeles observados como válidos tanto en 2017 como en 2024.
    ${flagged > 0 ? `${flagged} ABRAE tienen alerta por diferencia de nubes/no-data.` : ""}
  </span>`;

  contextCard.innerHTML = text;
}

function showDetail(props) {
  detailCard.classList.remove("hidden");

  document.getElementById("detail-name").textContent = props.NAME_ENG;
  document.getElementById("detail-type").textContent = props.DESIG;

  document.getElementById("detail-metrics").innerHTML = `
    <div class="detail-metric">
      <span class="label">Bosque 2017</span>
      <span class="value">${fmt(props.forest_2017_ha)} ha</span>
    </div>

    <div class="detail-metric">
      <span class="label">Bosque 2024</span>
      <span class="value">${fmt(props.forest_2024_ha)} ha</span>
    </div>

    <div class="detail-metric">
      <span class="label">Cambio neto</span>
      <span class="value ${props.forest_loss_ha > 0 ? 'loss' : 'gain'}">
        ${props.forest_loss_ha > 0
          ? '-' + fmt(props.forest_loss_ha) + ' ha (' + props.forest_loss_pct + '%)'
          : '+' + fmt(props.forest_2024_ha - props.forest_2017_ha) + ' ha'}
      </span>
    </div>

    <div class="detail-metric">
      <span class="label">Área comparable</span>
      <span class="value">${fmt(props.total_area_ha)} ha</span>
    </div>

    <div class="detail-metric">
      <span class="label">Ganancia agrícola</span>
      <span class="value">${fmt(props.agriculture_gain_ha)} ha</span>
    </div>

    <div class="detail-metric">
      <span class="label">Expansión urbana</span>
      <span class="value">${fmt(props.urban_gain_ha)} ha</span>
    </div>

    <div class="detail-metric">
      <span class="label">Comparabilidad</span>
      <span class="value">${fmtPct(props.valid_common_pct)}</span>
    </div>

    <div class="detail-metric">
      <span class="label">Excluido nube/no-data</span>
      <span class="value">${fmtPct(props.excluded_pct)}</span>
    </div>

    <div class="detail-quality ${reliabilityClass(props)}">
      <span class="label">Confiabilidad temporal</span>
      <span class="value">${reliabilityLabel(props)}</span>
      <small>
        ${props.cloud_contamination_flag
          ? "Esta ABRAE presenta diferencias relevantes de nubes/no-data entre años. Interpretar el cambio con cautela."
          : "La comparación temporal presenta alta cobertura válida común."}
      </small>
    </div>
  `;

  Plotly.newPlot("chart-detail-comparison", [{
    x: ["Bosque 2017", "Bosque 2024"],
    y: [props.forest_2017_ha, props.forest_2024_ha],
    type: "bar",
    marker: { color: ["#2ecc71", "#27ae60"] },
    text: [fmt(props.forest_2017_ha), fmt(props.forest_2024_ha)],
    textposition: "auto",
    textfont: { color: "#f0f2f4", size: 11 },
  }], {
    ...chartLayout(),
    height: 160,
    margin: { t: 8, b: 30, l: 40, r: 8 },
    yaxis: { ...chartLayout().yaxis, title: "" },
  }, { displayModeBar: false, responsive: true });
}

function reliabilityLabel(props) {
  return props.cloud_contamination_flag ? "Revisar" : "Alta";
}

function reliabilityClass(props) {
  return props.cloud_contamination_flag ? "warning" : "ok";
}

function fmt(v) {
  return (v || 0).toLocaleString("es-VE", { maximumFractionDigits: 0 });
}

function fmtPct(v) {
  return (v ?? 0).toLocaleString("es-VE", {
    maximumFractionDigits: 2,
  }) + "%";
}

function renderCharts() {
  renderRankingChart();
  renderTypeChart();
}

function chartLayout() {
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "DM Sans", color: "#d8dce0", size: 11 },
    margin: { t: 8, b: 40, l: 120, r: 16 },
    xaxis: { gridcolor: "#2a3038", zerolinecolor: "#2a3038" },
    yaxis: { gridcolor: "#2a3038", zerolinecolor: "#2a3038", automargin: true },
  };
}

function renderRankingChart() {
  const cfg = METRICS[currentMetric];

  document.getElementById("ranking-title").textContent = cfg.shortLabel;

  const scope = currentType === "all" ? "national" : currentType;

  let data = rankingsData.filter(
    r => r.metric === currentMetric && r.rank_scope === scope
  );

  if (data.length === 0) {
    const features = filterFeatures().features;

    data = features
      .map(f => f.properties)
      .filter(p => (p[currentMetric] || 0) > 0)
      .sort((a, b) => b[currentMetric] - a[currentMetric])
      .slice(0, 10);
  }

  const top10 = data.slice(0, 10).reverse();
  const names = top10.map(d => truncate(d.NAME_ENG, 35));
  const values = top10.map(d => d[currentMetric] || 0);

  Plotly.newPlot("chart-ranking", [{
    y: names,
    x: values,
    type: "bar",
    orientation: "h",
    marker: { color: cfg.colorScale[3] },
    text: values.map(v => cfg.format(v)),
    textposition: "auto",
    textfont: { color: "#f0f2f4", size: 10 },
    hovertemplate: "%{y}: %{x}<extra></extra>",
  }], {
    ...chartLayout(),
    height: Math.max(220, top10.length * 28),
    margin: { ...chartLayout().margin, l: 180 },
  }, { displayModeBar: false, responsive: true });
}

function renderTypeChart() {
  if (!summaryByType || summaryByType.length === 0) return;

  const cfg = METRICS[currentMetric];
  let metricKey = currentMetric;

  if (!summaryByType[0].hasOwnProperty(metricKey) && metricKey === "forest_loss_pct") {
    summaryByType.forEach(d => {
      d.forest_loss_pct = d.forest_2017_ha > 0
        ? (d.forest_loss_ha / d.forest_2017_ha * 100)
        : 0;
    });
  }

  const sorted = [...summaryByType]
    .filter(d => (d[metricKey] || 0) > 0)
    .sort((a, b) => b[metricKey] - a[metricKey]);

  Plotly.newPlot("chart-by-type", [{
    y: sorted.map(d => truncate(d.DESIG, 30)),
    x: sorted.map(d => d[metricKey] || 0),
    type: "bar",
    orientation: "h",
    marker: { color: cfg.colorScale[2] },
    text: sorted.map(d => cfg.format(d[metricKey] || 0)),
    textposition: "auto",
    textfont: { color: "#f0f2f4", size: 10 },
    hovertemplate: "%{y}: %{x}<extra></extra>",
  }], {
    ...chartLayout(),
    height: Math.max(180, sorted.length * 36),
  }, { displayModeBar: false, responsive: true });
}

function truncate(str, n) {
  return str && str.length > n ? str.substring(0, n - 1) + "…" : str;
}

function populateTypeFilter() {
  const types = [...new Set(geojsonData.features.map(f => f.properties.DESIG))].sort();

  types.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  });
}

metricSelect.addEventListener("change", () => {
  currentMetric = metricSelect.value;
  updateAbraeLayer();
  renderCharts();
});

typeSelect.addEventListener("change", () => {
  currentType = typeSelect.value;
  updateAbraeLayer();
  renderCharts();
});

document.getElementById("close-detail").addEventListener("click", () => {
  detailCard.classList.add("hidden");
});

async function init() {
  initPMTiles();
  await loadData();
  initMap();
  renderCharts();
}

init();