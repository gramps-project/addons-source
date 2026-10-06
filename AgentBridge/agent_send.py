#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Brian Caudill
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
Low-level command line client for the Gramps Agent Bridge gramplet.

This is a debugging aid that bypasses MCP and talks to the bridge directly.
For normal AI-driven use, prefer the MCP server (gramps_mcp_server.py).

Usage:
    python agent_send.py ping
    python agent_send.py eval -c "result = db.get_number_of_people()"
    python agent_send.py eval -f snippet.py
    echo "result = 1 + 1" | python agent_send.py eval
"""
import os
import sys
import json
import time
import uuid
import argparse

CONTROL = os.environ.get(
    "GRAMPS_AGENT_DIR", os.path.join(os.path.expanduser("~"), ".gramps_agent")
)
REQ = os.path.join(CONTROL, "requests")
RESP = os.path.join(CONTROL, "responses")
TOKEN_FILE = os.path.join(CONTROL, "token")


def read_token():
    """Return the shared secret expected by the bridge, or '' if not found."""
    env_token = os.environ.get("GRAMPS_AGENT_TOKEN")
    if env_token:
        return env_token
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def send(action, code=None, files=None, name=None, timeout=60):
    """Write a request and block until the response arrives or timeout."""
    os.makedirs(REQ, exist_ok=True)
    os.makedirs(RESP, exist_ok=True)
    rid = uuid.uuid4().hex[:12]
    req = {"id": rid, "action": action, "token": read_token()}
    if code is not None:
        req["code"] = code
    if files is not None:
        req["files"] = files
    if name is not None:
        req["name"] = name
    tmp = os.path.join(REQ, rid + ".req.json.part")
    final = os.path.join(REQ, rid + ".req.json")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(req, handle)
    os.replace(tmp, final)

    respfile = os.path.join(RESP, rid + ".resp.json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(respfile):
            try:
                with open(respfile, "r", encoding="utf-8") as handle:
                    resp = json.load(handle)
            except (ValueError, OSError):
                time.sleep(0.1)
                continue
            try:
                os.remove(respfile)
            except OSError:
                pass
            return resp
        time.sleep(0.15)
    return {
        "ok": False,
        "error": "timeout after %ss -- is the Agent Bridge gramplet added "
        "and Gramps running?" % timeout,
    }


def main():
    parser = argparse.ArgumentParser(description="Drive the Gramps Agent Bridge")
    parser.add_argument("action", choices=["ping", "eval", "install"])
    parser.add_argument("-c", "--code", help="inline code for eval")
    parser.add_argument("-f", "--file", help="read eval code from this file")
    parser.add_argument("-n", "--name", help="plugin dir name for install")
    parser.add_argument(
        "-F",
        "--plugin-file",
        action="append",
        default=[],
        metavar="DEST=SRCPATH",
        help="install file mapping, repeatable",
    )
    parser.add_argument("-t", "--timeout", type=float, default=60)
    parser.add_argument("--raw", action="store_true", help="print raw JSON only")
    args = parser.parse_args()

    code = None
    files = None
    if args.action == "eval":
        if args.code is not None:
            code = args.code
        elif args.file:
            with open(args.file, "r", encoding="utf-8") as handle:
                code = handle.read()
        else:
            code = sys.stdin.read()
    elif args.action == "install":
        files = {}
        for mapping in args.plugin_file:
            dest, _, srcpath = mapping.partition("=")
            with open(srcpath, "r", encoding="utf-8") as handle:
                files[dest] = handle.read()

    action = "install_plugin" if args.action == "install" else args.action
    resp = send(
        action, code=code, files=files, name=args.name, timeout=args.timeout
    )

    if args.raw:
        print(json.dumps(resp, indent=2))
        return 0 if resp.get("ok") else 1

    print("ok:", resp.get("ok"))
    if resp.get("stdout"):
        print("--- stdout ---")
        print(resp["stdout"], end="" if resp["stdout"].endswith("\n") else "\n")
    if "result" in resp and resp["result"] not in (None, "None"):
        print("--- result ---")
        print(resp["result"])
    if resp.get("error"):
        print("--- error ---")
        print(resp["error"], end="" if resp["error"].endswith("\n") else "\n")
    if resp.get("written"):
        print("--- installed ---")
        print("\n".join(resp["written"]))
    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
