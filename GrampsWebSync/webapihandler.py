"""Web API handler class for the Gramps Web Sync plugin."""

import gzip
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import gramps
from gramps.gen.db import KEY_TO_CLASS_MAP, DbTxn
from gramps.gen.db.dbconst import TXNADD, TXNDEL, TXNUPD
from gramps.gen.utils.grampslocale import GrampsLocale


class WebApiHandler:
    """Web API connection handler."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        download_callback: Optional[Callable] = None,
    ) -> None:
        """Initialize given URL, user name, and password."""
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self._access_token: Optional[str] = None
        self.download_callback = download_callback
        # get and cache the access token
        self.fetch_token()

    @property
    def access_token(self) -> str:
        """Get the access token. Cached after first call"""
        if not self._access_token:
            self.fetch_token()
        return self._access_token

    def fetch_token(self) -> None:
        """Fetch and store an access token."""
        data = json.dumps({"username": self.username, "password": self.password})
        req = Request(
            f"{self.url}/token/",
            data=data.encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req) as res:
                res_json = json.load(res)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.url = f"{self.url}/api"
            return self.fetch_token()
        self._access_token = res_json["access_token"]

    def get_lang(self) -> Optional[str]:
        """Fetch language information."""
        req = Request(
            f"{self.url}/metadata/",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        with urlopen(req) as res:
            try:
                res_json = json.load(res)
            except (UnicodeDecodeError, json.JSONDecodeError, HTTPError):
                return None
        return (res_json.get("locale") or {}).get("lang")

    def download_xml(self) -> Path:
        """Download an XML export and return the path of the temp file."""
        url = f"{self.url}/exporters/gramps/file"
        temp = NamedTemporaryFile(delete=False)
        try:
            self._download_file(url=url, fobj=temp)
        finally:
            temp.close()
        unzipped_name = f"{temp.name}.gramps"
        with open(unzipped_name, "wb") as fu:
            with gzip.open(temp.name) as fz:
                fu.write(fz.read())
        os.remove(temp.name)
        return Path(unzipped_name)

    def commit(self, trans: DbTxn) -> None:
        """Commit the changes to the remote database."""
        lang = self.get_lang()
        payload = transaction_to_json(trans, lang)
        if payload:
            data = json.dumps(payload).encode()
            req = Request(
                f"{self.url}/transactions/",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
            )
            urlopen(req)

    def get_missing_files(self, retry: bool = True) -> None:
        """Get a list of remote media objects with missing files."""
        req = Request(
            f"{self.url}/media/?filemissing=1",
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            with urlopen(req) as res:
                res_json = json.load(res)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self.get_missing_files(retry=False)
            raise
        return res_json

    def _download_file(
        self, url: str, fobj, retry: bool = True, token_url: bool = False
    ):
        """Download a file."""
        if token_url:
            req = Request(f"{url}?jwt={self.access_token}")
        else:
            req = Request(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        try:
            with urlopen(req) as res:
                chunk_size = 1024
                chunk = res.read(chunk_size)
                fobj.write(chunk)
                while chunk:
                    if self.download_callback is not None:
                        self.download_callback()
                    chunk = res.read(chunk_size)
                    fobj.write(chunk)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self._download_file(
                    url=url, fobj=fobj, retry=False, token_url=token_url
                )
            raise

    def download_media_file(self, handle: str, path) -> bool:
        """Download a media file."""
        url = f"{self.url}/media/{handle}/file"
        with open(path, "wb") as f:
            self._download_file(url=url, fobj=f, token_url=True)
        return True

    def upload_media_file(self, handle: str, path) -> bool:
        """Upload a media file."""
        url = f"{self.url}/media/{handle}/file?uploadmissing=1"
        try:
            with open(path, "rb") as f:
                self._upload_file(url=url, fobj=f)
        except HTTPError as exc:
            if exc.code == 409:
                return False
            raise
        return True

    def _upload_file(self, url: str, fobj, retry: bool = True):
        """Upload a file."""
        req = Request(
            url,
            data=fobj,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="PUT",
        )
        try:
            with urlopen(req) as res:
                pass
        except HTTPError as exc:
            if exc.code == 401 and retry:
                # in case of 401, retry once with a new token
                sleep(1)  # avoid server-side rate limit
                self.fetch_token()
                return self._upload_file(url=url, fobj=fobj, retry=False)
            raise


# special cases for type names. See https://github.com/gramps-project/gramps-webapi/issues/163#issuecomment-940361882
_type_name_special_cases = {
    "Father Age": "Father's Age",
    "Mother Age": "Mother's Age",
    "BIC": "Born In Covenant",
    "DNS": "Do not seal",
    "DNS/CAN": "Do not seal/Cancel",
    "bold": "Bold",
    "italic": "Italic",
    "underline": "Underline",
    "fontface": "Fontface",
    "fontsize": "Fontsize",
    "fontcolor": "Fontcolor",
    "highlight": "Highlight",
    "superscript": "Superscript",
    "link": "Link",
}


def to_json(obj, lang: Optional[str] = None) -> str:
    """
    Encode a Gramps object to a JSON object.

    Patched from `gramps.gen.serialize` to allow translation of type names.
    """

    def __default(obj):
        obj_dict = {"_class": obj.__class__.__name__}
        if isinstance(obj, gramps.gen.lib.GrampsType):
            if not lang:
                obj_dict["string"] = getattr(obj, "string")
            else:
                # if the remote locale is different from the local one,
                # need to translate type names.
                glocale = GrampsLocale(lang=lang)
                # In most cases, the xml_str
                # is the same as the gettext message, so it can just be translated.
                s_untrans = obj.xml_str()
                # handle exceptional cases
                s_untrans = _type_name_special_cases.get(s_untrans, s_untrans)
                # translate
                obj_dict["string"] = glocale.translation.gettext(s_untrans)
        if isinstance(obj, gramps.gen.lib.Date):
            if obj.is_empty() and not obj.text:
                return None
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):
                obj_dict[key] = value
        for key, value in obj.__class__.__dict__.items():
            if isinstance(value, property):
                if key != "year":
                    obj_dict[key] = getattr(obj, key)
        return obj_dict

    return json.dumps(obj, default=__default, ensure_ascii=False)


def transaction_to_json(
    transaction: DbTxn, lang: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return a JSON representation of a database transaction."""
    out = []
    for recno in transaction.get_recnos(reverse=False):
        key, action, handle, old_data, new_data = transaction.get_record(recno)
        try:
            obj_cls_name = KEY_TO_CLASS_MAP[key]
        except KeyError:
            continue  # this happens for references
        trans_dict = {TXNUPD: "update", TXNDEL: "delete", TXNADD: "add"}
        obj_cls = getattr(gramps.gen.lib, obj_cls_name)
        if old_data:
            old_data = obj_cls().unserialize(old_data)
        if new_data:
            new_data = obj_cls().unserialize(new_data)
        item = {
            "type": trans_dict[action],
            "handle": handle,
            "_class": obj_cls_name,
            "old": json.loads(to_json(old_data, lang=lang)),
            "new": json.loads(to_json(new_data, lang=lang)),
        }
        out.append(item)
    return out
