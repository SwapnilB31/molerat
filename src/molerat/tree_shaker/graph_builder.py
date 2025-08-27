import ast
import os
from typing import List
from dataclasses import dataclass
from pathlib import Path


class PythonFileNode:
    pass


@dataclass
class RootNode(PythonFileNode):
    retaive_path: str
    absolute_path: str
    used_imports: List[str]
    dependencies: List["DependencyNode"]


@dataclass
class DependencyNode(PythonFileNode):
    relative_path: str
    absolute_path: str
    referenced_constructs: List[str]
    used_imports: List[str]
    dependencies: List["DependencyNode"]


class DependencyGraph:
    __slots__ = "root"

    def __init__(self, root: RootNode):
        self.root = root


def build_dependency_graph(entry_point: Path):
    pass
