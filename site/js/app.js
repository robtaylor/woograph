/**
 * app.js - Main application logic for WooGraph viewer
 */

import { loadGraphData, loadStats } from './data-loader.js';
import { initGraphView, updateLayout } from './graph-view.js';
import { initFilters, initSearch } from './filters.js';
import { initDetailPanel } from './detail-panel.js';

// Store full data globally so filters can rebuild the graph
let allNodes = [];
let allEdges = [];
let entityTypes = new Map();
let currentCy = null;

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

  // Initial render with degree filter
  const defaultMinDegree = parseInt(document.getElementById('degree-slider')?.value || '3');
  renderGraph(graphContainer, defaultMinDegree, 0);

  // Set up filters (they call renderGraph on change)
  initFilters(null, entityTypes, renderGraph.bind(null, graphContainer));

  // Initialize search (works on current cy instance)
  initSearch({ get: () => currentCy });

  // Initialize detail panel
  initDetailPanel({ get: () => currentCy });
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
  initDetailPanel({ get: () => currentCy });
}

function setupTabs() {
  const tabs = document.querySelectorAll('.tab-nav button[data-tab]');
  const panels = document.querySelectorAll('.view-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      panels.forEach(p => {
        p.classList.toggle('active', p.id === target);
      });
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
