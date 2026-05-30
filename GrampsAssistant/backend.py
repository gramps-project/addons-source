#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024  Gramps Development Team
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
Streaming chat backends for the Gramps Chatbot.

All HTTP is done with the Python standard library (http.client / urllib.parse).
No third-party packages are required.

Supported backends
------------------
OpenAICompatibleBackend
    Works with Ollama, llama.cpp server, LM Studio, and OpenAI.
    Uses the ``/v1/chat/completions`` endpoint with ``stream=True``.

AnthropicBackend
    Uses the Anthropic ``/v1/messages`` endpoint.
    Handles the different message format and SSE event schema.
"""

import http.client
import json
import logging
import ssl
import threading
import urllib.parse
from abc import ABC, abstractmethod

_LOG = logging.getLogger(__name__)

try:
    import opik
    _OPIK_CLIENT = opik.Opik(project_name="gramps-assistant")
    _LOG.debug("Opik tracing enabled (project: gramps-assistant)")
except Exception:
    _OPIK_CLIENT = None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class ChatBackend(ABC):
    """
    Abstract base class for streaming chat backends.

    ``stream_chat`` spawns a daemon thread and returns immediately.
    All callbacks are called from that background thread **except**
    ``on_tool_call``, which the panel marshals to the GTK main thread
    via ``GLib.idle_add``.
    """

    @abstractmethod
    def stream_chat(
        self,
        messages: list,
        tools: list,
        on_chunk,
        on_tool_call,
        on_done,
        on_error,
        thread_id: str = None,
    ):
        """
        Start a streaming completion in a background thread.

        Parameters
        ----------
        messages:
            Conversation history in OpenAI message format::

                [{"role": "user", "content": "Hello"}]

        tools:
            List of tool dicts in the backend's native format.
            Pass an empty list to disable tool use.

        on_chunk(text: str):
            Called for each incremental text token from the model.

        on_tool_call(name: str, args: dict, result_callback: callable):
            Called when the model requests a tool invocation.
            The panel must eventually call ``result_callback(result_str)``
            (from any thread) to resume the stream.

        on_done():
            Called once when the full response is complete.

        on_error(exc: Exception):
            Called if an unrecoverable error occurs.
        """


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_connection(parsed_url):
    """Return an ``http.client`` connection for *parsed_url*."""
    scheme = parsed_url.scheme
    host = parsed_url.hostname
    port = parsed_url.port
    if scheme == "https":
        ctx = ssl.create_default_context()
        return http.client.HTTPSConnection(host, port or 443, context=ctx, timeout=120)
    return http.client.HTTPConnection(host, port or 80, timeout=120)


def _execute_tool_calls(tool_call_accum, messages, on_tool_call, _trace=None):
    """
    Synchronously execute all accumulated tool calls.

    Blocks the calling (background) thread on a ``threading.Event`` while
    the GTK main thread runs each tool via ``GLib.idle_add``.

    Returns the updated *messages* list with tool results appended.
    """
    # Build the canonical tool_calls list from accumulator, skipping
    # any entries with an empty name (malformed model output).
    tool_calls_list = []
    for idx in sorted(tool_call_accum.keys()):
        acc = tool_call_accum[idx]
        if not acc.get("name"):
            continue
        tool_calls_list.append(
            {
                "id": acc["id"],
                "type": "function",
                "function": {
                    "name": acc["name"],
                    "arguments": acc["arguments"],
                },
            }
        )

    if not tool_calls_list:
        return messages  # no valid tool calls; caller will invoke on_done()

    # Append the assistant message that triggered the tool calls
    messages = messages + [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls_list,
        }
    ]

    # Execute each tool call, blocking until result arrives from main thread
    for tc in tool_calls_list:
        tc_name = tc["function"]["name"]
        try:
            tc_args = json.loads(tc["function"]["arguments"])
        except json.JSONDecodeError:
            tc_args = {}

        tool_span = None
        if _trace:
            try:
                tool_span = _trace.span(
                    name=f"tool:{tc_name}",
                    type="tool",
                    input={"name": tc_name, "args": tc_args},
                )
            except Exception:
                pass

        result_holder = [None]
        event = threading.Event()

        def _result_callback(result, _ev=event, _rh=result_holder):
            _rh[0] = result
            _ev.set()

        on_tool_call(tc_name, tc_args, _result_callback)
        if not event.wait(timeout=60):  # block until GTK thread executes tool
            _LOG.warning("Tool call %r timed out after 60 s", tc_name)
        result_str = str(result_holder[0]) if result_holder[0] is not None else ""

        if tool_span:
            try:
                tool_span.end(output={"result": result_str})
            except Exception:
                pass

        messages = messages + [
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result_str,
            }
        ]

    return messages


def _read_sse_lines(response):
    """
    Yield decoded lines from an SSE response.

    Uses ``response.fp.readline()`` for true line-by-line streaming.
    Falls back to splitting the full body if ``fp`` is unavailable.
    """
    fp = getattr(response, "fp", None)
    if fp is not None:
        while True:
            raw = fp.readline()
            if not raw:
                break
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")
    else:
        # Fallback: buffer entire response (no live streaming)
        body = response.read().decode("utf-8", errors="replace")
        for line in body.splitlines():
            yield line


# ---------------------------------------------------------------------------
# OpenAI-compatible backend
# ---------------------------------------------------------------------------


class OpenAICompatibleBackend(ChatBackend):
    """
    Streaming backend for any OpenAI-compatible API.

    Works with Ollama (``http://localhost:11434``), llama.cpp server,
    LM Studio, and the OpenAI API (``https://api.openai.com``).
    """

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._parsed = urllib.parse.urlparse(self.base_url)

    def stream_chat(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id=None):
        t = threading.Thread(
            target=self._worker,
            args=(messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id),
            daemon=True,
        )
        t.start()

    def _worker(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id=None):
        trace = None
        if _OPIK_CLIENT:
            try:
                trace = _OPIK_CLIENT.trace(
                    name="gramps-chat",
                    input={"messages": messages},
                    project_name="gramps-assistant",
                    metadata={"backend": "openai", "model": self.model},
                    thread_id=thread_id,
                )
                _orig_done = on_done
                _orig_error = on_error
                _orig_on_chunk = on_chunk
                _all_parts = []

                def on_chunk(text):
                    _all_parts.append(text)
                    _orig_on_chunk(text)

                def on_done():
                    try:
                        trace.end(output={"text": "".join(_all_parts)})
                    except Exception:
                        pass
                    _orig_done()

                def on_error(exc):
                    try:
                        trace.end(output={"text": "".join(_all_parts)},
                                  metadata={"error": str(exc)})
                    except Exception:
                        pass
                    _orig_error(exc)
            except Exception:
                _LOG.debug("Opik trace creation failed", exc_info=True)
        try:
            self._do_stream(messages, tools, on_chunk, on_tool_call, on_done, on_error, trace)
        except Exception as exc:
            _LOG.debug("OpenAI backend stream error", exc_info=True)
            on_error(exc)

    def _do_stream(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, _trace=None):
        """Core streaming loop — may recurse after tool calls."""
        span = None
        _response_parts = []
        _orig_on_chunk = on_chunk
        if _trace:
            try:
                span = _trace.span(
                    name="llm",
                    type="llm",
                    input={"messages": messages},
                    model=self.model,
                )

                def on_chunk(text):
                    _response_parts.append(text)
                    _orig_on_chunk(text)
            except Exception:
                _LOG.debug("Opik span creation failed", exc_info=True)

        base_path = self._parsed.path.rstrip("/")
        path = base_path + "/v1/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        conn = _make_connection(self._parsed)
        try:
            conn.request("POST", path, body=body, headers=headers)
            response = conn.getresponse()

            if response.status != 200:
                raw = response.read().decode("utf-8", errors="replace")
                try:
                    msg = json.loads(raw).get("error", {}).get("message") or raw[:500]
                except Exception:
                    msg = raw[:500]
                raise RuntimeError(f"HTTP {response.status}: {msg}")

            tool_call_accum = {}  # index → {"id","name","arguments"}
            finish_reason = None

            for line in _read_sse_lines(response):
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason") or finish_reason

                # Text delta
                content = delta.get("content")
                if content:
                    on_chunk(content)

                # Tool call delta accumulation
                for tc_delta in delta.get("tool_calls") or []:
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_call_accum:
                        tool_call_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    acc = tool_call_accum[idx]
                    if tc_delta.get("id"):
                        acc["id"] = tc_delta["id"]
                    func = tc_delta.get("function", {})
                    if func.get("name"):
                        acc["name"] = func["name"]
                    if func.get("arguments"):
                        acc["arguments"] += func["arguments"]

                if finish_reason in ("stop", "end_turn", "tool_calls"):
                    break
        finally:
            conn.close()

        # Fallback: some smaller models emit the tool call as plain-text JSON
        # e.g. {"function":"get_main_person"} instead of using tool_calls.
        if not tool_call_accum and _response_parts and tools:
            plain = "".join(_response_parts).strip()
            try:
                obj = json.loads(plain)
                if isinstance(obj, dict) and "function" in obj:
                    tool_call_accum[0] = {
                        "id": "plain-0",
                        "name": obj["function"],
                        "arguments": json.dumps(obj.get("arguments") or obj.get("parameters") or {}),
                    }
                    finish_reason = "tool_calls"
                    _response_parts.clear()
            except (json.JSONDecodeError, TypeError):
                pass

        if tool_call_accum:
            if span:
                try:
                    span.end(output={"text": "".join(_response_parts), "finish_reason": finish_reason})
                except Exception:
                    pass
            updated_messages = _execute_tool_calls(
                tool_call_accum, messages, on_tool_call, _trace
            )
            if updated_messages is messages:
                # All tool calls had empty names; nothing was executed.
                on_done()
                return
            self._do_stream(
                updated_messages, tools, _orig_on_chunk, on_tool_call, on_done, on_error, _trace
            )
        else:
            if span:
                try:
                    span.end(output={"text": "".join(_response_parts)})
                except Exception:
                    pass
            on_done()


# ---------------------------------------------------------------------------
# Anthropic backend
# ---------------------------------------------------------------------------


class AnthropicBackend(ChatBackend):
    """
    Streaming backend for the Anthropic Messages API.

    Default base URL is ``https://api.anthropic.com``.
    """

    ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-opus-4-5",
        api_key: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._parsed = urllib.parse.urlparse(self.base_url)

    # ------------------------------------------------------------------
    # Message format conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_messages(messages: list):
        """
        Translate from internal OpenAI-format messages to Anthropic format.

        Returns ``(system_str_or_None, anthropic_messages_list)``.

        Rules
        -----
        * ``role=="system"`` → extracted into the top-level ``system`` field.
        * ``role=="assistant"`` with ``tool_calls`` → content list with
          ``{"type":"tool_use", ...}`` blocks.
        * Consecutive ``role=="tool"`` messages → merged into one
          ``role=="user"`` message with a list of ``tool_result`` blocks.
        """
        system_parts = []
        result = []
        i = 0

        while i < len(messages):
            msg = messages[i]
            role = msg["role"]

            if role == "system":
                if msg.get("content"):
                    system_parts.append(msg["content"])
                i += 1
                continue

            if role == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    result.append({"role": "user", "content": content})
                else:
                    result.append({"role": "user", "content": content or ""})
                i += 1
                continue

            if role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    content_blocks = []
                    if msg.get("content"):
                        content_blocks.append({"type": "text", "text": msg["content"]})
                    for tc in tool_calls:
                        try:
                            inp = json.loads(tc["function"]["arguments"])
                        except (json.JSONDecodeError, KeyError):
                            inp = {}
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "input": inp,
                            }
                        )
                    result.append({"role": "assistant", "content": content_blocks})
                else:
                    result.append(
                        {"role": "assistant", "content": msg.get("content") or ""}
                    )
                i += 1
                continue

            if role == "tool":
                # Gather consecutive tool-result messages into one user turn
                tool_results = []
                while i < len(messages) and messages[i]["role"] == "tool":
                    tm = messages[i]
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tm.get("tool_call_id", ""),
                            "content": tm.get("content", ""),
                        }
                    )
                    i += 1
                result.append({"role": "user", "content": tool_results})
                continue

            i += 1

        system_str = "\n\n".join(system_parts) if system_parts else None
        return system_str, result

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def stream_chat(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id=None):
        t = threading.Thread(
            target=self._worker,
            args=(messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id),
            daemon=True,
        )
        t.start()

    def _worker(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, thread_id=None):
        trace = None
        if _OPIK_CLIENT:
            try:
                trace = _OPIK_CLIENT.trace(
                    name="gramps-chat",
                    input={"messages": messages},
                    project_name="gramps-assistant",
                    metadata={"backend": "anthropic", "model": self.model},
                    thread_id=thread_id,
                )
                _orig_done = on_done
                _orig_error = on_error
                _orig_on_chunk = on_chunk
                _all_parts = []

                def on_chunk(text):
                    _all_parts.append(text)
                    _orig_on_chunk(text)

                def on_done():
                    try:
                        trace.end(output={"text": "".join(_all_parts)})
                    except Exception:
                        pass
                    _orig_done()

                def on_error(exc):
                    try:
                        trace.end(output={"text": "".join(_all_parts)},
                                  metadata={"error": str(exc)})
                    except Exception:
                        pass
                    _orig_error(exc)
            except Exception:
                _LOG.debug("Opik trace creation failed", exc_info=True)
        try:
            self._do_stream(messages, tools, on_chunk, on_tool_call, on_done, on_error, trace)
        except Exception as exc:
            _LOG.debug("Anthropic backend stream error", exc_info=True)
            on_error(exc)

    def _do_stream(self, messages, tools, on_chunk, on_tool_call, on_done, on_error, _trace=None):
        """Core streaming loop for the Anthropic API."""
        span = None
        _response_parts = []
        _orig_on_chunk = on_chunk
        if _trace:
            try:
                span = _trace.span(
                    name="llm",
                    type="llm",
                    input={"messages": messages},
                    model=self.model,
                )

                def on_chunk(text):
                    _response_parts.append(text)
                    _orig_on_chunk(text)
            except Exception:
                _LOG.debug("Opik span creation failed", exc_info=True)

        system_str, anthropic_messages = self._convert_messages(messages)

        base_path = self._parsed.path.rstrip("/")
        path = base_path + "/v1/messages"

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": anthropic_messages,
            "stream": True,
        }
        if system_str:
            payload["system"] = system_str
        if tools:
            payload["tools"] = tools

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "anthropic-version": self.ANTHROPIC_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        conn = _make_connection(self._parsed)
        try:
            conn.request("POST", path, body=body, headers=headers)
            response = conn.getresponse()

            if response.status != 200:
                raw = response.read().decode("utf-8", errors="replace")
                try:
                    msg = json.loads(raw).get("error", {}).get("message") or raw[:500]
                except Exception:
                    msg = raw[:500]
                raise RuntimeError(f"HTTP {response.status}: {msg}")

            # Accumulate tool-use blocks indexed by content-block index
            # Each entry: {"id","name","partial_json"}
            tool_use_accum = {}
            stop_reason = None

            for line in _read_sse_lines(response):
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                etype = event.get("type", "")

                if etype == "content_block_start":
                    block = event.get("content_block", {})
                    idx = event.get("index", 0)
                    if block.get("type") == "tool_use":
                        tool_use_accum[idx] = {
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                            "partial_json": "",
                        }

                elif etype == "content_block_delta":
                    idx = event.get("index", 0)
                    delta = event.get("delta", {})
                    dtype = delta.get("type", "")

                    if dtype == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            on_chunk(text)

                    elif dtype == "input_json_delta":
                        if idx in tool_use_accum:
                            tool_use_accum[idx]["partial_json"] += delta.get(
                                "partial_json", ""
                            )

                elif etype == "message_delta":
                    stop_reason = event.get("delta", {}).get("stop_reason")

                elif etype == "message_stop":
                    break

        finally:
            conn.close()

        if stop_reason == "tool_use" and tool_use_accum:
            if span:
                try:
                    span.end(output={"text": "".join(_response_parts), "finish_reason": "tool_use"})
                except Exception:
                    pass
            # Convert Anthropic accumulator format → OpenAI tool_call_accum format
            openai_style_accum = {}
            for idx, tu in tool_use_accum.items():
                openai_style_accum[idx] = {
                    "id": tu["id"],
                    "name": tu["name"],
                    "arguments": tu["partial_json"],
                }
            updated_messages = _execute_tool_calls(
                openai_style_accum, messages, on_tool_call, _trace
            )
            if updated_messages is messages:
                on_done()
                return
            self._do_stream(
                updated_messages, tools, _orig_on_chunk, on_tool_call, on_done, on_error, _trace
            )
        else:
            if span:
                try:
                    span.end(output={"text": "".join(_response_parts)})
                except Exception:
                    pass
            on_done()
