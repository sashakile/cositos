# Live hosting: myBinder + Voila

Render cositos widgets **live** (a running kernel + real comm traffic), as opposed to the
static export in `../static-export/`. Both paths below rely on `Widget._repr_mimebundle_`,
so a bare `widget` in a cell renders.

## myBinder

myBinder turns a Git repo into a reproducible, kernel-backed JupyterLab in the browser.

1. Put `environment.yml` (this folder's file, adjusted for your repo layout) at the
   repository root or in a top-level `binder/` directory. It installs cositos from the
   repo plus `anywidget` (the frontend cositos targets), `jupyterlab`, and `voila`.
2. Launch: `https://mybinder.org/v2/gh/<owner>/<repo>/<branch>`
3. Open `examples/notebooks/python_counter.ipynb` and run all cells — the widget renders
   and interaction round-trips over the live comm.

Add a launch badge to your README:

```markdown
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/<owner>/<repo>/<branch>)
```

## Voila

[Voila](https://voila.readthedocs.io) serves a single notebook as a standalone web app
(hidden code, live widgets):

```bash
pip install voila anywidget
voila examples/notebooks/python_counter.ipynb
```

Voila executes the notebook on a kernel and streams widget views to the browser — the
same live comm path as JupyterLab, no notebook UI. Combine with Binder to publish an
interactive app from a repo.

## Status

The environment and commands are provided as a recipe. They were **not executed in this
evaluation environment** (no Binder/Voila server available here); the live comm path they
use is the one exercised by the real-kernel end-to-end test (`tests/test_e2e_jupyter.py`).

## Static alternative

If you don't need a live kernel, export to a self-contained page instead — see
`../static-export/` and `cositos.embed.write_html`.
