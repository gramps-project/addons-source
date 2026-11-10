"""Collecte ponctuelle de géométrie GTK, sans correction des widgets."""

import json
import os
from pathlib import Path


def collect_gtk_geometry(root):
    unavailable = {}

    def read(name, operation):
        try:
            value = operation()
            if value is None:
                unavailable[name] = "indisponible"
            return value
        except Exception as error:
            unavailable[name] = str(error)
            return None

    header = root._timeline_header_area
    body = root._timeline_drawing_area
    scrolled = root._timeline_scrolled_window
    result = {}
    for name, widget in (("header", header), ("body", body)):
        origin = read(name + "_origin", lambda: widget.translate_coordinates(root, 0, 0))
        result[name + "_x"] = origin[0] if origin is not None else None
        result[name + "_width"] = read(name + "_width", widget.get_allocated_width)
    result["delta_x"] = (
        result["body_x"] - result["header_x"]
        if result["body_x"] is not None and result["header_x"] is not None else None
    )
    result["root_width"] = read("root_width", root.get_allocated_width)
    result["window_width"] = read("window_width", lambda: root.get_toplevel().get_allocated_width())
    result["scrolled_width"] = read("scrolled_width", scrolled.get_allocated_width)
    result["viewport_width"] = read("viewport_width", lambda: scrolled.get_child().get_allocated_width())
    result["horizontal_adjustment"] = read("horizontal_adjustment", lambda: scrolled.get_hadjustment().get_value())
    result["horizontal_page_size"] = read("horizontal_page_size", lambda: scrolled.get_hadjustment().get_page_size())
    result["overlay_scrolling"] = read("overlay_scrolling", scrolled.get_overlay_scrolling)
    for name, getter in (("horizontal_scrollbar", scrolled.get_hscrollbar),
                         ("vertical_scrollbar", scrolled.get_vscrollbar)):
        bar = read(name, getter)
        if bar is None:
            result[name] = None
            continue
        origin = read(name + "_origin", lambda: bar.translate_coordinates(root, 0, 0))
        result[name] = {
            "visible": read(name + "_visible", bar.get_visible),
            "mapped": read(name + "_mapped", bar.get_mapped),
            "x": origin[0] if origin is not None else None,
            "width": read(name + "_width", bar.get_allocated_width),
        }
    result["unavailable"] = unavailable
    return result


def enable_gtk_geometry_diagnostic(root):
    """Active sur demande une collecte idle après le premier map de la racine."""
    report_path = os.environ.get("DESCENDANTS_TIMELINE_GTK_DIAGNOSTIC")
    if not report_path:
        return
    from gi.repository import GLib

    def report():
        result = collect_gtk_geometry(root)
        text = "Descendants Timeline — Z009-J GTK\n" + json.dumps(result, ensure_ascii=False, indent=2)
        try:
            Path(report_path).write_text(text + "\n", encoding="utf-8")
        except OSError as error:
            print("Z009-J : rapport non enregistré :", error, flush=True)
        print(text, flush=True)
        return False

    def mapped(widget):
        widget.disconnect(handler)
        GLib.idle_add(report)

    handler = root.connect("map", mapped)
