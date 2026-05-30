#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps Development Team
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
Tests for backend.py: message conversion, SSE parsing, tool-call filtering,
and live integration tests against the configured OpenAI-compatible backend.
"""

import io
import json
import os
import threading

import pytest

from backend import (
    AnthropicBackend,
    OpenAICompatibleBackend,
    _execute_tool_calls,
    _read_sse_lines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HAVE_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


def _make_fake_fp_response(lines):
    """Return an object with a ``.fp`` whose ``readline`` yields *lines*."""
    body = "\r\n".join(lines).encode("utf-8") + b"\r\n"

    class _FP:
        _buf = io.BytesIO(body)

        @classmethod
        def readline(cls):
            return cls._buf.readline()

    class _Resp:
        fp = _FP

    return _Resp()


def _collect(backend, messages, tools=None, timeout=30):
    """
    Drive *backend.stream_chat* synchronously and return ``(full_text, tool_calls_list)``.

    tool_calls_list contains dicts {name, args} for each invocation.
    Raises the backend error if one occurs.
    """
    chunks = []
    tool_calls = []
    done_ev = threading.Event()
    error_holder = [None]

    def on_chunk(text):
        chunks.append(text)

    def on_tool_call(name, args, result_cb):
        tool_calls.append({"name": name, "args": args})
        result_cb(json.dumps({"result": "ok"}))

    def on_done():
        done_ev.set()

    def on_error(exc):
        error_holder[0] = exc
        done_ev.set()

    backend.stream_chat(
        messages=messages,
        tools=tools or [],
        on_chunk=on_chunk,
        on_tool_call=on_tool_call,
        on_done=on_done,
        on_error=on_error,
    )
    done_ev.wait(timeout=timeout)
    if error_holder[0]:
        raise error_holder[0]
    return "".join(chunks), tool_calls


# ---------------------------------------------------------------------------
# AnthropicBackend._convert_messages
# ---------------------------------------------------------------------------


class TestConvertMessages:
    def test_system_extracted_from_messages(self):
        msgs = [{"role": "system", "content": "You are helpful."}]
        system, result = AnthropicBackend._convert_messages(msgs)
        assert system == "You are helpful."
        assert result == []

    def test_no_system_returns_none(self):
        msgs = [{"role": "user", "content": "Hi"}]
        system, _ = AnthropicBackend._convert_messages(msgs)
        assert system is None

    def test_multiple_systems_joined(self):
        msgs = [
            {"role": "system", "content": "Part 1."},
            {"role": "system", "content": "Part 2."},
        ]
        system, _ = AnthropicBackend._convert_messages(msgs)
        assert "Part 1." in system and "Part 2." in system

    def test_user_message_preserved(self):
        msgs = [{"role": "user", "content": "Hello"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        assert result[0] == {"role": "user", "content": "Hello"}

    def test_assistant_message_preserved(self):
        msgs = [{"role": "assistant", "content": "Hi there"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hi there"

    def test_assistant_with_tool_calls_produces_tool_use_blocks(self):
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call1",
                        "type": "function",
                        "function": {
                            "name": "get_person",
                            "arguments": '{"gramps_id": "I001"}',
                        },
                    }
                ],
            }
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        assert result[0]["role"] == "assistant"
        blocks = result[0]["content"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0]["name"] == "get_person"
        assert tool_blocks[0]["input"] == {"gramps_id": "I001"}

    def test_assistant_text_plus_tool_call_includes_text_block(self):
        msgs = [
            {
                "role": "assistant",
                "content": "Let me look that up.",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": "{}"},
                    }
                ],
            }
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        blocks = result[0]["content"]
        types = [b["type"] for b in blocks]
        assert "text" in types
        assert "tool_use" in types

    def test_single_tool_result_becomes_user_message(self):
        msgs = [{"role": "tool", "tool_call_id": "c1", "content": "Smith, John"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        assert result[0]["role"] == "user"
        blocks = result[0]["content"]
        assert blocks[0]["type"] == "tool_result"
        assert blocks[0]["tool_use_id"] == "c1"
        assert blocks[0]["content"] == "Smith, John"

    def test_consecutive_tool_results_merged_into_one_user_message(self):
        msgs = [
            {"role": "tool", "tool_call_id": "c1", "content": "result1"},
            {"role": "tool", "tool_call_id": "c2", "content": "result2"},
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["content"]) == 2

    def test_tool_results_not_merged_across_assistant_turns(self):
        msgs = [
            {"role": "tool", "tool_call_id": "c1", "content": "r1"},
            {"role": "assistant", "content": "ok"},
            {"role": "tool", "tool_call_id": "c2", "content": "r2"},
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        user_msgs = [m for m in result if m["role"] == "user"]
        assert len(user_msgs) == 2

    def test_invalid_tool_call_json_yields_empty_input(self):
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "foo", "arguments": "NOT JSON"},
                    }
                ],
            }
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        blocks = result[0]["content"]
        tool_block = next(b for b in blocks if b["type"] == "tool_use")
        assert tool_block["input"] == {}


# ---------------------------------------------------------------------------
# _read_sse_lines
# ---------------------------------------------------------------------------


class TestReadSseLines:
    def test_fp_readline_used_when_available(self):
        resp = _make_fake_fp_response(["data: hello", "data: world"])
        lines = [l for l in _read_sse_lines(resp) if l]
        assert "data: hello" in lines
        assert "data: world" in lines

    def test_fallback_when_no_fp(self):
        class _NoFPResp:
            fp = None

            def read(self):
                return b"data: one\r\ndata: two\r\n"

        lines = [l for l in _read_sse_lines(_NoFPResp()) if l]
        assert "data: one" in lines
        assert "data: two" in lines

    def test_done_sentinel_yields_as_line(self):
        resp = _make_fake_fp_response(["data: [DONE]"])
        lines = list(_read_sse_lines(resp))
        assert any("[DONE]" in l for l in lines)

    def test_empty_body_yields_nothing_meaningful(self):
        resp = _make_fake_fp_response([])
        non_empty = [l for l in _read_sse_lines(resp) if l]
        assert non_empty == []


# ---------------------------------------------------------------------------
# _execute_tool_calls (unit — no HTTP)
# ---------------------------------------------------------------------------


class TestExecuteToolCalls:
    def _make_accum(self, **overrides):
        base = {"id": "call_1", "name": "my_tool", "arguments": '{"x": 1}'}
        base.update(overrides)
        return {0: base}

    def _sync_on_tool_call(self, name, args, result_cb):
        """Immediately return a canned result."""
        result_cb(json.dumps({"done": True}))

    def test_returns_updated_messages(self):
        messages = [{"role": "user", "content": "Hi"}]
        updated = _execute_tool_calls(
            self._make_accum(), messages, self._sync_on_tool_call
        )
        assert updated is not messages
        roles = [m["role"] for m in updated]
        assert "assistant" in roles
        assert "tool" in roles

    def test_tool_result_appended(self):
        messages = [{"role": "user", "content": "Hi"}]
        updated = _execute_tool_calls(
            self._make_accum(), messages, self._sync_on_tool_call
        )
        tool_msg = next(m for m in updated if m["role"] == "tool")
        assert tool_msg["tool_call_id"] == "call_1"

    def test_empty_name_skipped_returns_original(self):
        messages = [{"role": "user", "content": "Hi"}]
        accum = {0: {"id": "bad", "name": "", "arguments": "{}"}}
        updated = _execute_tool_calls(accum, messages, self._sync_on_tool_call)
        assert updated is messages  # identity check — nothing was executed

    def test_multiple_tool_calls_all_executed(self):
        invocations = []

        def on_tool_call(name, args, result_cb):
            invocations.append(name)
            result_cb(json.dumps({"ok": True}))

        accum = {
            0: {"id": "c1", "name": "tool_a", "arguments": "{}"},
            1: {"id": "c2", "name": "tool_b", "arguments": "{}"},
        }
        messages = [{"role": "user", "content": "run both"}]
        _execute_tool_calls(accum, messages, on_tool_call)
        assert "tool_a" in invocations
        assert "tool_b" in invocations

    def test_mixed_empty_and_valid_names(self):
        invocations = []

        def on_tool_call(name, args, result_cb):
            invocations.append(name)
            result_cb("{}")

        accum = {
            0: {"id": "c0", "name": "",        "arguments": "{}"},
            1: {"id": "c1", "name": "real_tool","arguments": "{}"},
        }
        messages = [{"role": "user", "content": "hi"}]
        updated = _execute_tool_calls(accum, messages, on_tool_call)
        assert updated is not messages
        assert invocations == ["real_tool"]


# ---------------------------------------------------------------------------
# _process_chunk pure-logic unit tests (no GTK required)
# ---------------------------------------------------------------------------


class TestProcessChunkLogic:
    """
    Verify the increment / line-buffer logic that mirrors _process_chunk.

    This is extracted from grampsassistant.py as a pure function so it can run
    without GTK.  A regression test for the 'May24' / 'Johnjalmar' space-loss
    investigation: if spaces dropped here, the display would be wrong.
    """

    @staticmethod
    def _simulate(chunks):
        """
        Simulate the core text-assembly of _process_chunk.

        Returns ``(committed_lines, final_partial)`` where committed_lines are
        the completed (newline-terminated) lines and final_partial is the
        unfinished partial line still in the buffer.
        """
        line_buffer = ""
        committed = []

        for text in chunks:
            combined = line_buffer + text
            parts = combined.split("\n")

            for part in parts[:-1]:
                line_buffer = part
                committed.append(part)
                line_buffer = ""

            new_partial = parts[-1]
            # Only the increment (characters not yet in the buffer) gets inserted
            increment = new_partial[len(line_buffer):]  # noqa: F841 — mirrors real code
            line_buffer = new_partial

        return committed, line_buffer

    def test_single_chunk_no_newline(self):
        _, partial = self._simulate(["Hello world"])
        assert partial == "Hello world"

    def test_space_preserved_as_own_chunk(self):
        _, partial = self._simulate(["May", " ", "24"])
        assert partial == "May 24"

    def test_space_at_end_of_chunk(self):
        _, partial = self._simulate(["May ", "24"])
        assert partial == "May 24"

    def test_space_at_start_of_next_chunk(self):
        _, partial = self._simulate(["May", " 24"])
        assert partial == "May 24"

    def test_words_not_merged(self):
        _, partial = self._simulate(["John", " ", "Hjalmar"])
        assert partial == "John Hjalmar"
        assert "JohnHjalmar" not in partial

    def test_newline_commits_line(self):
        committed, partial = self._simulate(["Hello\n", "world"])
        assert committed == ["Hello"]
        assert partial == "world"

    def test_multiple_lines_in_one_chunk(self):
        committed, partial = self._simulate(["line1\nline2\npar"])
        assert committed == ["line1", "line2"]
        assert partial == "par"

    def test_partial_then_newline_commits(self):
        committed, partial = self._simulate(["Hel", "lo\n", "nex"])
        assert committed == ["Hello"]
        assert partial == "nex"

    def test_empty_chunk_ignored(self):
        _, partial = self._simulate(["Hello", "", " world"])
        assert partial == "Hello world"

    def test_multiple_spaces_preserved(self):
        _, partial = self._simulate(["a ", " b"])
        assert partial == "a  b"

    def test_final_empty_line_after_newline(self):
        committed, partial = self._simulate(["done\n"])
        assert committed == ["done"]
        assert partial == ""


# ---------------------------------------------------------------------------
# Live integration — OpenAI-compatible backend
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAVE_OPENAI_KEY, reason="OPENAI_API_KEY not set")
class TestOpenAIBackendLive:
    """End-to-end tests against the real OpenAI API (gpt-4.1-mini for speed/cost)."""

    def _backend(self):
        return OpenAICompatibleBackend(
            base_url="https://api.openai.com",
            model="gpt-4.1-mini",
            api_key=os.environ["OPENAI_API_KEY"],
        )

    def test_basic_response_streamed(self):
        messages = [{"role": "user", "content": "Reply with exactly the word: PONG"}]
        text, _ = _collect(self._backend(), messages)
        assert "PONG" in text

    def test_response_is_non_empty_text(self):
        """Streamed chunks assemble into a non-empty string."""
        messages = [{"role": "user", "content": "Say exactly: hello world"}]
        text, _ = _collect(self._backend(), messages)
        assert len(text) > 0
        assert " " in text  # at minimum "hello world" has a space

    def test_multiline_response_has_newlines(self):
        messages = [
            {
                "role": "user",
                "content": "List three colors, one per line, nothing else.",
            }
        ]
        text, _ = _collect(self._backend(), messages)
        assert text.count("\n") >= 2

    def test_tool_call_is_invoked(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_temperature",
                    "description": "Get the current temperature in Celsius.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        messages = [
            {
                "role": "user",
                "content": (
                    "You must call get_temperature to answer this question. "
                    "What is the current temperature? Call the tool now."
                ),
            }
        ]
        _, tool_calls = _collect(self._backend(), messages, tools=tools)
        assert any(tc["name"] == "get_temperature" for tc in tool_calls)

    def test_tool_result_used_in_response(self):
        """Model should incorporate the tool result into its reply."""
        tool_result_value = "42 degrees Celsius"
        chunks = []
        done_ev = threading.Event()
        error_holder = [None]

        def on_chunk(t):
            chunks.append(t)

        def on_tool_call(name, args, result_cb):
            result_cb(json.dumps({"temperature": tool_result_value}))

        def on_done():
            done_ev.set()

        def on_error(exc):
            error_holder[0] = exc
            done_ev.set()

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_temperature",
                    "description": "Get the current temperature.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        messages = [
            {
                "role": "user",
                "content": "What is the temperature? Use get_temperature and tell me the exact value.",
            }
        ]
        backend = self._backend()
        backend.stream_chat(
            messages=messages,
            tools=tools,
            on_chunk=on_chunk,
            on_tool_call=on_tool_call,
            on_done=on_done,
            on_error=on_error,
        )
        done_ev.wait(timeout=30)
        if error_holder[0]:
            raise error_holder[0]

        full = "".join(chunks)
        assert "42" in full

    def test_bad_api_key_raises_runtime_error(self):
        backend = OpenAICompatibleBackend(
            base_url="https://api.openai.com",
            model="gpt-4.1-mini",
            api_key="sk-bad-key",
        )
        with pytest.raises(RuntimeError, match="HTTP 401"):
            _collect(backend, [{"role": "user", "content": "hi"}])
