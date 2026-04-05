/**
 * timeline-view.js - Horizontal timeline visualization of dated entities and sources
 *
 * Three zoom levels:
 *   0 = Decades: clustered dots with count badges
 *   1 = Years: small cards with titles
 *   2 = Months: full cards with thumbnails
 */

let timelineData = null;
let container = null;
let axisEl = null;
let itemsEl = null;
let zoomLevel = 0; // 0=decades, 1=years, 2=months
let currentFilters = null;

/**
 * Fetch timeline.json from the data directory.
 * @returns {Promise<Object|null>}
 */
export async function loadTimelineData() {
  try {
    const resp = await fetch('data/timeline.json');
    if (!resp.ok) return null;
    timelineData = await resp.json();
    return timelineData;
  } catch {
    return null;
  }
}

/**
 * Initialize the timeline DOM structure and event handlers.
 * Safe to call multiple times — only initializes once.
 */
export function initTimelineView() {
  container = document.getElementById('timeline-container');
  if (!container || container.dataset.initialized) return;
  container.dataset.initialized = 'true';

  // Create axis and items layers
  axisEl = document.createElement('div');
  axisEl.className = 'timeline-axis-layer';
  container.appendChild(axisEl);

  itemsEl = document.createElement('div');
  itemsEl.className = 'timeline-items-layer';
  container.appendChild(itemsEl);

  // Zoom controls
  const zoomSlider = document.getElementById('timeline-zoom');
  const zoomLabel = document.getElementById('timeline-range-label');
  const zoomIn = document.getElementById('timeline-zoom-in');
  const zoomOut = document.getElementById('timeline-zoom-out');

  const zoomLabels = ['Decades', 'Years', 'Months'];

  function setZoom(level) {
    zoomLevel = Math.max(0, Math.min(2, level));
    if (zoomSlider) zoomSlider.value = zoomLevel;
    if (zoomLabel) zoomLabel.textContent = zoomLabels[zoomLevel];
    renderTimeline();
  }

  if (zoomSlider) {
    zoomSlider.addEventListener('input', () => setZoom(parseInt(zoomSlider.value)));
  }
  if (zoomIn) zoomIn.addEventListener('click', () => setZoom(zoomLevel + 1));
  if (zoomOut) zoomOut.addEventListener('click', () => setZoom(zoomLevel - 1));

  // Scroll wheel zoom (ctrl/cmd + scroll)
  container.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      setZoom(zoomLevel + (e.deltaY < 0 ? 1 : -1));
    }
  }, { passive: false });
}

/**
 * Render or re-render the timeline with current data and filters.
 * @param {Object} [filters] - Optional filter state {activeTypes, minConfidence}
 */
export function renderTimeline(filters) {
  if (filters) currentFilters = filters;
  if (!timelineData || !container) return;

  const items = _filterItems(timelineData.items);
  if (items.length === 0) {
    itemsEl.innerHTML = '<div class="timeline-empty">No items match current filters</div>';
    axisEl.innerHTML = '';
    return;
  }

  const loadingEl = document.getElementById('timeline-loading');
  if (loadingEl) loadingEl.style.display = 'none';

  if (zoomLevel === 0) {
    _renderDecades(items);
  } else if (zoomLevel === 1) {
    _renderYears(items);
  } else {
    _renderMonths(items);
  }
}

/**
 * Filter items based on active entity type filters.
 */
function _filterItems(items) {
  if (!currentFilters || !currentFilters.activeTypes) return items;

  const types = currentFilters.activeTypes;
  return items.filter(item => {
    // Date items show when 'Date' type is active
    if (item.type === 'date') return types.has('Date');
    // Source items show when 'woo:Source' type is active (or always if not filtered)
    if (item.type === 'source') return types.has('woo:Source') || !types.size;
    return true;
  });
}

// ── Zoom Level 0: Decades ──────────────────────────────────────────────

function _renderDecades(items) {
  const decades = _groupByDecade(items);
  const decadeKeys = Object.keys(decades).map(Number).sort();

  const pxPerDecade = 160;
  const totalWidth = decadeKeys.length * pxPerDecade + 100;

  axisEl.innerHTML = '';
  itemsEl.innerHTML = '';
  axisEl.style.width = totalWidth + 'px';
  itemsEl.style.width = totalWidth + 'px';

  // Axis line
  const line = document.createElement('div');
  line.className = 'timeline-axis-line';
  axisEl.appendChild(line);

  decadeKeys.forEach((decade, i) => {
    const x = 50 + i * pxPerDecade;
    const group = decades[decade];

    // Tick + label
    const tick = document.createElement('div');
    tick.className = 'timeline-tick';
    tick.style.left = x + 'px';
    axisEl.appendChild(tick);

    const label = document.createElement('div');
    label.className = 'timeline-tick-label';
    label.style.left = x + 'px';
    label.textContent = decade + 's';
    axisEl.appendChild(label);

    // Cluster dot
    const cluster = document.createElement('div');
    cluster.className = 'timeline-cluster';
    cluster.style.left = x + 'px';
    cluster.style.width = Math.min(12 + group.length * 2, 40) + 'px';
    cluster.style.height = Math.min(12 + group.length * 2, 40) + 'px';
    cluster.title = `${decade}s: ${group.length} items`;

    const badge = document.createElement('span');
    badge.className = 'timeline-cluster-badge';
    badge.textContent = group.length;
    cluster.appendChild(badge);

    cluster.addEventListener('click', () => {
      // Zoom in to years and scroll to this decade
      const zoomSlider = document.getElementById('timeline-zoom');
      if (zoomSlider) zoomSlider.value = '1';
      zoomLevel = 1;
      const zoomLabel = document.getElementById('timeline-range-label');
      if (zoomLabel) zoomLabel.textContent = 'Years';
      renderTimeline();
      // Scroll to approximate position
      const yearIndex = decade - (timelineData.spans.min_year - timelineData.spans.min_year % 10);
      container.scrollLeft = Math.max(0, (yearIndex / 10) * 100 - container.clientWidth / 3);
    });

    itemsEl.appendChild(cluster);
  });
}

// ── Zoom Level 1: Years ────────────────────────────────────────────────

function _renderYears(items) {
  const minYear = timelineData.spans.min_year;
  const maxYear = timelineData.spans.max_year;
  const pxPerYear = 100;
  const totalWidth = (maxYear - minYear + 2) * pxPerYear + 100;

  axisEl.innerHTML = '';
  itemsEl.innerHTML = '';
  axisEl.style.width = totalWidth + 'px';
  itemsEl.style.width = totalWidth + 'px';

  // Axis line
  const line = document.createElement('div');
  line.className = 'timeline-axis-line';
  axisEl.appendChild(line);

  // Year ticks
  for (let y = minYear; y <= maxYear; y++) {
    const x = 50 + (y - minYear) * pxPerYear;
    const isDecade = y % 10 === 0;

    const tick = document.createElement('div');
    tick.className = 'timeline-tick' + (isDecade ? ' decade' : '');
    tick.style.left = x + 'px';
    axisEl.appendChild(tick);

    if (isDecade || y === minYear || y === maxYear) {
      const label = document.createElement('div');
      label.className = 'timeline-tick-label';
      label.style.left = x + 'px';
      label.textContent = y;
      axisEl.appendChild(label);
    }
  }

  // Items as small cards
  const byYear = {};
  items.forEach(item => {
    const y = item.year;
    if (!byYear[y]) byYear[y] = [];
    byYear[y].push(item);
  });

  Object.entries(byYear).forEach(([year, group]) => {
    const x = 50 + (year - minYear) * pxPerYear;

    group.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = 'timeline-card-small';
      // Alternate above/below axis
      const above = idx % 2 === 0;
      card.style.left = (x - 40) + 'px';
      card.style.bottom = above ? '55%' : 'auto';
      card.style.top = above ? 'auto' : '55%';
      card.style.marginTop = above ? '0' : (idx * 4) + 'px';
      card.style.marginBottom = above ? (idx * 4) + 'px' : '0';

      const typeIcon = _typeIcon(item);
      card.innerHTML = `
        <span class="card-type-icon">${typeIcon}</span>
        <span class="card-title">${_escapeHtml(_truncate(item.label, 30))}</span>
      `;
      card.title = item.label;
      card.addEventListener('click', () => _onItemClick(item));

      itemsEl.appendChild(card);
    });
  });
}

// ── Zoom Level 2: Months (full cards with thumbnails) ──────────────────

function _renderMonths(items) {
  const minYear = timelineData.spans.min_year;
  const maxYear = timelineData.spans.max_year;
  const pxPerMonth = 80;
  const totalMonths = (maxYear - minYear + 1) * 12;
  const totalWidth = totalMonths * pxPerMonth + 100;

  axisEl.innerHTML = '';
  itemsEl.innerHTML = '';
  axisEl.style.width = totalWidth + 'px';
  itemsEl.style.width = totalWidth + 'px';

  // Axis line
  const line = document.createElement('div');
  line.className = 'timeline-axis-line';
  axisEl.appendChild(line);

  // Year labels on axis
  for (let y = minYear; y <= maxYear; y++) {
    const monthOffset = (y - minYear) * 12;
    const x = 50 + monthOffset * pxPerMonth;

    const tick = document.createElement('div');
    tick.className = 'timeline-tick decade';
    tick.style.left = x + 'px';
    axisEl.appendChild(tick);

    const label = document.createElement('div');
    label.className = 'timeline-tick-label';
    label.style.left = x + 'px';
    label.textContent = y;
    axisEl.appendChild(label);
  }

  // Full cards
  items.forEach((item, i) => {
    const year = item.year;
    const month = _extractMonth(item.iso_start) || 6; // default to June if unknown
    const monthOffset = (year - minYear) * 12 + (month - 1);
    const x = 50 + monthOffset * pxPerMonth;

    const card = document.createElement('div');
    card.className = 'timeline-card-full';
    const above = i % 2 === 0;
    card.style.left = (x - 80) + 'px';
    card.style.bottom = above ? '55%' : 'auto';
    card.style.top = above ? 'auto' : '55%';

    let thumbHtml = '';
    if (item.thumbnail) {
      thumbHtml = `<img class="card-thumb" src="${_escapeHtml(item.thumbnail)}" alt="" loading="lazy">`;
    }

    const typeIcon = _typeIcon(item);
    const precisionLabel = item.precision === 'day' ? item.iso_start : (item.precision === 'month' ? item.iso_start : item.year);

    card.innerHTML = `
      ${thumbHtml}
      <div class="card-body">
        <span class="card-type-icon">${typeIcon}</span>
        <span class="card-title">${_escapeHtml(_truncate(item.label, 40))}</span>
        <span class="card-date">${precisionLabel}</span>
      </div>
    `;
    card.title = item.label;
    card.addEventListener('click', () => _onItemClick(item));

    itemsEl.appendChild(card);
  });
}

// ── Helpers ─────────────────────────────────────────────────────────────

function _groupByDecade(items) {
  const decades = {};
  items.forEach(item => {
    const decade = Math.floor(item.year / 10) * 10;
    if (!decades[decade]) decades[decade] = [];
    decades[decade].push(item);
  });
  return decades;
}

function _extractMonth(isoStart) {
  if (!isoStart) return null;
  const parts = isoStart.split('-');
  return parts.length >= 2 ? parseInt(parts[1]) : null;
}

function _typeIcon(item) {
  if (item.source_type === 'video') return '&#x1F3AC;'; // film
  if (item.source_type === 'pdf') return '&#x1F4C4;'; // document
  if (item.source_type === 'url') return '&#x1F310;'; // globe
  if (item.type === 'date') return '&#x1F4C5;'; // calendar
  return '&#x2B50;'; // star
}

function _onItemClick(item) {
  // For video sources, open the video viewer
  if (item.source_type === 'video' && item.sources && item.sources.length > 0) {
    const slug = item.sources[0].replace('source:', '');
    window.open(`video.html?source=${encodeURIComponent(slug)}`, '_blank');
    return;
  }

  // Show a detail popup
  _showItemDetail(item);
}

function _showItemDetail(item) {
  const detailBody = document.getElementById('detail-body');
  const layout = document.getElementById('app-layout');
  if (!detailBody || !layout) return;

  let html = `
    <div class="entity-name">${_escapeHtml(item.label)}</div>
    <span class="entity-type" style="background: ${item.type === 'date' ? '#90A4AE22' : '#FFD54F22'}; color: ${item.type === 'date' ? '#90A4AE' : '#FFD54F'}; border: 1px solid ${item.type === 'date' ? '#90A4AE44' : '#FFD54F44'};">
      ${item.type === 'date' ? 'Date' : 'Source'}
    </span>
  `;

  if (item.thumbnail) {
    html += `<div class="detail-section"><img src="${_escapeHtml(item.thumbnail)}" style="width:100%;border-radius:6px;margin-top:8px;"></div>`;
  }

  html += `
    <div class="detail-section">
      <h4>Date</h4>
      <div class="meta-row"><span>Value</span><span>${_escapeHtml(item.iso_start || '?')}${item.iso_end && item.iso_end !== item.iso_start ? ' – ' + _escapeHtml(item.iso_end) : ''}</span></div>
      <div class="meta-row"><span>Precision</span><span>${_escapeHtml(item.precision || '?')}</span></div>
    </div>
  `;

  if (item.sources && item.sources.length > 0) {
    html += `
      <div class="detail-section">
        <h4>Sources</h4>
        <ul class="source-list">
          ${item.sources.map(s => {
            const slug = s.replace('source:', '');
            const display = slug.replace(/-/g, ' ');
            return `<li><a href="#" class="source-link" data-slug="${_escapeHtml(slug)}">${_escapeHtml(display)}</a></li>`;
          }).join('')}
        </ul>
      </div>
    `;
  }

  if (item.description) {
    html += `<div class="detail-section"><h4>Description</h4><p style="color:var(--text-secondary);font-size:13px;">${_escapeHtml(item.description)}</p></div>`;
  }

  if (item.tags && item.tags.length > 0) {
    html += `<div class="detail-section"><h4>Tags</h4><div class="alias-list">${item.tags.map(t => `<span class="alias-tag">${_escapeHtml(t)}</span>`).join('')}</div></div>`;
  }

  detailBody.innerHTML = html;
  layout.classList.add('detail-open');
}

function _truncate(str, max) {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

function _escapeHtml(text) {
  const el = document.createElement('span');
  el.textContent = text;
  return el.innerHTML;
}
