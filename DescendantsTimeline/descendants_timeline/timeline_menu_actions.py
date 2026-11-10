"""Temporary inhibition of the two view actions that target the active person."""


class TimelineMenuActions:
    targets = (("other_action", "SetActive"), ("book_action", "AddBook"))

    def __init__(self, view):
        self.view = view
        self.held = {}
        self.generation = 0

    def _installed(self, group, name):
        manager = self.view.uimanager
        if group is not None and group in manager.get_action_groups():
            return manager.get_action(group, name)
        return None

    def _can_restore(self, group, name):
        state = self.view.dbstate
        if not group.sensitive or not state.is_open():
            return False
        if name == "SetActive" and state.db.readonly:
            return False
        # DisplayState.set_sensitive() changes the pane before the Gio actions.
        pane = getattr(self.view.uistate.viewmanager, "hpane", None)
        return pane is None or pane.get_sensitive()

    def _native_enabled(self, action, _property, key):
        entry = self.held.get(key)
        if entry is not None and entry[0] is action and action.get_enabled():
            entry[2] = True
            action.set_enabled(False)

    def update(self, blocked):
        if not blocked and not self.held:
            return
        self.generation += 1
        generation = self.generation
        for group_attribute, name in self.targets:
            if generation != self.generation:
                return
            group = getattr(self.view, group_attribute, None)
            action = self._installed(group, name)
            entry = self.held.get(name)
            if entry is not None and (not blocked or entry[0] is not action):
                previous, handler, enabled = self.held.pop(name)
                previous.disconnect(handler)
                if previous is action:
                    previous.set_enabled(bool(enabled and self._can_restore(group, name)))
                if generation != self.generation:
                    return
            if blocked and action is not None and name not in self.held:
                enabled = action.get_enabled()
                handler = action.connect("notify::enabled", self._native_enabled, name)
                self.held[name] = [action, handler, enabled]
                action.set_enabled(False)
