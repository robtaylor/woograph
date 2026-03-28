/**
 * detail-panel.js - Node/edge detail sidebar
 */

import { TYPE_COLORS } from './data-loader.js';

/**
 * Initialize the detail panel click handlers.
 * @param {Object} cy - Cytoscape instance
 */
export function initDetailPanel(cy) {
  const layout = document.getElementById('app-layout');
  const panel = document.getElementById('detail-panel');
  const closeBtn = document.getElementById('detail-close');
  const detailBody = document.getElementById('detail-body');

  if (!panel || !detailBody) return;

  // Click node -> show entity detail
  cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    showNodeDetail(node.data(), detailBody);
    layout.classList.add('detail-open');
  });

  // Click edge -> show relationship detail
  cy.on('tap', 'edge', (evt) => {
    const edge = evt.target;
    showEdgeDetail(edge, detailBody);
    layout.classList.add('detail-open');
  });

  // Click background -> hide panel
  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      layout.classList.remove('detail-open');
    }
  });

  // Close button
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      layout.classList.remove('detail-open');
    });
  }
}

/**
 * Render entity (node) details into the panel.
 */
function showNodeDetail(data, container) {
  const color = data.color || TYPE_COLORS.Thing;
  const aliases = data.aliases || [];
  const mentionedIn = data.mentionedIn || [];

  let html = `
    <div class="entity-name">${escapeHtml(data.label)}</div>
    <span class="entity-type" style="background: ${color}22; color: ${color}; border: 1px solid ${color}44;">
      ${escapeHtml(data.type)}
    </span>
  `;

  // Aliases
  if (aliases.length > 0) {
    html += `
      <div class="detail-section">
        <h4>Aliases</h4>
        <div class="alias-list">
          ${aliases.map(a => `<span class="alias-tag">${escapeHtml(a)}</span>`).join('')}
        </div>
      </div>
    `;
  }

  // ID
  html += `
    <div class="detail-section">
      <h4>ID</h4>
      <code style="font-size: 11px; color: var(--text-muted); word-break: break-all;">${escapeHtml(data.id)}</code>
    </div>
  `;

  // Sources (mentionedIn)
  if (mentionedIn.length > 0) {
    html += `
      <div class="detail-section">
        <h4>Mentioned In (${mentionedIn.length} sources)</h4>
        <ul class="source-list">
          ${mentionedIn.map(src => {
            const sourceId = typeof src === 'string' ? src : (src['@id'] || '');
            const displayName = sourceId.replace(/^source:/, '').replace(/-/g, ' ');
            return `<li><a href="#" title="${escapeHtml(sourceId)}">${escapeHtml(displayName)}</a></li>`;
          }).join('')}
        </ul>
      </div>
    `;
  }

  // Stats
  html += `
    <div class="detail-section">
      <h4>Stats</h4>
      <div class="meta-row">
        <span>Mentions</span>
        <span>${data.mentionCount || 0}</span>
      </div>
    </div>
  `;

  container.innerHTML = html;
}

/**
 * Render relationship (edge) details into the panel.
 */
function showEdgeDetail(edge, container) {
  const data = edge.data();
  const sourceLabel = edge.source().data('label') || data.source;
  const targetLabel = edge.target().data('label') || data.target;
  const confidence = data.confidence || 0;
  const confidencePct = Math.round(confidence * 100);

  // Color the confidence bar
  let barColor = '#81C784'; // green
  if (confidence < 0.5) barColor = '#E57373'; // red
  else if (confidence < 0.75) barColor = '#FFB74D'; // orange

  const html = `
    <div style="font-size: 14px; font-weight: 500; color: var(--text-secondary); margin-bottom: 4px;">Relationship</div>
    <div class="edge-arrow">
      <span>${escapeHtml(sourceLabel)}</span>
      <span class="arrow">&rarr;</span>
      <strong>${escapeHtml(data.label)}</strong>
      <span class="arrow">&rarr;</span>
      <span>${escapeHtml(targetLabel)}</span>
    </div>
    <div class="detail-section">
      <h4>Confidence</h4>
      <div class="confidence-bar">
        <div class="fill" style="width: ${confidencePct}%; background: ${barColor};"></div>
      </div>
      <div class="meta-row">
        <span>${confidencePct}%</span>
        <span>${confidence.toFixed(2)}</span>
      </div>
    </div>
    <div class="detail-section">
      <h4>Predicate</h4>
      <code style="font-size: 11px; color: var(--text-muted);">${escapeHtml(data.predicate)}</code>
    </div>
    ${data.extractedBy ? `
      <div class="detail-section">
        <h4>Extracted By</h4>
        <span style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(data.extractedBy)}</span>
      </div>
    ` : ''}
  `;

  container.innerHTML = html;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
