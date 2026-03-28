/**
 * graph-view.js - Cytoscape.js network visualization
 */

const LAYOUT_OPTIONS = {
  cose: {
    name: 'cose',
    animate: true,
    animationDuration: 500,
    nodeRepulsion: 8000,
    idealEdgeLength: 120,
    gravity: 0.25,
    numIter: 1000,
    padding: 40,
  },
  circle: {
    name: 'circle',
    animate: true,
    animationDuration: 500,
    padding: 40,
  },
  grid: {
    name: 'grid',
    animate: true,
    animationDuration: 500,
    padding: 40,
  },
  breadthfirst: {
    name: 'breadthfirst',
    animate: true,
    animationDuration: 500,
    padding: 40,
    spacingFactor: 1.25,
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
          'label': 'data(label)',
          'background-color': 'data(color)',
          'width': 'data(size)',
          'height': 'data(size)',
          'font-size': '10px',
          'color': '#e8e8e8',
          'text-outline-color': '#1a1a2e',
          'text-outline-width': 2,
          'text-valign': 'bottom',
          'text-halign': 'center',
          'text-margin-y': 6,
          'border-width': 2,
          'border-color': 'data(color)',
          'border-opacity': 0.4,
          'overlay-padding': 4,
          'transition-property': 'opacity, border-width',
          'transition-duration': '150ms',
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#ffffff',
          'border-opacity': 1,
        },
      },
      {
        selector: 'edge',
        style: {
          'label': 'data(label)',
          'width': 'data(width)',
          'line-color': '#4a4a6a',
          'target-arrow-color': '#4a4a6a',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'font-size': '9px',
          'color': '#8888aa',
          'text-outline-color': '#1a1a2e',
          'text-outline-width': 1.5,
          'text-rotation': 'autorotate',
          'opacity': 'data(opacity)',
          'arrow-scale': 0.8,
          'transition-property': 'opacity, line-color',
          'transition-duration': '150ms',
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

  // Hover: highlight connected nodes
  cyInstance.on('mouseover', 'node', (evt) => {
    const node = evt.target;
    const neighborhood = node.closedNeighborhood();
    cyInstance.elements().addClass('dimmed');
    neighborhood.removeClass('dimmed').addClass('highlighted');
  });

  cyInstance.on('mouseout', 'node', () => {
    cyInstance.elements().removeClass('dimmed highlighted');
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
