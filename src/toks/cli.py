"""CLI entry point using click."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from toks import __version__
from toks.providers.base import FileResult
from toks.config import load_config, load_env_api_key, get_web_context_window
from toks.registry import get_registry, get_context_window, infer_provider, refresh_registry, list_models_for_provider
from toks.scanner import scan_files, detect_mime_type, parse_size
from toks.runner import run_token_counting
from toks.output import render_tree, render_quiet, render_summary
from toks.providers import get_provider, PROVIDER_ENV_KEYS

console = Console()


class CountTokensGroup(click.Group):
    """Custom group that treats unknown commands as the target argument for counting."""

    def parse_args(self, ctx, args):
        if not args or args == ["--help"] or args == ["--version"]:
            return super().parse_args(ctx, args)
        if args[0] not in self.commands and not args[0].startswith("-"):
            args = ["count"] + args
        elif args[0].startswith("-"):
            args = ["count"] + args
        return super().parse_args(ctx, args)


@click.group(cls=CountTokensGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="toks")
@click.pass_context
def app(ctx):
    """Count tokens for files across LLM providers.

    \b
    Usage examples:
      toks file.py --for claude
      toks src/ --for gemini --glob "*.py"
      toks setup
      toks models --refresh
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@app.command(name="count", hidden=True)
@click.argument("target")
@click.option("--for", "for_provider", help="Provider to use (claude, openai, gemini, grok).")
@click.option("--model", help="Specific model to use.")
@click.option("--glob", "glob_pattern", help="Filter files by glob pattern.")
@click.option("--max-size", default="50MB", help="Max file size (e.g., 10MB).")
@click.option("--no-gitignore", is_flag=True, help="Include gitignored files.")
@click.option("--include-binary", is_flag=True, help="Include binary files.")
@click.option("--concurrency", default=10, help="Concurrent API requests.")
@click.option("--retries", default=3, help="Retry count for transient errors.")
@click.option("--mime-type", help="Override MIME type (for stdin).")
@click.option("--quiet", "-q", is_flag=True, help="Output only total token count.")
@click.option("--summary", is_flag=True, help="Output only totals, no tree.")
@click.option("--no-progress", is_flag=True, help="Suppress progress bar.")
def count_command(target, for_provider, model, glob_pattern, max_size, no_gitignore,
                  include_binary, concurrency, retries, mime_type, quiet, summary, no_progress):
    """Count tokens for a file or directory."""
    _run_count(
        target=target, for_provider=for_provider, model=model,
        glob_pattern=glob_pattern, max_size=max_size, no_gitignore=no_gitignore,
        include_binary=include_binary, concurrency=concurrency, retries=retries,
        mime_type_override=mime_type, quiet=quiet, summary=summary,
        no_progress=no_progress,
    )


@app.command()
def setup():
    """Interactive configuration wizard."""
    from toks.setup import run_setup
    from toks.config import CONFIG_FILE

    run_setup()
    console.print(f"\n[bold green]Setup complete![/bold green] Config saved to {CONFIG_FILE}")


@app.command()
@click.option("--refresh", is_flag=True, help="Refresh the model registry from GitHub.")
def models(refresh):
    """List known models and their context windows."""
    if refresh:
        console.print("Refreshing model registry...")
        refresh_registry()
        console.print("[green]Registry updated.[/green]\n")

    config = load_config()
    provider_names = list(config.providers.keys()) if config else ["claude", "openai", "gemini", "grok"]

    registry = get_registry()
    for name in provider_names:
        model_list = list_models_for_provider(provider=name, registry=registry)
        if model_list:
            console.print(f"\n[bold]{name}[/bold]")
            for m in model_list[:20]:
                ctx = m["max_input_tokens"]
                ctx_str = f"{ctx:,}" if ctx else "N/A"
                console.print(f"  {m['model_id']}: {ctx_str} tokens")
            if len(model_list) > 20:
                console.print(f"  ... and {len(model_list) - 20} more")


def _run_count(
    *,
    target: str,
    for_provider: str | None,
    model: str | None,
    glob_pattern: str | None,
    max_size: str,
    no_gitignore: bool,
    include_binary: bool,
    concurrency: int,
    retries: int,
    mime_type_override: str | None,
    quiet: bool,
    summary: bool,
    no_progress: bool,
) -> None:
    config = load_config()
    registry = get_registry()

    resolved_provider = None
    resolved_model = None

    if model:
        resolved_provider = infer_provider(model_id=model, registry=registry)
        if not resolved_provider:
            console.print(f"[red]Model '{model}' not found in registry. Use --for <provider>, or run 'toks models --refresh'.[/red]")
            sys.exit(1)
        resolved_model = model
    elif for_provider:
        resolved_provider = for_provider
        if config and for_provider in config.providers:
            resolved_model = config.providers[for_provider].model
    elif config and config.default_provider:
        resolved_provider = config.default_provider
        if resolved_provider in config.providers:
            resolved_model = config.providers[resolved_provider].model

    if not resolved_provider:
        console.print("[red]No provider specified. Use --for <provider>, --model <model>, or run 'toks setup'.[/red]")
        sys.exit(1)

    if not resolved_model:
        fallback = {"claude": "claude-sonnet-4-6", "openai": "gpt-4o-mini", "gemini": "gemini-2.5-flash", "grok": "grok-3"}
        resolved_model = fallback.get(resolved_provider, "")

    api_key = load_env_api_key(provider=resolved_provider)
    if not api_key:
        env_key_name = PROVIDER_ENV_KEYS.get(resolved_provider, "")
        console.print(f"[red]{env_key_name} not configured. Run 'toks setup' or set it in your .env file.[/red]")
        sys.exit(1)

    provider = get_provider(name=resolved_provider, api_key=api_key)

    # Preflight: validate model works with provider before processing files
    try:
        asyncio.run(provider.count_tokens(content=b"hello", mime_type="text/plain", model=resolved_model))
    except Exception as exc:
        console.print(f"[red]Preflight check failed for {resolved_provider}/{resolved_model}: {exc}[/red]")
        console.print("[red]Check that the model name is valid. Run 'toks models --refresh' to update the registry.[/red]")
        sys.exit(1)

    max_size_bytes = parse_size(size_str=max_size)

    if target == "-":
        content = sys.stdin.buffer.read()
        mime = mime_type_override or "text/plain"
        file_results = [FileResult(path=Path("<stdin>"), mime_type=mime, file_size=len(content))]

        async def count_stdin():
            try:
                result = await provider.count_tokens(content=content, mime_type=mime, model=resolved_model)
                file_results[0].status = "success"
                file_results[0].token_count = result
            except Exception as exc:
                file_results[0].status = "failed"
                file_results[0].error = str(exc)

        asyncio.run(count_stdin())
    else:
        target_path = Path(target).resolve()

        if target_path.is_file():
            mime = mime_type_override or detect_mime_type(path=target_path)
            file_results = [FileResult(path=target_path, mime_type=mime, file_size=target_path.stat().st_size)]
            asyncio.run(run_token_counting(
                provider=provider, file_results=file_results, model=resolved_model,
                concurrency=1, retries=retries,
            ))
        elif target_path.is_dir():
            scanned = scan_files(
                target=target_path, glob_pattern=glob_pattern, max_size=max_size_bytes,
                no_gitignore=no_gitignore, include_binary=include_binary,
            )
            if not scanned:
                console.print("No files matched")
                sys.exit(0)

            file_results = [FileResult(path=p, mime_type=m, file_size=s) for p, m, s in scanned]
            show_progress = not quiet and not no_progress and len(file_results) > 1

            if show_progress:
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                    BarColumn(), MofNCompleteColumn(), console=console, transient=True,
                ) as progress:
                    task_id = progress.add_task("Counting tokens...", total=len(file_results))
                    asyncio.run(run_token_counting(
                        provider=provider, file_results=file_results, model=resolved_model,
                        concurrency=concurrency, retries=retries,
                        progress_callback=lambda: progress.advance(task_id),
                    ))
            else:
                asyncio.run(run_token_counting(
                    provider=provider, file_results=file_results, model=resolved_model,
                    concurrency=concurrency, retries=retries,
                ))
        else:
            console.print(f"[red]Not a file or directory: {target}[/red]")
            sys.exit(2)

    # Render output
    successful = [r for r in file_results if r.status == "success"]
    agent_window = None
    web_window = None
    api_window = get_context_window(model_id=resolved_model, registry=registry)

    if config and resolved_provider in config.providers:
        pc = config.providers[resolved_provider]
        web_window = get_web_context_window(provider=resolved_provider, plan=pc.plan)
        if pc.has_coding_agent and pc.agent_model:
            agent_window = get_context_window(model_id=pc.agent_model, registry=registry)

    if quiet:
        render_quiet(results=file_results)
    elif summary:
        render_summary(results=file_results, agent_window=agent_window, web_window=web_window, api_window=api_window,
                       provider_name=resolved_provider, model_name=resolved_model)
    else:
        base = Path(target).resolve() if target != "-" else Path(".")
        render_tree(
            results=file_results,
            base_path=base if base.is_dir() else base.parent,
            agent_window=agent_window, web_window=web_window, api_window=api_window,
            provider_name=resolved_provider, model_name=resolved_model,
        )

    if not successful and any(r.status == "failed" for r in file_results):
        sys.exit(1)
