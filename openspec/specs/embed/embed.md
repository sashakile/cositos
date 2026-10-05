---
id: embed
kind: intent
statement: "WHEN embed_html is called with a serialized widget-state Document THE system SHALL render a single self-contained HTML string that embeds the state, one view script per requested model, and the CDN html-manager loader, without a running kernel"
---

# embed

Renders a serialized widget-state `Document` into one self-contained HTML page: the
widget state is embedded as `application/vnd.jupyter.widget-state+json`, one
`application/vnd.jupyter.widget-view+json` script is emitted per model, and the stock
ipywidgets html-manager is loaded from a CDN. It is not a live widget host — no kernel
and no round-trip; it renders a static snapshot for any browser or static host.

## Constraints

| id | kind | expr | traces_to |
|----|------|------|-----------|
| c1 | invariant | the embedded widget-state block's parsed JSON equals the document state enriched with anywidget view identity | [[embed]] |
| c2 | invariant | exactly one widget-view script is emitted per requested model id, each carrying version_major, version_minor and model_id | [[embed]] |
| c3 | invariant | the output references the @jupyter-widgets/html-manager from a CDN | [[embed]] |
| c4 | invariant | the raw substring `</script>` never appears inside the embedded widget-state block | [[embed]] |
| c5 | effect | write_html persists exactly the embed_html output at the given path | [[embed]] |

## Model

### States

- `document`
- `html`

### Transitions

| id | from | to | guard |
|----|------|----|-------|
| t1 | document | html | [[embed.c1]] |
| t2 | html | html | [[embed.c4]] |

## Properties

| id | kind | derives_from | generator | predicate |
|----|------|--------------|-----------|-----------|
| p1 | unit | [[embed.c1]] | any valid widget-state Document | embed_html output contains a widget-state+json block whose parsed JSON equals the enriched state |
| p2 | unit | [[embed.c2]] | a document with model ids a and b, views=["a"] | exactly one view script is emitted and it names model id a |
| p3 | unit | [[embed.c3]] | any valid widget-state Document | the output contains the CDN html-manager loader reference |
| p4 | unit | [[embed.c4]] | a document whose state contains the substring `</script>` | the raw substring does not appear inside the widget-state block |
| p5 | unit | [[embed.c5]] | a document and a temp path | the written file equals embed_html(document) |
