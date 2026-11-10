class GrampsDataAdapter:
    def __init__(self, database, *, diagnostics=None):
        self._database = database
        self._diagnostics = diagnostics

    def get_person(self, handle, *, diagnostics=None):
        read_person = self._database.get_person_from_handle
        diagnostics = self._diagnostics if diagnostics is None else diagnostics
        if diagnostics is not None:
            diagnostics.increment("person_api_calls", 1)
        return read_person(handle)

    def get_family(self, handle, *, diagnostics=None):
        read_family = self._database.get_family_from_handle
        diagnostics = self._diagnostics if diagnostics is None else diagnostics
        if diagnostics is not None:
            diagnostics.increment("family_api_calls", 1)
        return read_family(handle)

    def get_event(self, handle, *, diagnostics=None):
        read_event = self._database.get_event_from_handle
        diagnostics = self._diagnostics if diagnostics is None else diagnostics
        if diagnostics is not None:
            diagnostics.increment("event_api_calls", 1)
        return read_event(handle)
