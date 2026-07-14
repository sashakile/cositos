#!/usr/bin/env bash
# Binder startup script — launches JupyterLab with cositos examples.
#
# This is invoked by BinderHub after the container starts. It can set environment
# variables, install runtime deps that need network access, or run one-time setup.
#
# BinderHub calls start-notebook.py after this, so we just set up the environment.

set -euo pipefail

echo "=== cositos Binder container ==="
echo "Kernels available:"
jupyter kernelspec list 2>&1

# Verify cositos is importable in Python
python -c "import cositos; print(f'cositos {cositos.__version__} OK')" 2>&1 || echo "Warning: cositos Python import failed"

# Verify Cositos.jl is available in Julia
julia -e 'import Pkg; Pkg.activate("/opt/julia/environments/cositos"); using Cositos; println("Cositos.jl OK")' 2>&1 || echo "Warning: Cositos.jl import failed"

# Verify the Clojure kernel is registered
jupyter kernelspec list 2>&1 | grep -q cositos-clj && echo "Clojure kernel OK" || echo "Warning: Clojure kernel not registered"

echo "=== Ready ==="