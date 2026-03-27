# Submitting Sources to WooGraph

Contributors add sources by opening a Pull Request with a YAML manifest file.

## Quick Start

1. Fork this repository
2. Create a file in `submissions/` named `YYYY-MM-DD-short-title.yaml`
3. Fill in the YAML (see format below)
4. For PDF sources, add the file to `submissions/files/`
5. Open a Pull Request

The CI will validate your submission automatically. Once merged, the pipeline processes your source and updates the knowledge graph.

## File Naming

Use the format: `YYYY-MM-DD-short-descriptive-title.yaml`

Examples:
- `2026-03-26-battle-of-midway.yaml`
- `2026-03-26-cia-memo-1963.yaml`

## YAML Format

```yaml
source:
  title: "Full title of the source"
  type: pdf           # pdf | url | account | video
  url: null           # Required for url and video types
  file: null          # Required for pdf type — filename relative to submissions/files/
  author: "Author or contributor name"
  date_added: "2026-03-26"  # Today's date, YYYY-MM-DD
  tags: ["tag1", "tag2"]    # Relevant topic tags
  description: "Brief description of what this source contains"
```

## Source Types

| Type | When to use | Required fields |
|------|-------------|-----------------|
| `pdf` | A document file you are uploading | `file` |
| `url` | A web page or article | `url` |
| `video` | A YouTube or video link | `url` |
| `account` | A personal account or testimony written by the contributor | none (create a companion `.md` file) |

### PDF sources

Place the PDF in `submissions/files/` and set `file` to just the filename:

```yaml
source:
  type: pdf
  file: "my-document.pdf"
```

### URL sources

```yaml
source:
  type: url
  url: "https://example.com/article"
```

### Personal accounts

Create two files with the same base name:
- `submissions/2026-03-26-my-account.yaml` (metadata)
- `submissions/2026-03-26-my-account.md` (narrative text)

```yaml
source:
  type: account
  author: "Your Name"
  description: "My first-hand account of..."
```

## Validation

The `_schema.yaml` file in this directory defines the JSON Schema used to validate submissions. Your PR will fail CI if the YAML does not conform.

Common mistakes:
- Missing `url` for `url` or `video` types
- Missing `file` for `pdf` types
- `date_added` not in `YYYY-MM-DD` format
- `url` field not a valid URI (must include `https://`)
