"""Diagnostic isolé, désactivé par défaut, avec export JSONL explicite."""

from contextlib import contextmanager, nullcontext
from itertools import count
import json
from math import isfinite
import os
from pathlib import Path
import time


ALLOWED_PHASE_NAMES = frozenset({
    "collection", "dfs", "inference", "model", "layout", "framing",
})

ALLOWED_COUNTER_NAMES = frozenset({
    "persons_collected", "families_collected", "events_collected",
    "temporal_targets", "temporal_evidences", "dfs_rows", "family_occurrences",
    "person_api_calls", "family_api_calls", "event_api_calls", "reconstructions",
})

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_ATTEMPT_IDS = count(1)
PERFORMANCE_REPORT_VARIABLE = "DESCENDANTS_TIMELINE_PERFORMANCE_REPORT"


def create_loading_diagnostics_from_environment(*, environment=None, clock=None):
    """Renvoie (diagnostic, destination), sans écriture ni changement d'environnement."""
    source = os.environ if environment is None else environment
    value = source.get(PERFORMANCE_REPORT_VARIABLE)
    destination = None
    if (
        type(value) is str and value and value == value.strip()
        and not any(ord(character) < 32 for character in value)
        and not any(character in value for character in '<>"|?*')
        and not value.endswith(("/", "\\"))
    ):
        candidate = Path(value)
        if (
            candidate.is_absolute() and candidate.suffix.lower() == ".jsonl"
            and ":" not in value[len(candidate.drive):]
        ):
            destination = candidate
    return LoadingDiagnostics(enabled=destination is not None, clock=clock), destination


def _is_duration(value):
    return (
        type(value) is int and value >= 0
        or type(value) is float and isfinite(value) and value >= 0.0
    )


def _validated_values(values, allowed_names, *, counters=False):
    if type(values) is not dict:
        raise ValueError("Invalid diagnostic values")
    result = {}
    for name, value in values.items():
        if type(name) is not str or name not in allowed_names:
            raise ValueError("Invalid diagnostic name")
        valid = type(value) is int and value >= 0 if counters else _is_duration(value)
        if not valid:
            raise ValueError("Invalid diagnostic value")
        result[name] = value
    return result


class LoadingDiagnostics:
    """Mesure en mémoire ; seule une demande d'export ouvre un fichier."""

    def __init__(self, *, enabled=False, clock=None):
        self._clock = (time.perf_counter if clock is None else clock) if enabled else None
        self._started_at = self._clock() if self._clock is not None else None
        self._summary = None
        self._phase_durations = {}
        self._phase_exclusive_durations = {}
        self._phase_stack = []
        self._multiple_phases = False
        self._counters = {}
        self._attempt_id = next(_ATTEMPT_IDS) if self._clock is not None else None
        self._terminal_status = None
        self._export_state = None
        self._first_body_draw_duration_seconds = None
        self._first_body_draw_wait_seconds = None
        self._first_header_draw_duration_seconds = None
        self._first_header_draw_wait_seconds = None

    @property
    def has_first_draw_measurements(self):
        """Signale une mesure existante sans lire l'horloge ni exposer le résumé."""
        return any(value is not None for value in (
            self._first_body_draw_wait_seconds, self._first_body_draw_duration_seconds,
            self._first_header_draw_wait_seconds, self._first_header_draw_duration_seconds,
        ))

    @property
    def has_complete_first_draw_measurements(self):
        return all(value is not None for value in (
            self._first_body_draw_wait_seconds, self._first_body_draw_duration_seconds,
            self._first_header_draw_wait_seconds, self._first_header_draw_duration_seconds,
        ))

    @property
    def first_header_draw_clock(self):
        """Horloge de la première durée d'en-tête, indépendante du corps."""
        if self._summary is None and self._first_header_draw_duration_seconds is None:
            return self._clock
        return None

    def record_first_header_draw_duration(self, duration):
        """Conserve uniquement la première durée d'en-tête reconnue et valide."""
        if self.first_header_draw_clock is not None and _is_duration(duration):
            self._first_header_draw_duration_seconds = duration

    def record_first_header_draw_wait(self, duration):
        """Conserve l'attente du premier en-tête reconnu pour cette tentative."""
        if (
            self.first_header_draw_clock is not None
            and self._first_header_draw_wait_seconds is None
            and _is_duration(duration)
        ):
            self._first_header_draw_wait_seconds = duration

    @property
    def first_body_draw_clock(self):
        """Horloge disponible jusqu'à la première mesure ou la finalisation.

        Une tentative explicitement réutilisée conserve sa première durée.
        Une nouvelle mesure exige une tentative distincte.
        """
        if self._summary is None and self._first_body_draw_duration_seconds is None:
            return self._clock
        return None

    def record_first_body_draw_duration(self, duration):
        """Stocke uniquement une durée dont la représentation a été reconnue."""
        if self.first_body_draw_clock is not None and _is_duration(duration):
            self._first_body_draw_duration_seconds = duration

    def record_first_body_draw_wait(self, duration):
        """Conserve l'attente de la première représentation reconnue seulement."""
        if (
            self.first_body_draw_clock is not None
            and self._first_body_draw_wait_seconds is None
            and _is_duration(duration)
        ):
            self._first_body_draw_wait_seconds = duration

    @property
    def attempt_id(self):
        return self._attempt_id

    @property
    def terminal_status(self):
        return self._terminal_status

    def phase(self, name):
        if self._clock is None:
            return nullcontext()
        return self._measure_phase(name)

    @contextmanager
    def _measure_phase(self, name):
        if type(name) is not str or name not in ALLOWED_PHASE_NAMES:
            raise ValueError("Unsupported diagnostic phase")
        if self._summary is not None:
            raise RuntimeError("Cannot measure a phase in a finalized attempt")
        frame = {"started_at": self._clock(), "children_seconds": 0.0}
        if self._phase_stack or self._phase_durations:
            self._multiple_phases = True
        self._phase_stack.append(frame)
        try:
            yield
        finally:
            duration = self._clock() - frame["started_at"]
            self._phase_stack.pop()
            exclusive_duration = duration - frame["children_seconds"]
            self._phase_durations[name] = self._phase_durations.get(name, 0.0) + duration
            self._phase_exclusive_durations[name] = (
                self._phase_exclusive_durations.get(name, 0.0) + exclusive_duration
            )
            if self._phase_stack:
                self._phase_stack[-1]["children_seconds"] += duration

    def increment(self, name, amount=1):
        if self._clock is None:
            return None
        if self._summary is not None:
            raise RuntimeError("Cannot increment a counter in a finalized attempt")
        if type(name) is not str or name not in ALLOWED_COUNTER_NAMES:
            raise ValueError("Unsupported diagnostic counter")
        if type(amount) is not int:
            raise TypeError("Counter amount must be an integer")
        if amount < 0:
            raise ValueError("Counter amount must be nonnegative")
        self._counters[name] = self._counters.get(name, 0) + amount

    def finish(self, *, status=None):
        if self._clock is None:
            return None
        if self._summary is not None:
            return self._summary
        if status is not None and (type(status) is not str or status not in TERMINAL_STATUSES):
            raise ValueError("Unsupported diagnostic terminal status")
        if self._phase_stack:
            raise RuntimeError("Cannot finish while a diagnostic phase is active")
        if self._summary is None:
            self._summary = {"duration_seconds": self._clock() - self._started_at}
            if self._first_header_draw_duration_seconds is not None:
                self._summary["first_header_draw_duration_seconds"] = self._first_header_draw_duration_seconds
            if self._first_header_draw_wait_seconds is not None:
                self._summary["first_header_draw_wait_seconds"] = self._first_header_draw_wait_seconds
            if self._first_body_draw_duration_seconds is not None:
                self._summary["first_body_draw_duration_seconds"] = self._first_body_draw_duration_seconds
            if self._first_body_draw_wait_seconds is not None:
                self._summary["first_body_draw_wait_seconds"] = self._first_body_draw_wait_seconds
            if self._phase_durations:
                self._summary["phase_durations_seconds"] = dict(self._phase_durations)
            if self._multiple_phases:
                self._summary["phase_exclusive_durations_seconds"] = dict(
                    self._phase_exclusive_durations,
                )
            if self._counters:
                self._summary["counters"] = dict(self._counters)
            self._terminal_status = "completed" if status is None else status
            if status is not None:
                self._summary["attempt_id"] = self._attempt_id
                self._summary["status"] = self._terminal_status
        return self._summary

    def export_jsonl(self, destination):
        """Exporte une fois ; renvoie un état technique sans exposer les erreurs."""
        if self._clock is None:
            return "disabled"
        if self._summary is None:
            return "not_finalized"
        if self._export_state == "exported":
            return "already_exported"
        if self._export_state == "write_uncertain":
            return "write_uncertain"
        try:
            duration = self._summary["duration_seconds"]
            if not _is_duration(duration):
                raise ValueError("Invalid diagnostic duration")
            if type(self._attempt_id) is not int or self._attempt_id <= 0:
                raise ValueError("Invalid diagnostic identity")
            if type(self._terminal_status) is not str or self._terminal_status not in TERMINAL_STATUSES:
                raise ValueError("Invalid diagnostic status")
            document = {
                "attempt_id": self._attempt_id,
                "status": self._terminal_status,
                "duration_seconds": duration,
            }
            for field in ("phase_durations_seconds", "phase_exclusive_durations_seconds"):
                if field in self._summary:
                    document[field] = _validated_values(self._summary[field], ALLOWED_PHASE_NAMES)
            if "counters" in self._summary:
                document["counters"] = _validated_values(
                    self._summary["counters"], ALLOWED_COUNTER_NAMES, counters=True,
                )
            for field in (
                "first_body_draw_wait_seconds", "first_body_draw_duration_seconds",
                "first_header_draw_wait_seconds", "first_header_draw_duration_seconds",
            ):
                if field in self._summary:
                    value = self._summary[field]
                    if not _is_duration(value):
                        raise ValueError("Invalid first draw duration")
                    document[field] = value
            payload = (json.dumps(document, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (KeyError, ValueError, TypeError, OverflowError):
            return "invalid_summary"

        opened = False
        try:
            with open(destination, "a+b") as stream:
                opened = True
                stream.seek(0, 2)
                offset = stream.tell()
                try:
                    if stream.write(payload) != len(payload):
                        raise OSError("Incomplete diagnostic write")
                    stream.flush()
                except OSError:
                    try:
                        stream.seek(offset)
                        stream.truncate(offset)
                        stream.flush()
                    except OSError:
                        self._export_state = "write_uncertain"
                        return "write_uncertain"
                    return "write_error"
        except (OSError, TypeError, ValueError):
            if opened:
                self._export_state = "write_uncertain"
                return "write_uncertain"
            return "write_error"
        self._export_state = "exported"
        return "exported"
