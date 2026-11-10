"""Fabrique de vue avec une classe de base fournie par l'appelant."""

from descendants_timeline.gtk_timeline_widget import build_timeline_navigation_widget
from descendants_timeline.gtk_draw_adapter import queue_timeline_draw
from descendants_timeline.timeline.timeline_constructibility import has_admissible_temporal_anchor


def make_descendants_timeline_view_class(
    navigation_view_base, gtk_module, gdk_module, layout, controller,
    *, root_handle_is_valid=None, cooperative_driver=None,
):
    class DescendantsTimelineView(navigation_view_base):
        _last_person_hits = ()
        _selected_person_placement = None

        def _diagnostics_for_representation(self, timeline_model, timeline_layout):
            association = getattr(self, "_timeline_diagnostic_association", None)
            if (
                association is not None
                and association[0] is timeline_model
                and association[1] is timeline_layout
                and getattr(self, "_timeline_model", None) is timeline_model
                and getattr(self, "_timeline_layout", None) is timeline_layout
            ):
                return association[2]
            return None

        def _recognize_first_body_draw(self, timeline_model, timeline_layout, diagnostics, *, started_at=None, duration=None):
            if diagnostics is None or self._diagnostics_for_representation(timeline_model, timeline_layout) is not diagnostics:
                return False
            association = self._timeline_diagnostic_association
            if association[3]:
                return False
            self._timeline_diagnostic_association = (*association[:3], True, *association[4:])
            if started_at is not None and association[4] is not None:
                diagnostics.record_first_body_draw_wait(max(0.0, started_at - association[4]))
            if duration is not None:
                diagnostics.record_first_body_draw_duration(duration)
            self._complete_managed_first_draws(timeline_model, timeline_layout, diagnostics)
            return True

        def _recognize_first_header_draw(self, timeline_model, timeline_layout, diagnostics, *, started_at=None, duration=None):
            if diagnostics is None or self._diagnostics_for_representation(timeline_model, timeline_layout) is not diagnostics:
                return False
            association = self._timeline_diagnostic_association
            if association[5]:
                return False
            self._timeline_diagnostic_association = (*association[:5], True)
            if started_at is not None and association[4] is not None:
                diagnostics.record_first_header_draw_wait(max(0.0, started_at - association[4]))
            if duration is not None:
                diagnostics.record_first_header_draw_duration(duration)
            self._complete_managed_first_draws(timeline_model, timeline_layout, diagnostics)
            return True

        def _complete_managed_first_draws(self, timeline_model, timeline_layout, diagnostics):
            owned = vars(self).get("_timeline_managed_representation")
            if owned is None or not (
                owned[0] is timeline_model and owned[1] is timeline_layout and owned[2] is diagnostics
            ):
                return
            association = getattr(self, "_timeline_diagnostic_association", None)
            if (
                association is not None and association[3] and association[5]
                and self._diagnostics_for_representation(timeline_model, timeline_layout) is diagnostics
                and diagnostics.terminal_status is None
                and diagnostics.has_complete_first_draw_measurements
            ):
                # One automatic call, even if the factory's diagnostic fails to finish.
                vars(self).pop("_timeline_managed_representation", None)
                try:
                    diagnostics.finish(status="completed")
                except Exception:
                    # A secondary diagnostic failure must not fail a successful draw.
                    pass
                else:
                    destination = vars(self).get("_timeline_diagnostics_destination")
                    if destination is not None and diagnostics.terminal_status == "completed":
                        try:
                            diagnostics.export_jsonl(destination)
                        except Exception:
                            # Export is secondary to completion; no automatic retry.
                            pass

        def set_inactive(self):
            driver = getattr(self, "_timeline_load", None)
            if driver is not None:
                driver.deactivate()
            result = super().set_inactive()
            if driver is not None and driver.menu_actions is not None:
                driver.menu_actions.update(False)
            return result

        def set_active(self):
            result = super().set_active()
            self._sync_timeline_menu_actions()
            return result

        def change_page(self):
            result = super().change_page()
            self._sync_timeline_menu_actions()
            return result

        def _sync_timeline_menu_actions(self):
            driver = getattr(self, "_timeline_load", None)
            if driver is not None and driver.menu_actions is not None:
                driver.menu_actions.update(self.active and driver.blocked)

        def ui_definition(self):
            return [
                *super().ui_definition(),
                """
                <placeholder id="otheredit">
                    <item>
                        <attribute name="action">win.SetActive</attribute>
                        <attribute name="label" translatable="yes">Set _Home Person</attribute>
                    </item>
                </placeholder>
                """,
                """
                <section id="AddEditBook">
                    <item>
                        <attribute name="action">win.AddBook</attribute>
                        <attribute name="label" translatable="yes">_Add Bookmark</attribute>
                    </item>
                    <item>
                        <attribute name="action">win.EditBook</attribute>
                        <attribute name="label" translatable="yes">Organize Bookmarks</attribute>
                    </item>
                </section>
                """,
            ]

        def selected_handles(self):
            if self._timeline_interactions_blocked():
                return []
            return super().selected_handles()

        def add_bookmark(self, *args):
            if not self._timeline_interactions_blocked():
                return super().add_bookmark(*args)

        def set_default_person(self, *args):
            if not self._timeline_interactions_blocked():
                return super().set_default_person(*args)

        def _timeline_interactions_blocked(self):
            driver = getattr(self, "_timeline_load", None)
            return driver is not None and driver.blocked

        def disable_action_group(self):
            # PageView connects this method to no-database once at construction.
            super().disable_action_group()
            self.invalidate_timeline()

        def _current_managed_representation(self):
            owned = vars(self).get("_timeline_managed_representation")
            if owned is not None and self._diagnostics_for_representation(owned[0], owned[1]) is owned[2]:
                return owned
            return None

        def _cancel_managed_representation(self, owned):
            if owned is not None and owned[2].attempt_id is not None and owned[2].terminal_status is None:
                try:
                    owned[2].finish(status="cancelled")
                except Exception:
                    # Secondary diagnostic failure: preserve the accomplished functional transition.
                    pass
                else:
                    destination = vars(self).get("_timeline_diagnostics_destination")
                    if destination is not None and owned[2].terminal_status == "cancelled":
                        try:
                            owned[2].export_jsonl(destination)
                        except Exception:
                            # Export is secondary to cancellation; no automatic retry.
                            pass

        def invalidate_timeline(self):
            """Retire l'état de l'arbre sans lire la base ni recréer la vue."""
            driver = getattr(self, "_timeline_load", None)
            if driver is not None:
                driver.cancel()
            owned = self._current_managed_representation()
            vars(self).pop("_timeline_root_handle", None)
            try:
                self._clear_timeline_representation()
            finally:
                if (
                    owned is not None
                    and all(name not in vars(self) for name in (
                        "_timeline_root_handle", "_timeline_model", "_timeline_layout",
                        "_timeline_diagnostic_association", "_timeline_managed_representation",
                    ))
                    and controller.model is None and controller.layout is None and controller.transform is None
                ):
                    self._cancel_managed_representation(owned)

        def _clear_timeline_representation(self):
            """Clear graphical state while preserving the selected root."""
            for attribute in ("_timeline_model", "_timeline_layout"):
                vars(self).pop(attribute, None)
            vars(self).pop("_timeline_diagnostic_association", None)
            vars(self).pop("_timeline_managed_representation", None)
            controller.clear_timeline()
            self._selected_person_placement = None
            self._last_person_hits = ()
            widget = getattr(self, "_timeline_widget", None)
            if widget is not None:
                queue_timeline_draw(widget._timeline_drawing_area)

        def _refuse_timeline(self):
            self._clear_timeline_representation()
            dialog = gtk_module.MessageDialog(
                transient_for=getattr(getattr(self, "uistate", None), "window", None),
                flags=gtk_module.DialogFlags.MODAL,
                message_type=gtk_module.MessageType.INFO,
                buttons=gtk_module.ButtonsType.OK,
                title="Vue impossible à construire",
                text="Vue impossible à construire",
            )
            dialog.format_secondary_text(
                "La descendance ne contient aucun ancrage temporel permettant de positionner les individus sur la chronologie."
            )
            try:
                dialog.run()
            finally:
                dialog.destroy()

        def _on_person_hits(self, hits):
            previous_selection = self._selected_person_placement
            self._last_person_hits = hits
            if len(hits) <= 1:
                self._selected_person_placement = hits[0] if hits else None
            if self._selected_person_placement is not previous_selection:
                widget = getattr(self, "_timeline_widget", None)
                drawing_area = getattr(widget, "_timeline_drawing_area", None)
                if drawing_area is not None:
                    queue_timeline_draw(drawing_area)

        def navigation_type(self):
            return "Person"

        def configure_timeline(self, data_loader, model_builder, layout_engine):
            was_configured = all(
                hasattr(self, attribute)
                for attribute in (
                    "_timeline_data_loader", "_timeline_model_builder", "_timeline_layout_engine",
                )
            )
            self._timeline_data_loader = data_loader
            self._timeline_model_builder = model_builder
            self._timeline_layout_engine = layout_engine
            if (
                not was_configured
                and hasattr(self, "_timeline_root_handle")
                and not hasattr(self, "_timeline_model")
            ):
                if getattr(self, "_timeline_load", None) is not None:
                    self.goto_handle(self._timeline_root_handle)
                else:
                    self.refresh_timeline(data_loader, model_builder, layout_engine)
            return None

        def refresh_timeline(self, data_loader, model_builder, layout_engine, *, diagnostics=None):
            if not vars(self).get("_timeline_diagnostics_configuration_read", False):
                self._timeline_diagnostics_configuration_read = True
                # Either explicit attribute reserves the whole configuration for the caller.
                if not any(name in vars(self) for name in (
                    "_timeline_diagnostics_factory", "_timeline_diagnostics_destination",
                )):
                    import os
                    from pathlib import Path
                    from descendants_timeline import loading_diagnostics

                    value = os.environ.get(loading_diagnostics.PERFORMANCE_REPORT_VARIABLE)
                    if (
                        type(value) is str and value and value == value.strip()
                        and not any(ord(character) < 32 for character in value)
                        and not any(character in value for character in '<>"|?*')
                        and not value.endswith(("/", "\\"))
                    ):
                        destination = Path(value)
                        if (
                            destination.is_absolute() and destination.suffix.lower() == ".jsonl"
                            and ":" not in value[len(destination.drive):]
                        ):
                            self._timeline_diagnostics_factory = lambda: loading_diagnostics.LoadingDiagnostics(enabled=True)
                            self._timeline_diagnostics_destination = destination
                            self._timeline_environment_configuration = (self._timeline_diagnostics_factory, destination)
            environmental = vars(self).get("_timeline_environment_configuration")
            if environmental is not None:
                names = ("_timeline_diagnostics_factory", "_timeline_diagnostics_destination")
                if any(vars(self).get(name) is not original for name, original in zip(names, environmental)):
                    # A later partial injection must not inherit the other environmental half.
                    for name, original in zip(names, environmental):
                        if vars(self).get(name) is original:
                            vars(self).pop(name, None)
                    vars(self).pop("_timeline_environment_configuration", None)
            managed = False
            if diagnostics is None and getattr(self, "_timeline_root_handle", None) is not None:
                factory = vars(self).get("_timeline_diagnostics_factory")
                if factory is not None:
                    diagnostics = factory()
                    managed = True
            if diagnostics is not None and getattr(self, "_timeline_root_handle", None) is not None:
                diagnostics.increment("reconstructions", 1)
            publication_attributes = ("_timeline_model", "_timeline_layout", "_timeline_diagnostic_association")
            previous = tuple(vars(self).get(name) for name in publication_attributes) if managed else None
            try:
                timeline_model, timeline_layout = self.prepare_timeline(
                    data_loader,
                    model_builder,
                    layout_engine,
                    **({"diagnostics": diagnostics} if diagnostics is not None else {}),
                )
                if timeline_layout is not None:
                    self.install_timeline(
                        timeline_model,
                        timeline_layout,
                        **({"diagnostics": diagnostics} if diagnostics is not None else {}),
                        **({"_managed": True} if managed else {}),
                    )
            except Exception:
                if (
                    managed and diagnostics is not None and diagnostics.attempt_id is not None
                    and diagnostics.terminal_status is None and not diagnostics.has_first_draw_measurements
                    and (previous[2] is None or previous[2][2] is not diagnostics)
                    and all(vars(self).get(name) is value for name, value in zip(publication_attributes, previous))
                ):
                    try:
                        diagnostics.finish(status="failed")
                    except Exception:
                        # Only this secondary failure is suppressed; preserve the reconstruction error.
                        pass
                    else:
                        destination = vars(self).get("_timeline_diagnostics_destination")
                        if destination is not None and diagnostics.terminal_status == "failed":
                            try:
                                diagnostics.export_jsonl(destination)
                            except Exception:
                                # Preserve the original reconstruction error; no automatic retry.
                                pass
                raise
            if timeline_layout is None:
                self._refuse_timeline()
                return None
            return None

        def install_timeline(self, timeline_model, timeline_layout, *, diagnostics=None, _managed=False):
            previous_owned = self._current_managed_representation()
            previous_association = vars(self).get("_timeline_diagnostic_association")
            controller.set_model_and_layout(
                timeline_model,
                timeline_layout,
                **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )
            replaced_managed = (
                previous_owned is not None and previous_association is not None
                and previous_owned is self._current_managed_representation()
                and previous_association is vars(self).get("_timeline_diagnostic_association")
                and (timeline_model is not previous_owned[0] or timeline_layout is not previous_owned[1])
                and diagnostics is not previous_owned[2]
            )

            if (
                getattr(self, "_timeline_layout", None) is not timeline_layout
                and (self._selected_person_placement is not None or self._last_person_hits)
            ):
                self._selected_person_placement = None
                self._last_person_hits = ()
            self._timeline_model = timeline_model
            self._timeline_layout = timeline_layout
            vars(self).pop("_timeline_managed_representation", None)
            if diagnostics is None:
                vars(self).pop("_timeline_diagnostic_association", None)
            else:
                self._timeline_diagnostic_association = (timeline_model, timeline_layout, diagnostics, False, None, False)
                clock = diagnostics.first_body_draw_clock
                if clock is None:
                    clock = diagnostics.first_header_draw_clock
                if clock is not None:
                    published_at = clock()
                    self._timeline_diagnostic_association = (timeline_model, timeline_layout, diagnostics, False, published_at, False)
                if (
                    _managed and diagnostics.first_body_draw_clock is not None
                    and diagnostics.first_header_draw_clock is not None
                    and not diagnostics.has_first_draw_measurements
                ):
                    self._timeline_managed_representation = (timeline_model, timeline_layout, diagnostics)

            if replaced_managed:
                self._cancel_managed_representation(previous_owned)

            widget = getattr(self, "_timeline_widget", None)
            if widget is not None:
                queue_timeline_draw(widget._timeline_drawing_area)

            return None

        def prepare_timeline(self, data_loader, model_builder, layout_engine, *, diagnostics=None):
            raw_data = self.load_root_data(
                data_loader, **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )
            timeline_model = self.build_timeline_model(
                raw_data,
                model_builder,
                **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )
            timeline_layout = self.build_timeline_layout(
                timeline_model,
                layout_engine,
                **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )
            return timeline_model, timeline_layout

        def set_timeline_layout(self, timeline_layout):
            controller.set_model_and_layout(
                self._timeline_model,
                timeline_layout,
            )
            selected = self._selected_person_placement
            if selected is not None and not any(item is selected for item in timeline_layout.person_placements):
                self._selected_person_placement = None
            if getattr(self, "_timeline_layout", None) is not timeline_layout and self._last_person_hits:
                self._last_person_hits = ()
            self._timeline_layout = timeline_layout
            vars(self).pop("_timeline_diagnostic_association", None)
            vars(self).pop("_timeline_managed_representation", None)
            widget = getattr(self, "_timeline_widget", None)
            if widget is not None:
                queue_timeline_draw(widget._timeline_drawing_area)
            return None

        def rebuild_timeline(self, data_loader, model_builder, layout_engine):
            raw_data = self.load_root_data(data_loader)
            timeline_model = self.build_timeline_model(raw_data, model_builder)
            timeline_layout = self.build_timeline_layout(
                timeline_model,
                layout_engine,
            )
            if timeline_layout is None:
                self._refuse_timeline()
                return None
            self._timeline_model = timeline_model
            vars(self).pop("_timeline_diagnostic_association", None)
            return timeline_layout

        def build_timeline_layout(self, timeline_model, layout_engine, *, diagnostics=None):
            if not has_admissible_temporal_anchor(timeline_model):
                return None
            return layout_engine.build(
                timeline_model, **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )

        def build_timeline_model(self, raw_data, model_builder, *, diagnostics=None):
            return model_builder(
                raw_data, **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )

        def load_root_data(self, data_loader, *, diagnostics=None):
            return data_loader(
                self._timeline_root_handle, **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )

        def goto_handle(self, handle):
            if root_handle_is_valid is not None and not root_handle_is_valid(handle):
                self.invalidate_timeline()
                return None
            driver = getattr(self, "_timeline_load", None)
            if driver is not None and hasattr(self, "_timeline_data_loader"):
                # Keep the explicit diagnostic session on its original synchronous
                # path: spanning idle turns would change its timing semantics.
                import os
                from descendants_timeline.loading_diagnostics import PERFORMANCE_REPORT_VARIABLE

                from descendants_timeline.cooperative_timeline_load import sqlite_revision_reader

                read_revision = sqlite_revision_reader(self.dbstate.db)
                if read_revision is not None and not (os.environ.get(PERFORMANCE_REPORT_VARIABLE)
                        or getattr(self, "_timeline_diagnostics_factory", None)):
                    driver.request(handle, read_revision)
                    return None
                driver.cancel()
            previous_root = getattr(self, "_timeline_root_handle", None)
            previous_model = getattr(self, "_timeline_model", None)
            previous_layout = getattr(self, "_timeline_layout", None)
            self._timeline_root_handle = handle
            if all(
                hasattr(self, attribute)
                for attribute in (
                    "_timeline_data_loader",
                    "_timeline_model_builder",
                    "_timeline_layout_engine",
                )
            ):
                try:
                    self.refresh_timeline(
                        self._timeline_data_loader,
                        self._timeline_model_builder,
                        self._timeline_layout_engine,
                    )
                except Exception:
                    if (
                        previous_model is not None
                        and getattr(self, "_timeline_model", None) is previous_model
                        and getattr(self, "_timeline_layout", None) is previous_layout
                    ):
                        self._timeline_root_handle = previous_root
                    raise
            return None

        def build_tree(self):
            return None

        def build_widget(self):
            widget = build_timeline_navigation_widget(
                gtk_module, gdk_module, layout, controller,
                layout_provider=lambda: getattr(self, "_timeline_layout", None),
                on_person_hits=self._on_person_hits,
                selection_provider=lambda: self._selected_person_placement,
            )
            self._timeline_widget = widget
            drawing_area = widget._timeline_drawing_area if hasattr(widget, "_timeline_drawing_area") else None
            if drawing_area is not None:
                drawing_area._timeline_diagnostics_provider = self._diagnostics_for_representation
                drawing_area._timeline_body_draw_completed = self._recognize_first_body_draw
            header = widget._timeline_header_area if hasattr(widget, "_timeline_header_area") else None
            if header is not None:
                header._timeline_diagnostics_provider = self._diagnostics_for_representation
                header._timeline_header_draw_completed = self._recognize_first_header_draw
            widget_type = getattr(gtk_module, "Widget", None) if cooperative_driver is not None else None
            if cooperative_driver is not None and isinstance(widget_type, type) and isinstance(widget, widget_type):
                driver = cooperative_driver(self, widget)
                self._timeline_load = driver
                drawing_area._timeline_cooperative_drawn = driver.drawn
                header._timeline_cooperative_drawn = driver.drawn
                return driver.container
            return widget

    return DescendantsTimelineView

