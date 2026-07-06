# Tasks: embed-static-html

## 1. embed_html (behaviour, TDD)

- [ ] 1.1 RED: `embed_html(document)` output parses to contain a `widget-state+json` block equal to `document`.
- [ ] 1.2 GREEN: build the widget-state block + CDN html-manager (require.js + embed-amd.js) loader + html wrapper.
- [ ] 1.3 RED/GREEN: a `widget-view+json` script per model id; `views=[...]` restricts to those ids.
- [ ] 1.4 RED/GREEN: script-escape the embedded JSON (`</script>`, `<!--`).

## 2. write_html + wiring

- [ ] 2.1 `write_html(path, document, **kwargs)` writes `embed_html(...)`; test file contents match.
- [ ] 2.2 Re-export `embed_html`/`write_html` from `src/cositos/__init__.py`.

## 3. Gates

- [ ] 3.1 `mise run verify` green (lint, typecheck, coverage, complexity, specs).
- [ ] 3.2 Note CDN dependency + a manual browser-render check in `docs/` or the embed docstring.
