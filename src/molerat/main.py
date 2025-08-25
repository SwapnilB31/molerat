import shutil
import os
import json
import importlib.util
import ast
import toml
from typing import List, Tuple
from molerat.config import MoleRatConfig
from typing import Optional
from rich.console import Console
from watchdog.events import (
    FileSystemEvent,
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from pathlib import Path
from importlib.metadata import PackageNotFoundError, distribution, distributions


console = Console()

DEFAULT_CONFIG_PATH = "molerat.json"
GITIGNORE_PATH = ".gitignore"
PYPROJECT_TOML_FILE = "pyproject.toml"


class MoleRatFileChangeHanlder(FileSystemEventHandler):
    __slots__ = ("source_dir", "destination", "directory", "destination_dir")

    def __init__(self, source_dir: str, destination: str, directory: str):
        self.source_dir = source_dir
        self.destination = destination
        self.directory = directory
        self.destination_dir = os.path.join(destination, directory)

    def on_any_event(self, event):
        relative_file_path = event.src_path[len(self.source_dir) + 1 :]
        destination_path = self.destination_dir + os.path.sep + relative_file_path
        if isinstance(event, FileCreatedEvent) or isinstance(event, FileModifiedEvent):
            if isinstance(event, FileCreatedEvent):
                console.log(
                    f"[green][File Created][/green] copying {event.src_path} to {destination_path}"
                )
            elif isinstance(event, FileModifiedEvent):
                console.log(
                    f"[yellow][File Modified][/yellow] syncing {event.src_path} to {destination_path}"
                )
            shutil.copy(event.src_path, destination_path)

            console.log("[blue][Info][/blue] analyzing affected dependencies")
            MoleratDistributionSync.promote_dependencies(
                event.src_path, self.destination, is_directory=False
            )

        elif isinstance(event, FileDeletedEvent):
            console.log(
                f"[red][File Deleted][/red] {event.src_path}. deleting file at destination: {destination_path}"
            )
            os.remove(destination_path)


class MoleratDistributionResolver:
    """Resolve a deduplicated list of installed distributions for packages used in a directory's .py files."""

    _cache = {}  # cache {package_name: distribution_name}
    __slots__ = ("path", "packages", "distributions", "is_directory")

    def __init__(self, path: str, is_directory: bool = True):
        """Initiate with directory path (absolute or relative)."""
        self.path = Path(path).resolve()
        self.is_directory = is_directory
        if is_directory and not self.path.is_dir():
            raise NotADirectoryError(f"{self.path} is not a directory.")
        self.packages = set()
        self.distributions = set()

    def resolve(self):
        """Resolve installed distributions for packages used in directory."""
        if self.is_directory:
            for py_file in self.path.rglob("*.py"):
                self._parse_file(py_file)
        else:
            self._parse_file(self.path)

        for pkg in self.packages:
            dist = self._find_distribution_for_package(pkg)
            if dist:
                self.distributions.add(dist)

        return sorted(self.distributions)

    def _parse_file(self, file: Path):
        """Parse a .py file and extract top-level package names from import statements."""
        with file.open("r", encoding="utf-8") as f:
            node = ast.parse(f.read(), filename=str(file))

        for elem in ast.walk(node):
            if isinstance(elem, ast.Import):
                self.packages.add(elem.names[0].name.split(".")[0])
            elif isinstance(elem, ast.ImportFrom):
                if elem.level == 0 and elem.module:
                    base = elem.module.split(".")[0]
                    self.packages.add(base)

    @classmethod
    def _find_distribution_for_package(cls, import_name):
        """Resolve the installed distribution for a given package, with cache."""
        if import_name in cls._cache:
            return cls._cache[import_name]

        spec = importlib.util.find_spec(import_name)
        if not spec or not spec.origin:
            cls._cache[import_name] = None
            return None

        package_file = Path(spec.origin).resolve()
        is_package = package_file.is_dir()

        for dist in importlib.metadata.distributions():
            for file in dist.files or []:
                file_path = (Path(dist.locate_file(file))).resolve()

                if is_package and file_path == package_file:
                    cls._cache[import_name] = dist.metadata["Name"]
                    return dist.metadata["Name"]

                if not is_package and file_path == package_file:
                    cls._cache[import_name] = dist.metadata["Name"]
                    return dist.metadata["Name"]

        cls._cache[import_name] = None
        return None


class MoleratDistributionSync:
    @staticmethod
    def append_to_gitignore(directory: str, cwd: str):
        """Add directory to .gitignore if it's not already present."""
        if os.path.exists(GITIGNORE_PATH) and os.path.isfile(GITIGNORE_PATH):
            relative_directory = directory[len(cwd) + 1 :]  # path relative to cwd
            with open(GITIGNORE_PATH, "r+") as f:
                text_content = f.read()
                if f"{relative_directory}/" not in text_content:
                    console.log(
                        f"[blue][Info][/blue] Adding {relative_directory}/ to .gitignore."
                    )
                    f.write(
                        f'\n\n# directory "{relative_directory}/" added to {GITIGNORE_PATH} by molerat'
                    )
                    f.write(f"\n{relative_directory}/")

    @staticmethod
    def _load_toml_file(path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return toml.loads(f.read())

    @staticmethod
    def _update_toml_file(path, toml_obj):
        """Save the updated TOML back to disk."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(toml.dumps(toml_obj))

    @staticmethod
    def _find_installable_deps(used: List[str], base_toml: dict):
        """Resolve which used deps are present in base toml and are installable or dev."""
        installed: List[str] = base_toml.get("project", {}).get("dependencies", [])
        dev: List[str] = base_toml.get("dependency-groups", {}).get("dev", [])

        installable: List[str] = []

        for dep in used:
            for i_dep in installed:
                if i_dep.startswith(dep):
                    installable.append(i_dep)

        installable_dev: List[str] = []

        for dep in used:
            for i_dep in dev:
                if i_dep.startswith(dep):
                    installable_dev.append(i_dep)

        return installable, installable_dev

    @staticmethod
    def promote_dependencies(
        watch_dir: str, destination_dir: str, is_directory: bool = True
    ):
        # print(f"promote_dependencies called with {watch_dir=}, {destination_dir=}, {is_directory=}")
        """Analyze watch directory's imports and promote to destination's pyproject.toml."""
        if not (
            os.path.exists(PYPROJECT_TOML_FILE) and os.path.isfile(PYPROJECT_TOML_FILE)
        ):
            print("root doesn't contain pyproject.toml")
            return

        workspace_pyproject = os.path.join(destination_dir, PYPROJECT_TOML_FILE)
        if not (
            os.path.exists(workspace_pyproject) and os.path.isfile(workspace_pyproject)
        ):
            print("workspace doesn't contain pyproject.toml")
            return

        console.log(
            f"[blue][Info][/blue] Workspace/Sub-Project detected at {destination_dir}{os.path.sep}. Promoting dependencies used by {watch_dir}{os.path.sep}*.py to {workspace_pyproject}"
        )
        console.log(
            f"[blue][Info][/blue] Promoting deps from {watch_dir} to {workspace_pyproject}"
        )

        resolver = MoleratDistributionResolver(watch_dir, is_directory)
        used_deps = resolver.resolve()

        base_toml = MoleratDistributionSync._load_toml_file(PYPROJECT_TOML_FILE)
        workspace_toml = MoleratDistributionSync._load_toml_file(workspace_pyproject)

        installed, dev = MoleratDistributionSync._find_installable_deps(
            used_deps, base_toml
        )

        if installed:
            if "project" not in workspace_toml:
                workspace_toml["project"] = {}
            if 'dependencies' not in workspace_toml['project']:
                workspace_toml["project"]["dependencies"] = []

            for dep in installed:
                if dep not in workspace_toml["project"]["dependencies"]:
                    workspace_toml["project"]["dependencies"].append(dep)

            console.log(
                f"[green][Success][/green] {len(installed)} deps promoted to {workspace_pyproject}."
            )

        if dev:
            if "dependency-groups" not in workspace_toml:
                workspace_toml["dependency-groups"] = {}
            if 'dev' not in workspace_toml['dependency-groups']:
                workspace_toml["dependency-groups"]["dev"] = []

            for dep in dev:
                if dep not in workspace_toml["dependency-groups"]["dev"]:
                    workspace_toml["dependency-groups"]["dev"].append(dep)

            console.log(
                f"[green][Success][/green] {len(dev)} dev deps promoted to {workspace_pyproject}."
            )

        MoleratDistributionSync._update_toml_file(workspace_pyproject, workspace_toml)


class MoleRatFileSync:
    config: Optional[MoleRatConfig]
    config_path: str
    no_watch: bool

    def __init__(
        self,
        *,
        no_watch: bool = False,
        config_path: Optional[str] = None,
        config: Optional[MoleRatConfig] = None,
    ):
        self.config_path = config_path if config_path else DEFAULT_CONFIG_PATH
        self.config = config
        self.no_watch = no_watch

    def _init_config(self):
        if os.path.exists(self.config_path) and os.path.isfile(self.config_path):
            console.log(
                f"[cyan][Init][/cyan] reading config file at {self.config_path}"
            )
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_json = f.read()
                config_dict = json.loads(config_json)
                self.config = MoleRatConfig(**config_dict)
                console.log("[cyan][Init][/cyan] config successfully loaded")

    def copy_watched_folder_to_dest(self):
        console.log(
            "[cyan][Startup Sync][/cyan] copying watched folders to configured destinations"
        )

        cwd = os.getcwd()
        sep = os.path.sep

        for sync_item in self.config.sync:
            source = cwd + sep + sync_item.watch
            source_dir_name = source.split(sep)[-1]
            exclude_patterns = sync_item.exclude or []

            console.log(
                f"[cyan][Startup Sync][/cyan] copying files from watched folder: {source}"
            )

            if not os.path.exists(source) or not os.path.isdir(source):
                console.log(
                    f"🚫[yellow][Invalid Path][/yellow] cannot watch [b]{source}[/b] as it is either not a folder or is not a valida path. [red]aborting![/red]"
                )

            for destination in sync_item.destinations:
                dest_path = cwd + sep + destination.path
                entry_point = (
                    f"{cwd}{sep}{destination.entrypoint}"
                    if destination.entrypoint
                    else None
                )
                directory = (
                    f"{cwd}{sep}{destination.path}{sep}{destination.directory}"
                    if destination.directory
                    else f"{cwd}{sep}{destination}{sep}{source_dir_name}"
                )

                if (
                    os.path.exists(dest_path) == False
                    or os.path.isdir(dest_path) == False
                ):
                    console.log(
                        f"[yellow][Invalid Path] ⚠[/yellow] {dest_path} is not a valid destination!. skipping initializing"
                    )
                    continue

                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    console.log(
                        f"[green][Directory Created][/green]destination directory successfully created {directory}"
                    )
                else:
                    shutil.rmtree(directory)
                    os.mkdir(directory)
                    console.log(
                        f"[cyan][Cleanup][/cyan] existing directory {directory} cleaned"
                    )

                shutil.copytree(
                    source,
                    directory,
                    ignore_dangling_symlinks=True,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(*exclude_patterns),
                )
                console.log(
                    f"[green][Sync Successful][/green] contents of the watched directory {source} successfuly copied to {directory}"
                )

                MoleratDistributionSync.append_to_gitignore(directory, cwd)
                MoleratDistributionSync.promote_dependencies(
                    sync_item.watch, destination.path
                )

    def run(self):
        console.log("[green][Init] [b]molerat[/b][/green] is starting up")
        if not self.config:
            self._init_config()
        if self.config:
            self.copy_watched_folder_to_dest()

            if self.no_watch:
                console.log("[cyan][Exit][/cyan] Exiting. --no-watch flag was enabled")
                return

            console.log("[cyan][Watch][/cyan] watching files for changes")
            observers: List[BaseObserver] = []

            cwd = os.getcwd()
            sep = os.path.sep

            for sync_item in self.config.sync:
                source_dir = cwd + sep + sync_item.watch
                source_dir_name = source_dir.split(sep)[-1]

                for destination in sync_item.destinations:
                    dest_path = cwd + sep + destination.path
                    dest_dir = (
                        f"{destination.directory}"
                        if destination.directory
                        else f"{source_dir_name}"
                    )
                    event_handler = MoleRatFileChangeHanlder(
                        source_dir, dest_path, dest_dir
                    )
                    observer = Observer()
                    observer.schedule(
                        event_handler,
                        source_dir,
                        recursive=True,
                        event_filter=[
                            FileCreatedEvent,
                            FileModifiedEvent,
                            FileDeletedEvent,
                        ],
                    )

                    observers.append(observer)

                    console.log(
                        f"[cyan][Watch][/cyan] Watching for changes at {source_dir}. Sync setup to {dest_dir}"
                    )

                for obs in observers:
                    obs.start()

                try:
                    while True:
                        continue
                except KeyboardInterrupt:
                    console.log(
                        "\n[yellow][Interrupt Ctrl+C] keyboard Interrupt detected[/yellow]. shutting down..."
                    )
                    for obs in observers:
                        obs.stop()

                for obs in observers:
                    obs.join()

        else:
            console.log(
                """
❌ [bold yellow]Aborting![/bold yellow] config not defined. configure [b]molerat[/b] either by:
1. create a molerat.json file in the project root directory
2. expicitly pass the path of the configuration file
3. Initialize the MoleRatFileSync object with a config object
"""
            )


if __name__ == "__main__":
    sync = MoleRatFileSync()
    sync.run()
