/**
 * app.js - Main application logic for WooGraph viewer
 */

import { loadGraphData, loadStats } from './data-loader.js';
import { initGraphView, updateLayout } from './graph-view.js';
import { initFilters, initSearch } from './filters.js';
import { initDetailPanel } from './detail-panel.js';

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

  // Update stats bar
  updateStatsBar(stats, graphData);

  // Hide loading
  if (loadingOverlay) {
    loadingOverlay.style.display = 'none';
  }

  // Check for empty graph
  if (graphData.nodes.length === 0) {
    showEmptyState(graphContainer);
    return;
  }

  // Initialize Cytoscape
  const elements = [...graphData.nodes, ...graphData.edges];
  const cy = initGraphView(graphContainer, elements);

  // Initialize filters
  initFilters(cy, graphData.entityTypes);

  // Initialize search
  initSearch(cy);

  // Initialize detail panel
  initDetailPanel(cy);
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
