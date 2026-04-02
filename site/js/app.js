/**
 * app.js - Main application logic for WooGraph viewer
 */

import { loadGraphData, loadStats } from './data-loader.js';
import { initGraphView, updateLayout } from './graph-view.js';
import { initFilters, initSearch } from './filters.js';
import { initDetailPanel } from './detail-panel.js';
import { loadGeocodedData, initMapView, renderMapMarkers, invalidateMapSize } from './map-view.js';

// Store full data globally so filters can rebuild the graph
let allNodes = [];
let allEdges = [];
let entityTypes = new Map();
let currentCy = null;

// Map state
let mapInitialized = false;
let geocodedData = null;
let placeEdgeIndex = null;  // Map<placeId, Set<placeId>>

async function main() {
  const graphContainer = document.getElementById('cy');
  const loadingOverlay = document.getElementById('loading');

  // Tab switching
  setupTabs();

  // Layout selector
  setupLayoutSelector();

  // Load data
  const [graphData, stats] = await Promise.all([
    loadGraphData(),
    loadStats(),
  ]);

  allNodes = graphData.nodes;
  allEdges = graphData.edges;
  entityTypes = graphData.entityTypes;

  // Update stats bar
  updateStatsBar(stats, graphData);

  // Hide loading
  if (loadingOverlay) {
    loadingOverlay.style.display = 'none';
  }

  // Check for empty graph
  if (allNodes.length === 0) {
    showEmptyState(graphContainer);
    return;
  }

  // Pre-compute degree for each node
  const nodeDegree = new Map();
  for (const edge of allEdges) {
    const src = edge.data.source;
    const tgt = edge.data.target;
    nodeDegree.set(src, (nodeDegree.get(src) || 0) + 1);
    nodeDegree.set(tgt, (nodeDegree.get(tgt) || 0) + 1);
  }
  // Attach degree to node data
  for (const node of allNodes) {
    node.data.degree = nodeDegree.get(node.data.id) || 0;
  }

  // Build place-to-place edge index (used by map view)
  placeEdgeIndex = buildPlaceEdgeIndex();

  // Initial render with degree filter
  const defaultMinDegree = parseInt(document.getElementById('degree-slider')?.value || '3');
  renderGraph(graphContainer, defaultMinDegree, 0);

  // Set up filters (they call renderGraph on change)
  initFilters(null, entityTypes, renderGraph.bind(null, graphContainer));

  // Initialize search (works on current cy instance via ref)
  initSearch({ get: () => currentCy });
}

/**
 * Build an index of place-to-place co-occurrence edges.
 * @returns {Map<string, Set<string>>}
 */
function buildPlaceEdgeIndex() {
  const placeIds = new Set(allNodes.filter(n => n.data.type === 'Place').map(n => n.data.id));
  const index = new Map();
  for (const edge of allEdges) {
    const src = edge.data.source;
    const tgt = edge.data.target;
    if (!placeIds.has(src) || !placeIds.has(tgt)) continue;
    if (!index.has(src)) index.set(src, new Set());
    if (!index.has(tgt)) index.set(tgt, new Set());
    index.get(src).add(tgt);
    index.get(tgt).add(src);
  }
  return index;
}

/**
 * Render the graph with only the elements that pass the filters.
 * Recreates the Cytoscape instance each time (faster than hiding 4000 nodes).
 */
function renderGraph(container, minDegree, minConfidence, activeTypes = null) {
  // Filter nodes
  const filteredNodes = allNodes.filter(n => {
    if (activeTypes && !activeTypes.has(n.data.type)) return false;
    return n.data.degree >= minDegree;
  });
  const visibleIds = new Set(filteredNodes.map(n => n.data.id));

  // Filter edges: both ends visible + confidence threshold
  const filteredEdges = allEdges.filter(e => {
    if (!visibleIds.has(e.data.source) || !visibleIds.has(e.data.target)) return false;
    return (e.data.confidence || 0) >= minConfidence;
  });

  // Update visible count in stats bar
  const visibleCount = document.getElementById('stat-visible');
  if (visibleCount) {
    visibleCount.textContent = `${filteredNodes.length} / ${allNodes.length}`;
  }

  const elements = [...filteredNodes, ...filteredEdges];

  if (currentCy) {
    currentCy.destroy();
  }
  currentCy = initGraphView(container, elements);
  initDetailPanel(currentCy);

  // Update map if it's initialized — show all Place nodes regardless of degree filter
  if (mapInitialized && geocodedData) {
    const mapPlaceNodes = allNodes.filter(n =>
      n.data.type === 'Place' && (!activeTypes || activeTypes.has('Place'))
    );
    renderMapMarkers(mapPlaceNodes, geocodedData, placeEdgeIndex, filteredEdges);
  }
}

async function initMap() {
  console.log('[map] initMap start, allNodes:', allNodes.length);
  const loadingMsg = document.getElementById('map-loading');
  if (loadingMsg) loadingMsg.style.display = 'block';

  try {
    initMapView();
  } catch (err) {
    console.error('[map] initMapView threw:', err);
    return;
  }
  geocodedData = await loadGeocodedData();
  console.log('[map] geocodedData loaded:', !!geocodedData, geocodedData?.stats);

  if (loadingMsg) loadingMsg.style.display = 'none';

  if (!geocodedData) {
    const container = document.getElementById('map-container');
    if (container) {
      container.innerHTML = '<div class="map-error">Geocoded data not available. Run <code>woograph geocode</code> to generate.</div>';
    }
    return;
  }

  // Map shows all Place nodes — degree filter doesn't apply here (geographic exploration)
  // Only respect the type toggle in case user explicitly hides Place type
  const activeTypesEl = document.querySelectorAll('#type-filters input[type=checkbox]:checked');
  const activeTypes = activeTypesEl.length > 0
    ? new Set([...activeTypesEl].map(el => el.value))
    : null;

  const placeNodes = allNodes.filter(n =>
    n.data.type === 'Place' && (!activeTypes || activeTypes.has('Place'))
  );

  renderMapMarkers(placeNodes, geocodedData, placeEdgeIndex, allEdges);
  mapInitialized = true;

  // Wire up "View in graph" popup links via event delegation
  document.getElementById('map-container')?.addEventListener('click', e => {
    const link = e.target.closest('.popup-graph-link');
    if (!link) return;
    e.preventDefault();
    const nodeId = link.dataset.nodeId;
    if (!nodeId) return;
    // Switch to graph tab and highlight node
    document.querySelector('.tab-nav button[data-tab="graph-view"]')?.click();
    if (currentCy) {
      const node = currentCy.getElementById(nodeId);
      if (node.length) {
        currentCy.animate({ fit: { eles: node, padding: 80 } }, { duration: 400 });
        node.select();
      }
    }
  });
}

function setupTabs() {
  const tabs = document.querySelectorAll('.tab-nav button[data-tab]');
  const panels = document.querySelectorAll('.view-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', async () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      panels.forEach(p => {
        p.classList.toggle('active', p.id === target);
      });

      if (target === 'map-view') {
        if (!mapInitialized) {
          await initMap();
        } else {
          invalidateMapSize();
        }
      }
    });
  });
}

function setupLayoutSelector() {
  const selector = document.getElementById('layout-select');
  if (!selector) return;

  selector.addEventListener('change', () => {
    updateLayout(selector.value);
  });
}

function updateStatsBar(stats, graphData) {
  const entityCount = document.getElementById('stat-entities');
  const relCount = document.getElementById('stat-relationships');
  const sourceCount = document.getElementById('stat-sources');

  if (entityCount) {
    entityCount.textContent = stats.total_entities || graphData.nodes.length || 0;
  }
  if (relCount) {
    relCount.textContent = stats.total_relationships || graphData.edges.length || 0;
  }
  if (sourceCount) {
    sourceCount.textContent = stats.total_sources || 0;
  }
}

function showEmptyState(container) {
  container.innerHTML = `
    <div class="empty-state">
      <div class="icon">&#x1f578;</div>
      <h2>No graph data yet</h2>
      <p>
        Submit source documents to build the knowledge graph.
        Entities and relationships will appear here once processed.
      </p>
    </div>
  `;
}

// Start app
main().catch(err => {
  console.error('Failed to initialize WooGraph:', err);
});
