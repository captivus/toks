# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-03-24

### Added

- Token counting via provider REST APIs (Claude, OpenAI, Gemini, Grok)
- Tree-style output with context window percentages (Agent, Web, API)
- Interactive setup wizard with API key validation
- Model registry from LiteLLM (cached locally)
- Support for text, images, PDFs, and Office documents (provider-dependent)
- Grok image token counting using local tiling formula (no API call)
- Async concurrent processing with semaphore, exponential backoff, and circuit breaker
- Gitignore-aware file scanning with glob filtering
- Quiet mode (`-q`) and summary mode (`--summary`)
- Stdin support (`toks - --for claude`)
- `ct` command alias
