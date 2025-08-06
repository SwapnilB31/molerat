# Molerat: Tree Shaker Moudle
The Tree Shaker module in molerat intends to prune out dependencies that are not referenced by a file called the entrypoint. Entrypoint is the file that contains the main method, and the execution of all code begins from the main function.

The idea behind tree shaking is to created a dependency graph of imports from the entrypoint going back to any files/modules, the code defined wherein, is directly or indirectly referenced by the entrypoint.

# Example
We have a file structure like this

```
project-root/
├── main.py
├── lib_a/
│   └── __init__.py
├── lib_b.py
├── lib_c.py
├── lib_d/
│   └── __init__.py
├── lib_e.py
└── lib_f/
    ├── __init__.py
    └── util.py
```
And the code looks like this
```python
# main.py
import lib_a
from lib_b import func_ba

# lib_a/__init__.py
import lib_c as lc

# lib_b.py
from lib_d import func_da, func_db
import lib_e

# lib_c.py
def func_ca():
    print("func_ca")

def func_cb():
    print("func_cb")

# lib_d/__init__.py
def func_da():
    print("func_da")

def func_db():
    print("func_db")

# lib_e.py
import lib_f.util as lf_util

def func_ea():
    print("func_ea")

# lib_f/util.py
def func_fa():
    print("func_fa")

```

We would have the following dependency graph

```
 +----------+       +--------------+          +-------------+
 | main.py  | ------|     lib-a    | -------- |   lib-c     |
 +----------+ \     +--------------+          +-------------+
               \
                \   +--------------+          +---------------+
                 +--| lib_b        | -------- |  lib_d        |
                    +--------------+ \        +---------------+
                                      \
                                       \      +----------+        +---------------+
                                        +---- |   lib_e  | ------ |   lib_f.util  |
                                              +----------+        +---------------+
```                      

The job of the treeshaker is:
- Create the dependency graph
- prune all unused imports
    - if no imports from a file is used, delete it from the distribution
    - if some imports are used, rewrite the file to only have the used implementations
    - rewrite the original folder only if the user wants to 

# Approach
- Model this as a graph data structure, even though it can be viewed as a tree
- There are two kinds of Nodes in this graph - Root (Entry-Point) or Dependency
- Each node will have
    - a path: relative and absolute that will be used by the tree shaker to parse the asts of the dependency
    - used_imports: this will be passed to the dependency, which will use it to prune unused references
    - referenced_constructs: A list of constructs that are referenced by a node that comes before the current file in the dependency graph. The refrenced_constructs will consider four types of nodes:
        1. FunctionDef: A function definition
        2. ClassDef: A class definition
        3. Assign: Assignment to a variable
        4. AnnAsign: An Assignment that includes type annotation

        The referenced imports list won't be able to distinguish between Assign and AnnAsign, so the analyzer will prune both Assign and AnnAssign nodes at the top level by matching names

- When a node is processed, used imports would need to be listed, so that it can be passed down to the dependency node.
- This is how it will be done
    - Parse the body recursively to first resolve all top-level Imports that come from local modules or packages, not installed dependencies
    -Then create a symbol table that maps names, to an import
    - Call a walk function that takes in the symbol table, level (0 for top level and it increases with nesting) and parent_class_name (optional) and then follows the nodes using BFS.
    - It parses the following types of nodes
     - Assign
     - AnnAssign
     - FunctionDef
     - ClassDef
     - If
     - While
     - Match
       - MatchValue
       - MatchOr
       - MatchAs

    Except for Assign and AnnAssign all are traversed recursively.
    With the symbol table upated to reference local variables inside the local scope for the walk, the walk is called with a new symbol table, level and the parent_class_name parameter

    - When walking recursively, if an Assign or Call is found and it references a named import from the symbol table we mark it as used and move ahead

    - Once the entire graph is created, we start dumping the dependency graph into the chosed dist directory specified by the user. If they chose to overwrite_source, we rename the source_directory as <source>.bak and create a new directory with name <source>. Then we traverse the graph and unparse the dependency graph there. We do this by
        - Travelling from the root
        - get the AST
        - remove unused imports
        - remove unreferenced nodes at the top level
        - if no refrences from a file are used, it is not written back

# Implementation Plan for Molerat Tree Shaker Module

## 1. Parse Entrypoint and Build Dependency Graph
- Identify the entrypoint (main file).
- Parse the entrypoint's AST to extract all local imports (modules/packages in the project).
- For each import, recursively parse the imported file/module and repeat the process.
- Build a graph structure where each node represents a file/module and edges represent import relationships.

## 2. Symbol Table Construction
- For each file/module, build a symbol table mapping imported names to their source modules.
- Track all top-level constructs: FunctionDef, ClassDef, Assign, AnnAssign.
- For each node, record referenced constructs (functions, classes, variables) that are used by the parent node.

## 3. Reference Analysis (Mark-and-Sweep)
- Walk the AST of each file/module, marking constructs that are referenced by the entrypoint or by other referenced constructs.
- For each Assign or Call node, check if it references a named import from the symbol table; if so, mark it as used.
- Propagate usage information down the dependency graph.

## 4. Prune Unused Imports and Constructs
- For each file/module, remove unused imports and top-level constructs that are not referenced.
- If a file/module has no used imports or constructs, exclude it from the output distribution.
- If only some constructs are used, rewrite the file to include only those.

## 5. Output Generation
- If the user chooses to overwrite the source, rename the original source directory as <source>.bak and create a new directory for the pruned code.
- Traverse the dependency graph and unparse the pruned ASTs into the output directory.
- Ensure that only used files and constructs are included in the final distribution.

## 6. CLI/Configuration Support
- Allow the user to specify the entrypoint, output directory, and whether to overwrite the source.
- Provide options for dry-run, verbose logging, and reporting of pruned files/constructs.

## 7. Testing and Validation
- Write tests to ensure that the pruned code runs correctly and that unused code is removed.
- Validate that the dependency graph is correct and that all referenced constructs are preserved.

# Detailed Implementation Plan for Molerat Tree Shaker Module

## 1. Parse Entrypoint and Build Dependency Graph
- **Class:** `DependencyGraphBuilder`
- **Methods:**
    - `build(entrypoint_path: str) -> DependencyGraph`
    - `parse_imports(file_path: str) -> List[ImportInfo]`
- **Algorithm:**
    1. Start from the entrypoint file (e.g., `main.py`).
    2. Parse its AST and extract all local imports (ignore standard library and installed packages).
    3. For each import, resolve its file path (handle both modules and packages).
    4. Recursively repeat the process for each imported file/module, avoiding cycles.
    5. Construct a graph where each node is a file/module and edges represent import relationships.
    6. Store metadata for each node: file path, imported names, and parent/child relationships.

## 2. Symbol Table Construction
- **Class:** `SymbolTableBuilder`
- **Methods:**
    - `build(file_path: str) -> SymbolTable`
    - `extract_top_level_symbols(tree: ast.AST) -> Dict[str, SymbolInfo]`
- **Algorithm:**
    1. For each file/module, parse the AST.
    2. Collect all top-level constructs: `FunctionDef`, `ClassDef`, `Assign`, `AnnAssign`.
    3. Map each symbol name to its definition and source module.
    4. Track imported names and their origins for later reference analysis.
    5. Store symbol tables per file/module for fast lookup during analysis.

## 3. Reference Analysis (Mark-and-Sweep)
- **Class:** `ReferenceAnalyzer`
- **Methods:**
    - `analyze(graph: DependencyGraph, symbol_tables: Dict[str, SymbolTable]) -> None`
    - `mark_used_symbols(node: GraphNode, used_symbols: Set[str]) -> None`
- **Algorithm:**
    1. Start from the entrypoint node and mark all directly used constructs as 'used'.
    2. Traverse the AST of each file/module, looking for references to imported or locally defined symbols.
    3. For each reference (e.g., in `Assign`, `Call`, `Attribute`), check if it matches a symbol in the symbol table.
    4. Mark referenced constructs as 'used' and propagate usage to dependencies.
    5. Repeat recursively until no new symbols are marked as used.

## 4. Prune Unused Imports and Constructs
- **Class:** `Pruner`
- **Methods:**
    - `prune(file_path: str, used_symbols: Set[str]) -> ast.AST`
    - `remove_unused_imports(tree: ast.AST, used_imports: Set[str]) -> ast.AST`
    - `remove_unused_defs(tree: ast.AST, used_symbols: Set[str]) -> ast.AST`
- **Algorithm:**
    1. For each file/module, walk its AST.
    2. Remove import statements that are not in the set of used imports.
    3. Remove top-level constructs (`FunctionDef`, `ClassDef`, `Assign`, `AnnAssign`) that are not marked as used.
    4. If a file/module has no used constructs, exclude it from the output.
    5. Optionally, format or clean up the resulting AST for readability.

## 5. Output Generation
- **Class:** `OutputWriter`
- **Methods:**
    - `write_pruned_files(graph: DependencyGraph, output_dir: str) -> None`
    - `backup_and_overwrite_source(source_dir: str) -> None`
- **Algorithm:**
    1. If overwriting source, rename the original directory as `<source>.bak` and create a new directory for output.
    2. For each node in the dependency graph, unparse the pruned AST and write it to the output directory, preserving structure.
    3. Only write files that have used constructs.
    4. Ensure all import paths are still valid in the output.

## 6. CLI/Configuration Support
- **Class:** `TreeShakerCLI`
- **Methods:**
    - `parse_args()`
    - `run()`
- **Algorithm:**
    1. Parse command-line arguments for entrypoint, output directory, overwrite flag, dry-run, and verbosity.
    2. Pass configuration to the main tree-shaking workflow.
    3. Optionally, print a summary of pruned files and constructs.

## 7. Testing and Validation
- **Class:** `TreeShakerTestSuite`
- **Methods:**
    - `test_pruned_code_runs()`
    - `test_unused_code_removed()`
    - `test_dependency_graph_correct()`
- **Algorithm:**
    1. Write unit and integration tests to ensure correctness.
    2. Validate that pruned code executes as expected.
    3. Check that all unused code is removed and all used code is preserved.
    4. Optionally, provide a test harness for user projects.

---
