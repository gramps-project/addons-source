GrampsWebApiDb is a Gramps database backend that uses a Gramps Web API
server (e.g. gramps-connect or Gramps Web) as a live database, mirrored
locally in SQLite for speed. Reads are served from the local mirror, which
is kept current via the server's transaction-history feed -- both at load
time and on an ongoing poll while the tree stays open, so a change made
from another client (the web app, another desktop instance) shows up here
without closing and reopening the tree; local edits are pushed back to the
server as they're committed. Every already-open Gramps view (People,
Families, ...) refreshes itself automatically as synced changes land, the
same as it would for a local edit -- see `grampswebapidb.py`'s module
docstring for how. The initial sync when opening a tree reports real
progress through Gramps' own load-progress bar, not just a spinning
cursor.

## Credentials

The addon takes a single credential, via the `GRAMPS_WEB_API_KEY`
environment variable, shaped `<REFRESH_TOKEN>*<BASE64URL(URL)>`. There is
deliberately no login dialog wired into WebApiDB itself, and no per-tree
settings.ini. Generate one once via username/password.

The easiest way is the **Generate Gramps Web API key** tool (this addon
also installs `mintapikeytool.py`/`mintapikeytool.gpr.py`): open it from
Tools → Utilities → Generate Gramps Web API key (no Family Tree needs to
be open), enter the server URL, username, and password, and click
**Generate API Key**. On success it sets `GRAMPS_WEB_API_KEY` in the
running Gramps process's environment, so a WebApiDB-backed Family Tree
can be opened right away without restarting Gramps -- but that only lasts
for this process; it is not written to a shell profile, settings.ini, or
any open Family Tree. Copy the displayed key into your shell's startup
file too if you want it set automatically next time.

Click **Create Synced Family Tree for this key** to also create a new,
empty Family Tree for that key's account, using the `grampswebapidb`
database backend and already named correctly (see "Family Tree naming"
below) -- equivalent to creating one by hand via Family Trees → Manage
Family Trees, just with the name and backend filled in for you. It
creates the tree but does not open it; open it from Family Trees →
Manage Family Trees afterward to start syncing.

Alternatively, generate one from the command line with the standalone
`gramps-api-client` package (not yet published; pip-installable from
its own repo, e.g. `pip install -e path/to/gramps-api-client`):

```bash
export GRAMPS_WEB_API_KEY=$(gramps-api-client generate-key --url https://your-server/api --username youruser)
```

or from Python, using either that package's `Client.mint_api_key(url,
username, password)` or this addon's own vendored copy,
`WebApiHandler.mint_api_key(url, username, password)` (see
`webapi_client.py`) — same method, same result, no addon-specific
dependency either way.

**Security tradeoff:** the token embedded in `GRAMPS_WEB_API_KEY` is a
standard JWT *refresh* token obtained from the server's normal `/token/`
login endpoint — the same endpoint and flow the official web client uses,
not an undocumented or exploited access path. gramps-web-api leaves refresh
tokens non-expiring by default, so this key is a long-lived, general-purpose
credential carrying the full permissions of the account that minted it. It
is *not* the same as a real scoped, independently revocable personal access
token (gramps-web-api has that machinery, but it isn't generally wired into
request auth yet). Practically, that means:

* A leaked `GRAMPS_WEB_API_KEY` is as damaging as a leaked password — it
  grants full account access until the underlying password is changed.
  There is no "revoke this key" action independent of that.
* Treat it accordingly: don't commit it, don't log it, and store it the
  same way you'd store a password.

This is a documented engineering tradeoff, made because the properly-scoped
alternative isn't available server-side today — not a vulnerability in
gramps-web-api or a loophole being exploited.

## Family Tree naming

Because credentials come from an environment variable rather than a
per-tree setting, nothing else ties a Family Tree's local mirror to one
particular server account. Gramps must therefore name each Family Tree
using this backend `<username>@<host>` for the account `GRAMPS_WEB_API_KEY`
authenticates as — e.g. `dblank@hadaly.duckdns.org`. Opening a Family Tree
whose name doesn't match the currently-set `GRAMPS_WEB_API_KEY` fails to
load rather than silently mixing that account's data into a mirror synced
from a different one. To connect to a different server or account, create
a new Family Tree named accordingly rather than reusing an existing one.

Gramps' own Family Tree Manager silently replaces characters like `.` with
`_` in any name you type (it needs the name safe to use as a filename), so
a hostname's dots never survive intact — name the tree
`dblank@hadaly_duckdns_org`, not `dblank@hadaly.duckdns.org`. The error
dialog shown for a mismatch always spells out the exact typeable name to
use.

## See also

* `grampswebapidb.py` for the sync/write-through design (module docstring).
* `webapi_client.py` for the token fetch/refresh implementation. This is a
  hand-synced vendored copy (see its own docstring) -- the canonical,
  standalone source is the `gramps-api-client` package, which also
  has the `generate-key` CLI referenced above.
