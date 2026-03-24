"""Output rendering: tree view, summary, quiet mode."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from count_tokens.providers.base import FileResult


def format_tokens(*, count: int) -> str:
    return f"{count:,}"


def format_pct(*, tokens: int, window: int | None) -> str:
    if window is None or window == 0:
        return "N/A"
    pct = (tokens / window) * 100
    if pct < 0.1:
        return "<0.1%"
    return f"{pct:.1f}%"


def format_window_size(*, window: int | None) -> str:
    if window is None:
        return "N/A"
    if window >= 1_000_000:
        return f"{window / 1_000_000:.0f}M"
    return f"{window / 1_000:.0f}K"


def build_tree_structure(*, results: list[FileResult], base_path: Path) -> dict:
    tree: dict = {"children": {}, "tokens": 0, "files": []}
    for fr in results:
        if fr.status != "success" or fr.token_count is None:
            continue
        try:
            rel = fr.path.relative_to(base_path)
        except ValueError:
            rel = fr.path
        parts = rel.parts
        node = tree
        for part in parts[:-1]:
            if part not in node["children"]:
                node["children"][part] = {"children": {}, "tokens": 0, "files": []}
            node = node["children"][part]
        node["files"].append(fr)
        tokens = fr.token_count.total_tokens
        node["tokens"] += tokens
        current = tree
        for part in parts[:-1]:
            current["tokens"] += tokens
            current = current["children"][part]

    return tree


def render_tree(
    *,
    results: list[FileResult],
    base_path: Path,
    agent_window: int | None,
    web_window: int | None,
    api_window: int | None,
    provider_name: str | None = None,
    model_name: str | None = None,
    console: Console | None = None,
) -> None:
    if console is None:
        console = Console()

    successful = [r for r in results if r.status == "success" and r.token_count]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    total_tokens = sum(r.token_count.total_tokens for r in successful)

    if not successful and not skipped and not failed:
        console.print("No files matched")
        return

    if provider_name:
        label = f"Provider: [bold]{provider_name}[/bold]"
        if model_name:
            label += f" ({model_name})"
        console.print(label)
        console.print()

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Tokens", justify="right")
    table.add_column("Agent", justify="right")
    table.add_column("Web", justify="right")
    table.add_column("API", justify="right")

    tree_data = build_tree_structure(results=successful, base_path=base_path)

    def add_entries(*, node: dict, prefix: str = "", depth: int = 0) -> None:
        dirs = sorted(node["children"].keys())
        files = sorted(node["files"], key=lambda f: f.path.name)
        items = [(True, d) for d in dirs] + [(False, f) for f in files]

        for is_dir, item in items:
            if is_dir:
                dir_node = node["children"][item]
                dir_tokens = dir_node["tokens"]
                table.add_row(
                    f"{'  ' * depth}{item}/",
                    f"[{format_tokens(count=dir_tokens)}]",
                    format_pct(tokens=dir_tokens, window=agent_window),
                    format_pct(tokens=dir_tokens, window=web_window),
                    format_pct(tokens=dir_tokens, window=api_window),
                )
                add_entries(node=dir_node, prefix=f"{prefix}{item}/", depth=depth + 1)
            else:
                fr = item
                tokens = fr.token_count.total_tokens
                table.add_row(
                    f"{'  ' * depth}{fr.path.name}",
                    f"{format_tokens(count=tokens)}",
                    format_pct(tokens=tokens, window=agent_window),
                    format_pct(tokens=tokens, window=web_window),
                    format_pct(tokens=tokens, window=api_window),
                )

    add_entries(node=tree_data)
    console.print(table)

    console.print()
    console.print(f"Total: {format_tokens(count=total_tokens)} tokens")
    console.print(f"  Agent ({format_window_size(window=agent_window)}):  {format_pct(tokens=total_tokens, window=agent_window)}")
    console.print(f"  Web ({format_window_size(window=web_window)}):    {format_pct(tokens=total_tokens, window=web_window)}")
    console.print(f"  API ({format_window_size(window=api_window)}):    {format_pct(tokens=total_tokens, window=api_window)}")

    if skipped:
        console.print()
        console.print(f"Skipped ({len(skipped)} files):")
        for fr in skipped:
            console.print(f"  {fr.path.name} — {fr.skip_reason}")

    if failed:
        console.print()
        console.print(f"[red]Failed ({len(failed)} files):[/red]")
        for fr in failed:
            console.print(f"  [red]{fr.path.name} — {fr.error}[/red]")


def render_quiet(*, results: list[FileResult]) -> None:
    total = sum(r.token_count.total_tokens for r in results if r.status == "success" and r.token_count)
    print(total)


def render_summary(
    *,
    results: list[FileResult],
    agent_window: int | None,
    web_window: int | None,
    api_window: int | None,
    provider_name: str | None = None,
    model_name: str | None = None,
    console: Console | None = None,
) -> None:
    if console is None:
        console = Console()

    if provider_name:
        label = f"Provider: [bold]{provider_name}[/bold]"
        if model_name:
            label += f" ({model_name})"
        console.print(label)
        console.print()

    total = sum(r.token_count.total_tokens for r in results if r.status == "success" and r.token_count)
    console.print(f"Total: {format_tokens(count=total)} tokens")
    console.print(f"  Agent ({format_window_size(window=agent_window)}):  {format_pct(tokens=total, window=agent_window)}")
    console.print(f"  Web ({format_window_size(window=web_window)}):    {format_pct(tokens=total, window=web_window)}")
    console.print(f"  API ({format_window_size(window=api_window)}):    {format_pct(tokens=total, window=api_window)}")

    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]
    if skipped:
        console.print()
        console.print(f"Skipped ({len(skipped)} files):")
        for fr in skipped:
            console.print(f"  {fr.path.name} — {fr.skip_reason}")
    if failed:
        console.print()
        console.print(f"[red]Failed ({len(failed)} files):[/red]")
        for fr in failed:
            console.print(f"  [red]{fr.path.name} — {fr.error}[/red]")
