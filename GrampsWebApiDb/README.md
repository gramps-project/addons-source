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
environment variable, shaped `<TOKEN>*<BASE64URL(URL)>`. There is
deliberately no login dialog wired into WebApiDB itself, and no per-tree
settings.ini. Generate one once via username/password.

The easiest way is the **Generate Gramps Web API key** tool (this addon
also installs `mintapikeytool.py`/`mintapikeytool.gpr.py`): open it from
Tools → Utilities → Generate Gramps Web API key, enter the server URL,
username, and password, and a **Key name** for this computer (it defaults
to the hostname), then click **Generate API Key**. Gramps only shows
the Tools menu once *some* Family Tree is open -- it doesn't have to be a
WebApiDB one, even an empty local tree works, so open (or create) one
first if you don't already have one open. On success the tool sets
`GRAMPS_WEB_API_KEY` in the
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

or from Python, using this addon's own vendored client,
`WebApiHandler.mint_sync_api_key(url, username, password, label)` (see
`webapi_client.py`). A key created in another client's API keys list
(e.g. gramps-connect's user menu → API keys...) works just the same.

**Two kinds of key.** The `TOKEN` half is one of:

* A **sync token** (gramps-web-api v3.23.0 and later) — what the tool
  creates. It's a named, per-device key: you can see when each one was
  last used and remove one without affecting your other devices. The
  access it grants is limited to reading and editing the tree (including
  private records); it can't change your account's e-mail or password.
  WebApiDB trades it for short-lived access tokens at `/token/sync/`.
* A JWT **refresh** token from the server's normal `/token/` login — what
  the tool falls back to against a server older than v3.23.0, and what
  `WebApiHandler.mint_api_key()` and `gramps-api-client generate-key`
  create. gramps-web-api leaves refresh tokens non-expiring by default, so
  this key carries the full permissions of the account that minted it and
  can't be revoked: not even changing the password invalidates it — only
  deleting the account does. Prefer a sync token wherever the server
  supports one.

The addon tells the two apart by shape (a JWT always contains `.`, a sync
token never does), so either works in `GRAMPS_WEB_API_KEY` with no other
setting. Either way, treat the key like a password: don't commit it,
don't log it, and if a sync-token key leaks, remove it from your
account's API keys list and generate a new one.

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
