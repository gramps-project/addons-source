# ChatWithTree

ChatWithTree is a Gramplet Addon for Gramps.

The sources adhere to the Gramps GNU License - check the file headers for details.

## Explanation of the ChatWithTree Gramplet

The idea is to have an addon that uses Large Language Models (LLMs) to have a chat with your own genealogy tree. The Addon serves a few tools to interact with the genealogy tree database and uses
the [Python LiteLLM SDK](https://docs.litellm.ai/) to interact with either a local running LLM or
remote ones.

For running local LLMs you could run an instance of [Ollama](https://ollama.com/blog/tool-support) or
you can use the stronger remote cloud LLMs, for exampe via OpenRouter, Anthrophic, MoonShotAI or any other, as long as they support the Python LiteLLM SDK.

## Short introduction

type `/help` in the chat to get rudimentary help

TODO: Update documentation and create online documentation at Gramps Project websit

### Development documentation

`ChatWithTree.py` — The gramplet UI class for Gramps that embeds the chat panel, connects signals, and manages UI updates while interacting with the chat service.

`AsyncChatService.py` — Asynchronous service layer that orchestrates streaming chat interactions and emits incremental responses for UI consumption.

`chatwithllm.py` — Core chat logic defining an abstract IChatLogic interface and a ChatWithLLM implementation that talks to an LLM, including yield types for partial results and support for tool/function calling.

`ChatWithTree.gpr.py` — Gramps plugin registration file providing metadata and wiring to load the ChatWithTree gramplet.

`ChatWithTreeBot.py` — A chat logic implementation tailored for genealogy use that integrates with a Gramps database to answer questions about the user’s tree by implementing tools to interact with Gramps.

`.markdownlint.yaml` — Configuration for markdown linting rules used in this project.

`.pre-commit-config.yaml` — Pre-commit hook configuration (e.g., formatting, linting) to maintain code quality.

To execute run `pre-commit run -a` in the `/ChatWithTree` folder.
