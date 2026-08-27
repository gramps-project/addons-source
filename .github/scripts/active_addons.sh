# Single source of truth for the is_active() addon filter, sourced by every
# ci.yml job step that gates on include_in_listing.
#
# An addon is "active" (built and released by make.py, so CI gates on it) when
# at least one register() in its .gpr.py would be listed — include_in_listing
# omitted (make.py default True) or set to anything but the literal False. Only
# an addon whose EVERY register() sets include_in_listing=False is inactive.
# Those are skipped by lint, the structure check, compile, and the unit /
# integration test runners. Previously each of those ~6 job steps inlined an
# identical copy of this function; this file is the one place it now lives, so a
# change to the active-addon rule is a one-site edit (per PR #820; Gary Griffin).
#
# The rule itself lives in active_addons.py (ast-based, per-register,
# comment-proof — a grep cannot tell one register's flag from another's, nor a
# real flag from one in a comment). This helper computes the active set ONCE at
# source time and is_active() is a membership test, so a sourcing step starts
# one interpreter, not one per addon. python3, falling back to python for the
# conda Windows lane which ships only `python`. A helper failure aborts the
# sourcing step (its shell runs under set -e) rather than silently marking
# every addon inactive.
#
# Source it from a `shell: bash` step (the function uses `local`, a bashism):
#     source .github/scripts/active_addons.sh
_AA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then _AA_PY=python3; else _AA_PY=python; fi
_ACTIVE_ADDONS="$("$_AA_PY" "$_AA_DIR/active_addons.py" --list .)" || {
  echo "::error::active_addons.py failed — cannot determine active addons" >&2
  return 1 2>/dev/null || exit 1
}

is_active() {
  # Accept a dir name or path; compare on the basename (strip trailing slash
  # then any leading path), matching the names active_addons.py --list prints.
  local name="${1%/}"
  name="${name##*/}"
  printf '%s\n' "$_ACTIVE_ADDONS" | grep -qxF "$name"
}
