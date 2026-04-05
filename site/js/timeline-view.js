/**
 * timeline-view.js - Horizontal timeline visualization of dated entities and sources
 *
 * Continuous zoom from decades overview to individual months.
 * Zoom level 0..100 maps to pxPerYear from 6 (decades) to 960 (months).
 * Scroll position is preserved across zoom changes.
 */

let timelineData = null;
let container = null;
let axisEl = null;
let itemsEl = null;
let zoomLevel = 0; // 0..100 continuous
let currentFilters = null;

// Stem height variation — seeded from item index for consistency
const STEM_HEIGHTS = [50, 75, 100, 130, 65, 90, 115, 55, 85, 105, 70, 95, 120, 60, 80, 110];

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

  function setZoom(level) {
    zoomLevel = Math.max(0, Math.min(100, level));
    if (zoomSlider) zoomSlider.value = zoomLevel;
    if (zoomLabel) zoomLabel.textContent = _zoomLabel(zoomLevel);
    renderTimeline();
  }

  if (zoomSlider) {
    zoomSlider.addEventListener('input', () => setZoom(parseInt(zoomSlider.value)));
  }
  if (zoomIn) zoomIn.addEventListener('click', () => setZoom(zoomLevel + 10));
  if (zoomOut) zoomOut.addEventListener('click', () => setZoom(zoomLevel - 10));

  // Scroll wheel zoom (ctrl/cmd + scroll) — preserves scroll position
  container.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 5 : -5;
      setZoom(zoomLevel + delta);
    }
  }, { passive: false });
}

function _zoomLabel(level) {
  if (level < 15) return 'Decades';
  if (level < 40) return 'Years';
  if (level < 70) return 'Years (detail)';
  return 'Months';
}

/**
 * Map zoom level 0..100 to pixels per year.
 * 0 → 6px/yr (decades), 50 → 100px/yr (years), 100 → 960px/yr (months)
 */
function _pxPerYear(level) {
  // Exponential curve: more resolution at higher zoom
  return Math.round(6 * Math.pow(160, level / 100));
}

/**
 * Get the preferred display label for a timeline item.
 */
function _displayLabel(item) {
  return item.display_label || item.label;
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

  // Capture scroll position as a fraction of total width
  const oldWidth = parseFloat(axisEl.style.width) || container.scrollWidth || 1;
  const scrollCenter = container.scrollLeft + container.clientWidth / 2;
  const scrollFraction = scrollCenter / oldWidth;

  const pxPerYear = _pxPerYear(zoomLevel);

  if (pxPerYear < 15) {
    _renderDecades(items, pxPerYear);
  } else {
    _renderItems(items, pxPerYear);
  }

  // Restore scroll position — keep the same point centered
  const newWidth = parseFloat(axisEl.style.width) || container.scrollWidth || 1;
  const newCenter = scrollFraction * newWidth;
  container.scrollLeft = newCenter - container.clientWidth / 2;
}

/**
 * Filter items based on active entity type filters.
 */
function _filterItems(items) {
  if (!currentFilters || !currentFilters.activeTypes) return items;

  const types = currentFilters.activeTypes;
  return items.filter(item => {
    if (item.type === 'date') return types.has('Date');
    if (item.type === 'source') return types.has('woo:Source') || !types.size;
    return true;
  });
}

// ── Decades (low zoom) ───────────────────────────────────────────────

function _renderDecades(items, pxPerYear) {
  const decades = _groupByDecade(items);
  const decadeKeys = Object.keys(decades).map(Number).sort();

  const minDecade = decadeKeys[0];
  const maxDecade = decadeKeys[decadeKeys.length - 1];
  const totalWidth = ((maxDecade - minDecade) / 10 + 2) * pxPerYear * 10 + 100;

  axisEl.innerHTML = '';
  itemsEl.innerHTML = '';
  axisEl.style.width = totalWidth + 'px';
  itemsEl.style.width = totalWidth + 'px';

  // Axis line
  const line = document.createElement('div');
  line.className = 'timeline-axis-line';
  axisEl.appendChild(line);

  decadeKeys.forEach((decade) => {
    const x = 50 + ((decade - minDecade) / 10) * pxPerYear * 10;
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
      // Zoom into this decade
      const zoomSlider = document.getElementById('timeline-zoom');
      const zoomLabel = document.getElementById('timeline-range-label');
      zoomLevel = 30;
      if (zoomSlider) zoomSlider.value = zoomLevel;
      if (zoomLabel) zoomLabel.textContent = _zoomLabel(zoomLevel);

      // Center on this decade
      const minYear = timelineData.spans.min_year;
      const newPx = _pxPerYear(zoomLevel);
      const targetX = 50 + (decade - minYear) * newPx;
      renderTimeline();
      container.scrollLeft = targetX - container.clientWidth / 3;
    });

    itemsEl.appendChild(cluster);
  });
}

// ── Items view (years / months depending on zoom) ─────────────────────

function _renderItems(items, pxPerYear) {
  const minYear = timelineData.spans.min_year;
  const maxYear = timelineData.spans.max_year;
  const totalWidth = (maxYear - minYear + 2) * pxPerYear + 100;

  axisEl.innerHTML = '';
  itemsEl.innerHTML = '';
  axisEl.style.width = totalWidth + 'px';
  itemsEl.style.width = totalWidth + 'px';

  // Axis line
  const line = document.createElement('div');
  line.className = 'timeline-axis-line';
  axisEl.appendChild(line);

  // Determine tick interval based on zoom
  let tickInterval = 10;  // decades
  if (pxPerYear >= 40) tickInterval = 5;
  if (pxPerYear >= 80) tickInterval = 1;

  // Year ticks
  for (let y = minYear; y <= maxYear; y++) {
    if (y % tickInterval !== 0 && y !== minYear && y !== maxYear) continue;
    const x = 50 + (y - minYear) * pxPerYear;
    const isDecade = y % 10 === 0;

    const tick = document.createElement('div');
    tick.className = 'timeline-tick' + (isDecade ? ' decade' : '');
    tick.style.left = x + 'px';
    axisEl.appendChild(tick);

    // Show label for decades, or for all visible ticks at higher zoom
    if (isDecade || pxPerYear >= 80 || y === minYear || y === maxYear) {
      const label = document.createElement('div');
      label.className = 'timeline-tick-label';
      label.style.left = x + 'px';
      label.textContent = y;
      axisEl.appendChild(label);
    }
  }

  // Determine card style based on zoom
  const showThumbs = pxPerYear >= 50;
  const showFullCards = pxPerYear >= 200;

  // Group by year for stacking
  const byYear = {};
  items.forEach(item => {
    const y = item.year;
    if (!byYear[y]) byYear[y] = [];
    byYear[y].push(item);
  });

  Object.entries(byYear).forEach(([year, group]) => {
    group.forEach((item, idx) => {
      // Position: use month precision at high zoom
      let xFraction = 0.5; // default: middle of year
      if (pxPerYear >= 80) {
        const month = _extractMonth(item.iso_start);
        if (month) xFraction = (month - 1) / 12;
      }
      const x = 50 + (year - minYear + xFraction) * pxPerYear;

      const above = idx % 2 === 0;
      const stemIdx = (parseInt(year) * 7 + idx * 3) % STEM_HEIGHTS.length;
      const stemHeight = STEM_HEIGHTS[stemIdx];

      // Vertical stem
      const stem = document.createElement('div');
      stem.className = 'timeline-stem' + (above ? ' above' : ' below');
      stem.style.left = x + 'px';
      stem.style.height = stemHeight + 'px';
      itemsEl.appendChild(stem);

      // Card
      const card = document.createElement('div');
      const cardClass = showFullCards ? 'timeline-card-full' : 'timeline-card-small';
      card.className = cardClass;
      const cardWidth = showFullCards ? 160 : 120;
      card.style.left = (x - cardWidth / 2) + 'px';
      card.style.bottom = above ? `calc(50% + ${stemHeight}px)` : 'auto';
      card.style.top = above ? 'auto' : `calc(50% + ${stemHeight}px)`;

      const typeIcon = _typeIcon(item);
      const displayText = _displayLabel(item);
      const dateText = item.label; // original date text

      if (showFullCards) {
        let thumbHtml = '';
        if (item.thumbnail) {
          thumbHtml = `<img class="card-thumb" src="${_escapeHtml(item.thumbnail)}" alt="" loading="lazy">`;
        }
        const precisionLabel = item.precision === 'day' ? item.iso_start
          : (item.precision === 'month' ? item.iso_start : item.year);

        card.innerHTML = `
          ${thumbHtml}
          <div class="card-body">
            <span class="card-type-icon">${typeIcon}</span>
            <span class="card-title">${_escapeHtml(_truncate(displayText, 40))}</span>
            <span class="card-date">${precisionLabel} ${dateText !== displayText ? '· ' + _escapeHtml(_truncate(dateText, 20)) : ''}</span>
          </div>
        `;
      } else {
        let thumbHtml = '';
        if (showThumbs && item.thumbnail) {
          thumbHtml = `<img class="card-small-thumb" src="${_escapeHtml(item.thumbnail)}" alt="" loading="lazy">`;
        }
        card.innerHTML = `
          ${thumbHtml}
          <div class="card-small-body">
            <span class="card-type-icon">${typeIcon}</span>
            <span class="card-title">${_escapeHtml(_truncate(displayText, 30))}</span>
          </div>
        `;
      }
      card.title = `${displayText}\n${dateText}`;
      card.addEventListener('click', () => _onItemClick(item));

      itemsEl.appendChild(card);
    });
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

  const displayText = _displayLabel(item);

  let html = `
    <div class="entity-name">${_escapeHtml(displayText)}</div>
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
      ${item.label !== displayText ? `<div class="meta-row"><span>Original</span><span>${_escapeHtml(item.label)}</span></div>` : ''}
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
