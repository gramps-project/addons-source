#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Douglas S. Blank <doug.blank@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Shared plumbing for the GrampsWebApiDb *live* tests (see README.md in this
directory) -- everything here talks to the real, live demo server over
real HTTP. Nothing in this module (or anything that imports it) may be
imported by the addon's normal `tests/` suite.

Isolation convention: every object a live test creates on the server gets
the TEST_TAG tag, and every test deletes what it created in a `finally`
block. sweep.py (this directory) independently finds and deletes anything
still carrying TEST_TAG, for cleanup after a crashed run.
"""

import json
import os
import sys
import tempfile
import time
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlencode

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

from gramps.gen.db.utils import make_database  # noqa: E402

from webapi_client import WebApiHandler  # noqa: E402

#: The live server these tests run against. Not configurable via env on
#: purpose -- these tests are inherently tied to this one server (see
#: README.md), not a generic "any gramps-web-api instance" suite.
SERVER_URL = "https://gramps-connect.duckdns.org/api"

#: The one account these tests authenticate as. Same credentials the
#: original bug report used.
USERNAME = "editor-1"
PASSWORD = "editor-1"

#: Tag name every object a live test creates carries, so it's always
#: identifiable as test data and never mistaken for real demo content --
#: see this directory's README.md "Isolation" section.
TEST_TAG = "addon-live-test"


class RestClient:
    """Thin, dependency-free REST client for building/tearing down server
    state directly -- i.e. *not* through GrampsWebApiDb, so a live test can
    set up an "out-of-band" server change (simulating another editor, or a
    deliberately malformed record) independently of the addon under test.
    """

    def __init__(self, url=SERVER_URL, username=USERNAME, password=PASSWORD):
        self.url = url.rstrip("/")
        self._token = None
        self._authenticate(username, password)

    def _authenticate(self, username, password):
        body = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            f"{self.url}/token/",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            self._token = json.load(resp)["access_token"]

    def _request(self, method, path, data=None, params=None, expect_json=True):
        url = f"{self.url}{path}"
        if params:
            url += f"?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {self._token}"}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as resp:
            if not expect_json:
                return resp.read()
            raw = resp.read()
            return json.loads(raw) if raw else None

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, data=None, params=None):
        return self._request("POST", path, data=data, params=params)

    def put(self, path, data=None):
        return self._request("PUT", path, data=data)

    def delete(self, path):
        return self._request("DELETE", path, expect_json=False)

    # -- convenience wrappers -------------------------------------------------

    def get_or_create_tag(self, name):
        """Return the handle of a Tag named ``name``, creating it via a
        raw POST /people/ style object-add if it doesn't exist. Mirrors
        grampswebapidb.py's own _get_or_create_tag(), but server-side via
        REST, for building fixtures that already carry TEST_TAG before the
        addon ever touches them."""
        results = self.get("/search/", params={"query": name, "page": 1, "pagesize": 20})
        for item in results:
            if item.get("object_type") == "tag" and item["object"]["name"] == name:
                return item["object"]["handle"]
        handle = _new_handle()
        self.post(
            "/transactions/",
            data=[
                {
                    "type": "add",
                    "_class": "Tag",
                    "handle": handle,
                    "old": None,
                    "new": {
                        "_class": "Tag",
                        "handle": handle,
                        "name": name,
                        "color": "#ffffff",
                        "priority": 0,
                        "change": 0,
                    },
                }
            ],
            params={"message": "live test fixture: create tag"},
        )
        return handle

    def find_test_objects(self):
        """Yield (obj_class, handle) for every object currently tagged
        TEST_TAG, across every object type -- used by both per-test
        cleanup and sweep.py."""
        tag_handle = self.get_or_create_tag(TEST_TAG)
        for obj_class, endpoint in _CLASS_ENDPOINTS.items():
            page = 1
            while True:
                objs = self.get(
                    f"/{endpoint}/",
                    params={"page": page, "pagesize": 100},
                )
                if not objs:
                    break
                for obj in objs:
                    if tag_handle in obj.get("tag_list", []):
                        yield obj_class, obj["handle"]
                if len(objs) < 100:
                    break
                page += 1

    def delete_object(self, obj_class, handle):
        endpoint = _CLASS_ENDPOINTS[obj_class]
        try:
            self.delete(f"/{endpoint}/{handle}")
        except HTTPError as exc:
            if exc.code != 404:
                raise


_CLASS_ENDPOINTS = {
    "Person": "people",
    "Family": "families",
    "Event": "events",
    "Place": "places",
    "Source": "sources",
    "Citation": "citations",
    "Repository": "repositories",
    "Media": "media",
    "Note": "notes",
    "Tag": "tags",
}


def _new_handle():
    # Same shape create_id() produces in gramps.gen.utils.id -- 32 hex
    # chars, no dashes. Duplicated here (rather than importing it) since
    # it's the one piece of gramps.gen this module needs before the addon
    # dir is even on sys.path in some invocations.
    import uuid

    return uuid.uuid4().hex


def mint_api_key(url=SERVER_URL, username=USERNAME, password=PASSWORD):
    """Mint a GRAMPS_WEB_API_KEY-shaped string the same way a real user
    would (WebApiHandler.mint_api_key()), for setting GRAMPS_WEB_API_KEY
    before constructing a real WebApiDB mirror."""
    return WebApiHandler.mint_api_key(url, username, password)


def new_mirror_dir(prefix="grampswebapidb_livetest_"):
    """A fresh temp directory for a brand-new local SQLite mirror --
    passed straight to WebApiDB.load(), so the *real* load() bootstrap
    path runs (identity/permission/version checks, then a genuine
    bootstrap resync against the live server), not the tests/ suite's
    reclassify-an-already-loaded-db shortcut.

    Also writes name.txt with this account's expected identity
    ("<username>@<hostname>", normalized the same way
    _check_identity_async()/get_identity() do) -- the same file Gramps'
    own Family Tree Manager writes when a user names a new tree, which
    _check_identity_async() requires to already match before it will
    trust a mirror. A directory with no name.txt at all reproduces a
    real crash (TypeError inside on_fetched(), not a graceful
    DbConnectionError) rather than the scenario this harness wants to
    test -- see live_tests/test_live_new_mirror_no_name_txt.py.
    """
    import re
    from urllib.parse import urlparse

    directory = tempfile.mkdtemp(prefix=prefix)
    hostname = urlparse(SERVER_URL).hostname
    expected = f"{USERNAME}@{hostname}"
    typeable = re.sub(r"[':<>|,;=\"\[\]\.\+\*\/\?\\]", "_", expected)
    with open(os.path.join(directory, "name.txt"), "w", encoding="utf-8") as f:
        f.write(typeable)
    return directory


def import_webapidb():
    """Import grampswebapidb fresh, with GRAMPS_WEB_API_KEY already set in
    os.environ (WebApiHandler.from_env() reads it at _initialize() time,
    i.e. inside load(), not at import time) -- so callers must set the
    env var *before* calling this, and load() after."""
    import grampswebapidb

    return grampswebapidb


def pump_glib(seconds):
    """Run the GLib default main context for up to ``seconds``, the same
    way _run_async_to_completion() does internally -- used by live tests
    that need background timers (poll ticks) to actually fire."""
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    ctx = GLib.MainContext.default()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        while ctx.iteration(False):
            pass
        time.sleep(0.05)
