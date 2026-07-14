# Live hosting: myBinder + Voila

Render cositos widgets **live** (a running kernel + real comm traffic), as opposed to the
static export in `../static-export/`. Both paths below rely on `Widget._repr_mimebundle_`,
so a bare `widget` in a cell renders.

## Architecture

The repo ships a **two-stage container build** (copied from
[clojnder](https://github.com/sashakile/clojnder)), designed for fast BinderHub rebuilds
and deterministic images:

```
Dockerfile.binder-base       # Heavy: language runtimes + Jupyter kernels
       │                         Published to GHCR, rarely rebuilt
       ▼
Dockerfile.binder            # Project code: pip install cositos, Julia dev,
       │                         Clojure dep prefetch — rebuilt on every commit
       ▼
.binder/Dockerfile           # BinderHub entrypoint: pinned to a specific GHCR
                                 digest for deterministic builds
```

Three images are involved:

| Image | File | Contents | Rebuild cadence |
|---|---|---|---|
| `cositos-binder-base` | `Dockerfile.binder-base` | Python (ipykernel, anywidget, jupyterlab, voila), Julia + IJulia, Clojure CLI + clojupyter, R + IRkernel, .NET SDK + dotnet-interactive | Runtime version bumps only |
| `cositos-binder` | `Dockerfile.binder` | cositos Python package (`pip install -e .`), Cositos.jl (`Pkg.develop`), Clojure deps prefetch, all example notebooks | Every commit |
| `cositos-binder` (pinned) | `.binder/Dockerfile` | Same as above, pinned to an immutable GHCR digest | After every publish |

### Containers vs. environment.yml

An earlier `environment.yml`-based Binder recipe also lives in this directory. The
Dockerfile path is preferred because it:

- Supports **all five language kernels** (Python, Julia, Clojure, R, C#) — conda env only
  gets you Python
- Uses **Docker layer caching** for fast rebuilds: changing an example notebook doesn't
  re-install Julia or re-fetch Clojure deps
- Is **deterministic**: `.binder/Dockerfile` pins a specific digest, so today's build is
  identical to next week's

## myBinder

Try cositos live in your browser — no local install needed:

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/sashakile/cositos/main?urlpath=lab/tree/examples/notebooks/python_counter.ipynb)

After Binder finishes building (2-5 minutes the first time, cached thereafter):

1. **Python counter** (`python_counter.ipynb`, default): run all cells → click **increment** → read `state['count']` back from the kernel.
2. **Julia counter** (`julia_counter.ipynb`): switch kernel to **Julia**, run all cells — same widget, Julia backend.
3. **Clojure counter** (`clojure_counter.ipynb`): switch kernel to **Clojure (cositos)**, run all cells — same widget, Clojure backend.

### Pre-built GHCR images

The CI publish workflow (`.github/workflows/publish-binder-images.yml`) builds and pushes
both images to GHCR on every push to `main`:

- `ghcr.io/sashakile/cositos-binder-base` — base image (sha + latest tags)
- `ghcr.io/sashakile/cositos-binder` — project-code image (sha + latest tags)

After a publish, update the digest in `.binder/Dockerfile` to pin BinderHub to the new
deterministic build.

## Local testing

Build and run the Binder image from local source (no published GHCR image needed):

```bash
# Build the binder image (Dockerfile.binder layers over base)
mise run binder-local

# Serve with the Python counter notebook
mise run binder-serve
# Open http://localhost:8888

# Serve with a different notebook
mise run binder-serve-julia     # Julia counter
mise run binder-serve-clojure   # Clojure counter
```

To rebuild the base image locally (rarely needed):

```bash
mise run binder-base
```

### What's included

| Language | Kernel | Kernel name in Jupyter | Live widgets? |
|---|---|---|---|
| Python | ipykernel | `Python 3` | ✅ Tier 1 |
| Julia | IJulia (`CositosIJuliaExt`) | `Julia-1.11` | ✅ Tier 1 |
| Clojure | clojupyter (deps-based) | `Clojure (cositos)` | ✅ Tier 1 (internal-API crack) |
| R | IRkernel | `ir` | 🚧 upstream blocked (comm-open bug) |

See `probe/README.md` for the full tier classification and how each kernel was tested.

### First-Clojure-kernel cold start

The Clojure kernel uses a deps-based kernelspec that resolves dependencies from Clojars at
launch time. The first Clojure notebook cell may take 30-60 seconds while Maven downloads
the full clojupyter dep tree. Subsequent cells in the same session are fast.

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

In the built Binder image, you can run Voila instead of JupyterLab:

```bash
docker run --rm -p 8866:8866 \
  cositos-binder \
  voila --port=8866 --no-browser examples/notebooks/python_counter.ipynb
```

## Known limitations

- The base image downloads Julia + IJulia from the Julia General registry, and
  clojupyter from Clojars via the Clojure CLI. Both reach external package registries at
  build time. If your network blocks those, pre-build the base image on an unrestricted
  network.
- The Julia download URL targets `linux-x86_64` (BinderHub's architecture). Local testing
  on ARM (Apple Silicon) requires Docker's `--platform linux/amd64` or emulation.
- R and C# kernels are installed but cannot run live widgets due to upstream kernel
  limitations (see the [probe results](../../probe/README.md) for details). They are
  available for protocol-core-only testing.

## Static alternative

If you don't need a live kernel, export to a self-contained page instead — see
`../static-export/` and `cositos.embed.write_html`.