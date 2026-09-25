# GrampsWebApiDb — Known Gaps

Sync/conflict-handling gaps identified by code review, verified against
`maintenance/gramps60` (checked `_merge_or_overwrite`, `_is_retryable_push_error`,
`MAX_PENDING_PUSHES`, `_poll_tick`, `_scan_and_resolve_media`). Ordered by
priority: correctness first, then performance.

## Correctness

### 1. Scalar-field conflicts resolve silently, whole-object, server-wins — **closed**

**Status: fully implemented**, in two layers:

1. **Real field-level 3-way merge.** `_apply_uncontested_scalar_edits()`
   (grampswebapidb.py) runs after `merge()`'s own list-union/privacy-OR/
   primary-name handling, using the push payload's `old` snapshot
   (`entry["old"]`, threaded through as `_merge_or_overwrite()`'s optional
   `old_data`) as the true 3-way merge base: any plain scalar field
   (date, place, description, gender, ...) that only the local edit
   touched — the server never changed it — now survives, instead of every
   scalar field on the object being discarded just because *some* field
   on it collided. `_SCALAR_MERGE_LOCKED_FIELDS` excludes the handful of
   fields (currently just `Person.primary_name`) whose `merge()` already
   has real special-cased handling this generic layer would otherwise
   fight rather than complement. Covered by
   `TestApplyUncontestedScalarEdits` (unit) and
   `TestFieldLevelMergeAgainstARealDatabase` (real-DB integration,
   confirms two different fields edited concurrently both survive with
   no conflict note at all — there was never a real collision).
2. **Never-silent audit trail for what's left.** A genuine same-field
   collision (both sides touched the identical field to different
   values) still has no algorithmic "correct" answer and resolves
   server-wins, same as before — but no longer silently:
   `_discarded_scalar_fields()` + `_record_conflict_notes()` attach a
   gramps-connect-style `message`-tagged Note recording what was kept and
   what was discarded. See the "Design principle" section below. Covered
   by `TestDiscardedScalarFields` and `TestConflictNoteRecording`.
3. **Extended to every other genuine-conflict shape, strictly gated on
   "Only do for CONFLICTS."** Three more sources feed the same Note via
   `_conflict_summary_lines()`, each requiring a real, direct collision
   check (`_is_genuine_collision()`) rather than the current-vs-merged-
   result trick #2 uses, because none of them show up that way even when
   nothing was actually disputed:
   - `_demoted_field_conflicts()` — a `_SCALAR_MERGE_LOCKED_FIELDS` field
     (`Person.primary_name`) demoted into `alternate_names`. Fixed a real
     bug along the way: `_discarded_scalar_fields()` had no exclusion for
     locked fields, so it was flagging *every* local primary-name edit as
     "discarded" — including a plain, uncontested one on an object that
     happened to have some unrelated conflict — since `merge()` demotes
     the name unconditionally on every retry regardless of collision.
     Now excluded there and checked properly (collision-gated) here
     instead.
   - `_actively_resolved_conflicts()` — a `_SCALAR_MERGE_ACTIVELY_
     RESOLVED_FIELDS` field (`Citation.confidence`, whose
     `level_priority` rule silently picks between two explicit, differing
     values).
   - `_prune_dangling_references()`'s own `pruned` list (now threaded
     through `_merge_or_overwrite()`'s optional `pruned` param) — a
     delete-vs-reference conflict: local's edit still points at a
     Tag/Note/Citation the other side deleted outright.

   Explicitly **not** triggered by an uncontested edit, or by two
   *different* items both surviving a list union (e.g. both sides adding
   a different Tag) — Gramps core's own list-union merges
   (`gen/lib/*base.py`'s `_merge_*_list()` methods) are all equivalence-
   checked, confirmed by direct inspection, so that was never a possible
   source of duplicate entries in the first place; nothing needed here to
   guard against it. Covered by `TestDemotedFieldConflicts`,
   `TestActivelyResolvedConflicts`, `TestPruneDanglingReferencesPruned`,
   and three new cases in `TestConflictNoteRecording` (genuine
   primary-name collision leaves a note; an uncontested primary-name
   edit beside a *real* gender conflict names only the gender conflict;
   a deleted-but-still-referenced Tag leaves a note).

All in `tests/test_grampswebapidb.py` (274 tests total in that file as of
gap #6's close, 379 across the whole addon).

Originally: `_merge_or_overwrite()` unioned only list-valued fields
(notes/citations/media/tags/refs) via the object's own `merge()`, leaving
*every* scalar field (date, place, description, name, type, ...) at the
server's value on any conflict — silently, and regardless of whether that
particular field was the one that actually collided. Confirmed against
`Event.merge()`'s own docstring: "Lost: handle, id, marker, type, date,
place, description of acquisition."

### 2. Non-retryable push failures are dropped with no recovery path — **closed**

**Status: implemented**, and cheaper than the original fix sketch
expected: rather than a new `failed_pushes` metadata list plus GTK
status-bar UI, every drop point now reuses gap #1's own message-note
machinery directly. `_record_undelivered_push_notes()`
(grampswebapidb.py) attaches a `message`-tagged Note to each affected
object, called from `_push_payload_async()`'s `on_push_error` the moment
`_is_retryable_push_error()` says a fresh push's rejection is permanent.

A real correctness risk surfaced building this, not just a UI nicety:
recording a note is itself a local commit, which can itself fail to push
(e.g. permissions revoked mid-session) and land right back in the same
handler — unbounded recursion, one note about the last note's failure,
forever. `_is_message_note_push()` guards every call site: it checks a
failing payload's own `message` (forwarded from its local `DbTxn`
description, see `_message_note_description()`) to recognize "this
payload *is* a message-note commit" and skip recording a note about it.
`TestUndeliveredPushNotes.test_the_notes_own_failed_push_does_not_recurse`
exercises this for real — with every push (original edit *and* the
note-commit's own) rejected identically, exactly one note results, not a
runaway chain. Also reordered `on_push_error`'s non-retryable branch to
call `on_error(exc)` (which releases `self._syncing`) *before* recording
the note, not after — otherwise the note's own push finds `self._syncing`
still held by the very chain it's reporting on and gets needlessly
deferred to the queue instead of going out right away.

Covered by `TestUndeliveredPushNotes` (real-DB integration): a fresh
non-retryable rejection leaves a note; the recursion guard (above); a
queued push that now conflicts or is itself non-retryable on replay
leaves a note (see #3); a queue eviction leaves a note for the evicted
entry specifically, not innocent bystanders (padding entries for a
nonexistent handle absorb any cascading eviction the note-commit's own
queuing pressure causes, confirming the real target is the one and only
note attached).

### 3. `pending_pushes` queue silently evicts oldest entries past 1000 — **closed**

**Status: implemented** as part of #2 — `_queue_pending_push()`
(grampswebapidb.py) now calls `_record_undelivered_push_notes()` for
every evicted entry too, same guard, same tests.

One correctness fix specific to this call site: the trimmed queue is now
persisted (`_set_metadata()`) *before* recording notes for the evicted
entries, not after. Recording a note is a local commit that can itself
re-enter `_queue_pending_push()` (if its own push needs to queue) — doing
that before this method's own `_set_metadata()` call would let the
nested call read this method's not-yet-persisted state, then have its
own write silently overwritten once this call's `_set_metadata()`
finally runs, losing whatever the nested call had just queued. The same
class of risk exists, unfixed, in `_flush_one_pending_push()` (which
persists once at the end of its whole recursion, not after every pop) —
left as a documented, low-severity gap there (worst case, one
best-effort diagnostic note lost to a narrow double-failure race, not
the original edit) rather than rearchitected for it; see that method's
own docstring.

### 4. Birth/death index restore gives up on any event-list change, not just the conflicting one — **closed**

**Status: implemented**, per the fix sketch: `_snapshot_birth_death_indices()`
now captures each index as the specific `EventRef`'s *identity* —
`(ref.ref, ref.role.serialize())`, via the new `_birth_death_ref_identity()`
— rather than the bare integer position and a whole-list signature.
`_restore_birth_death_indices()` uses the new `_relocate_birth_death_index()`
to find that same ref in the post-resync list and restore the index to
wherever it moved, independently for birth and death, tolerating any
unrelated addition/removal/reorder elsewhere in the list. The old
`_event_ref_signature()` whole-list check is gone entirely — it's now
strictly subsumed by per-ref relocation. If the specific ref itself was
removed, restoring falls back to leaving `ImportXml`'s own recomputed
value alone, same conservative behavior as before for that one case.

One extra correctness win beyond the literal fix sketch: `-1` (nothing
marked primary) is now restored *unconditionally*, regardless of what
else in the event list changed — not just when the list is untouched.
`birth_ref_index`/`death_ref_index` has no representation in a Gramps
XML export at all, so no resync could ever legitimately update this
addon's own memory of it from any other client; that memory, including
"nothing was marked," is the best available answer regardless of what
else about the person changed. This changed the behavior (not just the
implementation) of the existing regression test for that case — see
`TestBirthDeathIndexPreservedAcrossResync.test_minus_one_is_restored_even_when_the_event_ref_list_changed`
(rewritten from `test_does_not_restore_when_the_event_ref_list_itself_changed`,
whose name described exactly the over-conservative behavior being fixed).

Covered by `TestBirthDeathIndexPreservedAcrossResync`: the existing
-1-heuristic-recompute case; the rewritten -1-survives-an-unrelated-
list-change case; a new real-index-relocates-across-an-unrelated-
list-change case (the literal fix-sketch scenario); a new
real-index-not-restored-when-its-own-ref-is-removed case; and the
existing deleted-person-is-skipped case.

### 5. `verify_totals` (mirror-completeness check) only runs at `load()`, not on the recurring poll — **closed**

*(The deprioritized outlier — only triggered by out-of-band server
writes, e.g. the demo.grampsweb.org reset case — but cheap enough to
close once reached, so done rather than left open.)*

**Status: implemented**, per the fix sketch: `_poll_tick()` now passes
`verify_totals=True` once every `VERIFY_TOTALS_POLL_INTERVAL_SECONDS`
(3600s / an hour) worth of ticks, tracked via a new
`self._polls_since_verify_totals` counter (reset by `load()` and by
`_poll_tick()` itself each time it actually fires a check) — not every
10-second tick, reusing the existing `_mirror_is_short_of_the_server_async()`
machinery unchanged. Counted in ticks rather than wall-clock time
deliberately: it drifts later for free during a `_record_poll_failure()`
backoff, with no extra bookkeeping, which is the right direction —
nothing useful to verify totals against while the server is unreachable.

Confirmed this doesn't reintroduce the GUI-blocking pattern the addon's
worker-thread rewrite (phases 0–6) eliminated: `_mirror_is_short_of_the_server_async()`
already splits its own work the same way every other operation in this
file does (a bounded local DB read on `runner`, the actual HTTP call on
`io_runner`) — adding it to an occasional poll tick is the same shape of
work `_sync_from_server_async()` already does every tick regardless, not
a new blocking call on the main thread.

Covered by new cases in `TestPolling`: a tick before the interval elapses
passes `verify_totals=False`; a tick at the interval passes
`verify_totals=True` and resets the counter; a tick skipped because a
sync is already running does not advance the counter; `load()` resets
the counter (extended the existing `test_load_resets_poll_backoff_state`).

### 6. Poll errors don't distinguish a permanent rejection from a connectivity blip — **closed**

*(Found while answering "do we have a test for a server reset mid-
session" — not the totals-verification scenario gap #5 covers, but a
distinct, more direct consequence of the same kind of event: a server
reset typically invalidates `GRAMPS_WEB_API_KEY` itself, since the
account the refresh token names is simply gone.)*

**Status: implemented.** `_on_poll_error()`/`_on_media_poll_error()`
(grampswebapidb.py) previously classified *every* `HTTPError` — 401, 403,
404, whatever — the same as a transient outage: back off
(`_record_poll_failure()`) and retry forever, one WARNING log line on the
first failure and only DEBUG noise after that. A revoked/expired token or
a reset server answers with exactly that shape of error, and it will
never self-heal by retrying — unlike the *push* path, which already
distinguishes this correctly (`_is_retryable_push_error()`, gap #2), the
poll's *read* path had no equivalent distinction, and nothing re-
validates credentials after `load()` either (`_check_identity_async()`/
`_check_permissions_async()`/`_check_server_version_async()` only ever
run once, at `load()`).

Both poll error handlers now reuse `_is_retryable_push_error()` (renamed
in spirit, not in code — see its own updated docstring — the 4xx-is-a-
considered-answer logic is identical regardless of which kind of request
it was) to route a permanent rejection to the new `_give_up_polling()`
instead: stops *both* timers (they share the one credential, so a
rejection on either means neither can succeed again), logs once, and
shows a native error dialog via the new `_notify_fatal_poll_error()` —
`gramps.gui.user.User.notify_db_error()`, the same `DBErrorDialog`
mechanism `load()`'s own `DbConnectionError` path relies on, reached
directly since a poll tick fires long after `load()` has already
returned (no `load()` call left for a raised exception to propagate out
of). `has_display()`-gated the same way `_import_progress_user()` already
is, so this stays a no-op (just the log line) headless or without
PyGObject installed.

Deliberately does **not** call `self.close()`: checked how Gramps core
actually closes a tree (`gui/viewmanager.py` calls `dbstate.db.close()`,
never the reverse), and nothing in this backend can tell
`dbstate`/`viewmanager` a tree closed — self-closing here would leave
Gramps' own UI still showing the tree as open while the connection
underneath is gone, silently broken rather than visibly stopped. Instead:
polling stops, the tree stays open and usable, local edits keep working
against the mirror and queuing (same as any other unreachable-server
state — they just never drain until the tree is closed and reopened with
a valid key), and the dialog gives the user a clear, undismissable reason
why.

Idempotent via a new `self._polling_abandoned` flag (reset by `load()`):
both pollers can hit a permanent rejection around the same tick, and the
second arrival stops its own timer quietly rather than show a second
dialog for the same problem.

Covered by new `TestPolling` cases (a permanently-rejected request stops
the record/media poll respectively, without rescheduling; `_give_up_
polling()` stops both timers from either entry point; idempotency across
both pollers; `load()` resets the flag) and a new `TestNotifyFatalPollError`
(mirrors `TestImportProgressUser`'s `has_display()`/import-failure
coverage for the dialog itself).

### 7. Spurious push conflict from a Unicode normalization mismatch — **mitigated, root cause unconfirmed**

Reported live (macOS, Gramps 6.0.6, 2026-09-24): opening a tree
(bootstrap resync, 10669 objects, three poll ticks all reporting zero
server-side changes), then adding a single Person Attribute, produced
`POST /transactions/ -> 400 "Object has changed"` on the very first
push — no other editor involved. The retry (after
`_resync_after_conflict_async()`'s own full resync) conflicted
*again*, identically, and `_after_conflict_resync()`'s give-up branch
fired — see gap-adjacent design note in the module docstring on that
path. Worse: the give-up path's own safety net,
`_send_note_payload_best_effort()`, *also* got rejected the same way,
so the edit was discarded with literally no trace on the server, the
exact failure `live_tests/test_live_repeated_conflict_note_trail.py`
exists to catch — just triggered by a real first conflict with no
out-of-band editor, which that test doesn't reproduce.

Same category of bug as gap 4 (`birth_ref_index`/`death_ref_index`):
Gramps XML export/import is not guaranteed to preserve everything
byte-for-byte, and `diff_items()` — both this addon's own and
gramps-web-api's `old_unchanged()` server-side — treats any resulting
drift as a real edit. The affected Person's name contained a diacritic
(`Zieliński`); the leading theory is Unicode normalization form (NFC
precomposed vs. NFD decomposed) not surviving the round trip
consistently, though this is **not yet confirmed against a live
repro** — a deliberately conservative diagnostic
(`_log_conflict_field_diffs()`/`_walk_conflict_diff()`, called from
`_after_conflict_resync()`) was added first specifically to identify
the actual differing field and flag whether it's NFC/NFD-equivalent,
rather than guessing.

Considered and rejected: patching `gramps.gen.merge.diff.diff_items()`
(gramps core) to compare strings NFC-normalized — the one place both
sides' checks already share, so a fix there would cover both for free
— but gramps core isn't taking bug fixes against the `gramps60`
maintenance line, so nothing landing there reaches a real `gramps60`
deployment. Also rejected: patching `gramps-web-api`'s own
`old_unchanged()` (`api/tasks.py`) directly — plausible since that
repo isn't core-frozen, but no other gramps-web-api client round-trips
through a Gramps XML export/reimport before comparing, so there's
nothing to suggest the server's own comparison logic is actually wrong
for anyone but this addon; fixing it there also depends on that
server's own release/deploy cadence, outside this addon's control.

**Status: mitigated, pending confirmation.** `_normalize_reimported_text()`
(grampswebapidb.py, alongside `_normalize_strings_to_nfc()`) walks
every primary object right after each reimport — both
`_full_resync_async()`'s `rebuild()` and `_bootstrap_full_resync()`,
under the same `self._pulling` context those already hold — and
rewrites any string leaf to NFC that isn't already, via the same
`object_to_dict()`/`data_to_object()` round trip the rest of this file
uses, using `_iter_raw_data()` (bulk, O(types), not O(handles) — see
`_snapshot_all_objects()`) so only a genuinely affected object is ever
recommitted. This is a *hypothesis-driven* fix: it corrects the local
mirror to a canonical form unconditionally, on the theory that Gramps'
own reimport is the side introducing the drift (per the user's own
framing — the affected Person's name was never edited by hand this
session, so whatever disagrees came from "the system importing it via
the server, and then later getting it from Gramps") rather than the
server. If a live repro instead shows the *server's* stored copy is
the one in NFD, this fix does nothing (or, worse, could disagree with
it the other way) — the diagnostic must confirm which side drifted
before this can be called closed rather than "the fix we tried
first."

Covered by `TestNormalizeStringsToNfc` (the pure recursive walk) and
`TestNormalizeReimportedText` (against a real DBAPI database, mimicking
what a real ImportXml round trip losing NFC could leave behind, the
same way `TestBirthDeathIndexPreservedAcrossResync` mimics ImportXml's
birth/death recompute without needing a real export/reimport to
reproduce it): decomposed text is rewritten to NFC and counted;
already-NFC and plain-ASCII data produce zero corrections (no spurious
commit, no bogus "N object(s) normalized" log line to puzzle over).

A second half closes the loop from the other direction:
`WebApiDB._commit_base()` — `DBAPI`'s own single choke point every
`commit_<type>()` (`DbGeneric`) funnels through for *every* write this
mirror ever makes, confirmed `ImportXml` included (it commits via the
ordinary `self.db.commit_person()`/`commit_family()`/... API, not a
bulk/raw bypass) — now normalizes to NFC on any *non-batch* commit, so
the addon itself (or whatever handed it the text — GTK, an input
method, anything upstream of Gramps) can never be the one introducing
a mismatch from an ordinary local edit, rather than only cleaning one
up after the fact on the next resync. Deliberately skipped when
`trans.batch` — a reimport's own `DbTxn` is `batch=True`, and
`DBAPI._commit_base()` itself already skips its usual per-object
bookkeeping there, so paying a fresh serialize round trip per object
regardless would add real cost across a resync's potentially tens of
thousands of objects; `_normalize_reimported_text()` above is the
batch-mode equivalent, done once in bulk instead. Covered by
`TestCommitBaseNormalizesText`: an ordinary commit's decomposed text
comes back NFC; a batch commit's is deliberately left alone (that
path's coverage is `TestNormalizeReimportedText`'s job instead).

**Next step:** get a real reproduction with `--debug` logging past this
change. If the theory is right, `conflict-diff` diagnostic lines
should stop appearing for this object's text fields, and the reported
edit-loss should stop recurring. If the diagnostic instead shows a
non-NFC-equal genuine difference, or the same NFC/NFD disagreement
persists after a resync, this fix is insufficient and the server-side
`old_unchanged()` patch (rejected above for cadence reasons, not
correctness ones) needs reconsidering.

**Other round-trip-fidelity candidates, if the diagnostic points
elsewhere.** Unicode normalization and `birth_ref_index`/
`death_ref_index` are the two confirmed instances of "something
`diff_items()` treats as ordinary content that a Gramps XML round trip
doesn't actually preserve identically" — there is no reason to assume
they're the only two. Not fixed pre-emptively (no evidence any of these
are actually happening, and an unverified fix for a problem that may
not exist carries its own risk — see the `force=1` option considered
and rejected above), but worth checking first if `_walk_conflict_diff()`
ever flags a field none of the above explains:

- **Locale-sensitive type resolution** — the precedent this repo
  already has: this file's own `CLAUDE.md` notes `LANGUAGE=en_US.UTF-8`
  used to be required and no longer is for v6.0+, meaning a
  `GrampsType` (event/attribute/name type, ...) has previously
  round-tripped through locale-aware string matching. The server and a
  client are separate Gramps processes with no guarantee of matching
  locale environments.
- **Version skew** between the server's Gramps/gramps-web-api version
  and a given client's — any "recompute on import" heuristic (not just
  birth/death index) can behave differently across point releases.
- **Empty-string vs. `None` / omitted-element ambiguity** on an
  optional text field, if the exporter's "nothing here" representation
  and the importer's default for a missing element don't agree.
- **Note styled-text tag ranges, or line-ending normalization**
  (`\r\n` vs `\n`) if anything in the transfer path touches it.
- Lower confidence, listed for completeness: reference-list reordering
  (event_ref_list, citation_list, ...) if any path sorts rather than
  preserves file order; Place lat/long is stored as a string in Gramps,
  not a float, so unlikely to be a precision issue, but worth
  remembering if it ever comes up.

## Performance

### 8. Media poll rescans everything, on the main thread, every 5 minutes

`_scan_and_resolve_media()` (grampswebapidb.py:3512) does `iter_media()` +
`os.path.exists()` for every Media object, on the GTK main thread, every
`MEDIA_POLL_INTERVAL_SECONDS` tick, plus a full `GET
/media/?filemissing=1` server query regardless of whether anything
changed.

**Fix sketch:** Maintain a persisted `media_dirty` handle set, populated
at the two points a Media object's path can change —
`transaction_commit()`'s local-edit walk and
`_sync_from_server_async()`'s replay of pulled changes — and have the
poll drain only that set (paths captured at commit time, so no
`self.dbapi` touch needed at scan time — movable off the main thread
entirely). Keep one full audit pass at `load()` as a fallback for drift
invisible to the dirty set (files deleted outside Gramps).

**Difficulty:** Medium — touches two commit paths for lightweight
bookkeeping plus a rework of the scan/transfer split; each piece mirrors
an existing pattern (`pending_pushes`-style persisted set), but it's real
surface area across several functions.

## Design principle: never silent, never blocking

**Status:** Implemented for #1, #2, and #3 (see each above) — all three
now share one mechanism (`_record_conflict_notes()` /
`_record_undelivered_push_notes()`), not three separate ones.

Gaps #1 (scalar-field conflict resolution), #2 (non-retryable push
failures), and #3 (pending-push queue eviction) are the same underlying
commitment applied at three different failure points: automatic conflict
resolution must never destroy an edit without leaving a trace, and it must
never block the user synchronously to ask them to choose a winner —
GrampsWebApiDb has no interactive-merge architecture anywhere (no login
dialog, no settings.ini, no wizard), and a background poll tick can't
suddenly demand a decision mid-session the way GrampsWebSync's
`presentation.py` does.

So the rule for all three: **automate silently only where automation
can't destroy data** (list-union, privacy-OR — the safe cases `merge()`
already handles); **anywhere automatic resolution has to pick a loser,
record what was discarded and what won, attached to the object itself,
and move on.** Never require a synchronous decision; never let a
discarded edit vanish without a trace either.

**Only do for CONFLICTS.** A regular edit that just changes a value with
no actual disagreement must never get a message — only a genuine,
two-sided collision (current *and* local both touched the same thing, to
different values) qualifies. Concretely this means: no message for an
edit only one side made (an ordinary uncontested change); no message for
two different items both surviving a list union (both sides adding a
different Tag is not a conflict); no message for a field whose "conflict"
is really just an artifact of the retry machinery running at all rather
than an actual disagreement (see gap #1's `Person.primary_name` bug
above — merge() demotes it on every retry regardless of collision, which
is *not* by itself grounds for a note). Every detector added to gap #1
checks this directly via `_is_genuine_collision()`, not by inference.

### Implementation: reuse gramps-connect's message-note convention

gramps-connect already has a lightweight, Gramps-core-compatible way to
attach an author-addressed note to an object: a plain `Note` (`NoteType`
untouched) carrying the `"message"` tag (plus `"todo-open"`/`"todo-done"`
for an open/acknowledged state), with text formatted as `"<author>:
<message>"` (`../gramps-connect/app/src/store/notesApi.ts`,
`authoredText.ts`). It degrades gracefully anywhere that doesn't know the
convention — gramps-web and desktop Gramps just show it as an ordinary
tagged note, not broken or garbled — so reusing it here means the
conflict record shows up as a review-worthy "message" in gramps-connect's
Messages view for free, with no new client-side code needed anywhere
else.

Concretely: on a genuinely irreconcilable scalar-field collision (#1,
`_discarded_scalar_fields()` + `_record_conflict_notes()` — note that
`_apply_uncontested_scalar_edits()` now applies first, so this only fires
for a true same-field double-edit, not every conflicting object), a
dropped non-retryable push (#2), or an evicted queue entry (#3, via #2's
own `_record_undelivered_push_notes()`), commit a Note tagged `message` +
`todo-open`, text along the lines of `"GrampsWebApiDb: <Class> -- kept
<field> (<value>), discarded local edit (<value>)"` (#1) or
`"GrampsWebApiDb: <Class> -- local edit could not be synced to the
server: <reason>"` (#2/#3), attached to the affected object's
`note_list`.

**Commit it as its own, separate local transaction, after the conflict
resolution's own transaction has already landed — not folded into the
resync/retry `DbTxn` itself.** Reasons:

- Keeps the delicate conflict-retry path (`_retry_after_conflict()`,
  `_merge_or_overwrite()`) free of unrelated bookkeeping logic.
- The note-attachment commit goes through the completely ordinary
  `transaction_commit()` → push path, exactly like any other local edit —
  no special-casing needed.
- It's safe even if *that* push itself hits a conflict: attaching a note
  is a list-valued change, which `merge()` already unions correctly, so a
  conflict on the note-attachment commit can never lose the conflict
  record the way a scalar-field conflict can lose the original edit.
