# .github/docker/gramps-headless/Dockerfile
#
# Headless Gramps 6.0 image for lint, compile-check, unit tests, and build.
# Includes PyGObject (GLib only, no GTK) because gramps.gen.const
# requires gi.repository.GLib for path resolution.
#
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.source="https://github.com/gramps-project/addons-source"
LABEL org.opencontainers.image.description="Gramps 6.0 headless (GLib only, no GTK) for CI"

# System libraries needed to build PyGObject from pip + build tools for make.py
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgirepository-2.0-dev \
        gir1.2-glib-2.0 \
        gcc \
        pkg-config \
        python3-dev \
        libcairo2-dev \
        intltool \
        gettext \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install PyGObject (compiled for this Python) + Gramps + CI tooling
RUN pip install --no-cache-dir \
        PyGObject \
        pycairo \
        "gramps>=6.0,<6.1" \
        orjson \
        pytest \
        ruff \
        dbf

# Clean up build deps that are no longer needed at runtime
RUN apt-get purge -y gcc python3-dev pkg-config && apt-get autoremove -y

# Smoke-test: gramps core is importable via GLib
RUN python -c "from gramps.gen.const import VERSION; print('Gramps', VERSION)"

WORKDIR /workspace
