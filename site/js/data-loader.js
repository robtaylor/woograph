/**
 * data-loader.js - Load and parse WooGraph JSON-LD data into Cytoscape format
 */

const TYPE_COLORS = {
  Person: '#4FC3F7',
  Place: '#81C784',
  Organization: '#FFB74D',
  Event: '#E57373',
  CreativeWork: '#BA68C8',
  Date: '#90A4AE',
  Thing: '#BDBDBD',
};

/**
 * Clean a predicate string for display.
 * "woo:commandedAt" -> "commanded at"
 * "woo:locatedIn" -> "located in"
 */
function cleanPredicate(predicate) {
  if (!predicate) return '';
  // Strip namespace prefix
  let cleaned = predicate.replace(/^woo:/, '').replace(/^https?:\/\/[^/]+\/[^/]+\//, '');
  // camelCase to space-separated
  cleaned = cleaned.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase();
  return cleaned;
}

/**
 * Resolve an entity @id reference.
 * Handles both string IDs and objects with @id.
 */
function resolveId(ref) {
  if (typeof ref === 'string') return ref;
  if (ref && ref['@id']) return ref['@id'];
  return null;
}

/**
 * Load the global graph data and convert to Cytoscape elements.
 * @returns {Promise<{nodes: Array, edges: Array, entityTypes: Map}>}
 */
export async function loadGraphData() {
  const response = await fetch('data/global.jsonld');
  if (!response.ok) {
    console.warn('Failed to load global.jsonld:', response.status);
    return { nodes: [], edges: [], entityTypes: new Map() };
  }

  const graph = await response.json();
  const entities = graph.entities || [];
  const relationships = graph.relationships || [];

  // Count mentions per entity for node sizing
  const mentionCounts = new Map();
  for (const entity of entities) {
    const mentions = Array.isArray(entity.mentionedIn) ? entity.mentionedIn.length : 0;
    mentionCounts.set(entity['@id'], mentions);
  }

  // Track entity types and counts
  const entityTypes = new Map();

  // Build nodes
  const nodes = entities.map(entity => {
    const id = entity['@id'];
    const type = entity['@type'] || 'Thing';
    const name = entity.name || id.split(':').pop().replace(/-/g, ' ');
    const aliases = entity.aliases || [];
    const mentionedIn = Array.isArray(entity.mentionedIn) ? entity.mentionedIn : [];
    const color = TYPE_COLORS[type] || TYPE_COLORS.Thing;
    const mentions = mentionCounts.get(id) || 0;

    // Track type counts
    entityTypes.set(type, (entityTypes.get(type) || 0) + 1);

    return {
      group: 'nodes',
      data: {
        id,
        label: name,
        type,
        color,
        aliases,
        mentionedIn,
        mentionCount: mentions,
        // Scale node size: base 20, +5 per mention, max 60
        size: Math.min(60, 20 + mentions * 5),
      },
    };
  });

  // Build a set of valid node IDs for filtering dangling edges
  const nodeIds = new Set(entities.map(e => e['@id']));

  // Build edges
  const edges = [];
  for (const rel of relationships) {
    const sourceId = resolveId(rel.subject);
    const targetId = resolveId(rel.object);

    if (!sourceId || !targetId) continue;
    // Skip edges where nodes don't exist
    if (!nodeIds.has(sourceId) || !nodeIds.has(targetId)) continue;

    const predicate = rel.predicate || '';
    const confidence = typeof rel.confidence === 'number' ? rel.confidence : 0.5;
    const extractedBy = rel.extractedBy || '';

    edges.push({
      group: 'edges',
      data: {
        id: `edge-${sourceId}-${predicate}-${targetId}`,
        source: sourceId,
        target: targetId,
        label: cleanPredicate(predicate),
        predicate,
        confidence,
        extractedBy,
        // Scale edge width by confidence
        width: 1 + confidence * 3,
        opacity: 0.3 + confidence * 0.7,
      },
    });
  }

  return { nodes, edges, entityTypes };
}

/**
 * Load stats.json
 * @returns {Promise<Object>}
 */
export async function loadStats() {
  try {
    const response = await fetch('data/stats.json');
    if (!response.ok) return {};
    return await response.json();
  } catch {
    return {};
  }
}

export { TYPE_COLORS, cleanPredicate };
