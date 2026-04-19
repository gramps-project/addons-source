# .github/docker/gramps-ci/Dockerfile
#
# Unified Gramps 6.0 CI image. Includes everything jobs need:
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
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.source="https://github.com/gramps-project/addons-source"
LABEL org.opencontainers.image.description="Unified Gramps 6.0 CI image (Python, Gramps, GTK typelibs, xvfb)"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgirepository-2.0-dev \
        gir1.2-glib-2.0 \
        gir1.2-gtk-3.0 \
        gir1.2-pango-1.0 \
        gir1.2-gdkpixbuf-2.0 \
        gir1.2-atk-1.0 \
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

RUN pip install --no-cache-dir \
        PyGObject \
        pycairo \
        "gramps>=6.0,<6.1" \
        orjson \
        ruff \
        dbf

RUN apt-get purge -y gcc python3-dev pkg-config && apt-get autoremove -y

RUN python -c "from gramps.gen.const import VERSION; print('Gramps', VERSION)" \
 && python -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK OK')"

WORKDIR /workspace
