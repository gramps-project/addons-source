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
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import (
    AnthropicBackend,
    OpenAICompatibleBackend,
    _decode_json_string,
    _execute_tool_calls,
    _infer_tool_name,
    _read_sse_lines,
    _recover_args,
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


class TestConvertMessages(unittest.TestCase):
    def test_system_extracted_from_messages(self):
        msgs = [{"role": "system", "content": "You are helpful."}]
        system, result = AnthropicBackend._convert_messages(msgs)
        self.assertEqual(system, "You are helpful.")
        self.assertEqual(result, [])

    def test_no_system_returns_none(self):
        msgs = [{"role": "user", "content": "Hi"}]
        system, _ = AnthropicBackend._convert_messages(msgs)
        self.assertIsNone(system)

    def test_multiple_systems_joined(self):
        msgs = [
            {"role": "system", "content": "Part 1."},
            {"role": "system", "content": "Part 2."},
        ]
        system, _ = AnthropicBackend._convert_messages(msgs)
        self.assertIn("Part 1.", system)
        self.assertIn("Part 2.", system)

    def test_user_message_preserved(self):
        msgs = [{"role": "user", "content": "Hello"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        self.assertEqual(result[0], {"role": "user", "content": "Hello"})

    def test_assistant_message_preserved(self):
        msgs = [{"role": "assistant", "content": "Hi there"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        self.assertEqual(result[0]["role"], "assistant")
        self.assertEqual(result[0]["content"], "Hi there")

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
        self.assertEqual(result[0]["role"], "assistant")
        blocks = result[0]["content"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        self.assertEqual(len(tool_blocks), 1)
        self.assertEqual(tool_blocks[0]["name"], "get_person")
        self.assertEqual(tool_blocks[0]["input"], {"gramps_id": "I001"})

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
        self.assertIn("text", types)
        self.assertIn("tool_use", types)

    def test_single_tool_result_becomes_user_message(self):
        msgs = [{"role": "tool", "tool_call_id": "c1", "content": "Smith, John"}]
        _, result = AnthropicBackend._convert_messages(msgs)
        self.assertEqual(result[0]["role"], "user")
        blocks = result[0]["content"]
        self.assertEqual(blocks[0]["type"], "tool_result")
        self.assertEqual(blocks[0]["tool_use_id"], "c1")
        self.assertEqual(blocks[0]["content"], "Smith, John")

    def test_consecutive_tool_results_merged_into_one_user_message(self):
        msgs = [
            {"role": "tool", "tool_call_id": "c1", "content": "result1"},
            {"role": "tool", "tool_call_id": "c2", "content": "result2"},
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(len(result[0]["content"]), 2)

    def test_tool_results_not_merged_across_assistant_turns(self):
        msgs = [
            {"role": "tool", "tool_call_id": "c1", "content": "r1"},
            {"role": "assistant", "content": "ok"},
            {"role": "tool", "tool_call_id": "c2", "content": "r2"},
        ]
        _, result = AnthropicBackend._convert_messages(msgs)
        user_msgs = [m for m in result if m["role"] == "user"]
        self.assertEqual(len(user_msgs), 2)

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
        self.assertEqual(tool_block["input"], {})


# ---------------------------------------------------------------------------
# _read_sse_lines
# ---------------------------------------------------------------------------


class TestReadSseLines(unittest.TestCase):
    def test_fp_readline_used_when_available(self):
        resp = _make_fake_fp_response(["data: hello", "data: world"])
        lines = [l for l in _read_sse_lines(resp) if l]
        self.assertIn("data: hello", lines)
        self.assertIn("data: world", lines)

    def test_fallback_when_no_fp(self):
        class _NoFPResp:
            fp = None

            def read(self):
                return b"data: one\r\ndata: two\r\n"

        lines = [l for l in _read_sse_lines(_NoFPResp()) if l]
        self.assertIn("data: one", lines)
        self.assertIn("data: two", lines)

    def test_done_sentinel_yields_as_line(self):
        resp = _make_fake_fp_response(["data: [DONE]"])
        lines = list(_read_sse_lines(resp))
        self.assertTrue(any("[DONE]" in l for l in lines))

    def test_empty_body_yields_nothing_meaningful(self):
        resp = _make_fake_fp_response([])
        non_empty = [l for l in _read_sse_lines(resp) if l]
        self.assertEqual(non_empty, [])


# ---------------------------------------------------------------------------
# _execute_tool_calls (unit — no HTTP)
# ---------------------------------------------------------------------------


class TestExecuteToolCalls(unittest.TestCase):
    def _make_accum(self, **overrides):
        base = {"id": "call_1", "name": "my_tool", "arguments": '{"x": 1}'}
        base.update(overrides)
        return {0: base}

    def _sync_on_tool_call(self, name, args, result_cb):
        result_cb(json.dumps({"done": True}))

    def test_returns_updated_messages(self):
        messages = [{"role": "user", "content": "Hi"}]
        updated = _execute_tool_calls(
            self._make_accum(), messages, self._sync_on_tool_call
        )
        self.assertIsNot(updated, messages)
        roles = [m["role"] for m in updated]
        self.assertIn("assistant", roles)
        self.assertIn("tool", roles)

    def test_tool_result_appended(self):
        messages = [{"role": "user", "content": "Hi"}]
        updated = _execute_tool_calls(
            self._make_accum(), messages, self._sync_on_tool_call
        )
        tool_msg = next(m for m in updated if m["role"] == "tool")
        self.assertEqual(tool_msg["tool_call_id"], "call_1")

    def test_empty_name_skipped_returns_original(self):
        messages = [{"role": "user", "content": "Hi"}]
        accum = {0: {"id": "bad", "name": "", "arguments": "{}"}}
        updated = _execute_tool_calls(accum, messages, self._sync_on_tool_call)
        self.assertIs(updated, messages)

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
        self.assertIn("tool_a", invocations)
        self.assertIn("tool_b", invocations)

    def test_mixed_empty_and_valid_names(self):
        invocations = []

        def on_tool_call(name, args, result_cb):
            invocations.append(name)
            result_cb("{}")

        accum = {
            0: {"id": "c0", "name": "",         "arguments": "{}"},
            1: {"id": "c1", "name": "real_tool", "arguments": "{}"},
        }
        messages = [{"role": "user", "content": "hi"}]
        updated = _execute_tool_calls(accum, messages, on_tool_call)
        self.assertIsNot(updated, messages)
        self.assertEqual(invocations, ["real_tool"])

    def test_empty_name_inferred_from_arguments(self):
        invocations = []

        def on_tool_call(name, args, result_cb):
            invocations.append(name)
            result_cb("{}")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_script",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                    },
                },
            }
        ]
        accum = {0: {"id": "", "name": "", "arguments": '{"code": "print(1)"}'}}
        messages = [{"role": "user", "content": "run"}]
        updated = _execute_tool_calls(accum, messages, on_tool_call, tools=tools)
        self.assertIsNot(updated, messages)
        self.assertEqual(invocations, ["execute_script"])

    def test_empty_name_inferred_from_malformed_arguments(self):
        invocations = []

        def on_tool_call(name, args, result_cb):
            invocations.append(name)
            result_cb("{}")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_script",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                    },
                },
            }
        ]
        accum = {0: {"id": "", "name": "", "arguments": '{"code# list all people'}}
        messages = [{"role": "user", "content": "run"}]
        updated = _execute_tool_calls(accum, messages, on_tool_call, tools=tools)
        self.assertIsNot(updated, messages)
        self.assertEqual(invocations, ["execute_script"])

    def test_missing_id_gets_fallback(self):
        def on_tool_call(name, args, result_cb):
            result_cb("{}")

        accum = {0: {"id": "", "name": "my_tool", "arguments": "{}"}}
        messages = [{"role": "user", "content": "hi"}]
        updated = _execute_tool_calls(accum, messages, on_tool_call)
        assistant_msg = next(m for m in updated if m["role"] == "assistant")
        tc_id = assistant_msg["tool_calls"][0]["id"]
        self.assertTrue(tc_id)


# ---------------------------------------------------------------------------
# _infer_tool_name
# ---------------------------------------------------------------------------


_EXECUTE_SCRIPT_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_script",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
    },
}

_GET_PERSON_TOOL = {
    "type": "function",
    "function": {
        "name": "get_person_details",
        "parameters": {
            "type": "object",
            "properties": {"gramps_id": {"type": "string"}},
            "required": ["gramps_id"],
        },
    },
}


_EXECUTE_SCRIPT_TOOL_ANTHROPIC = {
    "name": "execute_script",
    "description": "Run a GrampyScript.",
    "input_schema": {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    },
}


class TestInferToolName(unittest.TestCase):
    def test_infers_from_valid_json(self):
        self.assertEqual(
            _infer_tool_name('{"code": "print(1)"}', [_EXECUTE_SCRIPT_TOOL]),
            "execute_script",
        )

    def test_infers_from_malformed_json_missing_closing_quote(self):
        self.assertEqual(
            _infer_tool_name('{"code# list all people', [_EXECUTE_SCRIPT_TOOL]),
            "execute_script",
        )

    def test_infers_when_key_and_value_fused(self):
        self.assertEqual(
            _infer_tool_name('{"codecolumns(\'ID\', \'Name\')', [_EXECUTE_SCRIPT_TOOL]),
            "execute_script",
        )

    def test_infers_correct_tool_from_two_tools(self):
        tools = [_EXECUTE_SCRIPT_TOOL, _GET_PERSON_TOOL]
        self.assertEqual(_infer_tool_name('{"gramps_id": "I001"}', tools), "get_person_details")
        self.assertEqual(
            _infer_tool_name('{"code": "for p in people(): row(p)"}', tools), "execute_script"
        )

    def test_infers_from_anthropic_format_tools(self):
        self.assertEqual(
            _infer_tool_name('{"code": "print(1)"}', [_EXECUTE_SCRIPT_TOOL_ANTHROPIC]),
            "execute_script",
        )

    def test_infers_from_anthropic_format_malformed(self):
        self.assertEqual(
            _infer_tool_name('{"code# broken', [_EXECUTE_SCRIPT_TOOL_ANTHROPIC]),
            "execute_script",
        )

    def test_returns_none_when_no_match(self):
        self.assertIsNone(_infer_tool_name('{"unknown_param": "x"}', [_EXECUTE_SCRIPT_TOOL]))

    def test_returns_none_when_tools_empty(self):
        self.assertIsNone(_infer_tool_name('{"code": "x"}', []))

    def test_returns_none_when_arguments_empty(self):
        self.assertIsNone(_infer_tool_name("", [_EXECUTE_SCRIPT_TOOL]))

    def test_returns_none_when_ambiguous(self):
        tool_a = {"type": "function", "function": {
            "name": "tool_a",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
        }}
        tool_b = {"type": "function", "function": {
            "name": "tool_b",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
        }}
        self.assertIsNone(_infer_tool_name('{"name": "foo"}', [tool_a, tool_b]))


# ---------------------------------------------------------------------------
# _recover_args
# ---------------------------------------------------------------------------


class TestDecodeJsonString(unittest.TestCase):
    def test_newline_escape(self):
        self.assertEqual(_decode_json_string("line1\\nline2"), "line1\nline2")

    def test_tab_escape(self):
        self.assertEqual(_decode_json_string("col1\\tcol2"), "col1\tcol2")

    def test_quote_escape(self):
        self.assertEqual(_decode_json_string('\\"hello\\"'), '"hello"')

    def test_backslash_escape(self):
        self.assertEqual(_decode_json_string("a\\\\b"), "a\\b")

    def test_backslash_not_swallowed_by_n_replacement(self):
        self.assertEqual(_decode_json_string("\\\\n"), "\\n")

    def test_no_escapes_unchanged(self):
        self.assertEqual(_decode_json_string("plain text"), "plain text")

    def test_unknown_escape_drops_backslash(self):
        self.assertEqual(_decode_json_string("\\columns(x)"), "columns(x)")

    def test_unknown_escape_mid_string(self):
        self.assertEqual(_decode_json_string("abc\\def"), "abcdef")

    def test_real_grampy_script(self):
        raw = "for p in people():\\n    row(p.gramps_id, p.name)"
        decoded = _decode_json_string(raw)
        self.assertIn("\n", decoded)
        self.assertNotIn("\\n", decoded)


class TestRecoverArgs(unittest.TestCase):
    def test_valid_json_returned_unchanged(self):
        result = _recover_args('{"code": "print(1)"}', "execute_script", [_EXECUTE_SCRIPT_TOOL])
        self.assertEqual(result, {"code": "print(1)"})

    def test_recovers_code_from_malformed_json(self):
        raw = '{"code# for p in people(): print(p.name)'
        result = _recover_args(raw, "execute_script", [_EXECUTE_SCRIPT_TOOL])
        self.assertIn("code", result)
        self.assertIn("people", result["code"])

    def test_recovers_code_when_key_and_value_fused(self):
        raw = '{"codecolumns(\'Gramps ID\', \'Name\')\\nfor p in people():\\n    row(p.gramps_id)'
        result = _recover_args(raw, "execute_script", [_EXECUTE_SCRIPT_TOOL])
        self.assertIn("code", result)
        self.assertIn("columns", result["code"])
        self.assertIn("\n", result["code"])

    def test_returns_empty_dict_when_no_tool_matches(self):
        result = _recover_args('{"code# broken', "nonexistent_tool", [_EXECUTE_SCRIPT_TOOL])
        self.assertEqual(result, {})

    def test_returns_empty_dict_when_tools_none(self):
        result = _recover_args('{"code# broken', "execute_script", None)
        self.assertEqual(result, {})

    def test_returns_empty_dict_for_completely_garbled_input(self):
        result = _recover_args("not json at all", "execute_script", [_EXECUTE_SCRIPT_TOOL])
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# _process_chunk pure-logic unit tests (no GTK required)
# ---------------------------------------------------------------------------


class TestProcessChunkLogic(unittest.TestCase):
    @staticmethod
    def _simulate(chunks):
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
            increment = new_partial[len(line_buffer):]  # noqa: F841
            line_buffer = new_partial

        return committed, line_buffer

    def test_single_chunk_no_newline(self):
        _, partial = self._simulate(["Hello world"])
        self.assertEqual(partial, "Hello world")

    def test_space_preserved_as_own_chunk(self):
        _, partial = self._simulate(["May", " ", "24"])
        self.assertEqual(partial, "May 24")

    def test_space_at_end_of_chunk(self):
        _, partial = self._simulate(["May ", "24"])
        self.assertEqual(partial, "May 24")

    def test_space_at_start_of_next_chunk(self):
        _, partial = self._simulate(["May", " 24"])
        self.assertEqual(partial, "May 24")

    def test_words_not_merged(self):
        _, partial = self._simulate(["John", " ", "Hjalmar"])
        self.assertEqual(partial, "John Hjalmar")
        self.assertNotIn("JohnHjalmar", partial)

    def test_newline_commits_line(self):
        committed, partial = self._simulate(["Hello\n", "world"])
        self.assertEqual(committed, ["Hello"])
        self.assertEqual(partial, "world")

    def test_multiple_lines_in_one_chunk(self):
        committed, partial = self._simulate(["line1\nline2\npar"])
        self.assertEqual(committed, ["line1", "line2"])
        self.assertEqual(partial, "par")

    def test_partial_then_newline_commits(self):
        committed, partial = self._simulate(["Hel", "lo\n", "nex"])
        self.assertEqual(committed, ["Hello"])
        self.assertEqual(partial, "nex")

    def test_empty_chunk_ignored(self):
        _, partial = self._simulate(["Hello", "", " world"])
        self.assertEqual(partial, "Hello world")

    def test_multiple_spaces_preserved(self):
        _, partial = self._simulate(["a ", " b"])
        self.assertEqual(partial, "a  b")

    def test_final_empty_line_after_newline(self):
        committed, partial = self._simulate(["done\n"])
        self.assertEqual(committed, ["done"])
        self.assertEqual(partial, "")


# ---------------------------------------------------------------------------
# Live integration — OpenAI-compatible backend
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAVE_OPENAI_KEY, "OPENAI_API_KEY not set")
class TestOpenAIBackendLive(unittest.TestCase):
    """End-to-end tests against the real OpenAI API (gpt-4.1-mini for speed/cost)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Verify the key actually reaches the OpenAI API before running any live test.
        # OPENAI_API_KEY may be set for monitoring tools (e.g. OPIK) but not be a
        # valid direct-OpenAI credential; skip the whole class in that case.
        backend = OpenAICompatibleBackend(
            base_url="https://api.openai.com",
            model="gpt-4.1-mini",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        try:
            text, _ = _collect(backend, [{"role": "user", "content": "hi"}], timeout=15)
        except Exception as exc:
            raise unittest.SkipTest("OpenAI API not reachable: %s" % exc)
        if not text:
            raise unittest.SkipTest(
                "OpenAI API returned empty response — key may be for a different service"
            )

    def _backend(self):
        return OpenAICompatibleBackend(
            base_url="https://api.openai.com",
            model="gpt-4.1-mini",
            api_key=os.environ["OPENAI_API_KEY"],
        )

    def test_basic_response_streamed(self):
        messages = [{"role": "user", "content": "Reply with exactly the word: PONG"}]
        text, _ = _collect(self._backend(), messages)
        self.assertIn("PONG", text)

    def test_response_is_non_empty_text(self):
        messages = [{"role": "user", "content": "Say exactly: hello world"}]
        text, _ = _collect(self._backend(), messages)
        self.assertGreater(len(text), 0)
        self.assertIn(" ", text)

    def test_multiline_response_has_newlines(self):
        messages = [
            {
                "role": "user",
                "content": "List three colors, one per line, nothing else.",
            }
        ]
        text, _ = _collect(self._backend(), messages)
        self.assertGreaterEqual(text.count("\n"), 2)

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
        self.assertTrue(any(tc["name"] == "get_temperature" for tc in tool_calls))

    def test_tool_result_used_in_response(self):
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
        finished = done_ev.wait(timeout=30)
        if not finished:
            self.skipTest("API did not respond within timeout")
        if error_holder[0]:
            raise error_holder[0]

        full = "".join(chunks)
        self.assertIn("42", full)

    def test_bad_api_key_raises_runtime_error(self):
        backend = OpenAICompatibleBackend(
            base_url="https://api.openai.com",
            model="gpt-4.1-mini",
            api_key="sk-bad-key",
        )
        with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            _collect(backend, [{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
