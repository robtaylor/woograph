/**
 * filters.js - Entity type filtering and confidence threshold
 */

import { TYPE_COLORS } from './data-loader.js';

/**
 * Initialize filter controls in the sidebar.
 * @param {Object} cy - Cytoscape instance
 * @param {Map} entityTypes - Map of type name to count
 */
export function initFilters(cy, entityTypes) {
  const filterContainer = document.getElementById('type-filters');
  const confidenceSlider = document.getElementById('confidence-slider');
  const confidenceValue = document.getElementById('confidence-value');
  const selectAllBtn = document.getElementById('filter-select-all');
  const selectNoneBtn = document.getElementById('filter-select-none');

  if (!filterContainer) return;

  // Track active types
  const activeTypes = new Set(entityTypes.keys());

  // Build filter checkboxes
  filterContainer.innerHTML = '';
  const sortedTypes = [...entityTypes.entries()].sort((a, b) => b[1] - a[1]);

  for (const [type, count] of sortedTypes) {
    const color = TYPE_COLORS[type] || TYPE_COLORS.Thing;
    const item = document.createElement('div');
    item.className = 'filter-item';
    item.innerHTML = `
      <input type="checkbox" id="filter-${type}" checked data-type="${type}">
      <span class="color-dot" style="background: ${color}"></span>
      <label for="filter-${type}">${type}</label>
      <span class="count">${count}</span>
    `;
    filterContainer.appendChild(item);

    const checkbox = item.querySelector('input');
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        activeTypes.add(type);
      } else {
        activeTypes.delete(type);
      }
      applyFilters(cy, activeTypes, parseFloat(confidenceSlider?.value || '0'), parseInt(document.getElementById('degree-slider')?.value || '0'));
    });
  }

  // Select All / None
  if (selectAllBtn) {
    selectAllBtn.addEventListener('click', () => {
      filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
        activeTypes.add(cb.dataset.type);
      });
      applyFilters(cy, activeTypes, parseFloat(confidenceSlider?.value || '0'), parseInt(document.getElementById('degree-slider')?.value || '0'));
    });
  }

  if (selectNoneBtn) {
    selectNoneBtn.addEventListener('click', () => {
      filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
        activeTypes.delete(cb.dataset.type);
      });
      applyFilters(cy, activeTypes, parseFloat(confidenceSlider?.value || '0'), parseInt(document.getElementById('degree-slider')?.value || '0'));
    });
  }

  // Confidence threshold
  if (confidenceSlider) {
    confidenceSlider.addEventListener('input', () => {
      const val = parseFloat(confidenceSlider.value);
      if (confidenceValue) {
        confidenceValue.textContent = val.toFixed(2);
      }
      applyFilters(cy, activeTypes, val, parseInt(degreeSlider?.value || '0'));
    });
  }

  // Min connections (degree) filter
  const degreeSlider = document.getElementById('degree-slider');
  const degreeValue = document.getElementById('degree-value');

  if (degreeSlider) {
    // Apply initial degree filter
    applyFilters(cy, activeTypes, parseFloat(confidenceSlider?.value || '0'), parseInt(degreeSlider.value));

    degreeSlider.addEventListener('input', () => {
      const val = parseInt(degreeSlider.value);
      if (degreeValue) {
        degreeValue.textContent = val;
      }
      applyFilters(cy, activeTypes, parseFloat(confidenceSlider?.value || '0'), val);
    });
  }
}

/**
 * Apply type, confidence, and degree filters to the graph.
 */
function applyFilters(cy, activeTypes, minConfidence, minDegree = 0) {
  cy.batch(() => {
    // First pass: determine node visibility by type
    cy.nodes().forEach(node => {
      const type = node.data('type');
      node.data('typeVisible', activeTypes.has(type));
    });

    // Second pass: calculate visible degree for each node
    // (count edges where both ends pass the type filter and confidence threshold)
    const visibleDegree = new Map();
    cy.edges().forEach(edge => {
      const confidence = edge.data('confidence') || 0;
      if (confidence < minConfidence) return;
      if (!edge.source().data('typeVisible') || !edge.target().data('typeVisible')) return;
      visibleDegree.set(edge.source().id(), (visibleDegree.get(edge.source().id()) || 0) + 1);
      visibleDegree.set(edge.target().id(), (visibleDegree.get(edge.target().id()) || 0) + 1);
    });

    // Third pass: apply all filters
    cy.nodes().forEach(node => {
      const typeOk = node.data('typeVisible');
      const degree = visibleDegree.get(node.id()) || 0;
      const degreeOk = degree >= minDegree;
      if (typeOk && degreeOk) {
        node.removeClass('hidden');
      } else {
        node.addClass('hidden');
      }
    });

    // Filter edges by confidence and node visibility
    cy.edges().forEach(edge => {
      const confidence = edge.data('confidence') || 0;
      const sourceVisible = !edge.source().hasClass('hidden');
      const targetVisible = !edge.target().hasClass('hidden');
      if (sourceVisible && targetVisible && confidence >= minConfidence) {
        edge.removeClass('hidden');
      } else {
        edge.addClass('hidden');
      }
    });
  });
}

/**
 * Set up the search box to highlight matching nodes.
 * @param {Object} cy - Cytoscape instance
 */
export function initSearch(cy) {
  const searchInput = document.getElementById('search-input');
  if (!searchInput) return;

  let debounceTimer = null;

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const query = searchInput.value.trim().toLowerCase();

      if (!query) {
        // Clear search highlights
        cy.elements().removeClass('dimmed highlighted');
        return;
      }

      // Find matching nodes
      const matching = cy.nodes().filter(node => {
        const label = (node.data('label') || '').toLowerCase();
        const aliases = (node.data('aliases') || []).map(a => a.toLowerCase());
        return label.includes(query) || aliases.some(a => a.includes(query));
      });

      if (matching.length > 0) {
        const neighborhood = matching.closedNeighborhood();
        cy.elements().addClass('dimmed');
        neighborhood.removeClass('dimmed').addClass('highlighted');
        matching.removeClass('dimmed').addClass('highlighted');
      } else {
        cy.elements().removeClass('dimmed highlighted');
      }
    }, 200);
  });
}
