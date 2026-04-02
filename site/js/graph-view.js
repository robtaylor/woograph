/**
 * graph-view.js - Cytoscape.js network visualization
 */

const LAYOUT_OPTIONS = {
  cose: {
    name: 'cose',
    animate: false,
    nodeRepulsion: 10000,
    idealEdgeLength: 80,
    gravity: 0.5,
    numIter: 300,
    padding: 30,
    nodeOverlap: 20,
    randomize: true,
  },
  circle: {
    name: 'circle',
    animate: false,
    padding: 40,
  },
  grid: {
    name: 'grid',
    animate: false,
    padding: 40,
  },
  breadthfirst: {
    name: 'breadthfirst',
    animate: false,
    padding: 40,
    spacingFactor: 1.25,
  },
  concentric: {
    name: 'concentric',
    animate: false,
    padding: 30,
    minNodeSpacing: 30,
    concentric: function(node) { return node.data('degree') || 0; },
    levelWidth: function() { return 3; },
  },
};

let cyInstance = null;

/**
 * Initialize Cytoscape graph in the given container.
 * @param {HTMLElement} container - DOM element to render into
 * @param {Array} elements - Cytoscape elements (nodes + edges)
 * @returns {Object} Cytoscape instance
 */
export function initGraphView(container, elements) {
  if (cyInstance) {
    cyInstance.destroy();
  }

  /* global cytoscape */
  cyInstance = cytoscape({
    container,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'label': '',
          'background-color': 'data(color)',
          'width': 'data(size)',
          'height': 'data(size)',
          'border-width': 1,
          'border-color': 'data(color)',
          'border-opacity': 0.3,
          'overlay-padding': 4,
        },
      },
      // Show labels via class (ensures color is always set together)
      {
        selector: 'node.show-label, node[degree >= 10]',
        style: {
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#e8e8e8',
          'text-outline-color': '#1a1a2e',
          'text-outline-width': 1.5,
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 4,
        },
      },
      {
        selector: 'node:active, node:selected',
        style: {
          'label': 'data(label)',
          'font-size': '11px',
          'color': '#ffffff',
          'text-outline-color': '#1a1a2e',
          'text-outline-width': 2,
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 5,
          'border-width': 4,
          'border-color': '#ffffff',
          'border-opacity': 1,
        },
      },
      {
        selector: 'edge',
        style: {
          'width': 'data(width)',
          'line-color': '#3a3a5a',
          'target-arrow-color': '#3a3a5a',
          'target-arrow-shape': 'triangle',
          'curve-style': 'haystack',
          'opacity': 'data(opacity)',
          'arrow-scale': 0.6,
        },
      },
      {
        selector: 'edge.show-label, edge:selected',
        style: {
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#8888aa',
          'text-outline-color': '#1a1a2e',
          'text-outline-width': 1.5,
          'text-rotation': 'autorotate',
        },
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': '#4FC3F7',
          'target-arrow-color': '#4FC3F7',
          'opacity': 1,
        },
      },
      // Dimmed state for non-highlighted elements
      {
        selector: '.dimmed',
        style: {
          'opacity': 0.15,
        },
      },
      // Highlighted neighbors
      {
        selector: '.highlighted',
        style: {
          'opacity': 1,
        },
      },
      // Hidden by filter
      {
        selector: '.hidden',
        style: {
          'display': 'none',
        },
      },
    ],
    layout: LAYOUT_OPTIONS.cose,
    minZoom: 0.1,
    maxZoom: 5,
    wheelSensitivity: 0.3,
  });

  // Hover: highlight connected nodes and show labels via classes
  cyInstance.on('mouseover', 'node', (evt) => {
    const node = evt.target;
    const neighborhood = node.closedNeighborhood();
    cyInstance.batch(() => {
      cyInstance.elements().addClass('dimmed');
      neighborhood.removeClass('dimmed').addClass('highlighted show-label');
    });
  });

  cyInstance.on('mouseout', 'node', () => {
    cyInstance.batch(() => {
      cyInstance.elements().removeClass('dimmed highlighted show-label');
    });
  });

  return cyInstance;
}

/**
 * Update the graph layout.
 * @param {string} layoutName - One of: cose, circle, grid, breadthfirst
 */
export function updateLayout(layoutName) {
  if (!cyInstance) return;
  const options = LAYOUT_OPTIONS[layoutName] || LAYOUT_OPTIONS.cose;
  cyInstance.layout(options).run();
}

/**
 * Get the current Cytoscape instance.
 */
export function getCy() {
  return cyInstance;
}

export { LAYOUT_OPTIONS };
