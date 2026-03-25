"""
cli.py — FreeRouter command-line interface.

Context: Entry point for all terminal commands.
Kept intentionally minimal — the web dashboard handles everything else.

Commands:
    freerouter web    → start the web dashboard (default port 8080)
    freerouter proxy  → start the OpenAI-compatible proxy (default port 4000)
    freerouter version → show version

Imports: web/app.py, proxy_server.py, providers.py
Imported by: __main__.py
"""

import os
import sys
import threading
import webbrowser

import typer
from rich import print as rprint
from rich.panel import Panel

from freerouter import __version__

app = typer.Typer(
    name="freerouter",
    help="FreeRouter — routes AI requests to the best free provider automatically.",
    add_completion=False,
)


@app.command()
def web(
    port: int = typer.Option(3000, "--port", "-p", help="Dashboard port"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser"),
) -> None:
    """Start the unified FreeRouter dashboard (replaces old :8080 UI)."""
    import sys as _sys
    from pathlib import Path as _Path
    # Make packages importable from repo root
    _repo = _Path(__file__).resolve().parent.parent.parent.parent
    for _p in [str(_repo), str(_repo / "freerouter" / "src")]:
        if _p not in _sys.path:
            _sys.path.insert(0, _p)

    try:
        import uvicorn
        from apps.api.main import app as dashboard_app
    except ImportError as e:
        rprint(f"[red]Cannot load dashboard: {e}[/red]")
        rprint("Make sure you are running from the repo root: AI-Orchestration/")
        _sys.exit(1)

    rprint(Panel(
        f"[bold cyan]FreeRouter Dashboard[/bold cyan]\n\n"
        f"[bold]URL:[/bold] [cyan]http://localhost:{port}[/cyan]\n\n"
        f"[dim]All features in one place — pipeline, chat, providers, analytics.\n"
        f"Also run: python -m freerouter proxy  (LLM calls on :4000)\n"
        f"Press Ctrl+C to stop.[/dim]",
        border_style="cyan",
    ))

    if open_browser:
        def _open():
            import time; time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(dashboard_app, host=host, port=port, log_level="warning")


@app.command()
def proxy(
    port: int = typer.Option(4000, "--port", "-p", help="Proxy port"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    api_key: str = typer.Option(None, "--api-key", help="Optional auth key"),
) -> None:
    """Start the OpenAI-compatible proxy server.

    Point Cursor, Continue, or any OpenAI client at:
        base_url = http://localhost:4000/v1
        api_key  = any-value
    """
    try:
        import uvicorn
        from freerouter.proxy_server import create_proxy_app
    except ImportError as e:
        rprint(f"[red]Missing dependency: {e}[/red]")
        sys.exit(1)

    rprint(Panel(
        f"[bold cyan]FreeRouter Proxy[/bold cyan]\n\n"
        f"[bold]Endpoint:[/bold] [cyan]http://{host}:{port}/v1[/cyan]\n\n"
        f"[dim]Set in your tool:\n"
        f"  base_url = http://localhost:{port}/v1\n"
        f"  api_key  = any-value\n\n"
        f"Press Ctrl+C to stop.[/dim]",
        border_style="cyan",
    ))

    uvicorn.run(create_proxy_app(api_key=api_key), host=host, port=port, log_level="info")


@app.command()
def version() -> None:
    """Show FreeRouter version."""
    rprint(f"[bold]FreeRouter[/bold] [cyan]{__version__}[/cyan]")


if __name__ == "__main__":
    app()
