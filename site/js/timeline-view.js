/**
 * timeline-view.js - Horizontal timeline visualization of dated entities and sources
 *
 * Unified rendering at all zoom levels. Zoom controls how many items are
 * visible (rank-filtered) and how spread out the axis is. Stem heights and
 * card appearance stay consistent — only density changes.
 *
 * Items are ranked by: thumbnail > event connections > place connections > sources.
 * At low zoom only top-ranked items show; at max zoom all items appear.
 */

let timelineData = null;
let container = null;
let axisEl = null;
let itemsEl = null;
let zoomLevel = 0; // 0..100 continuous
let currentFilters = null;

/** Pre-computed item data: rank, stemHeight, side (above/below) */
let itemLayout = null;

/**
 * Fetch timeline.json from the data directory.
 * @returns {Promise<Object|null>}
 */
export async function loadTimelineData() {
  try {
    const resp = await fetch('data/timeline.json');
    if (!resp.ok) return null;
    timelineData = await resp.json();
    _computeLayout();
    return timelineData;
  } catch {
    return null;
  }
}

/**
 * Pre-compute stable layout properties for each item.
 * These never change with zoom — only visibility does.
 */
function _computeLayout() {
  if (!timelineData) return;
  itemLayout = new Map();

  const items = timelineData.items;

  // Score each item for ranking
  const scored = items.map(item => {
    let score = 0;
    if (item.thumbnail) score += 20;
    score += (item.events || []).length * 8;
    score += (item.places || []).length * 4;
    score += (item.sources || []).length * 2;
    // Prefer day/month precision over year/decade
    if (item.precision === 'day') score += 3;
    else if (item.precision === 'month') score += 2;
    else if (item.precision === 'season') score += 1;
    return { item, score };
  });

  // Sort by score desc, assign rank (0 = best)
  scored.sort((a, b) => b.score - a.score);
  const rankMap = new Map();
  scored.forEach((s, i) => rankMap.set(s.item.id, i));

  // Assign stable stem heights and sides per item
  // Group by year, alternate above/below within each year
  const byYear = {};
  items.forEach(item => {
    const y = item.year;
    if (!byYear[y]) byYear[y] = [];
    byYear[y].push(item);
  });

  // Stem height pool — varied for visual interest
  const heights = [55, 70, 90, 110, 130, 65, 85, 105, 120, 75, 95, 60, 80, 100, 115, 125];

  for (const [, group] of Object.entries(byYear)) {
    // Sort group by rank so best items get assigned first
    group.sort((a, b) => rankMap.get(a.id) - rankMap.get(b.id));

    group.forEach((item, idx) => {
      const above = idx % 2 === 0;
      const tier = Math.floor(idx / 2); // how far from axis (0 = closest pair)
      const heightIdx = ((_hashCode(item.id) & 0x7fffffff) % heights.length);
      const baseHeight = heights[heightIdx];
      // Add tier offset so stacked items in same year don't overlap
      const stemHeight = baseHeight + tier * 30;

      itemLayout.set(item.id, {
        rank: rankMap.get(item.id),
        stemHeight,
        above,
        score: scored.find(s => s.item === item)?.score || 0,
      });
    });
  }
}

/** Simple string hash for stable pseudo-random assignment */
function _hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return hash;
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

  // Scroll wheel zoom (ctrl/cmd + scroll)
  container.addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      setZoom(zoomLevel + (e.deltaY < 0 ? 5 : -5));
    }
  }, { passive: false });
}

function _zoomLabel(level) {
  if (level < 15) return 'Overview';
  if (level < 40) return 'Decades';
  if (level < 70) return 'Years';
  return 'Detail';
}

/**
 * Map zoom level 0..100 to pixels per year.
 * 0 → 6px/yr, 50 → 100px/yr, 100 → 960px/yr
 */
function _pxPerYear(level) {
  return Math.round(6 * Math.pow(160, level / 100));
}

/** Max items per spatial bucket. */
const MAX_PER_BUCKET = 3;

/** Bucket width in pixels (~half a card width). */
const BUCKET_PX = 70;

/**
 * Get the preferred display label for a timeline item.
 */
function _displayLabel(item) {
  return item.display_label || item.label;
}

/**
 * Spatially filter items: divide timeline into buckets of BUCKET_PX width,
 * keep at most MAX_PER_BUCKET best-ranked items per bucket.
 * This ensures even distribution — no empty gaps or overcrowded clusters.
 */
function _spatialFilter(items, pxPerYear, minYear) {
  // Compute x position for each item
  const withX = items
    .filter(item => itemLayout.has(item.id))
    .map(item => {
      let xFrac = 0.5;
      if (pxPerYear >= 40) {
        const month = _extractMonth(item.iso_start);
        if (month) xFrac = (month - 1) / 12;
      }
      const x = 50 + (item.year - minYear + xFrac) * pxPerYear;
      return { item, x, rank: itemLayout.get(item.id).rank };
    });

  // Assign to buckets
  const buckets = new Map();
  for (const entry of withX) {
    const bucketIdx = Math.floor(entry.x / BUCKET_PX);
    if (!buckets.has(bucketIdx)) buckets.set(bucketIdx, []);
    buckets.get(bucketIdx).push(entry);
  }

  // From each bucket, keep top MAX_PER_BUCKET by rank (lower rank = better)
  const result = [];
  for (const [, entries] of buckets) {
    entries.sort((a, b) => a.rank - b.rank);
    for (let i = 0; i < Math.min(MAX_PER_BUCKET, entries.length); i++) {
      result.push(entries[i].item);
    }
  }

  // Sort chronologically for rendering
  result.sort((a, b) => {
    if (a.year !== b.year) return a.year - b.year;
    return (a.iso_start || '').localeCompare(b.iso_start || '');
  });

  return result;
}

/**
 * Render or re-render the timeline with current data and filters.
 */
export function renderTimeline(filters) {
  if (filters) currentFilters = filters;
  if (!timelineData || !container || !itemLayout) return;

  const allItems = _filterItems(timelineData.items);
  if (allItems.length === 0) {
    itemsEl.innerHTML = '<div class="timeline-empty">No items match current filters</div>';
    axisEl.innerHTML = '';
    return;
  }

  const loadingEl = document.getElementById('timeline-loading');
  if (loadingEl) loadingEl.style.display = 'none';

  // Capture scroll position as fraction of content
  const oldWidth = parseFloat(axisEl.style.width) || container.scrollWidth || 1;
  const scrollCenter = container.scrollLeft + container.clientWidth / 2;
  const scrollFraction = scrollCenter / oldWidth;

  const pxPerYear = _pxPerYear(zoomLevel);
  const minYear = timelineData.spans.min_year;

  // Spatial filtering: max 3 items per ~70px bucket
  const items = _spatialFilter(allItems, pxPerYear, minYear);

  _render(items, pxPerYear);

  // Restore scroll position
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

// ── Unified Renderer ──────────────────────────────────────────────────

function _render(items, pxPerYear) {
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

  // Axis ticks — adaptive density
  _renderAxisTicks(minYear, maxYear, pxPerYear);

  // Cards + stems
  for (const item of items) {
    const layout = itemLayout.get(item.id);
    if (!layout) continue;

    // X position: year + optional month offset
    let xFraction = 0.5;
    if (pxPerYear >= 40) {
      const month = _extractMonth(item.iso_start);
      if (month) xFraction = (month - 1) / 12;
    }
    const x = 50 + (item.year - minYear + xFraction) * pxPerYear;

    // Stem
    const stem = document.createElement('div');
    stem.className = 'timeline-stem' + (layout.above ? ' above' : ' below');
    stem.style.left = x + 'px';
    stem.style.height = layout.stemHeight + 'px';
    itemsEl.appendChild(stem);

    // Card — always the same style
    const card = document.createElement('div');
    card.className = 'timeline-card';
    card.style.left = (x - 70) + 'px';
    card.style.bottom = layout.above ? `calc(50% + ${layout.stemHeight}px)` : 'auto';
    card.style.top = layout.above ? 'auto' : `calc(50% + ${layout.stemHeight}px)`;

    const typeIcon = _typeIcon(item);
    const displayText = _displayLabel(item);
    const dateText = item.label;

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
        <span class="card-title">${_escapeHtml(_truncate(displayText, 36))}</span>
        <span class="card-date">${precisionLabel}${dateText !== displayText ? ' · ' + _escapeHtml(_truncate(dateText, 18)) : ''}</span>
      </div>
    `;
    card.title = `${displayText}\n${dateText}`;
    card.addEventListener('click', () => _onItemClick(item));

    itemsEl.appendChild(card);
  }
}

function _renderAxisTicks(minYear, maxYear, pxPerYear) {
  // Choose tick interval so ticks are ~60-150px apart
  const intervals = [100, 50, 20, 10, 5, 2, 1];
  let tickInterval = 10;
  for (const iv of intervals) {
    if (iv * pxPerYear >= 50) {
      tickInterval = iv;
    }
  }

  for (let y = Math.floor(minYear / tickInterval) * tickInterval; y <= maxYear; y += tickInterval) {
    if (y < minYear) continue;
    const x = 50 + (y - minYear) * pxPerYear;
    const isDecade = y % 10 === 0;
    const isCentury = y % 100 === 0;

    const tick = document.createElement('div');
    tick.className = 'timeline-tick' + (isDecade ? ' decade' : '');
    tick.style.left = x + 'px';
    axisEl.appendChild(tick);

    // Label: always for decades+, and for single years at high zoom
    if (isCentury || isDecade || tickInterval <= 5) {
      const label = document.createElement('div');
      label.className = 'timeline-tick-label';
      label.style.left = x + 'px';
      label.textContent = y;
      axisEl.appendChild(label);
    }
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────

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
  if (item.source_type === 'video' && item.sources && item.sources.length > 0) {
    const slug = item.sources[0].replace('source:', '');
    window.open(`video.html?source=${encodeURIComponent(slug)}`, '_blank');
    return;
  }
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
