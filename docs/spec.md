# toks Feature Specification

## Key Design Decisions

1. **Single provider per run** — no multi-provider comparison in v1
2. **`--for` specifies a provider** — `--for claude`, `--for openai`, `--for gemini`, `--for grok`
3. **Three-column context window percentages** — Agent, Web, API columns in output
4. **LiteLLM model registry for context windows** — plain JSON from GitHub, no library dependency
5. **`httpx` instead of provider SDKs** — all four endpoints are simple REST POSTs (~20 MB vs ~125 MB)
6. **`asyncio` for concurrency** — `asyncio.Semaphore` for rate limit control
7. **API-only tokenization** — no local/offline tokenizers
8. **`--convert` and `--estimate` deferred to v1.1**
9. **Real API tests only** — no mocks

---

## 1. Overview & Purpose

A command-line application that counts the tokens a given file or directory of files would consume when loaded into a large language model. It supports multiple model providers and reports accurate token counts using official tokenization APIs.

LLMs have finite context windows. Before loading files into a model — whether for code review, document analysis, or any other task — users need to understand how much of that context window the content will consume. This tool answers "how many tokens will this cost me?" before you spend them.

### Target Users

Developers and power users who work with LLM APIs and need to plan their context window usage — especially when working with large codebases or document sets.

### Acceptance Criteria

- Running `toks --version` prints the version and exits 0
- Running `toks` with no arguments prints usage help and exits 0

## 2. Supported Models & Providers

The tool supports four providers at launch. Model names and context window sizes change frequently, so these are maintained as a data structure in code rather than hardcoded throughout the application.

### Anthropic (Claude)

#### Coding Agent (Claude Code)

| Model | Context Window | Notes |
|-------|---------------|-------|
| claude-sonnet-4-6 | 200K (1M beta) | Default |
| claude-opus-4-6 | 200K (1M beta) | |
| claude-haiku-4-5 | 200K | |

#### Web Chat (claude.ai)

| Model | Context Window | Notes |
|-------|---------------|-------|
| claude-sonnet-4-6 | 200K | Default for Free and Pro |
| claude-opus-4-6 | 200K | Pro and above only |
| claude-haiku-4-5 | 200K | |

Enterprise plans get 400-500K context windows. 1M beta available for eligible organizations.

#### API

| Model | Context Window |
|-------|---------------|
| claude-opus-4-6 | 200K (1M beta) |
| claude-sonnet-4-6 | 200K (1M beta) |
| claude-haiku-4-5 | 200K |

---

### OpenAI (GPT)

#### Coding Agent (Codex)

| Model | Context Window | Notes |
|-------|---------------|-------|
| gpt-5.4 | 272K (up to 1M) | Default |
| gpt-5.3-codex | 400K | |
| gpt-5.2-codex | 400K | |
| gpt-5.1-codex-max | — | |
| gpt-5.1-codex-mini | — | |
| codex-mini | 200K | Based on o4-mini |

#### Web Chat (ChatGPT)

| Model | Context Window | Notes |
|-------|---------------|-------|
| gpt-5.3-instant | ~8K (Free), ~32K (Plus), ~128K (Pro) | Default |
| gpt-5.4-thinking | ~128K (Pro) | Paid tiers only |
| gpt-5.4-pro | ~128K | Pro/Business/Enterprise only |

Free users fall back to gpt-5.3-mini after hitting message caps.

#### API

| Model | Context Window |
|-------|---------------|
| gpt-5.4 | 1M |
| gpt-5.4-pro | 1M |

---

### Google (Gemini)

#### Coding Agent (Gemini CLI)

| Model | Context Window | Notes |
|-------|---------------|-------|
| Auto (gemini-3.1-pro / gemini-3-flash) | 1M | Default (routes by complexity) |
| gemini-3.1-pro-preview | 1M | |
| gemini-3-flash-preview | 1M | |
| gemini-2.5-pro | 1M | |
| gemini-2.5-flash | 1M | |

#### Web Chat (gemini.google.com)

| Model | Context Window | Notes |
|-------|---------------|-------|
| gemini-3-flash | ~32K (Free), 1M (AI Pro/Ultra) | Default |
| gemini-3.1-pro | 1M | AI Pro/Ultra only |

#### API

| Model | Context Window |
|-------|---------------|
| gemini-3.1-pro | 1M (2M via Vertex AI) |
| gemini-3-flash | 1M |
| gemini-2.5-pro | 1M |
| gemini-2.5-flash | 1M |

---

### xAI (Grok)

#### Coding Agent

No dedicated coding agent.

#### Web Chat (grok.com)

| Model | Context Window | Notes |
|-------|---------------|-------|
| grok-4.1 | 256K | Default |
| grok-4.20-beta | up to 2.5M | Must be manually selected |
| grok-4-heavy | — | SuperGrok Heavy ($300/mo) only |

Free users limited to ~10 prompts per 2-hour window.

#### API

| Model | Context Window |
|-------|---------------|
| grok-4.1 | 256K |
| grok-4.1-fast | 2M |
| grok-3 | 128K |

### Model Registry

Context window sizes and model metadata are sourced from the [LiteLLM model registry](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) — a plain JSON file covering 2,600+ models across 140+ providers, updated multiple times daily. No dependency on the LiteLLM library itself.

The fields we depend on per model entry:
- `max_input_tokens` — context window size
- `max_output_tokens` — max output length
- `litellm_provider` — provider identifier (e.g., `anthropic`, `openai`, `vertex_ai-language-models`)

The JSON is cached locally at `~/.config/toks/models.json`.

- The cache is populated on first run or during `toks setup`
- `toks models` lists all known models for the configured provider(s)
- `toks models --refresh` updates the cached registry from GitHub
- When a user specifies a model not in the registry, the tool errors with a helpful message suggesting `--refresh` or checking the model name
- The registry also provides provider identification, enabling `--model` to infer which provider API to call

### Acceptance Criteria

- `toks models` lists models with their context windows for each configured provider
- `toks models --refresh` fetches the latest LiteLLM registry JSON and caches it locally
- Specifying `--model claude-sonnet-4-6` correctly identifies Anthropic as the provider
- Specifying `--model nonexistent-model-xyz` produces a helpful error suggesting `--refresh`

## 3. Tokenization Strategy

### Approach

- API-only, using each provider's official token counting endpoints
- No local/offline tokenization (if you can't reach the API, you can't use the model)
- One API call per file (no provider supports batching with per-item breakdown)

### Provider Abstraction Layer

Custom thin wrapper using `httpx` (async) — no provider SDKs, no third-party unified LLM libraries. All four providers expose their token counting as simple REST endpoints with JSON bodies and API key auth. Each provider is implemented as a small module (~30-50 lines). New providers can be added by implementing the common interface.

**Common interface**: Each provider implements a method that accepts file content (as bytes), a MIME type, and a model identifier, and returns a `TokenCountResult`. Providers raise `UnsupportedFileTypeError` for file types they cannot handle.

### Core Data Structures

```python
@dataclass
class TokenCountResult:
    total_tokens: int
    model: str                                  # the model used for counting
    modality_breakdown: dict[str, int] | None   # e.g. {"TEXT": 400, "IMAGE": 258}; only Gemini provides this

@dataclass
class FileResult:
    path: Path
    mime_type: str | None                       # detected MIME type
    file_size: int                              # size in bytes
    status: Literal["pending", "success", "failed", "skipped"]
    token_count: TokenCountResult | None
    error: str | None
    skip_reason: str | None

@dataclass
class ModelInfo:
    model_id: str
    provider: str
    max_input_tokens: int
    max_output_tokens: int | None

@dataclass
class Config:
    default_provider: str
    providers: dict[str, ProviderConfig]        # keyed by provider name

@dataclass
class ProviderConfig:
    api_key: str
    model: str                                  # default model for API calls
    agent_model: str | None                     # model used in coding agent (None if no agent)
    plan: str
    has_coding_agent: bool

@dataclass
class RunResult:
    results: list[FileResult]
    tree: dict                                  # nested directory structure for rendering
    provider: str
    model: str

class TokenCountProvider(Protocol):
    provider_name: str
    def supported_mime_types(self) -> set[str]: ...
    async def count_tokens(self, *, content: bytes, mime_type: str, model: str) -> TokenCountResult: ...
```

The `supported_mime_types()` method lets the core decide before making an API call whether to skip the file — rather than discovering unsupported types as errors.

### File Type Detection and Content Packaging

The tool detects each file's MIME type before passing it to a provider. Each provider implementation is responsible for packaging the content into the JSON payload its API expects. Providers differ in how they accept different file types:

| File Type | Claude | OpenAI | Gemini | Grok |
|-----------|--------|--------|--------|------|
| Text/code | `messages[].content[]` with `type: "text"` | `input` as string | `contents[].parts[]` with `text` field | `text` field (string) |
| Image (JPEG, PNG) | `type: "image"` with base64 `source` | `type: "input_image"` with base64 data URL | `inline_data` with `mime_type` + base64 | Local calculation (tiling formula) |
| Image (GIF, WebP) | `type: "image"` with base64 `source` | `type: "input_image"` with base64 data URL | `inline_data` with `mime_type` + base64 | Not supported |
| Image (HEIC, BMP, TIFF, SVG) | Not supported | Not supported | `inline_data` with `mime_type` + base64 | Not supported |
| PDF | `type: "document"` with base64 `source` | File input (base64) | `inline_data` with `mime_type` + base64 | Not supported |
| Office docs (docx, xlsx, pptx) | Not supported | File input (base64) | Not supported | Not supported |

MIME type detection and file reading are handled by the tool's core. Content packaging (building the right JSON structure, encoding to base64 where needed, etc.) is handled by each provider implementation.

### Provider REST Endpoint Details

All endpoints are called via `httpx` (async). No provider SDKs are used.

#### Claude

- **Endpoint**: `POST https://api.anthropic.com/v1/messages/count_tokens`
- **Auth**: `x-api-key` header + `anthropic-version: 2023-06-01` header. This is the only stable API version (since 2023). Verify against [Anthropic's versioning docs](https://platform.claude.com/docs/en/api/versioning) when updating the tool.
- **Input**: JSON body with `model` and `messages` (same structure as Messages API). Content must be wrapped in a messages structure — cannot pass raw text directly. Supports text, images (base64 or URL: JPEG, PNG, GIF, WebP), and PDFs (document blocks, base64 or URL).
- **Response**: `{ "input_tokens": <int> }`. No per-item or per-modality breakdown.
- **Rate limits**: 100-8,000 RPM depending on usage tier. Free to call. Separate from message creation limits.
- **Caveat**: Returns an estimate — actual usage may differ slightly. May include system-added tokens (not billed).

#### OpenAI

- **Endpoint**: `POST https://api.openai.com/v1/responses/input_tokens`
- **Auth**: `Authorization: Bearer` header
- **Input**: JSON body with `model` and `input` (same structure as Responses API). Accepts raw text strings or message arrays. Supports images (URL or base64 data URL; with `detail` parameter affecting token count), PDFs, docx, spreadsheets, code files (via URL or inline base64).
- **Response**: `{ "object": "response.input_tokens", "input_tokens": <int> }`. No breakdown.
- **Rate limits**: Not separately documented; likely shares Responses API limits.
- **Caveat**: PDFs extract both text AND page images, so token counts can be higher than expected. 50 MB per file limit.

#### Gemini

- **Endpoint**: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:countTokens?key={api_key}`
- **Auth**: API key as query parameter
- **Input**: JSON body with `contents` array of parts. Very flexible — accepts text strings, inline bytes with MIME type. Supports images (JPEG, PNG, WebP, HEIC, GIF, BMP, TIFF, SVG), video, audio, and PDFs.
- **Response**: `{ "totalTokens": <int>, "promptTokensDetails": [{ "modality": "TEXT", "tokenCount": <int> }, ...] }`. Includes per-modality breakdown.
- **Rate limits**: 3,000 RPM. Free to call.
- **Caveat**: Files uploaded via Files API must reach ACTIVE state before counting.

#### Grok

- **Endpoint**: `POST https://api.x.ai/v1/tokenize-text`
- **Auth**: `Authorization: Bearer` header
- **Input**: JSON body with `model` and `text` (string). Text only — no multimodal tokenization endpoint exists.
- **Response**: `{ "token_ids": [{ "token_id": <int>, "string_token": <str>, "token_bytes": [<int>...] }, ...] }`. Count is `len(token_ids)`.
- **Rate limits**: Not published; tier-based, visible in xAI Console.
- **Caveat**: Explicitly underestimates actual usage because "inference endpoints automatically add pre-defined tokens."
- **Image token calculation**: Grok supports images (JPEG, PNG) in the chat/responses API, but the tokenize endpoint does not. However, xAI documents a deterministic tiling formula for image tokens ([source](https://docs.x.ai/docs/key-information/consumption-and-rate-limits)): images are broken into 448x448 pixel tiles, each tile consumes 256 tokens, plus one extra tile is always added. Formula: `(number_of_tiles + 1) x 256`. Maximum: 6 tiles (1,792 tokens). This tool calculates image tokens locally using this formula — no API call needed.
- **PDF limitation**: PDFs are handled by xAI's server-side `attachment_search` tool via the Files API, not through tokenization. There is no way to pre-count tokens for PDFs ([source](https://docs.x.ai/developers/files)). PDFs remain unsupported for Grok token counting.

### Unsupported File Type Handling

When a file's type is not supported by the selected provider, it is skipped and reported in the output (e.g., "3 files skipped: docx not supported by Claude").

### Known Limitations

- **Accuracy varies**: Claude and Gemini describe their counts as estimates. OpenAI's is deterministic for the same input. Grok explicitly underestimates because "inference endpoints automatically add pre-defined tokens."
- **No per-file breakdown from any provider**: When counting a directory, the tool must make one API call per file to get individual counts.

### Acceptance Criteria

- Counting a known text file via Claude returns a positive integer token count
- Counting the same text file via OpenAI returns a positive integer token count
- Counting the same text file via Gemini returns a positive integer token count and a modality breakdown
- Counting the same text file via Grok returns a positive integer token count
- Counting a JPEG image via Claude returns a positive integer token count
- Counting a JPEG image via Grok returns a positive token count calculated from image dimensions
- Counting a PDF via Claude returns a positive integer token count
- Counting a docx file via Claude reports it as unsupported
- Counting a docx file via OpenAI returns a positive integer token count
- Each provider module is under 50 lines of code
- Adding a hypothetical fifth provider requires only implementing the `TokenCountProvider` protocol

## 4. CLI Interface

### Installation

Installs as `toks` with a short alias `ct`.

### Command Syntax

```
toks <target> [options]
```

Where `<target>` is a file path, directory path, or `-` for stdin.

Counting tokens is the default action — no subcommand required. Non-counting operations use subcommands:

- `toks setup` — interactive configuration workflow (see section 9)
- `toks models` — list all known models and their context windows

### Target Modes

- **Single file**: `toks ./main.py`
- **Directory**: `toks ./src` (recursive by default)
- **stdin**: `cat file.py | toks -` or piped input

### Provider Selection

Single provider per invocation. The tool uses the configured default model for the selected provider to make the API call.

- **No flag**: Uses the default provider and model configured during `setup`
- **`--for <provider>`**: Specifies the provider (e.g., `--for claude`, `--for openai`, `--for gemini`, `--for grok`). Uses the configured default model for that provider.
- **`--model <model-id>`**: Overrides to a specific model. Provider is inferred from the model name using the LiteLLM model registry. If the model is not in the registry, the tool errors with: "Model 'xyz' not found in registry. Use `--for <provider>` to specify the provider, or run `toks models --refresh`."
- **`--for` and `--model` together**: `--for` is ignored — `--model` is more specific and wins

### Filtering Flags

- **`--glob <pattern>`**: Filter files by glob pattern (e.g., `--glob "*.py"`, `--glob "*.{py,ts}"`)
- **`--max-size <size>`**: Exclude files larger than the given size (e.g., `--max-size 10MB`). Accepts KB, MB, GB (base 10). Default: 50MB.
- **`--no-gitignore`**: Include files that would normally be skipped by `.gitignore` rules
- **`--include-binary`**: Include binary files (excluded by default)
- **`--depth <n>`**: Limit directory recursion depth (e.g., `--depth 0` counts only files in the target directory, `--depth 1` includes one level of subdirectories). Omitting the flag recurses without limit.

### Behavior Flags

- **`--concurrency <n>`**: Override the default number of concurrent API requests (default: 10)
- **`--retries <n>`**: Override the default retry count for transient errors (default: 3)
- **`--mime-type <type>`**: Override MIME type detection (useful with stdin, e.g., `--mime-type image/png`)

### Output Flags

- **Default**: Tree-style display with per-file token counts and summary
- **`--quiet` / `-q`**: Output only the total token count (useful for scripting)
- **`--summary`**: Output only the totals, no tree
- **`--no-progress`**: Suppress progress bar (useful for AI agent tool use)

### Acceptance Criteria

- `toks ./file.py --for claude` counts tokens and exits 0
- `toks ./src/ --for claude` recursively counts all files and exits 0
- `cat file.py | toks - --for claude` reads from stdin and returns a count
- `toks ./src/ --for claude --glob "*.py"` only counts Python files
- `toks ./src/ --for claude --max-size 1KB` skips files larger than 1KB
- `toks ./src/ --for claude --no-gitignore` includes files that would normally be gitignored
- `toks ./file.py --model claude-sonnet-4-6` infers provider and counts correctly
- `toks ./file.py --for claude --model gpt-4o-mini` ignores `--for` and uses OpenAI
- `toks ./file.py` with no flags uses the default provider from config
- `toks ./file.py --for claude` without a configured API key exits 1 with a helpful error
- `toks setup` launches the interactive configuration workflow
- `toks ./src/ --for claude --depth 0` only counts files directly in `./src/`
- `toks ./src/ --for claude --depth 1` counts files in `./src/` and one level of subdirectories
- Both `toks` and `ct` invoke the tool

## 5. Output Format

### Default (Tree View)

Single provider per run. Three columns show context window percentage for each operating mode (Agent, Web, API):

- **Agent column**: Uses the configured coding agent model's context window from the LiteLLM registry (configured separately during setup). Shows "N/A" for providers without a coding agent (Grok).
- **Web column**: Uses the plan-tier mapping from the user's configuration (see section 9).
- **API column**: Uses the configured default model's context window from the LiteLLM registry.

```
                                                Agent    Web     API
./src/                          [4,812 tokens]   2.4%   2.4%    0.5%
├── main.py                      1,203 tokens    0.6%   0.6%    0.1%
├── utils/                      [2,105 tokens]   1.1%   1.1%    0.2%
│   ├── helpers.py               1,450 tokens    0.7%   0.7%    0.1%
│   └── config.py                  655 tokens    0.3%   0.3%    0.1%
└── tests/                      [1,504 tokens]   0.8%   0.8%    0.2%
    ├── test_main.py               890 tokens    0.4%   0.4%    0.1%
    └── test_helpers.py            614 tokens    0.3%   0.3%    0.1%

2 directories, 5 files

Total: 4,812 tokens
  Agent (200K):   2.4%
  Web (200K):     2.4%
  API (1M):       0.5%
```

### Quiet Mode (`--quiet`)

```
4812
```

### Summary Mode (`--summary`)

```
Total: 4,812 tokens
  Agent (200K):   2.4%
  Web (200K):     2.4%
  API (1M):       0.5%
```

### Skipped Files

Unsupported or inaccessible files are reported after the tree:

```
Skipped (3 files):
  report.docx — docx not supported by Claude
  photo.heic — HEIC not supported by Claude
  diagram.png — image token counting not supported by Grok
```

### Acceptance Criteria

- Default output shows a tree with token counts and three percentage columns (Agent, Web, API)
- Directory subtotals are shown in brackets
- A directory and file count is shown between the tree and the totals
- Summary at the bottom shows totals per mode with context window sizes
- `--quiet` outputs only the integer token count, no tree, no progress
- `--summary` outputs only the totals per mode, no tree
- Skipped files are listed after the tree with reasons
- For Grok, the Agent column shows "N/A"
- Output is rendered using `rich`

## 6. File Handling

### Directory Traversal

- Recursive by default when a directory is given as the target
- The `.git` directory is always excluded from traversal
- Does not follow symlinks into directories (avoids infinite loops). Symlinked files are still counted.
- Respects `.gitignore` rules by default: walks up from the target directory looking for a `.git` directory to find the repo root, then applies all nested `.gitignore` files from root down (matching git's behavior). If no `.git` directory is found, no `.gitignore` rules are applied. Does not include global gitignore (`~/.config/git/ignore`).
- `--no-gitignore` flag disables this and includes all files
- If no files match after filtering, outputs "No files matched" and exits 0

### Filtering

Applied before any API calls are made:

- **Glob pattern** (`--glob "*.py"`): Only include files matching the pattern
- **File size** (`--max-size 10MB`): Exclude files larger than the given size. Accepts KB, MB, GB (base 10). Default: 50MB.
- Multiple filters can be combined and are applied as AND conditions

### stdin

When reading from stdin (`toks -`), the content is assumed to be plain text. Use `--mime-type` to override (e.g., `--mime-type image/png`).

### File Type Detection

The tool detects each file's MIME type using stdlib `mimetypes` (extension-based) to determine how to handle it:

- **Text files** (`text/*`; source code, plain text, markdown, CSV, etc.): Read as text, sent to provider's text tokenization
- **Image files** (`image/*`; JPEG, PNG, GIF, WebP, HEIC, etc.): Sent as binary with MIME type to providers that support image tokenization
- **PDF files** (`application/pdf`): Sent as binary with MIME type to providers that support PDF tokenization
- **Office documents** (`application/vnd.openxmlformats*`; docx, xlsx, pptx): Sent to providers that support them (OpenAI, Gemini); flagged as unsupported for others
- **Binary files** (anything not matching the above categories): Excluded by default. `--include-binary` overrides this, though most providers will not be able to tokenize them
- **Unknown MIME type** (extension not recognized by `mimetypes`): Defaults to `text/plain`. Common unrecognized extensions include `.tsx`, `.vue`, `.svelte`, `.rs`, etc.

**Magic byte validation**: Before sending binary files (images, PDFs) to the API, the tool validates that the file content starts with the expected magic bytes for its MIME type (e.g., JPEG starts with FF D8 FF, PNG starts with 89 50 4E 47, PDF starts with %PDF). Files that fail this check are skipped.

### Unsupported File Handling

When a file's type is not supported by the selected provider, it is skipped and reported in the "Skipped files" section of the output.

### Acceptance Criteria

- A directory with a `.gitignore` that excludes `*.log` skips `.log` files by default
- `--no-gitignore` includes those `.log` files
- Nested `.gitignore` files are respected (e.g., `src/.gitignore` applies within `src/`)
- Symlinked directories are not followed
- Symlinked files are counted normally
- Binary files (e.g., `.exe`, `.zip`) are excluded by default
- `--include-binary` includes binary files (which will likely be skipped as unsupported by the provider)
- Files over 50MB are skipped by default
- `--max-size 1MB` skips files over 1MB
- An empty directory outputs "No files matched" and exits 0
- A directory where all files are filtered out outputs "No files matched" and exits 0
- stdin input is treated as plain text by default
- `--mime-type image/png` with stdin sends content as PNG to the provider

## 7. Performance

### Concurrency

- Uses `asyncio` with `asyncio.Semaphore` for concurrency control
- Default: 10 concurrent API requests
- `--concurrency <n>` flag to override
- On HTTP 429 (rate limit exceeded), exponential backoff: base delay 1 second, 2x multiplier, max delay 60 seconds, random jitter 50-150% of calculated delay (ensures non-zero delay). `Retry-After` header overrides the calculated delay when present.
- Circuit breaker: abort after 10 consecutive failures from a provider, report whatever results were collected

### Progress Indication

- Progress bar shown by default for directory operations (file count and percentage)
- No progress bar for single file operations
- `--no-progress` flag suppresses the progress bar (useful for AI agent tool use)
- `--quiet` flag also suppresses progress output

### Acceptance Criteria

- Counting a directory of 100+ files completes without errors (concurrency works)
- `--concurrency 1` processes files sequentially
- Progress bar appears for directory operations and updates as files complete
- `--no-progress` suppresses the progress bar
- `--quiet` suppresses the progress bar
- No progress bar for single file operations

## 8. Error Handling

### Missing or Invalid API Keys

If the selected provider's API key is not configured, the tool reports the error immediately and exits.

### Partial Failure

Each file is tracked independently with a status (pending, success, failed, skipped). If some files fail during a run:

- Successful results are included in the output as normal
- Failed files are listed after the tree with their error messages
- Other files are not affected by individual failures

### Retry Behavior

- Transient errors (HTTP 429, 500, 502, 503, 504, timeouts) are retried automatically
- Non-transient errors (400, 401, 403) are not retried — they indicate a real problem
- Default: 3 retries per file
- `--retries <n>` flag to override the default
- Failed files go back into the concurrency queue if retries remain; otherwise marked as failed

### Unsupported File Types

Handled as described in section 6 — unsupported files are skipped and reported.

### Inaccessible Files

Files that cannot be read (permissions, broken symlinks, etc.) are reported in the skipped/failed output and do not halt the run.

### Exit Codes

- **0** — success (including partial success where some files failed but results were produced)
- **1** — failure (no results produced — missing API key, all files failed, provider unreachable)
- **2** — usage error (bad arguments, unknown flags, invalid command syntax)

### Acceptance Criteria

- Missing API key for the selected provider exits 1 with a message naming the missing key
- If 3 of 100 files fail with transient errors and retries are exhausted, the 97 successful results are shown plus the 3 failures listed
- Non-transient errors (400, 401, 403) are not retried
- `--retries 0` disables retries
- After 10 consecutive failures, the tool aborts and reports partial results
- Inaccessible files (permissions errors) are reported as skipped, not as fatal errors
- Exit code is 0 when some files succeed
- Exit code is 1 when no files succeed (all failed or missing API key)
- Exit code is 2 for bad arguments (e.g., `toks --invalid-flag`)

## 9. Configuration

### Config File Location

Configuration is stored in `~/.config/toks/`:

- `config.toml` — provider selections, plan tiers, default provider, default model per provider
- `.env` — API keys (using standard env var names)

### Initial Setup Workflow

A guided `toks setup` command that walks the user through:

1. **Which providers do you use?** (multi-select: Claude, OpenAI, Gemini, Grok)
2. **For each selected provider:**
   - Enter your API key (validated by making a minimal token counting call — count tokens for the string `hello` — to confirm both the key and endpoint access)
   - What plan/tier are you on? (simple list per provider — see below)
   - Do you have access to the coding agent? (yes/no)
   - If yes: Which model does your coding agent use? (with sensible defaults: `claude-opus-4-6`, `gpt-4o-mini`, `gemini-2.5-flash`)
   - Which model do you primarily use for the API? (with sensible defaults: `claude-sonnet-4-6`, `gpt-4o-mini`, `gemini-2.5-flash`, `grok-3`)
3. **Set a default provider** for when no `--for` flag is specified

The plan/tier question determines the web chat context window for the "Web" column in output. The coding agent question determines whether the "Agent" column shows a value or "N/A". The model question determines which model is used for API calls and the "API" column context window.

#### Plan Options by Provider

**Claude:** Free, Pro ($20/mo), Max 5x ($100/mo), Max 20x ($200/mo), Team Standard, Team Premium, Enterprise

**OpenAI:** Free, Go ($8/mo), Plus ($20/mo), Pro ($200/mo), Business, Enterprise

**Gemini:** Free, AI Plus ($7.99/mo), AI Pro ($19.99/mo), AI Ultra ($249.99/mo)

**Grok:** Free, X Premium ($8/mo), X Premium+ ($40/mo), SuperGrok ($30/mo), SuperGrok Heavy ($300/mo)

#### Plan-to-Web-Context-Window Mapping

These mappings determine the "Web" column context window percentage:

| Provider | Plan | Web Context Window |
|----------|------|--------------------|
| Claude | Free, Pro, Max, Team Standard, Team Premium | 200K |
| Claude | Enterprise | 500K |
| OpenAI | Free | 16K |
| OpenAI | Go | 32K |
| OpenAI | Plus, Business | 32K |
| OpenAI | Pro, Enterprise | 128K |
| Gemini | Free | 32K |
| Gemini | AI Plus | 128K |
| Gemini | AI Pro, AI Ultra | 1M |
| Grok | Free, X Premium, X Premium+ | 128K |
| Grok | SuperGrok | 128K |
| Grok | SuperGrok Heavy | 256K |

#### Coding Agent Availability

| Provider | Agent Available | Agent Context Window |
|----------|---------------|---------------------|
| Claude | Pro, Max, Team Premium, Enterprise | From LiteLLM registry (per model) |
| OpenAI | Plus, Pro, Business, Enterprise | From LiteLLM registry (per model) |
| Gemini | All tiers (free with Google login) | From LiteLLM registry (per model) |
| Grok | No coding agent | N/A |

### Stored Configuration Schema

`config.toml` example:

```toml
default_provider = "claude"

[providers.claude]
model = "claude-sonnet-4-6"
agent_model = "claude-opus-4-6"
plan = "max_20x"
has_coding_agent = true

[providers.openai]
model = "gpt-4o-mini"
agent_model = "gpt-4o-mini"
plan = "plus"
has_coding_agent = true

[providers.gemini]
model = "gemini-2.5-flash"
agent_model = "gemini-2.5-flash"
plan = "ai_pro"
has_coding_agent = true
```

`.env` example:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
GROK_API_KEY=xai-...
```

### API Key Lookup Order

API keys are resolved in this order: 1) `~/.config/toks/.env`, 2) `.env` in the current directory, 3) environment variables.

### Runtime Overrides

- `--for <provider>` overrides the default provider for a single run
- `--model <model-id>` overrides to a specific model (provider inferred from LiteLLM registry)
- Runtime flags take precedence over stored configuration

### Re-running Setup

`toks setup` can be re-run at any time to update providers, plans, or API keys. It preserves existing values as defaults so the user only needs to change what's different.

### Acceptance Criteria

- `toks setup` creates `~/.config/toks/config.toml` and `~/.config/toks/.env`
- API keys entered during setup are validated with a minimal token counting call
- Invalid API keys are rejected with a helpful error during setup
- After setup, `toks ./file.py` works without any flags (uses default provider and model)
- Re-running setup preserves previously entered values as defaults
- `config.toml` contains provider selections, plan tiers, default model, and default provider
- `.env` contains API keys in the standard env var format
- Changing plan tier in setup changes the Web column context window percentages in output

## 10. Dependencies

Requires Python 3.11+ (for `tomllib` in stdlib).

- **HTTP client**: `httpx` (async, for all provider API calls — no provider SDKs)
- **CLI framework**: `click`
- **Progress bar / output rendering**: `rich` (also handles tree rendering and styled terminal output)
- **Interactive prompts**: `questionary` (multi-select, single-select, password input for the setup wizard)
- **MIME type detection**: stdlib `mimetypes` (extension-based, no system dependency required)
- **Gitignore parsing**: `pathspec`
- **Config file**: `tomllib` (stdlib for reading) + `tomli-w` (for writing)
- **Env file**: `python-dotenv`

## 11. Project Structure

```
src/toks/
    __init__.py
    __main__.py          # entry point for python -m toks
    cli.py               # click app, command definitions, argument parsing
    config.py            # setup wizard, config.toml and .env reading/writing
    setup.py             # Setup wizard: Prompter protocol, model validation, curated models
    registry.py          # LiteLLM JSON fetching, caching, model lookup
    scanner.py           # file discovery, gitignore, filtering, MIME detection
    runner.py            # async orchestrator: concurrency, retries, backoff, circuit breaker
    output.py            # rich tree rendering, summary formatting, quiet/summary modes
    providers/
        __init__.py      # provider registry, lookup by name
        base.py          # Protocol, TokenCountResult, FileResult, ModelInfo, exceptions
        claude.py        # ~30-50 lines
        openai.py        # ~30-50 lines
        gemini.py        # ~30-50 lines
        grok.py          # ~30-50 lines
tests/
    conftest.py          # shared fixtures, pytest markers for providers
    fixtures/
        hello.py
        hello.txt
        image.png
        image.jpg
        document.pdf
        document.docx
        empty.txt
        tree/            # nested directory structure with .gitignore for traversal tests
    test_providers.py
    test_cli.py
    test_provider_matrix.py
    test_preflight.py
    test_e2e_pipeline.py
    test_scanner.py
    test_config.py
    test_registry.py
```

## 12. Testing

### Strategy

All tests use real provider APIs. No mocks. This ensures the tool is validated against actual provider behavior, including payload formatting, authentication, and response parsing.

### Requirements

- API keys for all four providers must be configured to run the full test suite
- Tests can be run for a subset of providers using pytest markers (e.g., `pytest -m claude`)
- Tests are run via `uv run pytest`

### Test Fixtures

A `tests/fixtures/` directory committed to the repo containing known test files:

- `hello.py` — small Python source file (known content for reproducible counts)
- `hello.txt` — plain text file
- `image.png` — small PNG image
- `image.jpg` — small JPEG image
- `document.pdf` — small single-page PDF
- `document.docx` — small Word document
- `empty.txt` — empty file
- `large.txt` — file near or at the 50MB default limit (generated, not committed; created by a test setup fixture)
- A `fixtures/tree/` directory structure with nested subdirectories, a `.gitignore`, and mixed file types for tree/traversal tests

### Test Categories

#### Provider Tests (per provider)

- Count tokens for a known text file and verify a positive integer is returned
- Count tokens for an image file (where supported) and verify a positive integer
- Count tokens for a PDF (where supported) and verify a positive integer
- Verify unsupported file types raise `UnsupportedFileTypeError`
- Verify authentication errors (bad API key) return appropriate errors
- Verify the HTTP request is correctly formatted (right endpoint, headers, body shape)

#### CLI Tests

- `toks ./file.py --for claude` exits 0 and outputs a token count
- `toks ./src/ --for claude` outputs a tree with per-file counts
- `toks - --for claude < file.py` reads from stdin
- `--quiet` outputs only an integer
- `--summary` outputs only the totals
- `--glob "*.py"` filters correctly
- `--max-size 1KB` skips large files
- `--no-gitignore` includes gitignored files
- Bad arguments exit 2
- Missing API key exits 1

#### Output Tests

- Tree output includes Agent, Web, and API percentage columns
- Directory subtotals are calculated correctly
- Skipped files section lists unsupported files with reasons
- Quiet mode outputs only the integer

#### File Handling Tests

- `.gitignore` rules are respected (files matching patterns are skipped)
- Nested `.gitignore` files work correctly
- Symlinked directories are not followed
- Binary files are excluded by default
- Files over 50MB are skipped by default
- Empty directory outputs "No files matched"

#### Error Handling Tests

- Partial failure: some files succeed, some fail — exit 0, both results and errors reported
- All files fail — exit 1
- Retries happen on transient errors (429, 500)
- Retries do not happen on non-transient errors (400, 403)
- Circuit breaker triggers after 10 consecutive failures

#### Configuration Tests

- `toks setup` creates config files in `~/.config/toks/`
- Config is read correctly on subsequent runs
- `--for` and `--model` override config defaults

## 13. Deferred to v1.1

### `--convert` Flag

Enables automatic file format conversion for unsupported types. For example, converting docx to PDF before sending to Claude's token counting endpoint. The original file is never modified; conversion happens in memory.

**Rationale for deferral**: Reliable file format conversion in Python requires system-level dependencies (e.g., LibreOffice for docx-to-PDF). This adds significant complexity and installation burden for v1.

### `--estimate` Flag

Enables heuristic-based token counts where the provider's API cannot count a file type at all. For example, estimating Grok image tokens based on image dimensions using xAI's documented formula (256-1,792 tokens depending on resolution). Estimated counts would be clearly marked in the output.

**Rationale for deferral**: The heuristic ranges (e.g., Grok's 256-1,792 tokens for images) are imprecise enough to be misleading without clear communication to the user about the uncertainty.

## 14. Future Considerations

- Additional model/provider support
- Result caching — cache token counts for unchanged files (keyed by file modification time and provider/model) to avoid redundant API calls on repeated runs
- Multi-provider comparison in a single run
- Global gitignore support (`~/.config/git/ignore`)

---

*Plan tier data was researched March 2026 and should be verified periodically.*
