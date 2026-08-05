GrampsWebApiDb is a Gramps database backend that uses a Gramps Web API
server (e.g. gramps-connect or Gramps Web) as a live database, mirrored
locally in SQLite for speed. Reads are served from the local mirror, which
is kept current via the server's transaction-history feed; local edits are
pushed back to the server as they're committed.

## Credentials

The addon takes a single credential, via the `GRAMPS_WEB_API_KEY`
environment variable, shaped `<REFRESH_TOKEN>*<BASE64URL(URL)>`. There is
deliberately no login dialog and no per-tree settings.ini. Mint one once
via username/password, either from the command line with the standalone
`gramps-web-api-client` package (not yet published; pip-installable from
its own repo, e.g. `pip install -e path/to/gramps-web-api-client`):

```bash
export GRAMPS_WEB_API_KEY=$(gramps-web-api-client generate-key --url https://your-server/api --username youruser)
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

## See also

* `grampswebapidb.py` for the sync/write-through design (module docstring).
* `webapi_client.py` for the token fetch/refresh implementation. This is a
  hand-synced vendored copy (see its own docstring) -- the canonical,
  standalone source is the `gramps-web-api-client` package, which also
  has the `generate-key` CLI referenced above.
