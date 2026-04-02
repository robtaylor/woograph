/**
 * map-view.js - Leaflet geographic visualization of Place entities
 */

/* global L */

let map = null;
let markerClusterGroup = null;
let connectionLayer = null;
let showConnections = false;

/**
 * Load geocoded.json (lazy, called once on first map tab activation).
 * @returns {Promise<Object|null>}
 */
export async function loadGeocodedData() {
  try {
    const resp = await fetch('data/geocoded.json');
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

/**
 * Initialize the Leaflet map in the #map-container element.
 * Safe to call multiple times — only initializes once.
 */
export function initMapView() {
  if (map) return;

  const container = document.getElementById('map-container');
  if (!container) return;

  map = L.map('map-container', {
    center: [20, 0],
    zoom: 2,
    minZoom: 1,
    maxZoom: 18,
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // Marker cluster group (fall back to plain LayerGroup if plugin not loaded)
  if (typeof L.markerClusterGroup === 'function') {
    markerClusterGroup = L.markerClusterGroup({
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      zoomToBoundsOnClick: true,
    });
  } else {
    markerClusterGroup = L.layerGroup();
  }
  map.addLayer(markerClusterGroup);

  // Connection lines layer
  connectionLayer = L.layerGroup().addTo(map);

  // Toggle connections button
  const toggleBtn = document.getElementById('map-toggle-connections');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      showConnections = !showConnections;
      toggleBtn.textContent = showConnections ? 'Hide connections' : 'Show connections';
      toggleBtn.classList.toggle('active', showConnections);
      // Re-render will happen via _renderConnections call
      if (_lastRenderArgs) {
        _renderConnections(..._lastRenderArgs);
      }
    });
  }
}

// Store last render args so toggle can re-render
let _lastRenderArgs = null;

/**
 * Re-render markers and optional connection lines.
 * Called by app.js whenever filters change.
 *
 * @param {Array} placeNodes - Place nodes passing current filters (from allNodes)
 * @param {Object} geocoded - geocoded.json data
 * @param {Map} placeEdgeIndex - Map<placeId, Set<placeId>> of place-place edges
 * @param {Array} allEdges - all edges for connection data
 */
export function renderMapMarkers(placeNodes, geocoded, placeEdgeIndex, allEdges) {
  if (!map || !geocoded) return;

  _lastRenderArgs = [placeNodes, geocoded, placeEdgeIndex, allEdges];

  const places = geocoded.places || {};

  // Build markers
  markerClusterGroup.clearLayers();

  const visibleMarkers = [];

  for (const node of placeNodes) {
    const geo = places[node.data.id];
    if (!geo) continue;

    const marker = _createMarker(node, geo, placeEdgeIndex, allEdges);
    markerClusterGroup.addLayer(marker);
    visibleMarkers.push({ node, geo });
  }

  // Update stats overlay
  const countEl = document.getElementById('map-place-count');
  if (countEl) countEl.textContent = visibleMarkers.length;

  _renderConnections(visibleMarkers, geocoded, placeEdgeIndex);
}

function _renderConnections(visibleMarkers, geocoded, placeEdgeIndex) {
  if (!connectionLayer) return;
  connectionLayer.clearLayers();
  if (!showConnections || !placeEdgeIndex) return;

  const places = geocoded.places || {};
  const drawn = new Set();

  for (const { node, geo } of visibleMarkers) {
    const neighbors = placeEdgeIndex.get(node.data.id);
    if (!neighbors) continue;

    for (const neighborId of neighbors) {
      const key = [node.data.id, neighborId].sort().join('|');
      if (drawn.has(key)) continue;
      drawn.add(key);

      const neighborGeo = places[neighborId];
      if (!neighborGeo) continue;

      L.polyline(
        [[geo.lat, geo.lng], [neighborGeo.lat, neighborGeo.lng]],
        { color: '#81C784', weight: 1.5, opacity: 0.35 }
      ).addTo(connectionLayer);
    }
  }
}

function _createMarker(node, geo, placeEdgeIndex, allEdges) {
  const icon = L.divIcon({
    className: 'place-marker-icon',
    html: `<div class="place-marker" style="width:${_markerSize(node)}px;height:${_markerSize(node)}px"></div>`,
    iconSize: [_markerSize(node), _markerSize(node)],
    iconAnchor: [_markerSize(node) / 2, _markerSize(node) / 2],
  });

  const marker = L.marker([geo.lat, geo.lng], { icon });
  marker.bindPopup(() => _buildPopup(node, geo, placeEdgeIndex, allEdges), {
    maxWidth: 320,
    minWidth: 200,
  });
  return marker;
}

function _markerSize(node) {
  const mentions = node.data.mentionCount || 0;
  return Math.min(24, Math.max(8, 8 + mentions));
}

function _buildPopup(node, geo, placeEdgeIndex, allEdges) {
  const name = node.data.label || node.data.id;
  const displayName = geo.display_name || '';
  const shortDisplay = displayName.split(',').slice(0, 3).join(',');

  // Sources
  const mentionedIn = node.data.mentionedIn || [];
  const sourceList = mentionedIn.slice(0, 5)
    .map(s => {
      const srcId = typeof s === 'string' ? s : (s['@id'] || '');
      const label = srcId.split(':').pop().replace(/-/g, ' ');
      return `<li>${_escHtml(label)}</li>`;
    })
    .join('');
  const moreCount = mentionedIn.length > 5 ? `<li><em>+${mentionedIn.length - 5} more</em></li>` : '';

  // Connected places
  const neighbors = placeEdgeIndex ? (placeEdgeIndex.get(node.data.id) || new Set()) : new Set();
  const neighborItems = [...neighbors].slice(0, 4)
    .map(nid => {
      // Count shared edges
      const shared = (allEdges || []).filter(e =>
        (e.data.source === node.data.id && e.data.target === nid) ||
        (e.data.target === node.data.id && e.data.source === nid)
      ).length;
      const label = nid.split(':').pop().replace(/-/g, ' ');
      return `<li>${_escHtml(label)}${shared > 0 ? ` <small>(${shared})</small>` : ''}</li>`;
    })
    .join('');

  const viewInGraph = `<a href="#" class="popup-graph-link" data-node-id="${_escHtml(node.data.id)}">View in graph →</a>`;

  return `
    <div class="map-popup">
      <h4>${_escHtml(name)}</h4>
      <p class="popup-location">${_escHtml(shortDisplay)}</p>
      ${mentionedIn.length > 0 ? `
        <div class="popup-section">
          <strong>Sources (${mentionedIn.length}):</strong>
          <ul>${sourceList}${moreCount}</ul>
        </div>` : ''}
      ${neighborItems ? `
        <div class="popup-section">
          <strong>Connected places:</strong>
          <ul>${neighborItems}</ul>
        </div>` : ''}
      <div class="popup-footer">${viewInGraph}</div>
    </div>
  `;
}

function _escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Call after tab switch — Leaflet needs this when the container was hidden.
 */
export function invalidateMapSize() {
  if (map) {
    setTimeout(() => map.invalidateSize(), 50);
  }
}
