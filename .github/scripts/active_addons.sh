# Single source of truth for the is_active() addon filter, sourced by every
# ci.yml job step that gates on include_in_listing.
#
# An addon is "active" (built and released by make.py, so CI gates on it) unless
# EVERY register() in its .gpr.py sets include_in_listing=False. Those inactive
# addons are skipped by lint, the structure check, compile, and the unit /
# integration test runners. Previously each of those ~6 job steps inlined an
# identical copy of this function; this file is the one place it now lives, so a
# change to the active-addon rule is a one-site edit (per PR #820; Gary Griffin).
#
# Source it from a `shell: bash` step (the function uses `local`, a bashism):
#     source .github/scripts/active_addons.sh
is_active() {
  local addon="$1" g
  for g in "$addon"/*.gpr.py; do
    [ -f "$g" ] || continue
    grep -qE 'include_in_listing[[:space:]]*=[[:space:]]*True' "$g" && return 0
    grep -qE 'include_in_listing[[:space:]]*=' "$g" || return 0
  done
  return 1
}
