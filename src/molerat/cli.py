import argparse
import sys
import json
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from molerat.main import MoleRatFileSync
from molerat.config import MoleRatConfig, Sync, Destination

console = Console()


def print_help():
    console.print(
        "[bold green]molerat[/bold green] - [cyan]Sync code and promote dependencies across Python monorepos.[/cyan]\n"
        "\n[bold]Usage:[/bold]\n"
        "  python -m molerat.cli [OPTIONS]\n"
        "\n[bold]Options:[/bold]\n"
        "  [yellow]--watch[/yellow]         Source directory to watch (can be specified multiple times)\n"
        "  [yellow]--destination[/yellow]   Destination directory (can be specified multiple times, must match --watch order)\n"
        "  [yellow]--entrypoint[/yellow]    Entrypoint file for destination (optional, can be specified multiple times)\n"
        "  [yellow]--directory[/yellow]     Subdirectory in destination to sync into (optional, can be specified multiple times)\n"
        "  [yellow]--exclude[/yellow]       Exclude pattern for files/dirs (can be specified multiple times, applies to corresponding --watch)\n"
        "  [yellow]--config[/yellow]        Path to molerat.json config file (optional)\n"
        "  [yellow]-h, --help[/yellow]      Show this help message and exit\n"
        "\n[dim]If no CLI options are provided, molerat will look for a molerat.json config file in the current directory.[/dim]\n"
        "\n[dim]The --exclude option allows you to specify patterns (e.g. --exclude __pycache__) to ignore during sync.[/dim]\n"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="molerat: Sync code and promote dependencies across Python monorepos.",
        add_help=False,
    )
    parser.add_argument(
        "--watch", action="append", help="Source directory to watch", required=False
    )
    parser.add_argument(
        "--destination", action="append", help="Destination directory", required=False
    )
    parser.add_argument(
        "--entrypoint",
        action="append",
        help="Entrypoint file for destination",
        required=False,
    )
    parser.add_argument(
        "--directory",
        action="append",
        help="Subdirectory in destination to sync into",
        required=False,
    )
    parser.add_argument(
        "--exclude",
        action="append",
        help="Exclude pattern for files/dirs (can be specified multiple times, applies to corresponding --watch)",
        required=False,
    )
    parser.add_argument(
        "--config", type=str, help="Path to molerat.json config file", required=False
    )
    parser.add_argument("-h", "--help", action="store_true", help="Show help and exit")
    return parser.parse_args()


def main():
    args = parse_args()
    DEFAULT_CONFIG_PATH = "molerat.json"

    if args.help:
        print_help()
        return

    # 1. If --config is provided, use it
    if args.config:
        sync = MoleRatFileSync(config_path=args.config)
        sync.run()
        return

    # 2. If default config exists, use it
    if not any([args.watch, args.destination, args.entrypoint]) and os.path.exists(
        DEFAULT_CONFIG_PATH
    ):
        sync = MoleRatFileSync(config_path=DEFAULT_CONFIG_PATH)
        sync.run()
        return

    # 3. Only if no config file, require CLI args
    if not args.watch or not args.destination:
        console.print(
            "[red]Error: --watch and --destination are required unless a config file is provided.[/red]"
        )
        print_help()
        sys.exit(1)

    # Support multiple sync blocks if multiple --watch are given
    sync_blocks = []
    for idx, watch_dir in enumerate(args.watch):
        dests = []
        # Support multiple destinations per watch if user repeats --destination, --entrypoint, --directory
        dest_dir = (
            args.destination[idx]
            if idx < len(args.destination)
            else args.destination[-1]
        )
        entrypoint = (
            args.entrypoint[idx]
            if args.entrypoint and idx < len(args.entrypoint)
            else None
        )
        directory = (
            args.directory[idx]
            if args.directory and idx < len(args.directory)
            else None
        )
        exclude = (
            [args.exclude[idx]] if args.exclude and idx < len(args.exclude) else None
        )
        dests.append(
            Destination(path=dest_dir, entrypoint=entrypoint, directory=directory)
        )
        sync_blocks.append(Sync(watch=watch_dir, exclude=exclude, destinations=dests))

    config = MoleRatConfig(sync=sync_blocks)
    sync = MoleRatFileSync(config=config)
    sync.run()


if __name__ == "__main__":
    main()
