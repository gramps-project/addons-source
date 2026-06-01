# Agent Bridge

Agent Bridge embeds a control bridge inside a running Gramps session so an AI
agent can drive the live application — read and modify the family tree, operate
the user interface, run reports, and create and load new plugins on the fly.

It ships an **MCP server**, so any [Model Context
Protocol](https://modelcontextprotocol.io) client (Claude, and other AI agents)
can drive Gramps through standard tools with no custom glue.

> ⚠️ **Security**: this addon executes arbitrary Python inside Gramps with your
> user privileges. It listens on **no network port** — control happens purely
> through files under `~/.gramps_agent` — so the trust boundary is your user
> account. Only enable it on a machine you control, and remove the gramplet
> when you are done.
>
> As defense-in-depth, every request must carry a shared secret **token**. The
> gramplet generates it on first run at `~/.gramps_agent/token` (owner-only
> permissions) and refuses any request without it. The bundled MCP server and
> `agent_send.py` read the same file automatically, so on a normal single-user
> machine this is transparent. To use a fixed token (e.g. a synced control
> directory), set `GRAMPS_AGENT_TOKEN` in the environment of both Gramps and
> the MCP server.

## Architecture

```
   AI client (Claude / any MCP agent)
        │  Model Context Protocol (stdio)
        ▼
   gramps_mcp_server.py          (a normal Python process)
        │  watched control dir  (~/.gramps_agent)
        ▼
   Agent Bridge gramplet         (inside Gramps; GLib poller on the GTK main thread)
        │
        ▼
   live Gramps: database, UI state, plugin system
```

The gramplet polls the control directory **on the GTK main thread**, so injected
code can safely touch both the database and the GUI. The exec namespace is
persistent — names defined in one call survive to the next — making it a true
REPL. The MCP server is only a protocol adapter; it needs the `mcp` package and
file access, not Gramps' bundled interpreter.

## Install the gramplet

1. Copy the `AgentBridge` folder into your Gramps user plugin directory
   (e.g. `~/.gramps/gramps60/plugins/` on Linux, or
   `%APPDATA%\gramps\gramps60\plugins\` on Windows), or install it from the
   Gramps Addon Manager once published.
2. Restart Gramps.
3. On the **Dashboard**, right-click a gramplet bar → **Add a gramplet** →
   **Agent Bridge**. It should display *"Agent Bridge active"*. It persists in
   your Dashboard layout for future sessions.

## Wire up the MCP server

In the Python environment that runs your AI client (not Gramps' bundled one):

```bash
pip install "mcp[cli]"
```

Register the server with Claude Code:

```bash
claude mcp add gramps -- python /path/to/AgentBridge/gramps_mcp_server.py
```

…or add it to a project `.mcp.json`:

```json
{
  "mcpServers": {
    "gramps": {
      "command": "python",
      "args": ["/path/to/AgentBridge/gramps_mcp_server.py"]
    }
  }
}
```

If your control directory is not the default, set `GRAMPS_AGENT_DIR` in the
server's environment so both sides agree.

## Tools exposed over MCP

| Tool | What it does |
|------|--------------|
| `gramps_status` | Confirm the bridge is reachable; report requests served. |
| `gramps_eval` | Run Python in the live process (`db`, `dbstate`, `uistate`, `gui`, `gramps_lib`, `bridge` pre-bound; assign `result`). |
| `gramps_install_plugin` | Write a plugin into the user plugin dir and hot-reload it. |
| `gramps_people_count` | Number of people in the open tree. |
| `gramps_search_people` | Substring search by name; returns `{gramps_id, name}`. |
| `gramps_active_person` | The currently selected person. |
| `gramps_set_active_person` | Navigate Gramps to a person by Gramps ID. |

`gramps_eval` is the universal primitive; the others are convenience wrappers an
agent can reach for directly.

## Without MCP (debugging)

`agent_send.py` is a low-level CLI that talks to the bridge directly:

```bash
python agent_send.py ping
python agent_send.py eval -c "result = db.get_number_of_people()"
```

## Uninstall / disable

Remove the **Agent Bridge** gramplet from the Dashboard, or delete the
`AgentBridge` plugin folder, then restart Gramps. You may also delete
`~/.gramps_agent`.

## Contact

Brian Caudill — brian.m.caudill@gmail.com
