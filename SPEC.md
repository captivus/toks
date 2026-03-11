# count-tokens Feature Specification

## OPEN ITEMS — Review Feedback & Pending Decisions

This section captures feedback from architectural and engineering reviews, along with pending design decisions. These must be resolved before implementation begins.

### Decisions Made (pending spec updates)

1. **Eliminate multi-provider runs.** Single provider per invocation. This significantly simplifies output formatting, concurrency, error handling, and the CLI interface. Sections 4, 5, 7, and 8 need updating.

2. **Simplify `--for` to specify a provider** (e.g., `--for claude`, `--for openai`, `--for gemini`), not a context like `claude-code` or `chatgpt-web`.

3. **Operating modes (coding agent, web chat, API) only matter for context window percentage.** The token count is the same regardless of mode — only the "X% of Y context window" changes. Could show a summary table of percentages across modes.

4. **For v1, assume coding agent context** as the default operating mode. This is the primary use case. Revisit multi-mode context window display later.

### Still Under Discussion

5. **How to present context window percentages.** For a single file, a table showing percentage across modes (coding agent, web chat, API) is straightforward. For a directory tree, showing multiple percentages per line gets noisy. Need to decide: show only the default mode's percentage in the tree, and a multi-mode summary at the bottom? Or just the default mode everywhere?

### High Priority (blocks implementation)

6. **`--model` with unknown models can't route to a provider.** If someone says `--model my-custom-model`, how do we know which API to call? Options: (a) require `--for` with `--model`, (b) infer provider from model name prefix, (c) add a `--provider` flag.

7. **Config file location.** `.env` in current directory is wrong for a global CLI tool. Should be `~/.config/count-tokens/` or similar, with project-local `.env` as optional override.

8. **Async vs sync.** Both reviewers recommend `asyncio`. All four SDKs support async clients. Need to state this in the spec.

9. **Exit codes.** Not defined. Suggested: 0 = success (including partial success), 1 = all failed or config error, 2 = usage error.

10. **Dependency stack.** Need to decide: CLI framework (click/typer), progress bar (rich/tqdm), MIME detection (python-magic vs stdlib mimetypes), gitignore parsing (pathspec).

11. **Acceptance criteria and testing strategy.** No tests defined. Need per-section acceptance criteria and a dedicated testing section. All tests will use real APIs (no mocks). Need test fixtures (known files committed to repo).

### Medium Priority (should address before implementation)

12. **Missing API key in multi-provider run** — Now less relevant since we're doing single provider per run. But should still define behavior: error immediately.

13. **Provider SDKs as optional dependencies.** Engineer recommends making each provider installable separately (e.g., `uv add --optional grok xai-sdk`). The xai-sdk gRPC dependency is 30-40MB.

14. **Concurrency too high.** 10-20 is aggressive for lower-tier accounts. Recommend conservative default (5) with `--concurrency` flag.

15. **`--convert` is a hidden project.** docx-to-PDF requires LibreOffice or similar. Both reviewers suggest deferring to v1.1, or explicitly scoping to a single conversion with documented system dependencies.

16. **`.gitignore` discovery.** Which files? Nested? Global `~/.config/git/ignore`? Need to specify.

### Lower Priority (address during implementation)

17. **`--ext` and `--glob` overlap.** Consider cutting `--ext` since `--glob "*.py"` does the same thing.
18. **Symlink loop detection** in directory traversal.
19. **Default max file size.** Without `--max-size`, a 500MB file will blow up (OpenAI has 50MB limit).
20. **stdin MIME type.** No filename to detect from. Assume text? Flag for override?
21. **Empty directory / no matching files** behavior — should output "No files matched" and exit 0.
22. **`--max-size` unit format** unspecified (KB, MB, GB, bare bytes).
23. **`--depth` flag** for shallow directory traversal.
24. **Data structures should be explicit** — both reviewers want concrete dataclasses for `TokenCountResult`, `FileResult`, `ModelInfo` in the spec.
25. **Tree output rendering library** — `rich` recommended by both reviewers.
26. **Backoff strategy** — should specify exponential backoff with jitter, and respect `Retry-After` headers.
27. **Circuit breaker** — abort after K consecutive failures from a provider rather than burning through all files.

### Scope Cuts for v1

- **`--convert` flag** — defer to v1.1 (significant hidden complexity with system dependencies)
- **`--estimate` flag** — defer to v1.1 (Grok image estimation is imprecise enough to be misleading)
- **Multi-provider comparison in a single run** — eliminated (see decision #1 above)

### Section 9 — Pending Research Results

Plan tier research has been completed for all four providers. Results need to be incorporated into section 9's setup workflow. Key finding: for all providers, subscription plans and API access are independent — the wizard needs to ask about both separately.

---

## 1. Overview & Purpose

A command-line application that counts the tokens a given file or directory of files would consume when loaded into a large language model. It supports multiple model providers and reports accurate token counts using official tokenization APIs.

LLMs have finite context windows. Before loading files into a model — whether for code review, document analysis, or any other task — users need to understand how much of that context window the content will consume. This tool answers "how many tokens will this cost me?" before you spend them.

### Target Users

Developers and power users who work with LLM APIs and need to plan their context window usage — especially when working with large codebases or document sets.

## 2. Supported Models & Providers

The tool supports four providers at launch. Model names and context window sizes change frequently, so these are maintained as a data structure in code rather than hardcoded throughout the application.

### Anthropic (Claude)

#### Coding Agent (Claude Code)

| Model | Context Window | Notes |
|-------|---------------|-------|
| claude-sonnet-4-6 | 200K (1M beta) | Default |
| claude-opus-4-6 | 200K (1M beta) | |
| claude-haiku-4-5 | 200K | |

Also supports an `opusplan` alias (Opus for planning, Sonnet for implementation).

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

### Design Considerations

- The model registry should be a single, easily updated data structure (e.g., a dictionary or configuration file).
- When a user specifies a model not in the registry, the tool should still attempt the API call but warn that it cannot display context window percentage.
- The tool should provide a command to list all known models and their context windows.

## 3. Tokenization Strategy

### Approach

- API-only, using each provider's official token counting endpoints
- No local/offline tokenization (if you can't reach the API, you can't use the model)
- One API call per file (no provider supports batching with per-item breakdown)

### Provider Abstraction Layer

Custom thin wrapper (no third-party unified LLM libraries). Each provider implements a common interface/protocol. New providers can be added by implementing the interface.

**Common interface**: Each provider implements a method that accepts file content (as bytes), a MIME type, and a model identifier, and returns a result containing at minimum a total token count. Where the provider supports it (currently only Gemini), a per-modality breakdown (text, image, audio, video) is also returned. Providers return "unsupported" for file types they cannot handle.

### File Type Detection and Content Packaging

The tool detects each file's MIME type before passing it to a provider. Each provider implementation is responsible for packaging the content into the format its API expects. Providers differ in how they accept different file types:

| File Type | Claude | OpenAI | Gemini | Grok |
|-----------|--------|--------|--------|------|
| Text/code | `text` content block | Raw string or `input_text` | String or `Part.from_bytes()` | `tokenize_text()` |
| Image (JPEG, PNG, GIF, WebP) | `image` content block | `input_image` block | `Part.from_bytes()` | Not supported |
| Image (HEIC, BMP, TIFF, SVG) | Not supported | Not supported | `Part.from_bytes()` | Not supported |
| PDF | `document` content block | File input | `Part.from_bytes()` | Not supported |
| Office docs (docx, xlsx, pptx) | Not supported (convert to PDF or text) | File input | `Part.from_bytes()` | Not supported |

MIME type detection and file reading are handled by the tool's core. Content packaging (choosing the right block type, encoding to base64 where needed, etc.) is handled by each provider implementation.

### Provider SDK Details

#### Claude (`anthropic`)

- **Method**: `client.messages.count_tokens()`
- **Input**: Content must be wrapped in a messages structure (cannot pass raw text directly). Supports text, images (base64 or URL: JPEG, PNG, GIF, WebP), and PDFs (document blocks, base64 or URL).
- **Response**: Single integer (`input_tokens`). No per-item or per-modality breakdown.
- **Rate limits**: 100-8,000 RPM depending on usage tier. Free to call. Separate from message creation limits.
- **Caveat**: Returns an estimate — actual usage may differ slightly. May include system-added tokens (not billed).

#### OpenAI (`openai`)

- **Method**: `client.responses.input_tokens.count()`
- **Input**: Accepts raw text strings or message arrays. Supports images (URL, base64 data URL, or file ID; with `detail` parameter affecting token count), PDFs, docx, spreadsheets, code files (via file ID, URL, or inline base64).
- **Response**: Single integer (`input_tokens`). No breakdown.
- **Rate limits**: Not separately documented; likely shares Responses API limits.
- **Caveat**: PDFs extract both text AND page images, so token counts can be higher than expected. 50 MB per file limit.

#### Gemini (`google-genai`)

- **Method**: `client.models.count_tokens()`
- **Input**: Very flexible — accepts raw strings, PIL images, raw bytes with MIME type, or uploaded file references. Supports images (JPEG, PNG, WebP, HEIC, GIF, BMP, TIFF, SVG), video, audio, and PDFs.
- **Response**: Total token count (`total_tokens`) plus per-modality breakdown (`prompt_tokens_details` with TEXT, IMAGE, AUDIO, VIDEO counts).
- **Rate limits**: 3,000 RPM. Free to call.
- **Caveat**: `system_instruction` not supported via Gemini Developer API (only Vertex AI). Files must reach ACTIVE state before counting.

#### Grok (`xai-sdk`, gRPC-based)

- **Method**: `client.tokenize.tokenize_text()`
- **Input**: Plain text only. No image, PDF, or binary file support.
- **Response**: List of token objects (each with `token_id`, `string_token`, `token_bytes`). Count is `len(tokens)`.
- **Rate limits**: Not published; tier-based, visible in xAI Console.
- **Caveat**: Text-only — no image or document tokenization. Explicitly underestimates actual usage because "inference endpoints automatically add pre-defined tokens." For images, xAI documents a range of 256-1,792 tokens based on resolution (512x512 ~ 1,610 tokens) but provides no API to compute this.

### Unsupported File Type Handling

By default, the tool reports unsupported files in the output (e.g., "3 files skipped: docx not supported by Claude") without attempting to count them. Two opt-in flags modify this behavior:

- **`--convert`**: Enables automatic file format conversion for unsupported types. For example, converting docx to PDF before sending to Claude's token counting endpoint. The original file is never modified; conversion happens in memory.
- **`--estimate`**: Enables heuristic-based token counts where the provider's API cannot count a file type at all. For example, estimating Grok image tokens based on image dimensions using xAI's documented formula (256-1,792 tokens depending on resolution). Estimated counts are clearly marked in the output.

These are independent flags — `--convert` handles format translation, `--estimate` handles provider capability gaps.

### Known Limitations

- **Accuracy varies**: Claude and Gemini describe their counts as estimates. OpenAI's is deterministic for the same input. Grok explicitly underestimates because "inference endpoints automatically add pre-defined tokens."
- **No per-file breakdown from any provider**: When counting a directory, the tool must make one API call per file to get individual counts.

## 4. CLI Interface

### Installation

Installs as `count-tokens` with a short alias `ct`.

### Command Syntax

```
count-tokens <target> [options]
```

Where `<target>` is a file path, directory path, or `-` for stdin.

Counting tokens is the default action — no subcommand required. Non-counting operations use subcommands:

- `count-tokens setup` — interactive configuration workflow (see section 9)
- `count-tokens models` — list all known models and their context windows

### Target Modes

- **Single file**: `count-tokens ./main.py`
- **Directory**: `count-tokens ./src` (recursive by default)
- **stdin**: `cat file.py | count-tokens -` or piped input

### Provider/Model Selection

- **No flag**: Uses the default context configured during `setup`
- **`--for <context>`**: Overrides to a specific context (e.g., `--for claude-code`, `--for chatgpt-web`, `--for codex`)
- **`--model <model-id>`**: Overrides to a specific model (e.g., `--model gpt-5.4`)
- **Multiple providers**: Specify `--for` multiple times (e.g., `--for claude-code --for codex`)
- **`--for` and `--model` together**: Error — these are conflicting instructions

### Filtering Flags

- **`--glob <pattern>`**: Filter files by glob pattern (e.g., `--glob "*.py"`)
- **`--ext <extension>`**: Filter by file extension (e.g., `--ext py`, `--ext ts`)
- **`--max-size <size>`**: Exclude files larger than the given size (e.g., `--max-size 1MB`)
- **`--no-gitignore`**: Include files that would normally be skipped by `.gitignore` rules
- **`--include-binary`**: Include binary files (excluded by default)

### Behavior Flags

- **`--convert`**: Enable automatic file format conversion for unsupported types (see section 3)
- **`--estimate`**: Enable heuristic-based token counts for unsupported file types (see section 3)

### Output Flags

- **Default**: Tree-style display with per-file token counts and summary
- **`--quiet` / `-q`**: Output only the total token count (useful for scripting)
- **`--summary`**: Output only the per-provider totals, no tree

## 5. Output Format

### Default (Tree View)

```
./src/                          [4,812 tokens] (2.4% of 200K)
├── main.py                      1,203 tokens
├── utils/                      [2,105 tokens]
│   ├── helpers.py               1,450 tokens
│   └── config.py                  655 tokens
└── tests/                      [1,504 tokens]
    ├── test_main.py               890 tokens
    └── test_helpers.py            614 tokens

Total: 4,812 tokens (2.4% of claude-sonnet-4-6 200K context window)
```

### Multi-Provider (Tree View)

```
./src/                          [Claude: 4,812] [Codex: 4,650]
├── main.py                      Claude: 1,203   Codex: 1,180
├── utils/                      [Claude: 2,105] [Codex: 2,020]
│   ├── helpers.py               Claude: 1,450   Codex: 1,390
│   └── config.py                Claude:   655   Codex:   630
└── tests/                      [Claude: 1,504] [Codex: 1,450]
    ├── test_main.py             Claude:   890   Codex:   860
    └── test_helpers.py          Claude:   614   Codex:   590

Summary:
  claude-sonnet-4-6:  4,812 tokens (2.4% of 200K)
  gpt-5.4:            4,650 tokens (0.5% of 1M)
```

### Quiet Mode (`--quiet`)

Single provider:
```
4812
```

Multiple providers:
```
claude-sonnet-4-6:4812
gpt-5.4:4650
```

### Summary Mode (`--summary`)

```
claude-sonnet-4-6:  4,812 tokens (2.4% of 200K)
gpt-5.4:            4,650 tokens (0.5% of 1M)
```

### Skipped Files

Unsupported or inaccessible files are reported after the tree:

```
Skipped (3 files):
  report.docx — docx not supported by Claude (use --convert)
  photo.heic — HEIC not supported by Claude
  diagram.png — image token counting not supported by Grok (use --estimate)
```

## 6. File Handling

### Directory Traversal

- Recursive by default when a directory is given as the target
- Respects `.gitignore` rules by default (skips files matching `.gitignore` patterns)
- `--no-gitignore` flag disables this and includes all files

### Filtering

Applied before any API calls are made:

- **Glob pattern** (`--glob "*.py"`): Only include files matching the pattern
- **File extension** (`--ext py`): Only include files with the given extension
- **File size** (`--max-size 1MB`): Exclude files larger than the given size
- Multiple filters can be combined and are applied as AND conditions

### File Type Detection

The tool detects each file's MIME type to determine how to handle it:

- **Text files** (source code, plain text, markdown, CSV, etc.): Read as text, sent to provider's text tokenization
- **Image files** (JPEG, PNG, GIF, WebP, HEIC, etc.): Sent as binary with MIME type to providers that support image tokenization
- **PDF files**: Sent as binary with MIME type to providers that support PDF tokenization
- **Office documents** (docx, xlsx, pptx): Sent to providers that support them (OpenAI, Gemini); flagged as unsupported for others unless `--convert` is enabled
- **Binary files** (executables, archives, etc.): Excluded by default. `--include-binary` overrides this, though most providers will not be able to tokenize them

### Unsupported File Handling

When a file's type is not supported by the selected provider:

- **Default**: File is skipped and reported in the "Skipped files" section of the output
- **With `--convert`**: The tool attempts to convert the file to a supported format (e.g., docx to PDF for Claude). Conversion happens in memory; original files are never modified.
- **With `--estimate`**: The tool applies provider-documented heuristics where available (e.g., Grok image tokens based on resolution). Estimated counts are clearly marked.

## 7. Performance

### Concurrency

- Fixed concurrency of 10-20 concurrent API requests per provider
- On HTTP 429 (rate limit exceeded), back off and retry automatically
- When multiple providers are specified, all providers are called simultaneously (independent APIs with independent rate limits)

### Progress Indication

- Progress bar shown by default for directory operations (file count and percentage)
- No progress bar for single file operations
- `--no-progress` flag suppresses the progress bar (useful for AI agent tool use)
- `--quiet` flag also suppresses progress output

## 8. Error Handling

### Missing or Invalid API Keys

If the user requests a provider whose API key is not configured, the tool reports the error immediately and exits (does not proceed with partial providers).

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

Handled as described in section 6 — skipped by default, with `--convert` and `--estimate` flags for opt-in handling.

### Inaccessible Files

Files that cannot be read (permissions, broken symlinks, etc.) are reported in the skipped/failed output and do not halt the run.

## 9. Configuration

### Initial Setup Workflow

A guided `count-tokens setup` command that walks the user through:

- Which providers they have access to
- For each provider: what plan/tier (e.g., Claude Max $200/mo, ChatGPT Plus $20/mo, Gemini Free, etc.)
- Which contexts they use (coding agent, web chat, API)
- A default context for day-to-day use (e.g., "I mostly use coding agents")
- API keys for each configured provider (written to `.env` file)

### Stored Configuration

- API keys via `.env` file (using standard env var names: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`)
- Provider/plan/tier selections
- Default context and model preferences
- Configuration can be re-run at any time to update

### Runtime Overrides

- `--for <context>` (e.g., `--for claude-code`, `--for chatgpt-web`) to override the default context for a single run
- `--model <model-id>` to override with a specific model
- Runtime flags take precedence over stored configuration

## 10. Future Considerations

- Additional model/provider support
- Result caching — cache token counts for unchanged files (keyed by file modification time and provider/model) to avoid redundant API calls on repeated runs
- `--convert` flag for automatic file format conversion (deferred from v1 due to system dependency complexity)
- `--estimate` flag for heuristic-based token counts (deferred from v1)
- Multi-provider comparison in a single run
- Multi-mode context window percentage display (coding agent, web chat, API side by side)

## Appendix A: Provider Plan Tiers (Research Results)

This data was collected March 2026 and needs to be incorporated into the section 9 setup workflow.

### Anthropic (Claude)

| Plan | Price | Models | Claude Code | Web Chat | API | Context Window |
|------|-------|--------|-------------|----------|-----|---------------|
| Free | $0 | Sonnet 4.6, Haiku 4.5 | No | Yes | Separate (pay-per-token) | 200K |
| Pro | $20/mo | All | Yes | Yes | Separate | 200K |
| Max 5x | $100/mo | All | Yes | Yes | Separate | 200K (1M beta) |
| Max 20x | $200/mo | All | Yes | Yes | Separate | 200K (1M beta) |
| Team Standard | $25-30/seat | All | No | Yes | Separate | 200K |
| Team Premium | $100-150/seat | All | Yes | Yes | Separate | 200K |
| Enterprise | Custom | All | Yes | Yes | Separate | Up to 500K |

### OpenAI (GPT)

| Plan | Price | Models (Web) | Codex | API | Web Context Window |
|------|-------|-------------|-------|-----|--------------------|
| Free | $0 | GPT-5.2 Instant/Mini | Temporary promo | Separate (pay-per-token) | ~16K |
| Go | $8/mo | GPT-5.2 Instant | Temporary promo | Separate | ~16-32K |
| Plus | $20/mo | GPT-5.2, GPT-5.4 Thinking, o3 | Yes (~25 tasks/day) | Separate | ~32K |
| Pro | $200/mo | All including GPT-5.2 Pro, GPT-5.4 Pro | Yes (higher limits) | Separate | ~128K |
| Business | $25-30/seat | Same as Plus | Yes | Separate | ~32K |
| Enterprise | Custom | All | Yes | Separate | ~128K |

### Google (Gemini)

| Plan | Price | Web Context Window | CLI Access | API |
|------|-------|--------------------|------------|-----|
| Free | $0 | ~32K | Yes (free Google login, 1M context) | Separate (free tier available) |
| AI Plus | $7.99/mo | 128K | Yes | Separate |
| AI Pro | $19.99/mo | 1M | Yes (may boost quotas) | Separate |
| AI Ultra | $249.99/mo | 1M | Yes (may boost quotas) | Separate |

Note: Gemini CLI is usable for free with Google login (1M context, 60 RPM) regardless of subscription tier.

### xAI (Grok)

| Plan | Price | Web Context | API |
|------|-------|------------|-----|
| Free | $0 | Limited, ~10 msg/2hr | Separate (pay-per-token, $25 signup credit) |
| X Premium | $8/mo | Basic, ~100 msg/2hr | Separate |
| X Premium+ | $40/mo | Priority, higher limits | Separate |
| SuperGrok | $30/mo | 128K, unlimited queries | Separate |
| SuperGrok Heavy | $300/mo | 256K, Grok 4 Heavy exclusive | Separate |
