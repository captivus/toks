# toks

[![PyPI version](https://img.shields.io/pypi/v/toks)](https://pypi.org/project/toks/)
[![Python versions](https://img.shields.io/pypi/pyversions/toks)](https://pypi.org/project/toks/)
[![License](https://img.shields.io/pypi/l/toks)](https://github.com/captivus/toks/blob/master/LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](https://pypi.org/project/toks/)
[![CI](https://img.shields.io/github/actions/workflow/status/captivus/toks/ci.yml?branch=master&label=CI)](https://github.com/captivus/toks/actions)
[![Downloads](https://img.shields.io/pypi/dm/toks)](https://pypi.org/project/toks/)

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
toks src/ --for gemini --glob "*.py"

# Quiet mode (just the number)
toks README.md --for openai -q

# Pipe from stdin
cat file.py | toks - --for claude
```

### Output

```
Provider: gemini (gemini-2.5-flash)

File                    Tokens   Agent     Web     API
src/                   [4,812]    2.4%    2.4%    0.5%
├── main.py              1,203    0.6%    0.6%    0.1%
├── config.py              892    0.4%    0.4%   <0.1%
└── utils/             [2,717]    1.4%    1.4%    0.3%
    ├── parser.py        1,456    0.7%    0.7%    0.1%
    └── helpers.py       1,261    0.6%    0.6%    0.1%

Total: 4,812 tokens
  Agent (200K):   2.4%
  Web (200K):     2.4%
  API (1M):       0.5%
```

Three percentage columns show context window usage for each provider's interfaces: coding agent, web chat, and API.

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
