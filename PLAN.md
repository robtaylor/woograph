# WooGraph Implementation Plan

**Created:** 2026-03-26
**Project:** Collaborative Knowledge Graph Builder via GitHub Workflows

---

## Overview

WooGraph is a collaborative knowledge graph that lives entirely in a GitHub repository. Contributors submit sources (PDFs, URLs, personal accounts) via Pull Requests. GitHub Actions processes these sources into normalized markdown, extracts entities and relationships using spaCy (free) and Claude Haiku (cheap), and assembles a JSON-LD knowledge graph. The graph is visualized on GitHub Pages using Cytoscape.js (network view) and Leaflet (map view).

The key insight: **the repo IS the database**. JSON-LD fragments are committed alongside source markdown, and a merged global graph is the "query layer." GitHub provides versioning, collaboration, and hosting for free.

---

## Design Decisions

### D1: PR Submission Format

Contributors create a YAML manifest file in `submissions/` with metadata, plus attach source files. This is simpler than YAML front matter in markdown because the contributor never writes markdown -- the pipeline generates it.

```yaml
# submissions/2026-03-26-battle-of-midway.yaml
source:
  title: "Battle of Midway: A Naval Analysis"
  type: pdf              # pdf | url | account | video
  url: null              # for url/video types
  file: "battle-of-midway.pdf"  # for pdf type, relative to submissions/files/
  author: "Jane Historian"
  date_added: "2026-03-26"
  tags: ["wwii", "pacific-theater", "naval"]
  description: "Detailed analysis of the Battle of Midway"
  # For 'account' type, the narrative goes in a companion .md file
  # submissions/2026-03-26-battle-of-midway.md
```

**Rationale:** YAML is easy to validate in CI, easy to template in a PR template, and separates metadata from content. The pipeline reads the YAML, fetches/converts the source, and commits the result.

### D2: JSON-LD Schema

Use a domain-agnostic but extensible `@context` that covers common entity types. Each source produces a fragment; the global graph merges them.

```jsonld
{
  "@context": {
    "@vocab": "https://schema.org/",
    "woo": "https://woograph.github.io/ontology/",
    "entities": "woo:entities",
    "relationships": "woo:relationships",
    "source": "woo:source",
    "confidence": "woo:confidence",
    "extractedBy": "woo:extractedBy",
    "mentionedIn": "woo:mentionedIn",
    "geo": "https://schema.org/GeoCoordinates"
  }
}
```

Entity types (mapped to schema.org where possible):
- `Person` → schema:Person
- `Place` → schema:Place (with geo coordinates when resolvable)
- `Organization` → schema:Organization
- `Event` → schema:Event
- `CreativeWork` → schema:CreativeWork
- `woo:Concept` → custom, for abstract topics

Relationships use a simple triple model:
```jsonld
{
  "@type": "woo:Relationship",
  "woo:subject": {"@id": "entity:person-john-doe"},
  "woo:predicate": "woo:participatedIn",
  "woo:object": {"@id": "entity:event-battle-of-midway"},
  "confidence": 0.85,
  "extractedBy": "claude-haiku",
  "mentionedIn": ["source:2026-03-26-battle-of-midway"]
}
```

**Rationale:** JSON-LD is W3C standard, schema.org gives us interoperability, and the fragment-per-source model enables incremental updates. Confidence scores let the UI filter low-quality extractions.

### D3: Entity Disambiguation Strategy

Entity disambiguation is the hardest problem. Strategy:

1. **Canonical ID generation**: Normalize names to slug form (`john-f-kennedy` → `entity:person-john-f-kennedy`)
2. **spaCy first pass**: Extract raw entity mentions with types
3. **Claude Haiku second pass**: Given the raw entities + surrounding context, Claude:
   - Resolves aliases ("JFK", "Kennedy", "President Kennedy" → same entity)
   - Assigns canonical IDs
   - Checks against existing entity registry (`graph/entities/registry.json`)
   - Flags ambiguous cases for human review
4. **Entity registry**: A flat JSON file mapping canonical IDs to known aliases, used as context for future extractions

**Cost control**: Claude only sees entity mentions + small context windows (not full documents). Batch API where possible.

### D4: Incremental Processing

Each source has a processing manifest:
```
graph/sources/2026-03-26-battle-of-midway/
  manifest.json    # processing status, hash of source, timestamps
  fragment.jsonld  # extracted graph fragment
```

On PR merge:
1. Detect which `submissions/*.yaml` files are new/changed (git diff)
2. Only process those sources
3. After extraction, re-merge the global graph from all fragments

The global graph merge is always a full rebuild from fragments (it's fast -- just JSON concatenation + dedup). This avoids complex incremental merge logic.

### D5: GitHub Actions Structure (Revised - PR-first processing)

Four workflows:

1. **`validate-pr.yml`** -- Runs on PR open/update. Validates YAML schema. Fast (<30s).

2. **`process-pr.yml`** -- Runs on PR after approval. Does the heavy processing:
   - Trigger: `pull_request_review` [approved] OR push to PR branch when "approved" label present
   - Gate: only runs if PR has "approved" label or an approving review (saves Actions minutes)
   - Downloads PDFs from URLs, converts to markdown, runs NER + LLM extraction
   - Commits results (sources/, graph/fragments/) back to the PR branch
   - Posts a summary comment on the PR with entity counts, top entities, sample relationships, warnings
   - If reviewer pushes changes (e.g., noise-terms.txt update), re-triggers automatically
   - Reviewer can inspect committed fragments in the PR diff before merging

3. **`merge-graph.yml`** -- Runs on push to main (paths: graph/fragments/**). Lightweight:
   - Merges all fragments into global.jsonld (fast JSON assembly, no reprocessing)
   - Commits global.jsonld + stats.json
   - Triggers deploy

4. **`deploy-pages.yml`** -- Runs after merge-graph completes. Deploys visualization to GitHub Pages.

Key insight: all heavy processing happens on the PR branch, visible to reviewers before merge.
The merge step is just graph assembly (<30s). This gives quality control before data enters the graph.

**Fork PR handling:** For PRs from forks, the workflow cannot push to the fork branch. Instead:
- Extraction results posted as workflow artifacts (downloadable)
- Summary posted as PR comment
- Maintainer can cherry-pick artifacts into the PR or merge and reprocess
- For same-repo branches, bot commits directly to the PR branch
- PR template should note: "Check 'Allow edits from maintainers' for automated processing"

### D6: LLM Cost Management

- **spaCy does the heavy lifting** (free): NER, basic classification
- **Claude Haiku only for**: relationship extraction, entity disambiguation, geocoding ambiguous places
- **Batching**: Collect all entities from a PR's sources, send one batch to Claude
- **Caching**: Store Claude responses in `graph/cache/`. If source hasn't changed (by hash), skip LLM call
- **Token budget**: Each source gets a max context window. Large PDFs are chunked; only chunks with entities (per spaCy) are sent to Claude
- **Estimated cost**: ~$0.01-0.05 per source (Haiku is $0.25/MTok input, $1.25/MTok output)

---

## Directory Structure

```
woograph/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── source-submission.md        # Issue template for requesting sources
│   ├── PULL_REQUEST_TEMPLATE.md        # PR template with YAML scaffold
│   └── workflows/
│       ├── validate-pr.yml             # PR validation
│       ├── process-sources.yml         # Source processing pipeline
│       └── deploy-pages.yml           # GitHub Pages deployment
│
├── submissions/                        # Where contributors submit sources
│   ├── README.md                       # How to submit
│   ├── _schema.yaml                    # JSON Schema for validation
│   └── files/                          # Uploaded PDFs/attachments
│       └── .gitkeep
│
├── sources/                            # Processed/normalized content (generated)
│   ├── <source-slug>/
│   │   ├── content.md                  # Normalized markdown
│   │   ├── images/                     # Extracted images
│   │   └── metadata.json              # Processing metadata
│   └── ...
│
├── graph/                              # Knowledge graph (generated)
│   ├── context.jsonld                  # Shared @context definition
│   ├── global.jsonld                   # Merged global graph
│   ├── entities/
│   │   ├── registry.json              # Canonical entity registry
│   │   └── pending-review.json        # Ambiguous entities for human review
│   ├── fragments/                      # Per-source graph fragments
│   │   ├── <source-slug>.jsonld
│   │   └── ...
│   ├── cache/                          # LLM response cache
│   │   └── .gitignore                 # Don't commit cache in early phases
│   └── stats.json                     # Graph statistics
│
├── pipeline/                           # Python processing code
│   ├── pyproject.toml                  # uv project config
│   ├── src/
│   │   └── woograph/
│   │       ├── __init__.py
│   │       ├── cli.py                  # CLI entry point
│   │       ├── convert/
│   │       │   ├── __init__.py
│   │       │   ├── pdf.py             # pymupdf4llm PDF conversion
│   │       │   ├── web.py             # trafilatura web scraping
│   │       │   └── account.py         # Personal account passthrough
│   │       ├── extract/
│   │       │   ├── __init__.py
│   │       │   ├── ner.py             # spaCy NER extraction
│   │       │   ├── relationships.py   # Claude Haiku relationship extraction
│   │       │   └── disambiguate.py    # Entity disambiguation
│   │       ├── graph/
│   │       │   ├── __init__.py
│   │       │   ├── fragment.py        # Per-source fragment generation
│   │       │   ├── merge.py           # Global graph assembly
│   │       │   ├── registry.py        # Entity registry management
│   │       │   └── jsonld.py          # JSON-LD utilities
│   │       └── utils/
│   │           ├── __init__.py
│   │           ├── git.py             # Git diff helpers
│   │           ├── cache.py           # LLM response caching
│   │           └── validate.py        # YAML schema validation
│   └── tests/
│       ├── conftest.py
│       ├── test_convert.py
│       ├── test_extract.py
│       ├── test_graph.py
│       └── fixtures/
│           ├── sample.pdf
│           ├── sample-submission.yaml
│           └── sample-fragment.jsonld
│
├── site/                               # GitHub Pages visualization
│   ├── index.html                      # Main app shell
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js                     # Main app logic
│   │   ├── graph-view.js             # Cytoscape.js network view
│   │   ├── map-view.js               # Leaflet geographic view
│   │   ├── data-loader.js            # JSON-LD data loading
│   │   ├── filters.js                # Entity type, time range filters
│   │   └── detail-panel.js           # Node/edge detail sidebar
│   └── lib/                           # Vendored JS libs (or CDN)
│
├── docs/
│   ├── contributing.md                 # How to contribute sources
│   ├── ontology.md                     # Schema/ontology documentation
│   └── architecture.md                # System architecture
│
├── PLAN.md                             # This file
├── README.md
└── LICENSE
```

---

## Implementation Phases

### Phase 1: Foundation & Manual Pipeline (MVP)

**Goal:** Accept a PDF or URL via PR, convert to markdown, commit it. No graph yet -- just prove the ingestion pipeline works.

**Files to create:**
- `pipeline/pyproject.toml` -- Python project with dependencies
- `pipeline/src/woograph/__init__.py`
- `pipeline/src/woograph/cli.py` -- `process-submission` command
- `pipeline/src/woograph/convert/pdf.py` -- pymupdf4llm wrapper
- `pipeline/src/woograph/convert/web.py` -- trafilatura wrapper
- `pipeline/src/woograph/convert/account.py` -- passthrough for written accounts
- `pipeline/src/woograph/utils/validate.py` -- YAML schema validation
- `submissions/_schema.yaml` -- JSON Schema for submission YAML
- `submissions/README.md` -- Contributor guide
- `.github/PULL_REQUEST_TEMPLATE.md` -- PR template with YAML scaffold
- `.github/workflows/validate-pr.yml` -- Validate submission format on PR
- `.github/workflows/process-sources.yml` -- Convert sources on merge

**Key dependencies:**
```toml
[project]
name = "woograph"
requires-python = ">=3.11"
dependencies = [
    "pymupdf4llm>=0.0.10",
    "trafilatura>=1.8",
    "pyyaml>=6.0",
    "jsonschema>=4.20",
    "click>=8.1",
]
```

**Workflow: validate-pr.yml**
```yaml
name: Validate PR
on:
  pull_request:
    paths: ['submissions/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd pipeline && uv sync
      - run: |
          cd pipeline
          uv run python -m woograph validate \
            --changed-files "${{ steps.changed.outputs.files }}"
```

**Workflow: process-sources.yml (Phase 1 version)**
```yaml
name: Process Sources
on:
  push:
    branches: [main]
    paths: ['submissions/**']

jobs:
  process:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2  # Need parent commit for diff
      - uses: astral-sh/setup-uv@v4
      - run: cd pipeline && uv sync
      - name: Detect new submissions
        id: detect
        run: |
          # Find submission YAMLs added/modified in the merge commit
          CHANGED=$(git diff --name-only HEAD~1 HEAD -- 'submissions/*.yaml')
          echo "files=$CHANGED" >> $GITHUB_OUTPUT
      - name: Process submissions
        run: |
          cd pipeline
          for f in ${{ steps.detect.outputs.files }}; do
            uv run python -m woograph process "../$f"
          done
      - name: Commit processed sources
        run: |
          git config user.name "WooGraph Bot"
          git config user.email "woograph-bot@users.noreply.github.com"
          git add sources/
          git diff --staged --quiet || git commit -m "Process sources from submissions"
          git push
```

**Acceptance criteria:**
- [ ] Submit a PDF via PR, see it validated
- [ ] On merge, PDF is converted to markdown in `sources/<slug>/content.md`
- [ ] Submit a URL via PR, web content scraped and stored as markdown
- [ ] Personal accounts (markdown) pass through correctly
- [ ] Tests pass for conversion modules

**Estimated effort:** 2-3 days

---

### Phase 2: Entity Extraction (spaCy)

**Goal:** After converting sources to markdown, run spaCy NER to extract entities. Store as JSON alongside the source.

**Files to create/modify:**
- `pipeline/src/woograph/extract/ner.py` -- spaCy NER pipeline
- `pipeline/src/woograph/graph/fragment.py` -- Generate JSON-LD fragment from entities
- `pipeline/src/woograph/graph/jsonld.py` -- JSON-LD utilities
- `graph/context.jsonld` -- Shared @context
- `graph/entities/registry.json` -- Initial empty registry
- `pipeline/tests/test_extract.py`

**Additional dependency:**
```toml
"spacy>=3.7",
```
Plus the model download in CI:
```yaml
- run: cd pipeline && uv run python -m spacy download en_core_web_sm
```

**NER Pipeline design (`extract/ner.py`):**
```python
def extract_entities(markdown_text: str, source_id: str) -> list[Entity]:
    """
    Run spaCy NER on markdown text.
    Returns Entity objects with: name, type, spans, context_snippet.
    Filters out low-confidence and overly generic entities.
    """
```

Entity types to extract: PERSON, ORG, GPE, LOC, DATE, EVENT, WORK_OF_ART, FAC

**Fragment generation (`graph/fragment.py`):**
```python
def create_fragment(source_id: str, entities: list[Entity]) -> dict:
    """
    Generate a JSON-LD fragment for a source.
    Entities only (no relationships yet -- that's Phase 3).
    """
```

**Acceptance criteria:**
- [ ] spaCy extracts entities from processed markdown
- [ ] Entities stored as JSON-LD fragments in `graph/fragments/<slug>.jsonld`
- [ ] Entity types correctly mapped to schema.org types
- [ ] Duplicate entities within a single source are deduplicated
- [ ] Tests with fixture data pass

**Estimated effort:** 1-2 days

---

### Phase 3: Relationship Extraction (Claude Haiku)

**Goal:** Use Claude Haiku to infer relationships between extracted entities and disambiguate across sources.

**Files to create/modify:**
- `pipeline/src/woograph/extract/relationships.py` -- Claude API relationship extraction
- `pipeline/src/woograph/extract/disambiguate.py` -- Entity disambiguation
- `pipeline/src/woograph/graph/registry.py` -- Entity registry CRUD
- `pipeline/src/woograph/utils/cache.py` -- LLM response caching

**Additional dependency:**
```toml
"anthropic>=0.40",
```

**Relationship extraction prompt strategy:**

Send Claude Haiku a structured prompt per text chunk:
```
Given these entities extracted from a document about [topic]:
- Person: John F. Kennedy
- Organization: US Navy
- Event: Battle of Midway
- Place: Pacific Ocean

And this text excerpt:
"[relevant paragraph]"

Extract relationships as JSON:
[{"subject": "John F. Kennedy", "predicate": "served_in", "object": "US Navy", "confidence": 0.9},
 ...]

Use these predicates: participated_in, member_of, located_in, occurred_at,
created_by, related_to, preceded, followed, caused, part_of
```

**Cost optimization:**
- Only send chunks that contain 2+ entities (no relationships possible with <2)
- Max 500 tokens per chunk context
- Cache responses keyed by `hash(chunk_text + entity_list)`
- Use `claude-3-5-haiku-latest` (~$0.25/MTok in, $1.25/MTok out)
- Estimated: ~2K tokens per chunk = ~$0.001 per chunk

**Disambiguation strategy (`extract/disambiguate.py`):**
```python
def disambiguate_entities(
    new_entities: list[Entity],
    registry: EntityRegistry,
    source_context: str
) -> list[Entity]:
    """
    For each new entity:
    1. Check registry for exact match → use canonical ID
    2. Check registry for fuzzy match → ask Claude to confirm
    3. No match → create new canonical entry
    
    Claude prompt for ambiguous cases:
    "Is 'Kennedy' in context '[excerpt]' the same as 
     'John F. Kennedy' (entity:person-john-f-kennedy)? Yes/No"
    """
```

**CI secret:** `ANTHROPIC_API_KEY` stored as GitHub repository secret.

**Acceptance criteria:**
- [ ] Relationships extracted between entities within each source
- [ ] Entity disambiguation works against registry
- [ ] LLM responses cached (re-running doesn't re-call API)
- [ ] Fragments now include both entities and relationships
- [ ] Cost per source stays under $0.10
- [ ] Tests mock Claude API calls

**Estimated effort:** 3-4 days

---

### Phase 4: Global Graph Assembly

**Goal:** Merge all per-source fragments into a global JSON-LD graph with deduplication.

**Files to create/modify:**
- `pipeline/src/woograph/graph/merge.py` -- Global graph merge
- `graph/global.jsonld` -- The merged graph (generated)
- `graph/stats.json` -- Graph statistics
- `.github/workflows/process-sources.yml` -- Add merge step
- `pipeline/tests/test_graph.py`

**Merge algorithm (`graph/merge.py`):**
```python
def merge_global_graph(fragments_dir: Path, context_path: Path) -> dict:
    """
    1. Load all fragment .jsonld files
    2. Collect all entities by canonical ID (dedup)
    3. Collect all relationships (dedup by subject+predicate+object)
    4. For duplicate relationships, keep highest confidence
    5. Track which sources mention each entity (mentionedIn)
    6. Generate statistics
    7. Write global.jsonld
    """
```

**Stats tracking:**
```json
{
  "total_entities": 142,
  "total_relationships": 87,
  "total_sources": 12,
  "entities_by_type": {"Person": 45, "Place": 30, ...},
  "last_updated": "2026-03-26T12:00:00Z"
}
```

**Acceptance criteria:**
- [ ] Global graph correctly merges all fragments
- [ ] Entity deduplication works across sources
- [ ] Cross-source relationships preserved
- [ ] `mentionedIn` tracks source provenance
- [ ] Stats generated and committed
- [ ] Re-running merge is idempotent

**Estimated effort:** 2 days

---

### Phase 5: Basic Visualization (GitHub Pages)

**Goal:** Deploy a Cytoscape.js network graph viewer on GitHub Pages.

**Files to create:**
- `site/index.html` -- App shell with tab navigation
- `site/css/style.css` -- Styling
- `site/js/app.js` -- Main app logic, tab switching
- `site/js/data-loader.js` -- Fetch and parse global.jsonld
- `site/js/graph-view.js` -- Cytoscape.js network visualization
- `site/js/detail-panel.js` -- Click-to-inspect sidebar
- `site/js/filters.js` -- Entity type filter checkboxes
- `.github/workflows/deploy-pages.yml` -- GitHub Pages deployment

**Architecture:**
- Plain HTML/CSS/JS (no build step -- keeps it simple for GitHub Pages)
- Cytoscape.js loaded from CDN
- Reads `graph/global.jsonld` via fetch (relative path since it's in the same repo)

**Graph view features (Phase 5):**
- Force-directed layout (default)
- Nodes colored by entity type
- Edge labels show relationship predicate
- Click node → sidebar shows entity details + source list
- Click source link → opens source markdown
- Filter by entity type (checkboxes)

**Deployment workflow:**
```yaml
name: Deploy Pages
on:
  workflow_run:
    workflows: ["Process Sources"]
    types: [completed]
    branches: [main]
  push:
    branches: [main]
    paths: ['site/**', 'graph/global.jsonld']

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
    steps:
      - uses: actions/checkout@v4
      - name: Prepare site
        run: |
          # Copy graph data into site directory for Pages
          cp graph/global.jsonld site/data/
          cp graph/context.jsonld site/data/
          cp graph/stats.json site/data/
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/
      - uses: actions/deploy-pages@v4
```

**Acceptance criteria:**
- [ ] GitHub Pages deploys on merge
- [ ] Network graph renders with real data
- [ ] Nodes are clickable, show entity details
- [ ] Source links work
- [ ] Entity type filters work
- [ ] Loads in <3 seconds for graphs with <1000 nodes

**Estimated effort:** 3-4 days

---

### Phase 6: Geographic View

**Goal:** Add a Leaflet map view showing Place entities with coordinates.

**Files to create/modify:**
- `site/js/map-view.js` -- Leaflet map with entity markers
- `pipeline/src/woograph/extract/geocode.py` -- Resolve place names to coordinates
- `graph/entities/registry.json` -- Add geo coordinates to Place entities

**Geocoding strategy:**
- Use Nominatim (OpenStreetMap, free, rate-limited) for geocoding
- Cache results in the entity registry
- Fall back to Claude Haiku for ambiguous places (e.g., "Springfield")
- Store as schema.org GeoCoordinates in the entity

**Map features:**
- Markers for Place entities with popups
- Click marker → show related entities and sources
- Cluster markers at zoom levels
- Lines connecting co-occurring places (same source)
- Filter by time range if dates available

**Acceptance criteria:**
- [ ] Place entities geocoded and stored with coordinates
- [ ] Map renders with real data
- [ ] Markers clickable with entity details
- [ ] Map and graph views share filter state
- [ ] Nominatim rate limits respected (1 req/sec)

**Estimated effort:** 2-3 days

---

### Phase 7: Enhanced UX & Timeline

**Goal:** Polish the visualization with timeline view, search, and better interactivity.

**Features:**
- **Search bar**: Full-text search over entity names and source content
- **Timeline view**: Events and dates on a horizontal timeline
- **Subgraph exploration**: Select a node, see its N-hop neighborhood
- **Layout options**: Force-directed, hierarchical, circular
- **URL routing**: Deep link to specific entities (`#entity=person-john-doe`)
- **Responsive design**: Works on mobile
- **Entity cards**: Rich cards with images when available
- **Export**: Download subgraph as JSON-LD, CSV, or image

**Estimated effort:** 4-5 days

---

### Phase 8: Advanced Features (Future)

**Ideas for later phases (not planned in detail):**

1. **Conflict detection**: Flag contradictory relationships across sources
2. **Source quality scoring**: Rate sources by entity coverage, citation density
3. **Collaborative review**: GitHub Issues workflow for ambiguous entities
4. **Temporal graph**: Show how the graph evolves over time (git history)
5. **SPARQL endpoint**: Serve the JSON-LD via a lightweight SPARQL proxy
6. **Multi-language support**: spaCy multilingual models
7. **Video transcript extraction**: Whisper API for video sources
8. **Graph embeddings**: Use node2vec for similarity search
9. **Automatic source suggestions**: Given the graph, suggest missing sources
10. **Federation**: Link to other knowledge graphs (Wikidata, DBpedia)

---

## Key Workflow: End-to-End Source Processing

```
Contributor creates PR
    │
    ├── submissions/2026-03-26-new-source.yaml
    └── submissions/files/document.pdf (if PDF)
    │
    ▼
┌─────────────────────────────┐
│  validate-pr.yml            │
│  • YAML schema validation   │
│  • File size checks         │
│  • Type-specific checks     │
│  • Label PR with source type│
└──────────┬──────────────────┘
           │ PR merged
           ▼
┌─────────────────────────────────────────────────┐
│  process-sources.yml                            │
│                                                 │
│  1. git diff HEAD~1 → find new submissions      │
│  2. For each new submission:                    │
│     a. Read YAML manifest                       │
│     b. Convert source → markdown                │
│        - PDF: pymupdf4llm                       │
│        - URL: trafilatura                       │
│        - Account: passthrough                   │
│     c. Commit to sources/<slug>/                │
│     d. spaCy NER → raw entities                 │
│     e. Claude Haiku → relationships +           │
│        disambiguation                           │
│     f. Generate JSON-LD fragment                │
│     g. Update entity registry                   │
│  3. Merge all fragments → global.jsonld         │
│  4. Generate stats.json                         │
│  5. Commit graph/ changes                       │
│  6. Push                                        │
└──────────┬──────────────────────────────────────┘
           │ triggers
           ▼
┌─────────────────────────────┐
│  deploy-pages.yml           │
│  • Copy graph data to site/ │
│  • Deploy to GitHub Pages   │
└─────────────────────────────┘
```

---

## PR Template

```markdown
## Source Submission

<!-- Please fill in the YAML below and attach any files -->

### Submission YAML

Create a file: `submissions/YYYY-MM-DD-short-title.yaml`

```yaml
source:
  title: ""
  type: ""          # pdf | url | account | video
  url: ""           # Required for url/video types
  file: ""          # Required for pdf type (place file in submissions/files/)
  author: ""        # Your name or original author
  date_added: ""    # Today's date (YYYY-MM-DD)
  tags: []          # Relevant tags
  description: ""   # Brief description of the source
```

### For "account" type
Also create `submissions/YYYY-MM-DD-short-title.md` with the narrative text.

### Checklist
- [ ] YAML is valid
- [ ] Source type is correct
- [ ] File attached (if PDF)
- [ ] URL accessible (if URL/video)
- [ ] Tags are relevant
```

---

## JSON-LD Fragment Example

```jsonld
{
  "@context": "../context.jsonld",
  "@id": "source:2026-03-26-battle-of-midway",
  "@type": "woo:SourceFragment",
  "source": {
    "title": "Battle of Midway: A Naval Analysis",
    "file": "sources/2026-03-26-battle-of-midway/content.md",
    "date_added": "2026-03-26"
  },
  "entities": [
    {
      "@id": "entity:person-chester-nimitz",
      "@type": "Person",
      "name": "Chester Nimitz",
      "aliases": ["Admiral Nimitz", "Nimitz"],
      "mentionedIn": ["source:2026-03-26-battle-of-midway"]
    },
    {
      "@id": "entity:place-midway-atoll",
      "@type": "Place",
      "name": "Midway Atoll",
      "geo": {
        "@type": "GeoCoordinates",
        "latitude": 28.2072,
        "longitude": -177.3735
      },
      "mentionedIn": ["source:2026-03-26-battle-of-midway"]
    },
    {
      "@id": "entity:event-battle-of-midway",
      "@type": "Event",
      "name": "Battle of Midway",
      "startDate": "1942-06-04",
      "endDate": "1942-06-07",
      "mentionedIn": ["source:2026-03-26-battle-of-midway"]
    }
  ],
  "relationships": [
    {
      "@type": "woo:Relationship",
      "subject": {"@id": "entity:person-chester-nimitz"},
      "predicate": "woo:commandedAt",
      "object": {"@id": "entity:event-battle-of-midway"},
      "confidence": 0.92,
      "extractedBy": "claude-haiku"
    },
    {
      "@type": "woo:Relationship",
      "subject": {"@id": "entity:event-battle-of-midway"},
      "predicate": "woo:locatedIn",
      "object": {"@id": "entity:place-midway-atoll"},
      "confidence": 0.98,
      "extractedBy": "spacy"
    }
  ]
}
```

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Entity disambiguation errors | Graph quality degrades | High | Confidence scores + human review queue |
| LLM costs grow with source volume | Budget overrun | Medium | Per-source cost cap, caching, batch API |
| Large PDFs exceed GitHub file limits | Can't store sources | Low | Git LFS for files >50MB, or store only markdown |
| spaCy misses domain-specific entities | Incomplete extraction | Medium | Custom entity patterns, domain-specific spaCy models |
| JSON-LD global graph gets too large for browser | Slow visualization | Medium | Lazy loading, paginated graph, server-side filtering |
| GitHub Actions minutes exhausted | Pipeline stops | Low | Optimize workflow runtime, use caching |
| Rate limiting on web scraping | Incomplete ingestion | Medium | Retry with backoff, respect robots.txt |
| Contributor submits copyrighted content | Legal risk | Medium | Submission guidelines + review process |

---

## Open Questions (Resolved)

- [x] **Domain scope**: General-purpose, but each instance targets a specific topic (e.g., Epstein files, CIA research, UFO research). Ontology stays domain-agnostic; instances customize via tags and custom predicates.
- [x] **Graph size expectations**: ~2,700 PDFs (16GB) already exist locally. Expect 10K+ entities. Visualization must support lazy loading and clustering.
- [x] **Access control**: Public repo, public GitHub Pages.
- [x] **Video processing**: Deferred. Video links stored as attachments only.
- [x] **Entity review workflow**: Auto-resolve with confidence scores. Imperfect graph is fine initially; contributors fix via PRs. No blocking review process.
- [x] **Custom predicates**: Extensible. Contributors can add predicates; base set provides common vocabulary.

## Scale Considerations

Based on existing data (~2,700 JFK PDFs, 16GB):
- **PDFs stay external** — only links in submissions, extracted markdown + graph committed to repo
- **Initial batch cost** — ~2,700 sources × ~$0.03 = ~$80 for full LLM pass (manageable)
- **Visualization** — must handle 10K+ nodes; use Cytoscape clustering, lazy loading, search-driven exploration
- **Processing time** — batch pipeline needed for initial bulk import (not just PR-by-PR)
- **Git LFS** — may be needed for extracted images if volume is high

---

## Success Criteria

1. A contributor can submit a PDF via PR in under 5 minutes
2. Processing completes in under 10 minutes per source
3. The knowledge graph is viewable within 1 minute of processing completion
4. Entity extraction achieves >80% precision (spot-checked)
5. LLM costs stay under $1/month for typical usage (<50 sources/month)
6. The visualization loads in <3 seconds
7. Entities are correctly linked across sources >70% of the time
