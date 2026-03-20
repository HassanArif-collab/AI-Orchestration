"""CLI entry point for FreeRouter – Interactive Terminal Interface.

Uses only `rich` + standard Python `input()` for maximum terminal compatibility
on Windows (PowerShell, VS Code terminal, cmd.exe).
"""

import asyncio
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import print as rprint
from rich.rule import Rule

from freerouter import __version__
from freerouter.config import get_config_path, validate_environment, get_model_aliases
from freerouter.providers import (
    KNOWN_PROVIDERS, PROVIDER_MAP, ProviderType,
    get_linked_providers, save_api_key, check_provider_reachable, get_all_usage,
)

app = typer.Typer(
    name="freerouter",
    help="FreeRouter – Smart AI Proxy that always prefers free models",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


# ─── Generic Menu Helper ──────────────────────────────────────────────────────

def _pick(title: str, options: list[str]) -> int:
    """
    Show a numbered list of options and return the 0-based index chosen.
    Works in all terminals (PowerShell, cmd, VS Code, etc.) since it uses
    plain numbered input instead of arrow-key navigation.
    Returns -1 if input is cancelled.
    """
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}[/bold cyan]. {opt}")
    console.print()
    try:
        raw = Prompt.ask(
            "[bold]Enter number[/bold]",
            choices=[str(i) for i in range(1, len(options) + 1)],
            show_choices=False,
        )
        return int(raw) - 1
    except (KeyboardInterrupt, EOFError):
        return -1


# ─── Interactive Main Menu ────────────────────────────────────────────────────

def _interactive_menu() -> None:
    """Show the interactive main menu when the user runs `freerouter` with no args."""
    _print_welcome_banner()

    MENU = [
        "🚀  Start the AI Router Server",
        "🔌  Manage Providers  (add / view keys)",
        "📊  View Usage & Rate Limit Status",
        "📋  How to Connect My Apps  (Cursor, VS Code, Python…)",
        "⚙️   Show Current Configuration",
        "❌  Exit",
    ]

    while True:
        choice = _pick("What would you like to do?", MENU)

        if choice == -1 or choice == 5:  # Exit
            rprint("\n[dim]Bye! Run [bold]freerouter[/bold] again any time. 👋[/dim]\n")
            break
        elif choice == 0:   # Start server
            _cmd_start_interactive()
        elif choice == 1:   # Manage providers
            _menu_providers()
        elif choice == 2:   # Usage status
            _cmd_usage_status()
        elif choice == 3:   # Connection guide
            _menu_connection_guide()
        elif choice == 4:   # Show config
            _cmd_show_config()

        console.print()


# ─── Provider Management Menu ─────────────────────────────────────────────────

def _menu_providers() -> None:
    """Sub-menu: view and add providers."""
    while True:
        console.print(Rule("[bold cyan]Provider Management[/bold cyan]"))
        _print_providers_table()

        choice = _pick("Provider Actions", [
            "➕  Add or Update a Provider",
            "🩺  Test All Linked Providers Now",
            "↩️   Back to Main Menu",
        ])

        if choice == -1 or choice == 2:
            break
        elif choice == 0:
            _add_provider_wizard()
        elif choice == 1:
            asyncio.run(_test_all_providers())


def _print_providers_table() -> None:
    """Print a rich status table of all known providers."""
    linked = get_linked_providers()
    all_usage = get_all_usage()

    table = Table(title="Linked Providers", show_lines=True, expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Type", style="dim", justify="center", width=8)
    table.add_column("Status", justify="center", width=18)
    table.add_column("Usage (Requests)", min_width=28)
    table.add_column("👤 Get Key / Info", style="dim")

    for idx, (defn, is_configured) in enumerate(linked, 1):
        usage_info = all_usage.get(defn.name)

        # Status badge
        if not is_configured and defn.requires_auth:
            status = "[bright_red]✗ Not set[/bright_red]"
        elif usage_info and usage_info.is_hard_limited:
            status = "[red]⛔ Hard Limited[/red]"
        elif usage_info and usage_info.is_soft_limited:
            status = "[yellow]⚠ Soft Limited[/yellow]"
        else:
            status = "[green]✓ Ready[/green]"

        # Usage bar
        if usage_info and usage_info.requests_limit > 0 and usage_info.requests_remaining >= 0:
            used = usage_info.requests_limit - usage_info.requests_remaining
            pct  = used / usage_info.requests_limit
            bar_len = 16
            filled = int(bar_len * pct)
            bar_color = "green" if pct < 0.7 else ("yellow" if pct < 0.90 else "red")
            bar = (
                f"[{bar_color}]{'█' * filled}{'░' * (bar_len - filled)}[/{bar_color}]"
                f" {used}/{usage_info.requests_limit}"
            )
        elif not defn.requires_auth:
            bar = "[dim]Local – unlimited[/dim]"
        else:
            bar = "[dim]No data yet[/dim]"

        ptype = "☁ Cloud" if defn.provider_type == ProviderType.CLOUD else "🖥 Local"
        table.add_row(str(idx), defn.display_name, ptype, status, bar, defn.signup_url)

    console.print(table)


def _add_provider_wizard() -> None:
    """Step-by-step wizard to add or update a provider's API key."""
    console.print(Rule("[bold cyan]Add / Update a Provider[/bold cyan]"))

    choices = [f"{p.display_name}" for p in KNOWN_PROVIDERS] + ["Cancel"]
    idx = _pick("Which provider do you want to add?", choices)

    if idx == -1 or idx == len(KNOWN_PROVIDERS):
        return

    defn = KNOWN_PROVIDERS[idx]
    console.print()

    if defn.provider_type == ProviderType.LOCAL:
        rprint(f"[cyan]Checking if {defn.display_name} is running locally…[/cyan]")
        ok, msg = asyncio.run(check_provider_reachable(defn.name))
        if ok:
            rprint(f"[green]✓ {defn.display_name} is running and reachable![/green]")
            rprint("[dim]Ollama doesn't need an API key — it runs locally.[/dim]\n")
            rprint("[bold]Tip:[/bold] Pull models with: [cyan]ollama pull qwen2.5:7b[/cyan]")
        else:
            rprint(f"[yellow]! {defn.display_name} not detected ({msg})[/yellow]")
            console.print(Panel(
                "1. Go to [bold cyan]https://ollama.ai[/bold cyan] and download the installer\n"
                "2. Run [cyan]ollama serve[/cyan] in a separate terminal\n"
                "3. Pull a model: [cyan]ollama pull qwen2.5:7b[/cyan]\n"
                "4. Come back here and test again.",
                title="[bold]How to install Ollama[/bold]",
                border_style="yellow",
            ))
        return

    # Cloud provider
    console.print(Panel(
        f"[bold]Step 1:[/bold] Open this link to get your free API key:\n"
        f"  [bold cyan]{defn.signup_url}[/bold cyan]\n\n"
        f"[bold]Step 2:[/bold] Sign up (free), then copy your API key.\n"
        f"[bold]Step 3:[/bold] Paste your key below — it is saved to your [dim].env[/dim] file.",
        title=f"[bold]Setting up {defn.display_name}[/bold]",
        border_style="cyan",
    ))

    current_val = os.getenv(defn.env_key, "")
    if current_val:
        rprint(f"[dim]A key is already set. Leave blank to keep the existing one.[/dim]")

    try:
        api_key = Prompt.ask(f"Paste your [cyan]{defn.display_name}[/cyan] API key (input hidden)", password=True)
    except (KeyboardInterrupt, EOFError):
        rprint("\n[yellow]Cancelled.[/yellow]")
        return

    if not api_key.strip() and current_val:
        rprint("[dim]Keeping existing key.[/dim]")
        return

    if not api_key.strip():
        rprint("[yellow]No key entered. Cancelled.[/yellow]")
        return

    try:
        save_api_key(defn.name, api_key.strip())
        rprint(f"[green]✓ Key saved! Testing connection to {defn.display_name}…[/green]")
        ok, msg = asyncio.run(check_provider_reachable(defn.name))
        if ok:
            rprint(f"[green]✓ Connection to {defn.display_name} is working![/green]")
        else:
            rprint(f"[yellow]⚠ Could not verify: {msg}[/yellow]")
            rprint("[dim]Key was saved. Try restarting FreeRouter if the issue persists.[/dim]")
    except Exception as e:
        rprint(f"[red]Error saving key: {e}[/red]")


async def _test_all_providers() -> None:
    """Ping all configured providers and show results."""
    console.print(Rule("[bold cyan]Testing All Providers[/bold cyan]"))
    linked = get_linked_providers()
    configured = [defn for defn, is_set in linked if is_set or not defn.requires_auth]

    rprint(f"[dim]Pinging {len(configured)} provider(s)…[/dim]\n")
    results = await asyncio.gather(*[check_provider_reachable(defn.name) for defn in configured])

    table = Table(show_header=True, expand=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Result", justify="center")
    table.add_column("Details")

    for defn, (ok, msg) in zip(configured, results):
        result = "[green]✓ Online[/green]" if ok else "[red]✗ Offline[/red]"
        table.add_row(defn.display_name, result, msg)

    console.print(table)


# ─── Connection Guide ─────────────────────────────────────────────────────────

_GUIDES: dict[str, tuple[str, list[str]]] = {
    "Cursor IDE": (
        "A smart code editor. Connect it to FreeRouter to use free AI inside your code.",
        [
            "Open [bold]Cursor[/bold] → Settings ([cyan]Ctrl+,[/cyan])",
            "Go to the [bold]Models[/bold] tab",
            "Under [bold]OpenAI API Key[/bold]: type [cyan]any_key[/cyan]",
            "In [bold]Override OpenAI Base URL[/bold]: paste [cyan]http://127.0.0.1:4000/v1[/cyan]",
            "Click [bold]Verify[/bold]. Done!",
        ],
    ),
    "VS Code + Continue extension": (
        "Continue is a free AI coding assistant for VS Code.",
        [
            "Install the [bold]Continue[/bold] extension from the VS Code Marketplace",
            "Open the file [dim]~/.continue/config.json[/dim]",
            "Add this inside the [dim]models[/dim] list:\n"
            '  [dim]{ "title": "FreeRouter", "provider": "openai",\n'
            '    "model": "free-router/auto",\n'
            '    "apiBase": "http://127.0.0.1:4000/v1", "apiKey": "any_key" }[/dim]',
            "Save and restart VS Code.",
        ],
    ),
    "Python script": (
        "Use FreeRouter like the official OpenAI SDK in any Python script.",
        [
            "Run: [cyan]pip install openai[/cyan]",
            "Use this in your script:\n"
            "[dim]from openai import OpenAI\n"
            "client = OpenAI(base_url='http://127.0.0.1:4000/v1', api_key='any_key')\n"
            "resp = client.chat.completions.create(\n"
            "    model='free-router/auto',\n"
            "    messages=[{'role': 'user', 'content': 'Hello!'}]\n"
            ")\nprint(resp.choices[0].message.content)[/dim]",
        ],
    ),
    "Claude Code CLI": (
        "Use Anthropic's Claude Code CLI tool routed through FreeRouter.",
        [
            "In PowerShell, set the base URL before running:",
            "  [cyan]$env:ANTHROPIC_BASE_URL = 'http://127.0.0.1:4000'[/cyan]",
            "  [cyan]$env:ANTHROPIC_API_KEY  = 'any_key'[/cyan]",
            "Then run: [cyan]claude[/cyan]",
        ],
    ),
    "Any OpenAI-compatible tool": (
        "Any tool with an 'API Base URL' or 'OpenAI Base URL' setting works.",
        [
            "Set [bold]API Base URL[/bold] to: [cyan]http://127.0.0.1:4000/v1[/cyan]",
            "Set [bold]API Key[/bold] to: [cyan]any_key[/cyan]  (any non-empty value)",
            "Set [bold]Model[/bold] to: [cyan]free-router/auto[/cyan]",
            "Done! The tool will now use your free providers through FreeRouter.",
        ],
    ),
}


def _menu_connection_guide() -> None:
    """Sub-menu showing connection tutorials for each client tool."""
    console.print(Rule("[bold cyan]How to Connect Your Apps[/bold cyan]"))
    rprint("[dim]FreeRouter speaks the OpenAI API language. Point any tool to:[/dim]")
    rprint("  [bold cyan]http://127.0.0.1:4000/v1[/bold cyan]  with API key [cyan]any_key[/cyan]\n")

    names = list(_GUIDES.keys()) + ["↩️  Back"]
    idx = _pick("Choose your tool:", names)

    if idx == -1 or idx == len(_GUIDES):
        return

    tool_name = list(_GUIDES.keys())[idx]
    subtitle, steps = _GUIDES[tool_name]

    console.print()
    console.print(Panel(
        f"[dim]{subtitle}[/dim]",
        title=f"[bold cyan]Using FreeRouter with {tool_name}[/bold cyan]",
        border_style="cyan",
    ))
    for i, step in enumerate(steps, 1):
        rprint(f"  [bold green]{i}.[/bold green] {step}")
    console.print()
    rprint("[dim]💡 Make sure FreeRouter server is running before connecting your app.[/dim]")


# ─── Usage Status ─────────────────────────────────────────────────────────────

def _cmd_usage_status() -> None:
    console.print(Rule("[bold cyan]Usage & Rate Limit Status[/bold cyan]"))
    _print_providers_table()
    rprint("\n[dim]Usage is updated live from API response headers as you make requests.[/dim]")
    rprint("[dim]FreeRouter auto-switches providers at 90% usage to avoid rate limits.[/dim]\n")


# ─── Start Server ─────────────────────────────────────────────────────────────

def _cmd_start_interactive() -> None:
    linked = get_linked_providers()
    has_any = any(is_set or not defn.requires_auth for defn, is_set in linked)

    if not has_any:
        rprint("\n[yellow]⚠ No providers configured yet![/yellow]")
        rprint("[yellow]  Go to 'Manage Providers' first to add at least one key.[/yellow]\n")
        return

    rprint("\n[bold green]Starting FreeRouter…[/bold green]")
    rprint("[dim]Press Ctrl+C to stop.\n[/dim]")
    _start_server(host="0.0.0.0", port=4000, debug=False)


# ─── Config Display ───────────────────────────────────────────────────────────

def _cmd_show_config() -> None:
    config_path = get_config_path()
    rprint(f"[bold]Config:[/bold] [dim]{config_path}[/dim]")

    if config_path.exists():
        aliases = get_model_aliases()
        table = Table(title="Available Models", expand=True)
        table.add_column("Use this name in your app", style="cyan")
        table.add_column("Actual Backend Model", style="green")
        for alias, model in sorted(aliases.items()):
            table.add_row(alias, model)
        console.print(table)
        rprint(
            "\n[dim]💡 Use [bold cyan]free-router/auto[/bold cyan] to let FreeRouter "
            "choose the best model automatically.[/dim]"
        )
    else:
        rprint(f"[yellow]Config file not found at {config_path}[/yellow]")


# ─── Welcome Banner ───────────────────────────────────────────────────────────

def _show_onboarding_hint() -> None:
    linked = get_linked_providers()
    configured_count = sum(1 for _, is_set in linked if is_set)
    if configured_count == 0:
        console.print(Panel(
            "[bold yellow]👋 Welcome to FreeRouter![/bold yellow]\n\n"
            "No AI providers are linked yet. Here's how to get started:\n\n"
            "  [bold]1.[/bold] Select [bold cyan]2[/bold] → Manage Providers → Add a Provider\n"
            "  [bold]2.[/bold] Add an API key (e.g. Groq — it's free and very fast)\n"
            "  [bold]3.[/bold] Select [bold cyan]1[/bold] → Start the Server\n"
            "  [bold]4.[/bold] Connect your apps and go!\n\n"
            "[dim]All steps are guided — no technical knowledge needed.[/dim]",
            border_style="yellow",
            expand=False,
        ))


def _print_welcome_banner() -> None:
    console.print()
    console.print(Panel(
        "[bold cyan]FreeRouter[/bold cyan]  "
        f"[dim]v{__version__}[/dim]\n"
        "[dim]Routes your AI requests to the best free provider.\n"
        "Switches automatically before rate limits are reached.[/dim]",
        expand=False,
        border_style="cyan",
    ))
    _show_onboarding_hint()


# ─── Typer Commands ───────────────────────────────────────────────────────────

@app.callback()
def main(ctx: typer.Context) -> None:
    """FreeRouter — Smart AI Proxy that always prefers free models."""
    if ctx.invoked_subcommand is None:
        _interactive_menu()


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(4000, "--port", "-p", help="Port to bind to"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode"),
    ollama: bool = typer.Option(True, "--ollama/--no-ollama", help="Auto-start Ollama if not running"),
) -> None:
    """Start the FreeRouter proxy server directly (non-interactive)."""
    if config:
        os.environ["FREEROUTER_CONFIG"] = str(config)
    if ollama:
        _check_and_start_ollama()
    env_status = validate_environment()
    if not env_status["required_set"]:
        rprint("[yellow]⚠ No required API keys found. Run 'freerouter' to set them up.[/yellow]\n")
    _start_server(host=host, port=port, debug=debug, workers=workers)


@app.command("providers")
def providers_cmd(
    action: str = typer.Argument("list", help="Action: list | add <name> | test"),
    name: Optional[str] = typer.Argument(None, help="Provider name (for 'add')"),
) -> None:
    """Manage model providers (non-interactive shortcut)."""
    if action == "list":
        _print_providers_table()
    elif action == "add":
        if not name:
            rprint("[red]Usage: freerouter providers add <provider_name>[/red]")
            rprint(f"[dim]Available: {', '.join(PROVIDER_MAP.keys())}[/dim]")
            return
        defn = PROVIDER_MAP.get(name.lower())
        if not defn:
            rprint(f"[red]Unknown provider: {name}[/red]")
            rprint(f"[dim]Available: {', '.join(PROVIDER_MAP.keys())}[/dim]")
            return
        rprint(f"[cyan]Get your key at: {defn.signup_url}[/cyan]")
        api_key = typer.prompt(f"Paste your {defn.display_name} API key", hide_input=True)
        save_api_key(defn.name, api_key.strip())
        rprint(f"[green]✓ {defn.display_name} key saved![/green]")
    elif action == "test":
        asyncio.run(_test_all_providers())
    else:
        rprint(f"[red]Unknown action: {action}[/red]")
        rprint("[dim]Usage: freerouter providers [list|add|test][/dim]")


@app.command()
def env() -> None:
    """Check which provider API keys are configured."""
    _print_providers_table()


@app.command()
def version() -> None:
    """Show FreeRouter version."""
    rprint(f"[bold]FreeRouter[/bold] version [cyan]{__version__}[/cyan]")


@app.command()
def web(
    port: int = typer.Option(8080, "--port", "-p", help="Port for web dashboard"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
    proxy_port: int = typer.Option(4000, "--proxy-port", help="Port for the proxy server"),
) -> None:
    """Start the FreeRouter web dashboard.
    
    This launches a browser-based interface for managing providers,
    testing chat, and viewing usage statistics.
    """
    import uvicorn
    
    rprint(Panel(
        f"[bold cyan]FreeRouter Web Dashboard[/bold cyan]\n\n"
        f"[bold]Dashboard:[/bold] [cyan]http://{host}:{port}[/cyan]\n"
        f"[bold]Proxy API:[/bold] [cyan]http://localhost:{proxy_port}/v1[/cyan]\n\n"
        f"[dim]The dashboard provides an easy way to:\n"
        f"  • Configure API keys for providers\n"
        f"  • Test chat completions\n"
        f"  • View usage and rate limits\n"
        f"  • Export config for other tools[/dim]\n\n"
        f"[dim]Press Ctrl+C to stop.[/dim]",
        border_style="cyan",
    ))
    
    # Import the web app
    try:
        from freerouter.web.app import create_web_app
        
        # Set the proxy URL for the web app
        os.environ["FREEROUTER_PROXY_URL"] = f"http://localhost:{proxy_port}"
        
        app = create_web_app()
        
        if open_browser:
            # Open browser after a short delay
            def open_browser_delayed():
                import time
                time.sleep(1.5)
                webbrowser.open(f"http://{host}:{port}")
            
            import threading
            threading.Thread(target=open_browser_delayed, daemon=True).start()
        
        # Run the server
        uvicorn.run(app, host=host, port=port, log_level="warning")
        
    except ImportError as e:
        rprint(f"[red]Error loading web dashboard: {e}[/red]")
        rprint("[yellow]Make sure all dependencies are installed:[/yellow]")
        rprint("  pip install fastapi uvicorn")
        sys.exit(1)


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _start_server(host: str, port: int, debug: bool, workers: int = 1) -> None:
    config_path = get_config_path()
    console.print(Panel(
        f"[bold cyan]FreeRouter is starting...[/bold cyan]\n\n"
        f"[bold]Endpoint:[/bold]  [cyan]http://localhost:{port}/v1[/cyan]\n"
        f"[bold]Docs:[/bold]      [cyan]http://localhost:{port}/docs[/cyan]\n"
        f"[bold]Health:[/bold]    [cyan]http://localhost:{port}/health[/cyan]\n"
        f"[bold]Usage:[/bold]     [cyan]http://localhost:{port}/v1/usage[/cyan]\n"
        f"[bold]Config:[/bold]    [dim]{config_path}[/dim]\n\n"
        "[dim]Press Ctrl+C to stop.[/dim]",
        border_style="cyan",
    ))
    cmd = [
        sys.executable, "-m", "litellm.proxy.proxy_cli",
        "--config", str(config_path),
        "--host", host,
        "--port", str(port),
    ]
    if debug:
        cmd.append("--debug")
    if workers > 1:
        cmd.extend(["--num_workers", str(workers)])
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        rprint("\n[yellow]FreeRouter stopped.[/yellow]")
    except subprocess.CalledProcessError as e:
        rprint(f"[red]Error starting FreeRouter: {e}[/red]")
        sys.exit(1)


def _check_and_start_ollama() -> None:
    import httpx as _httpx
    try:
        resp = _httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if resp.status_code == 200:
            rprint("[green][ok][/green] Ollama is running")
            return
    except Exception:
        pass
    rprint("[yellow]Starting Ollama...[/yellow]")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS,
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        for _ in range(10):
            time.sleep(1)
            try:
                resp = _httpx.get("http://localhost:11434/api/tags", timeout=1.0)
                if resp.status_code == 200:
                    rprint("[green][ok][/green] Ollama started")
                    return
            except Exception:
                continue
        rprint("[yellow]Could not auto-start Ollama. Run 'ollama serve' separately.[/yellow]")
    except Exception:
        rprint("[yellow]Ollama not found. Install from https://ollama.ai[/yellow]")


if __name__ == "__main__":
    app()