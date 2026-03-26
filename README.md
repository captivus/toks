# toks

[![PyPI version](https://img.shields.io/pypi/v/toks)](https://pypi.org/project/toks/)
[![Python versions](https://img.shields.io/pypi/pyversions/toks)](https://pypi.org/project/toks/)
[![License](https://img.shields.io/pypi/l/toks?cacheSeconds=3600)](https://github.com/captivus/toks/blob/master/LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](https://pypi.org/project/toks/)
[![CI](https://img.shields.io/github/actions/workflow/status/captivus/toks/ci.yml?branch=master&label=CI)](https://github.com/captivus/toks/actions)
[![Downloads](https://img.shields.io/pypi/dm/toks?cacheSeconds=3600)](https://pypi.org/project/toks/)

Count tokens for files and directories across LLM providers. See how much of a model's context window your content will consume before you spend the tokens.

## Installation

```bash
pip install toks
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install toks
```

The `ct` shorthand alias is also available — `ct src/` is equivalent to `toks src/`.

## Quick Start

### 1. Configure your providers

```bash
toks setup
```

The interactive wizard walks you through selecting providers, entering API keys, and choosing models.

### 2. Count tokens

```bash
# Single file
toks src/main.py --for claude

# Entire directory with glob filter
toks src/ --for claude --glob "*.py"

# Quiet mode (just the number)
toks README.md --for claude -q

# Pipe from stdin
cat file.py | toks - --for claude
```

### Output

```
Provider: claude (claude-opus-4-6)

File                   Tokens  Agent    Web    API
toks/                [17,911]   1.8%   9.0%   1.8%
├── providers/        [4,174]   0.4%   2.1%   0.4%
│   ├── __init__.py       324  <0.1%   0.2%  <0.1%
│   ├── base.py           474  <0.1%   0.2%  <0.1%
│   ├── claude.py         600  <0.1%   0.3%  <0.1%
│   ├── gemini.py         643  <0.1%   0.3%  <0.1%
│   ├── grok.py         1,315   0.1%   0.7%   0.1%
│   └── openai.py         818  <0.1%   0.4%  <0.1%
├── __init__.py            33  <0.1%  <0.1%  <0.1%
├── __main__.py            28  <0.1%  <0.1%  <0.1%
├── cli.py              3,188   0.3%   1.6%   0.3%
├── config.py           1,338   0.1%   0.7%   0.1%
├── output.py           2,260   0.2%   1.1%   0.2%
├── registry.py           978  <0.1%   0.5%  <0.1%
├── runner.py           1,146   0.1%   0.6%   0.1%
├── scanner.py          1,318   0.1%   0.7%   0.1%
└── setup.py            3,448   0.3%   1.7%   0.3%

Total: 17,911 tokens
  Agent (1M):  1.8%
  Web (200K):    9.0%
  API (1M):    1.8%
```

Three percentage columns show context window usage for each provider's interfaces: coding agent, web chat, and API. The Agent and Web columns populate when you configure your plan and coding agent model via `toks setup`.

## Supported Providers

| Provider | Text | Images | PDF | Office Docs |
|----------|------|--------|-----|-------------|
| Claude (Anthropic) | Yes | JPEG, PNG, GIF, WebP | Yes | No |
| OpenAI | Yes | JPEG, PNG, GIF, WebP | Yes | DOCX, XLSX, PPTX |
| Gemini (Google) | Yes | JPEG, PNG, GIF, WebP + more | Yes | No |
| Grok (xAI) | Yes | JPEG, PNG (local calc) | No | No |

All token counting is done via each provider's REST API. No local tokenizer libraries are needed.

## Configuration

Config files live in `~/.config/toks/`:

- `config.toml` -- provider settings, default model, plan tier
- `.env` -- API keys

Re-run `toks setup` at any time to update your configuration.

## Commands

```bash
toks <target> [options]    # Count tokens (default command)
toks setup                 # Interactive configuration wizard
toks models --refresh      # List known models / refresh registry
```

`ct` can be used anywhere in place of `toks`.

## Options

| Flag | Description |
|------|-------------|
| `--for <provider>` | Provider to use (claude, openai, gemini, grok) |
| `--model <model>` | Specific model (provider inferred from registry) |
| `--glob <pattern>` | Filter files by glob pattern |
| `--max-size <size>` | Exclude files larger than size (default: 50MB) |
| `--depth <n>` | Limit directory recursion depth (0 = target dir only) |
| `-q` / `--quiet` | Output only the total token count |
| `--summary` | Totals without the tree |
| `--no-progress` | Suppress progress bar |
| `--concurrency <n>` | Concurrent API requests (default: 10) |
| `--retries <n>` | Retry count for transient errors (default: 3) |

## Documentation

- [Technical Documentation](docs/technical.md) -- architecture, module details, tutorials
- [Feature Specification](docs/spec.md) -- complete design specification

## License

[MIT](LICENSE)
