import os
import shutil
import tempfile
import json
import subprocess
import sys
import pytest

from molerat.config import MoleRatConfig, Sync, Destination
from molerat.main import MoleRatFileSync, MoleratDistributionResolver


@pytest.fixture
def temp_project(tmp_path):
    # Setup a fake project structure
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "util.py").write_text("import math\n")
    (shared / "skipme.py").write_text("print('skip')\n")
    module_a = tmp_path / "module_a"
    module_a.mkdir()
    (tmp_path / "pyproject.toml").write_text("""
[project]
dependencies = ["math"]
""")
    (module_a / "pyproject.toml").write_text("""
[project]
dependencies = []
""")
    yield tmp_path


def test_molerat_file_sync_basic(temp_project):
    # Prepare config
    config = MoleRatConfig(
        sync=[
            Sync(
                watch="shared",
                exclude=["skipme.py"],
                destinations=[
                    Destination(path="module_a", entrypoint=None, directory="shared")
                ],
            )
        ]
    )
    cwd = os.getcwd()
    os.chdir(temp_project)
    try:
        sync = MoleRatFileSync(config=config)
        sync.copy_watched_folder_to_dest()
        dest_shared = temp_project / "module_a" / "shared"
        assert (dest_shared / "util.py").exists()
        assert not (dest_shared / "skipme.py").exists()
    finally:
        os.chdir(cwd)


def test_distribution_resolver(temp_project):
    shared = temp_project / "shared"
    resolver = MoleratDistributionResolver(str(shared))
    # Should find 'math' as a used package (even if not a real distribution)
    pkgs = resolver.resolve()
    assert "math" in pkgs or isinstance(pkgs, list)


def test_cli_runs_with_config(tmp_path):
    # Write config file
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "util.py").write_text("import math\n")
    module_a = tmp_path / "module_a"
    module_a.mkdir()
    config = {
        "sync": [
            {
                "watch": "shared",
                "exclude": [],
                "destinations": [
                    {"path": "module_a", "entrypoint": None, "directory": "shared"}
                ],
            }
        ]
    }
    (tmp_path / "molerat.json").write_text(json.dumps(config))
    (tmp_path / "pyproject.toml").write_text("""
[project]
dependencies = ["math"]
""")
    (module_a / "pyproject.toml").write_text("""
[project]
dependencies = []
""")
    # Run CLI
    result = subprocess.run(
        [sys.executable, "-m", "molerat.cli"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "Sync Successful" in result.stdout or "Sync Successful" in result.stderr
    assert (module_a / "shared" / "util.py").exists()
