// app.js — Venezuela ABRAE Land Cover Change Dashboard

const METRICS = {
  forest_loss_ha: {
    label: "Pérdida de bosque (ha)",
    shortLabel: "Pérdida de bosque",
    unit: "ha",
    colorScale: ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "loss",
  },
  forest_loss_pct: {
    label: "Pérdida de bosque (%)",
    shortLabel: "Pérdida de bosque %",
    unit: "%",
    colorScale: ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"],
    format: v => v.toFixed(2) + "%",
    cssClass: "loss",
  },
  agriculture_gain_ha: {
    label: "Ganancia agrícola (ha)",
    shortLabel: "Ganancia agrícola",
    unit: "ha",
    colorScale: ["#ffffd4", "#fed98e", "#fe9929", "#d95f0e", "#993404"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "gain",
  },
  urban_gain_ha: {
    label: "Expansión urbana (ha)",
    shortLabel: "Expansión urbana",
    unit: "ha",
    colorScale: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#756bb1", "#54278f"],
    format: v => v.toLocaleString("es-VE", { maximumFractionDigits: 0 }),
    cssClass: "loss",
  },
};

// State
let geojsonData = null;
let boundaryData = null;
let summaryByType = null;
let rankingsData = null;

let map = null;
let abraeLayer = null;
let boundaryLayer = null;
let rasterLayers = {};
let layerControl = null;

let currentMetric = "forest_loss_ha";
let currentType = "all";

// DOM
const metricSelect = document.getElementById("metric-select");
const typeSelect = document.getElementById("type-select");
const contextCard = document.getElementById("context-summary");
const detailCard = document.getElementById("detail-card");
const legendEl = document.getElementById("map-legend");

// Data loading
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
  if (path.includes("/src/")) return path.substring(0, path.indexOf("/src/") + 5);
  return path.endsWith("/") ? path : path.substring(0, path.lastIndexOf("/") + 1);
}

function parseCSV(text) {
  const lines = text.trim().split("\n");
  const headers = lines[0].split(",");
  return lines.slice(1).map(line => {
    const values = line.split(",");
    const obj = {};
    headers.forEach((h, i) => {
      const v = values[i];
      obj[h.trim()] = isNaN(v) || v === "" ? v : parseFloat(v);
    });
    return obj;
  });
}

// Map
function initMap() {
  map = L.map("map", {
    center: [7.5, -66],
    zoom: 6,
    zoomControl: true,
    attributionControl: false,
  });

  // Basemaps
  const basemaps = {
    "Oscuro": L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
      { maxZoom: 18 }
    ),
    "Satélite": L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 18 }
    ),
  };

  basemaps["Oscuro"].addTo(map);

  // Labels always on top
  L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png",
    { maxZoom: 18, pane: "tooltipPane" }
  ).addTo(map);

  L.control.attribution({ position: "bottomright", prefix: false })
    .addAttribution('© <a href="https://carto.com/">CARTO</a> · © <a href="https://www.esri.com/">Esri</a>')
    .addTo(map);

  // Venezuela boundary (always on map, not in layer control)
  boundaryLayer = L.geoJSON(boundaryData, {
    style: {
      color: "#4a5568",
      weight: 1.5,
      fill: false,
      dashArray: "4 3",
    },
  }).addTo(map);

  // Raster tile layers
  const base = getBasePath();
  rasterLayers.lc2017 = L.tileLayer(
    `${base}data/rasters/lc2017/{z}/{x}/{y}.png`,
    { opacity: 0.7, maxZoom: 10, minZoom: 5, tms: true }
  );
  rasterLayers.lc2024 = L.tileLayer(
    `${base}data/rasters/lc2024/{z}/{x}/{y}.png`,
    { opacity: 0.7, maxZoom: 10, minZoom: 5, tms: true }
  );

  // Render ABRAEs before creating layer control
  renderAbraeLayer();

  // Layer control (no boundary)
  const overlays = {
    "ABRAEs": abraeLayer,
    "Cobertura 2017": rasterLayers.lc2017,
    "Cobertura 2024": rasterLayers.lc2024,
  };

  layerControl = L.control.layers(basemaps, overlays, {
    collapsed: true,
    position: "topright",
  }).addTo(map);

  // Sync toolbar toggle buttons with raster layers
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const layerName = btn.dataset.layer;
      const layer = rasterLayers[layerName];
      if (!layer) return;

      if (map.hasLayer(layer)) {
        map.removeLayer(layer);
        btn.classList.remove("active");
      } else {
        layer.addTo(map);
        btn.classList.add("active");
        if (abraeLayer && map.hasLayer(abraeLayer)) abraeLayer.bringToFront();
      }
    });
  });

  // Sync buttons when layers toggled from Leaflet control
  map.on("overlayadd", (e) => {
    if (abraeLayer && map.hasLayer(abraeLayer)) abraeLayer.bringToFront();
    document.querySelectorAll(".toggle-btn").forEach(btn => {
      const layer = rasterLayers[btn.dataset.layer];
      if (layer && e.layer === layer) btn.classList.add("active");
    });
  });

  map.on("overlayremove", (e) => {
    document.querySelectorAll(".toggle-btn").forEach(btn => {
      const layer = rasterLayers[btn.dataset.layer];
      if (layer && e.layer === layer) btn.classList.remove("active");
    });
  });
}

// Color scale
function getColorScale(metricKey) {
  const cfg = METRICS[metricKey];
  const values = geojsonData.features
    .map(f => f.properties[metricKey] || 0)
    .filter(v => v > 0);

  if (values.length === 0) return { getColor: () => "#333", min: 0, max: 0, colors: cfg.colorScale };

  const sorted = [...values].sort((a, b) => a - b);
  const max = sorted[Math.floor(sorted.length * 0.95)] || sorted[sorted.length - 1];

  return {
    getColor(value) {
      if (value <= 0) return "#1a1e22";
      const t = Math.min(value / max, 1);
      const idx = Math.min(Math.floor(t * (cfg.colorScale.length - 1)), cfg.colorScale.length - 2);
      const frac = t * (cfg.colorScale.length - 1) - idx;
      return lerpColor(cfg.colorScale[idx], cfg.colorScale[idx + 1], frac);
    },
    min: 0,
    max,
    colors: cfg.colorScale,
  };
}

function lerpColor(a, b, t) {
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  return `rgb(${Math.round(ar + (br - ar) * t)},${Math.round(ag + (bg - ag) * t)},${Math.round(ab + (bb - ab) * t)})`;
}

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// ABRAE layer
function renderAbraeLayer() {
  const wasVisible = abraeLayer ? map.hasLayer(abraeLayer) : true;

  if (abraeLayer) {
    if (layerControl) layerControl.removeLayer(abraeLayer);
    map.removeLayer(abraeLayer);
  }

  const scale = getColorScale(currentMetric);
  const cfg = METRICS[currentMetric];

  const filteredData = {
    type: "FeatureCollection",
    features: currentType === "all"
      ? geojsonData.features
      : geojsonData.features.filter(f => f.properties.DESIG === currentType),
  };

  abraeLayer = L.geoJSON(filteredData, {
    style(feature) {
      const val = feature.properties[currentMetric] || 0;
      return {
        fillColor: scale.getColor(val),
        fillOpacity: 0.75,
        color: "#3a4048",
        weight: 0.8,
      };
    },
    onEachFeature(feature, layer) {
      const p = feature.properties;
      const val = p[currentMetric] || 0;

      layer.bindTooltip(
        `<div class="tt-name">${p.NAME_ENG}</div>` +
        `<div class="tt-type">${p.DESIG}</div>` +
        `<div class="tt-metric ${cfg.cssClass}">${cfg.label}: ${cfg.format(val)}</div>`,
        { className: "abrae-tooltip", sticky: true }
      );

      layer.on("click", () => showDetail(p));

      layer.on("mouseover", function () {
        this.setStyle({ weight: 2, color: "#f0f2f4", fillOpacity: 0.9 });
        this.bringToFront();
      });

      layer.on("mouseout", function () {
        abraeLayer.resetStyle(this);
      });
    },
  });

  if (wasVisible) abraeLayer.addTo(map);
  if (layerControl) layerControl.addOverlay(abraeLayer, "ABRAEs");

  renderLegend(scale, cfg);
  updateContext(filteredData.features);
}

// Legend
function renderLegend(scale, cfg) {
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

// Context summary
function updateContext(features) {
  const cfg = METRICS[currentMetric];
  const values = features.map(f => f.properties[currentMetric] || 0);
  const total = values.reduce((a, b) => a + b, 0);
  const affected = values.filter(v => v > 0).length;
  const typeLabel = currentType === "all" ? "todas las ABRAEs" : currentType;

  let text = `<strong>${affected}</strong> de ${features.length} ${typeLabel} registran `;

  if (currentMetric.includes("loss")) {
    text += `pérdida de bosque, con un total de <span class="metric-highlight">${cfg.format(total)} ha.</span>`;
  } else if (currentMetric.includes("agriculture")) {
    text += `ganancia de superficie agrícola, totalizando <span class="metric-highlight">${cfg.format(total)} ha</span>.`;
  } else if (currentMetric.includes("urban")) {
    text += `expansión urbana, totalizando <span class="metric-highlight">${cfg.format(total)} ha</span>.`;
  }

  contextCard.innerHTML = text;
}

// Detail card
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
      <span class="label">Pérdida</span>
      <span class="value loss">${fmt(props.forest_loss_ha)} ha (${props.forest_loss_pct}%)</span>
    </div>
    <div class="detail-metric">
      <span class="label">Área total</span>
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

function fmt(v) {
  return (v || 0).toLocaleString("es-VE", { maximumFractionDigits: 0 });
}

// Charts
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
    const features = currentType === "all"
      ? geojsonData.features
      : geojsonData.features.filter(f => f.properties.DESIG === currentType);

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

// Filters
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
  renderAbraeLayer();
  renderCharts();
});

typeSelect.addEventListener("change", () => {
  currentType = typeSelect.value;
  renderAbraeLayer();
  renderCharts();
});

document.getElementById("close-detail").addEventListener("click", () => {
  detailCard.classList.add("hidden");
});

// Init
async function init() {
  await loadData();
  initMap();
  renderCharts();
}

init();