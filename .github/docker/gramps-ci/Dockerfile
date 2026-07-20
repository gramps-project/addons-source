# .github/docker/gramps-ci/Dockerfile
#
# Gramps CI image. The Gramps minor series (6.0, 6.1, …) is picked at
# build time via the GRAMPS_SERIES build arg, so the same Dockerfile
# produces gramps-ci:gramps60, gramps-ci:gramps61, … without per-branch
# edits. Includes everything jobs need:
#   - Python + pip-installed Gramps, PyGObject, pycairo
#   - GTK typelibs (so addon modules that `from gi.repository import Gtk`
#     at module load time are importable — widgets still need xvfb to render)
#   - intltool/gettext/git for make.py builds
#   - ruff, dbf for lint/test tooling (tests use stdlib unittest per AGENTS.md)
#   - xvfb + xauth for tests that actually render (wrap with `xvfb-run`)
#
# No display server runs by default — the image is headless unless a command
# explicitly invokes `xvfb-run`. When running with docker locally, pass
# `--init` (or use a container runtime that injects tini) because xvfb-run
# hangs if it inherits PID 1.
#
# Gramps install path. PyPI is tried first; when no gramps==${SERIES}.*
# release exists (e.g. while 6.1 is still in development) the build
# falls back to a SHA-pinned git clone of
# gramps-project/gramps@maintenance/gramps${SERIES_NODOT}. Other pip
# failures (network, etc.) are NOT silently retried so a transient
# PyPI outage cannot flip a normally-released branch to "test against
# moving tip" mode. docker-build.yml captures the upstream SHA via
# git ls-remote and passes it in as GRAMPS_FALLBACK_SHA; the SHA
# becomes part of the buildx cache key so a moved upstream tip
# actually re-runs the install layer.
#
# Local build (released series):
#   docker build --build-arg GRAMPS_SERIES=6.0 .github/docker/gramps-ci
#
# Local build (unreleased series, e.g. 6.1):
#   sha=$(git ls-remote https://github.com/gramps-project/gramps.git \
#         refs/heads/maintenance/gramps61 | awk '{print $1}')
#   docker build --build-arg GRAMPS_SERIES=6.1 \
#                --build-arg GRAMPS_FALLBACK_SHA=$sha \
#                .github/docker/gramps-ci
#
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

# Gramps minor series to install (e.g. 6.0, 6.1). No default — must be
# passed explicitly so a wrong default cannot silently produce an image
# for the wrong Gramps series. docker-build.yml derives this from the
# branch ref.
ARG GRAMPS_SERIES
# Commit SHA on gramps-project/gramps@maintenance/grampsNN. Only used
# when no gramps==${GRAMPS_SERIES}.* release exists on PyPI. Ignored
# otherwise. Empty default is intentional — on released branches the
# fallback never fires.
ARG GRAMPS_FALLBACK_SHA=""
RUN [ -n "$GRAMPS_SERIES" ] || { echo "GRAMPS_SERIES is required (e.g. 6.0)"; exit 1; }

LABEL org.opencontainers.image.source="https://github.com/gramps-project/addons-source"
LABEL org.opencontainers.image.description="Gramps ${GRAMPS_SERIES} CI image (Python, Gramps, GTK typelibs, xvfb)"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgirepository-2.0-dev \
        gir1.2-glib-2.0 \
        gir1.2-gtk-3.0 \
        gir1.2-pango-1.0 \
        gir1.2-gdkpixbuf-2.0 \
        gir1.2-atk-1.0 \
        gir1.2-gexiv2-0.10 \
        gcc \
        pkg-config \
        python3-dev \
        libcairo2-dev \
        intltool \
        gettext \
        git \
        xvfb \
        xauth \
    && rm -rf /var/lib/apt/lists/*

# Addon runtime deps (dbf, networkx, lxml, svgwrite, boto3, etc.) are
# NOT baked in here — ci.yml's "Install addon runtime deps (derived from
# requires_mod)" step pip-installs them at CI runtime from every
# .gpr.py's requires_mod list, matching what Gramps' Addon Manager does
# for an end user. Keeps .gpr.py the single source of truth.
# ruff is PINNED: an unpinned ruff would change the lint verdict on rebuild (a
# new rule in the E9/F63/F7/F82 selection flips a lane red — or silently stops
# flagging — with no repo change). Bump deliberately, not by rebuild drift.
RUN pip install --no-cache-dir PyGObject pycairo orjson ruff==0.15.22

# Install gramps: PyPI first, SHA-pinned git clone as fallback.
RUN /bin/bash -eo pipefail <<'BASH'
suffix_nodot="${GRAMPS_SERIES//./}"
if pip install --no-cache-dir "gramps==${GRAMPS_SERIES}.*" 2>/tmp/pip.err; then
    echo "::notice::installed gramps==${GRAMPS_SERIES}.* from PyPI"
elif grep -q "No matching distribution found for gramps==" /tmp/pip.err; then
    if [ -z "${GRAMPS_FALLBACK_SHA}" ]; then
        echo "::error::no gramps==${GRAMPS_SERIES}.* on PyPI and GRAMPS_FALLBACK_SHA is unset"
        exit 1
    fi
    echo "::warning::no gramps==${GRAMPS_SERIES}.* on PyPI; installing from gramps-project/gramps@maintenance/gramps${suffix_nodot} at ${GRAMPS_FALLBACK_SHA}"
    mkdir -p /tmp/gramps
    cd /tmp/gramps
    git init -q
    git remote add origin https://github.com/gramps-project/gramps.git
    git fetch --depth 1 origin "${GRAMPS_FALLBACK_SHA}"
    git checkout FETCH_HEAD
    pip install --no-cache-dir .
    cd /
    rm -rf /tmp/gramps
else
    echo "::error::pip install gramps failed (non-version reason); aborting rather than silently switching to git tip"
    cat /tmp/pip.err
    exit 1
fi
BASH

# NOTE: the build toolchain (gcc, python3-dev, pkg-config) is deliberately KEPT
# in the image — it is not purged here. Addon requires_mod are pip-installed at CI
# runtime (ci.yml "Install addon runtime deps"), and the source-built ones with no
# wheel on the apt lane (pygraphviz, psycopg2) compile a C extension during that
# step. Purging gcc/pkg-config left those builds with no compiler, so they failed
# and were swallowed by the install step's "|| echo … (continuing)" — silently
# degrading the affected addon's coverage while the job stayed green. The per-
# package system headers those builds link against (libgraphviz-dev, libpq-dev on
# apt) are derived from the addons' .gpr.py and installed at CI runtime by the same
# single-source map as requires_gi/requires_exe — see .github/scripts/
# addon_system_deps.py (MOD_BUILD_PACKAGES) and ci.yml's "Install addon system
# deps" step — so .gpr.py stays the single source of truth.

RUN python -c "from gramps.gen.const import VERSION; print('Gramps', VERSION)" \
 && python -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK OK')"

WORKDIR /workspace
