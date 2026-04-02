/**
 * filters.js - Entity type filtering, confidence threshold, degree filter
 *
 * Filters work by calling a renderGraph callback that rebuilds Cytoscape
 * with only the visible elements (much faster than CSS hiding for large graphs).
 */

import { TYPE_COLORS } from './data-loader.js';

let _renderCallback = null;
let _activeTypes = new Set();

/**
 * Initialize filter controls in the sidebar.
 * @param {Object|null} _cy - unused (kept for API compat)
 * @param {Map} entityTypes - Map of type name to count
 * @param {Function} renderCallback - function(minDegree, minConfidence, activeTypes)
 */
export function initFilters(_cy, entityTypes, renderCallback) {
  _renderCallback = renderCallback;

  const filterContainer = document.getElementById('type-filters');
  const confidenceSlider = document.getElementById('confidence-slider');
  const confidenceValue = document.getElementById('confidence-value');
  const degreeSlider = document.getElementById('degree-slider');
  const degreeValue = document.getElementById('degree-value');
  const selectAllBtn = document.getElementById('filter-select-all');
  const selectNoneBtn = document.getElementById('filter-select-none');

  if (!filterContainer) return;

  // Track active types
  _activeTypes = new Set(entityTypes.keys());

  // Build filter checkboxes
  filterContainer.innerHTML = '';
  const sortedTypes = [...entityTypes.entries()].sort((a, b) => b[1] - a[1]);

  for (const [type, count] of sortedTypes) {
    const color = TYPE_COLORS[type] || TYPE_COLORS.Thing;
    const item = document.createElement('div');
    item.className = 'filter-item';
    item.innerHTML = `
      <label>
        <input type="checkbox" data-type="${type}" checked>
        <span class="color-dot" style="background:${color}"></span>
        ${type} <span class="count">(${count})</span>
      </label>
    `;
    item.querySelector('input').addEventListener('change', (e) => {
      if (e.target.checked) {
        _activeTypes.add(type);
      } else {
        _activeTypes.delete(type);
      }
      triggerRender();
    });
    filterContainer.appendChild(item);
  }

  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
      filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
        _activeTypes.add(cb.dataset.type);
      });
      triggerRender();
    });
  }

  if (selectNoneBtn) {
    selectNoneBtn.addEventListener('click', () => {
      filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
        _activeTypes.delete(cb.dataset.type);
      });
      triggerRender();
    });
  }

  if (confidenceSlider) {
    confidenceSlider.addEventListener('input', () => {
      if (confidenceValue) {
        confidenceValue.textContent = parseFloat(confidenceSlider.value).toFixed(2);
      }
      triggerRender();
    });
  }

  if (degreeSlider) {
    degreeSlider.addEventListener('input', () => {
      if (degreeValue) {
        degreeValue.textContent = degreeSlider.value;
      }
      triggerRender();
    });
  }
}

function triggerRender() {
  if (!_renderCallback) return;
  const minDegree = parseInt(document.getElementById('degree-slider')?.value || '0');
  const minConfidence = parseFloat(document.getElementById('confidence-slider')?.value || '0');
  _renderCallback(minDegree, minConfidence, _activeTypes);
}

/**
 * Set up the search box to highlight matching nodes.
 * @param {Object} cyRef - object with .get() returning current Cytoscape instance
 */
export function initSearch(cyRef) {
  const searchInput = document.getElementById('search-input');
  if (!searchInput) return;

  let debounceTimer = null;

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const cy = cyRef.get();
      if (!cy) return;

      const query = searchInput.value.trim().toLowerCase();
      if (!query) {
        cy.elements().removeClass('dimmed highlighted');
        return;
      }

      cy.batch(() => {
        cy.elements().addClass('dimmed').removeClass('highlighted');
        const matches = cy.nodes().filter(n => {
          const label = (n.data('label') || '').toLowerCase();
          return label.includes(query);
        });
        matches.removeClass('dimmed').addClass('highlighted');
        matches.connectedEdges().removeClass('dimmed');
        matches.neighborhood().nodes().removeClass('dimmed');
      });
    }, 300);
  });
}
