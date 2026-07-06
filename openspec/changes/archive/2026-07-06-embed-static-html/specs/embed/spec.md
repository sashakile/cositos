## ADDED Requirements

### Requirement: Serialized Documents Render to Self-Contained HTML
The system SHALL render a widget-state `Document` into a single HTML string that embeds
the state and loads the stock ipywidgets html-manager, so a saved UI displays without a
running kernel.

#### Scenario: The document state is embedded as widget-state+json
- **WHEN** `embed_html(document)` is called
- **THEN** the output contains a `<script type="application/vnd.jupyter.widget-state+json">` block whose parsed JSON equals `document`

#### Scenario: A view script is emitted per model
- **WHEN** `embed_html(document)` is called with a document whose state has model ids `a` and `b`
- **THEN** the output contains a `application/vnd.jupyter.widget-view+json` script for each of `a` and `b`, each carrying `version_major`/`version_minor`/`model_id`

#### Scenario: Only requested views are emitted
- **WHEN** `embed_html(document, views=["a"])` is called
- **THEN** exactly one `widget-view+json` script is emitted, for model id `a`

#### Scenario: The CDN html-manager loader is included
- **WHEN** `embed_html(document)` is called
- **THEN** the output references `@jupyter-widgets/html-manager` from a CDN and (by default) require.js

### Requirement: Embedded JSON Is Script-Escaped
The system SHALL escape the embedded JSON so that widget content containing `</script>`
or `<!--` cannot break out of the script element.

#### Scenario: A closing script tag in state is neutralised
- **GIVEN** a document whose state contains the substring `</script>`
- **WHEN** `embed_html(document)` is called
- **THEN** the raw substring `</script>` does not appear inside the widget-state block (its `<` is escaped)

### Requirement: HTML Can Be Written To A File
The system SHALL write the rendered HTML to a path.

#### Scenario: write_html persists the page
- **WHEN** `write_html(path, document)` is called
- **THEN** the file at `path` contains the same HTML as `embed_html(document)`
