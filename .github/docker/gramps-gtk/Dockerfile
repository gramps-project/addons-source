# .github/docker/gramps-gtk/Dockerfile
#
# Full Gramps 6.0 image with GTK/GObject Introspection for integration tests.
# Extends gramps-headless (which already has PyGObject + GLib) with the GTK
# typelibs and supporting libraries.
#
ARG BASE_IMAGE=ghcr.io/gramps-project/addons-source/gramps-headless:gramps60
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.source="https://github.com/gramps-project/addons-source"
LABEL org.opencontainers.image.description="Gramps 6.0 with GTK for integration tests"

# Install GTK typelibs and supporting libraries.
# PyGObject is already pip-installed in the headless image, so we only need
# the GI typelib data files for GTK, Pango, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gir1.2-gtk-3.0 \
        gir1.2-pango-1.0 \
        gir1.2-gdkpixbuf-2.0 \
        gir1.2-atk-1.0 \
        xvfb \
        xauth \
    && rm -rf /var/lib/apt/lists/*

# Smoke-test: GTK is importable via the pip-installed PyGObject
RUN python -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK OK')"

WORKDIR /workspace
