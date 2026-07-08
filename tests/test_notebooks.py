"""Execute the checked-in example notebooks against real kernels and assert they render.

Guards the interactive-notebook deliverables (cositos-059.x) against rot: each notebook is
run headlessly and must (a) raise no cell errors and (b) emit the anywidget widget-view
mimetype, i.e. actually render a cositos widget over the live comm. Complements the
lower-level comm-traffic checks in ``test_e2e_jupyter.py`` / ``test_e2e_julia.py``.

Skipped unless the e2e extras (nbclient/jupyter_client) are installed. The Julia notebook
additionally needs ``julia`` on PATH and a Cositos-enabled IJulia kernelspec.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")

NOTEBOOKS = Path(__file__).resolve().parent.parent / "examples" / "notebooks"
WIDGET_VIEW_MIME = "application/vnd.jupyter.widget-view+json"


def _execute(path: Path, kernel_name: str) -> nbformat.NotebookNode:
    nb = nbformat.read(path, as_version=4)
    client = nbclient.NotebookClient(nb, kernel_name=kernel_name, timeout=180)
    client.execute()
    return nb


def _assert_clean_render(nb) -> None:
    rendered = False
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        for out in cell.get("outputs", []):
            assert out.get("output_type") != "error", (
                f"cell errored: {out.get('ename')}: {out.get('evalue')}"
            )
            if WIDGET_VIEW_MIME in out.get("data", {}):
                view = out["data"][WIDGET_VIEW_MIME]
                assert view["version_major"] == 2
                assert view["model_id"]  # a real comm id
                rendered = True
    assert rendered, f"no {WIDGET_VIEW_MIME} output — the widget did not render"


@pytest.mark.e2e
def test_python_counter_notebook_executes_and_renders():
    pytest.importorskip("jupyter_client")
    ipykernel_ks = pytest.importorskip("ipykernel.kernelspec")
    # Install a python3 kernelspec bound to THIS interpreter (so cositos is importable).
    ipykernel_ks.install(user=True, kernel_name="cositos-nb-py")
    try:
        nb = _execute(NOTEBOOKS / "python_counter.ipynb", "cositos-nb-py")
        _assert_clean_render(nb)
    finally:
        from jupyter_client.kernelspec import KernelSpecManager

        with contextlib.suppress(Exception):
            KernelSpecManager().remove_kernel_spec("cositos-nb-py")


@pytest.fixture(scope="module")
def julia_notebook_kernel(tmp_path_factory):
    if shutil.which("julia") is None:
        pytest.skip("julia not on PATH")
    pytest.importorskip("jupyter_client")
    julia_dir = Path(__file__).resolve().parent.parent / "julia"
    proj = tmp_path_factory.mktemp("cositos_julia_nb")
    install = (
        f'import Pkg; Pkg.activate(raw"{proj}"); '
        f'Pkg.develop(path=raw"{julia_dir}"); Pkg.add("IJulia"); using IJulia; '
        f'p = IJulia.installkernel("cositos-nb-julia"; env=Dict("JULIA_PROJECT"=>raw"{proj}")); '
        f"println(basename(p))"
    )
    result = subprocess.run(
        ["julia", "-e", install], capture_output=True, text=True, timeout=600, check=False
    )
    if result.returncode != 0:  # pragma: no cover - surfaces setup failures clearly
        pytest.fail(f"julia kernel setup failed:\n{result.stdout}\n{result.stderr}")
    name = result.stdout.strip().splitlines()[-1]
    yield name
    from jupyter_client.kernelspec import KernelSpecManager

    with contextlib.suppress(Exception):
        KernelSpecManager().remove_kernel_spec(name)


@pytest.mark.e2e
def test_julia_counter_notebook_executes_and_renders(julia_notebook_kernel):
    # The checked-in notebook pins kernel name "julia-1.12"; execute against the
    # Cositos-enabled kernel the fixture built instead.
    nb = _execute(NOTEBOOKS / "julia_counter.ipynb", julia_notebook_kernel)
    _assert_clean_render(nb)


@pytest.fixture(scope="module")
def clojure_notebook_kernel():
    if shutil.which("clojure") is None:
        pytest.skip("clojure not on PATH")
    pytest.importorskip("jupyter_client")
    import json

    from jupyter_client.kernelspec import KernelSpecManager

    name = "cositos-nb-clojure"
    kernel_json = {
        "argv": [
            "clojure",
            "-Sdeps",
            '{:deps {clojupyter/clojupyter {:mvn/version "0.4.332"}} '
            ':mvn/repos {"clojars" {:url "https://repo.clojars.org/"}}}',
            "-M",
            "-m",
            "clojupyter.kernel.core",
            "{connection_file}",
        ],
        "display_name": "Clojure (cositos e2e)",
        "language": "clojure",
    }
    ksm = KernelSpecManager()
    with contextlib.suppress(Exception):
        ksm.remove_kernel_spec(name)
    tmp_dir = Path(ksm.user_kernel_dir) / name
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "kernel.json").write_text(json.dumps(kernel_json))
    yield name
    with contextlib.suppress(Exception):
        ksm.remove_kernel_spec(name)


@pytest.mark.e2e
def test_clojure_counter_notebook_executes_and_renders(clojure_notebook_kernel):
    # The checked-in notebook pins kernel name "cositos-clj" (a developer's local
    # clojupyter install); execute against the throwaway bare-clojupyter kernel the
    # fixture built instead. The notebook's own first cell adds cositos to the classpath
    # at runtime via pomegranate, so a bare kernel is all this needs.
    nb = _execute(NOTEBOOKS / "clojure_counter.ipynb", clojure_notebook_kernel)
    _assert_clean_render(nb)
