"""Main-context orchestration for a single DescendantsTimeline view."""

from _i18n import _

from dataclasses import dataclass, field
import logging
from time import perf_counter

LOG = logging.getLogger(__name__)


def sqlite_revision_reader(database):
    """Read the native SQLite change tokens without opening a transaction."""
    connection = getattr(database, "dbapi", None)
    native_modules = {"sqlite", "gramps.plugins.db.dbapi.sqlite"}
    if type(database).__module__ not in native_modules or type(connection).__module__ not in native_modules:
        return None

    def read():
        if database.transaction is not None:
            raise RuntimeError("A Gramps transaction is still active")
        connection.execute("SELECT total_changes()")
        changes = connection.fetchone()[0]
        connection.execute("PRAGMA data_version")
        return changes, connection.fetchone()[0]

    return read


def disconnect_all(connections):
    # Gramps Callback.emit iterates its live subscriber list.
    for owner, connection in connections:
        owner.disconnect(connection)
    return False


@dataclass
class Attempt:
    generation: int
    database: object
    root: str
    steps: object
    read_revision: object
    ready: bool = False
    started: float | None = None
    revision: tuple | None = None
    invalidated: str | None = None
    phase: str = field(default_factory=lambda: _("Reading the family tree"))
    work_source: int = 0
    activity_source: int = 0
    connections: list = field(default_factory=list)
    published: tuple | None = None
    drawn: set = field(default_factory=set)
    published_at: float = 0.0
    last_pulse: float = 0.0


class CooperativeTimelineLoad:
    slice_seconds = 0.009
    show_after = 0.200
    pulse_interval = 0.150
    draw_timeout = 3.0

    def __init__(self, view, widget, gtk, glib, prepare, clock=perf_counter, *, menu_actions=None):
        self.view = view
        self.widget = widget
        self.glib = glib
        self.prepare = prepare
        self.clock = clock
        self.menu_actions = menu_actions
        self.attempt = None
        self.generation = 0
        self.blocked = False
        self.disposed = False
        self._window_type = getattr(gtk, "Window", None)
        self._held_focus = None

        self.container = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=3)
        self.label = gtk.Label(xalign=0, wrap=True)
        self.activity = gtk.ProgressBar()
        for item in (self.label, self.activity):
            item.set_no_show_all(True)
            self.container.pack_start(item, False, False, 0)
        self.container.pack_start(widget, True, True, 0)
        self.container.connect_after("map", self._start_mapped)
        self.container.connect("unmap", lambda *_: self.deactivate())
        self.container.connect("destroy", self.dispose)

    def _current(self, attempt):
        return not self.disposed and self.attempt is attempt and self.generation == attempt.generation

    def _valid(self, attempt):
        state = self.view.dbstate
        return self._current(attempt) and state.is_open() and state.db is attempt.database

    def _set_blocked(self, value):
        remember_focus = value and not self.blocked
        self.blocked = value
        if not self.disposed:
            generation = self.generation
            focus = self._timeline_focus() if remember_focus else None
            self.widget.set_sensitive(not value)
            if focus is not None and not self.disposed and self.generation == generation:
                window, previous = focus
                if window.get_focus() != previous:
                    handler = window.connect("set-focus", self._drop_focus)
                    self._held_focus = (window, previous, handler)
            if self.menu_actions is not None and not self.disposed and self.generation == generation:
                self.menu_actions.update(value and self.view.active)

    def _timeline_focus(self):
        if not isinstance(self._window_type, type):
            return None
        window = self.widget.get_toplevel()
        if isinstance(window, self._window_type):
            focused = window.get_focus()
            if focused is not None and focused.is_ancestor(self.widget):
                return window, focused
        return None

    def _drop_focus(self, *_):
        held, self._held_focus = self._held_focus, None
        if held is not None:
            held[0].disconnect(held[2])

    def _message(self, text):
        generation = self.generation
        if self.label.get_text() != text:
            self.label.set_text(text)
        if not self.disposed and self.generation == generation:
            self.label.show() if text else self.label.hide()

    def cancel(self, message="", *, stale=False, restore_focus=False):
        attempt, self.attempt = self.attempt, None
        self.generation += 1
        generation = self.generation
        if attempt is not None:
            for source in (attempt.work_source, attempt.activity_source):
                if source:
                    self.glib.source_remove(source)
            if attempt.connections:
                self.glib.idle_add(disconnect_all, attempt.connections)
            if attempt.steps is not None and not attempt.steps.gi_running:
                attempt.steps.close()
        if not self.disposed and self.generation == generation:
            self.activity.hide()
        if not self.disposed and self.generation == generation:
            self._set_blocked(stale)
        if not self.disposed and self.generation == generation:
            self._message(message)
        if not stale and self.generation == generation:
            held = self._held_focus
            self._drop_focus()
            if restore_focus and held is not None and not self.disposed and self.view.active:
                window, focused, _ = held
                if (self.container.get_mapped() and focused.get_toplevel() == window
                        and focused.get_mapped() and focused.is_sensitive()):
                    focused.grab_focus()

    def deactivate(self):
        self._drop_focus()
        if self.disposed or self.attempt is None:
            return
        stale = self.attempt.published is None and hasattr(self.view, "_timeline_model")
        self.cancel(_("Previous view") if stale else "", stale=stale)

    def dispose(self, *_):
        self.disposed = True
        self._drop_focus()
        self.cancel()
        if self.menu_actions is not None:
            self.menu_actions.update(False)

    def request(self, root, read_revision):
        if self.disposed:
            return
        generation = self.generation + 1
        self.cancel(stale=self.blocked)
        if self.disposed or self.generation != generation:
            return
        database = self.view.dbstate.db
        attempt = Attempt(self.generation, database, root, self.prepare(self.view, database, root),
                          read_revision)
        self.attempt = attempt
        self._set_blocked(True)
        if not self._current(attempt):
            return
        if hasattr(self.view, "_timeline_model"):
            self._message(_("Previous view"))
        if not self._current(attempt):
            return
        try:
            self._watch(attempt, self.view.dbstate, "database-changed",
                        lambda *_: self._database_changed(attempt))
            for kind in ("person", "family", "event"):
                for operation in ("add", "update", "delete", "rebuild"):
                    self._watch(attempt, database, f"{kind}-{operation}",
                                lambda *_: self._data_changed(attempt))
        except Exception:
            self._fail(attempt)
            return
        attempt.ready = True
        self._start_mapped()

    def _start_mapped(self, *_):
        attempt = self.attempt
        if (attempt is None or not attempt.ready or attempt.started is not None
                or not self.container.get_mapped()):
            return
        # Gramps drains pending GTK events while switching to the unmapped page.
        attempt.started = self.clock()
        try:
            attempt.work_source = self.glib.idle_add(self._resume, attempt)
            attempt.activity_source = self.glib.timeout_add(25, self._tick, attempt)
        except Exception:
            self._fail(attempt)

    def _watch(self, attempt, owner, signal, callback):
        connection = owner.connect(signal, callback)
        if connection is None:
            raise RuntimeError(f"Missing Gramps signal: {signal}")
        attempt.connections.append((owner, connection))

    def _database_changed(self, attempt):
        if self._current(attempt):
            attempt.invalidated = "database"

    def _data_changed(self, attempt):
        if self._current(attempt) and attempt.invalidated is None:
            attempt.invalidated = "data"

    def _check_revision(self, attempt):
        if attempt.invalidated == "database" or not self._valid(attempt):
            if self._current(attempt):
                self.view.invalidate_timeline()
            return False
        if attempt.invalidated is None:
            revision = attempt.read_revision()
            if not self._current(attempt):
                return False
            if attempt.invalidated == "database" or not self._valid(attempt):
                self.view.invalidate_timeline()
                return False
            if attempt.revision is None:
                attempt.revision = revision
            if attempt.invalidated is None and attempt.revision == revision:
                return True
        stale = hasattr(self.view, "_timeline_model")
        message = _("Data changed. Select another person or return to this view.")
        if stale:
            message = _("Previous view — %(message)s") % {"message": message}
        self.cancel(message, stale=stale)
        return False

    def _fail(self, attempt):
        if self._current(attempt):
            stale = hasattr(self.view, "_timeline_model")
            message = _("Could not load the timeline.")
            if stale:
                message = _("Previous view — %(message)s") % {"message": message}
            self.cancel(message, stale=stale)
            # Gramps displays ERROR logs in a modal dialog. The inline status
            # keeps recovery in this main-context turn.
            LOG.warning("DescendantsTimeline: cooperative load failed", exc_info=True)

    def _resume(self, attempt):
        source, attempt.work_source = attempt.work_source, 0
        try:
            if not self._check_revision(attempt):
                return False
        except Exception:
            self._fail(attempt)
            return False
        deadline = self.clock() + self.slice_seconds
        try:
            while True:
                phase = next(attempt.steps)
                if phase is not None:
                    attempt.phase = phase
                if not self._current(attempt):
                    attempt.steps.close()
                    return False
                if attempt.invalidated is not None:
                    self._check_revision(attempt)
                    return False
                if self.clock() >= deadline:
                    attempt.work_source = source
                    return True
        except StopIteration as result:
            attempt.work_source = 0
            attempt.steps = None
            try:
                if not self._check_revision(attempt):
                    return False
                model, layout = result.value
                if layout is None:
                    self.view._clear_timeline_representation()
                    if not self._current(attempt):
                        return False
                    self.view._timeline_root_handle = attempt.root
                    self.cancel(_("Cannot build the view: no usable date anchor."))
                else:
                    self.view.install_timeline(model, layout)
                    if not self._current(attempt):
                        return False
                    self.view._timeline_root_handle = attempt.root
                    attempt.published = (model, layout)
                    attempt.published_at = self.clock()
                    attempt.phase = _("Displaying the timeline")
            except Exception:
                self._fail(attempt)
            return False
        except Exception:
            attempt.work_source = 0
            self._fail(attempt)
            return False

    def drawn(self, surface, model, layout):
        attempt = self.attempt
        if (attempt is not None and self._valid(attempt) and attempt.invalidated is None
                and attempt.published is not None):
            expected_model, expected_layout = attempt.published
            if model is expected_model and layout is expected_layout:
                attempt.drawn.add(surface)

    def _tick(self, attempt):
        source, attempt.activity_source = attempt.activity_source, 0
        try:
            if not self._check_revision(attempt):
                return False
        except Exception:
            self._fail(attempt)
            return False
        now = self.clock()
        if attempt.drawn == {"body", "header"}:
            attempt.activity_source = 0
            self.cancel(restore_focus=True)
            return False
        if attempt.published is not None and now - attempt.published_at >= self.draw_timeout:
            attempt.activity_source = 0
            self.cancel(_("Could not confirm that the timeline was displayed."))
            return False
        if now - attempt.started >= self.show_after and now - attempt.last_pulse >= self.pulse_interval:
            text = _("%(phase)s…") % {"phase": attempt.phase}
            if attempt.published is None and hasattr(self.view, "_timeline_model"):
                text = _("%(phase)s · Previous view") % {"phase": text}
            self._message(text)
            if not self._current(attempt):
                return False
            self.activity.show()
            if not self._current(attempt):
                return False
            self.activity.pulse()
            attempt.last_pulse = now
        if not self._current(attempt):
            return False
        attempt.activity_source = source
        return True
