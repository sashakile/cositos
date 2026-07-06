"""Certifies the kernel capability probe against a real python3 kernel (Tier 1).

Installs a kernelspec pointing at this interpreter (so ipykernel's Comm is importable),
then asserts the probe classifies it BIDIRECTIONAL. Opt-in like the other e2e tests.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

jupyter_client = pytest.importorskip("jupyter_client")
ipykernel_ks = pytest.importorskip("ipykernel.kernelspec")

from jupyter_client.kernelspec import KernelSpecManager  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "probe"))
from kernel_probe import Tier, probe  # noqa: E402

KERNEL_NAME = "cositos-probe"


@pytest.fixture(scope="module")
def kernelspec():
    ipykernel_ks.install(user=True, kernel_name=KERNEL_NAME)
    yield KERNEL_NAME
    with contextlib.suppress(Exception):
        KernelSpecManager().remove_kernel_spec(KERNEL_NAME)


@pytest.mark.e2e
def test_probe_classifies_python3_as_bidirectional(kernelspec):
    # python3 (ipykernel) has full comm support: open + send + receive/echo.
    assert probe(kernelspec, program="python3") is Tier.BIDIRECTIONAL
