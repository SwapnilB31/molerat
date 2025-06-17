# molerat

**molerat** is a Python utility for synchronizing code between directories and promoting dependencies to sub-projects. It is especially useful for monorepos or multi-module Python projects where shared code and dependencies need to be kept in sync across multiple modules or packages.

Molerat supports syncing across multiple sources and destinations, making it easy to manage shared code in complex monorepo setups. 

> **Note:** Syncing only works when the code in shared folders only references code from within the shared folder itself. Imports like `import ..app as a` or any relative import that escapes the shared folder will not work.

## Features

- **Automatic Folder Sync:** Watches specified source directories and syncs their contents to one or more destination directories.
- **Dependency Promotion:** Analyzes Python imports in the watched directories and promotes required dependencies to the destination's `pyproject.toml`.
- **.gitignore Management:** Automatically adds synced directories to `.gitignore` to avoid accidental commits.
- **Rich Logging:** Uses [rich](https://github.com/Textualize/rich) for colorful and informative console output.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/SwapnilB31/molerat.git
```

## Usage

1. **Create a `molerat.json` config file** in your project root:

    ```json
    {
        "sync": [
            {
                "watch": "shared",
                "exclude": ["__pycache__"],  // Exclude patterns (optional)
                "destinations": [
                    {
                        "path": "module_a",
                        "entrypoint": "module_a/mod.py",
                        "directory": "shared"
                    }
                ]
            }
        ]
    }
    ```

    - The `exclude` option allows you to specify file or directory patterns (e.g. `["__pycache__"]`) to ignore during sync.

2. **Run molerat:**

    ```bash
    python -m molerat.cli
    ```

    - On startup, molerat will copy the contents of each watched folder to the configured destinations.
    - It will then watch for file changes and keep the destinations in sync.
    - Dependencies used in the watched code will be promoted to the destination's `pyproject.toml`.

> **Note:** Dependency promotion only works in projects using PEP 517 build systems such as [uv](https://github.com/astral-sh/uv), [poetry](https://python-poetry.org/), etc.

## Example Scenarios

### 1. Sharing Code Across Modules

Suppose you have a `shared` directory with utility code used by both `module_a` and `module_b`. Configure molerat to sync `shared` into both modules:

```json
{
    "sync": [
        {
            "watch": "shared",
            "destinations": [
                { "path": "module_a", "directory": "shared" },
                { "path": "module_b", "directory": "shared" }
            ]
        }
    ]
}
```

### 2. Promoting Only Used Dependencies

If `shared` uses `requests` and `numpy`, but `module_a` only uses `requests`, molerat will only promote `requests` to `module_a/pyproject.toml` if that's all that's imported.

### 3. Keeping Synced Folders Out of Git

molerat will automatically add synced directories to `.gitignore` to prevent accidental commits of generated or synced code.

## Example: CDK Monorepo with Lambdas and ECS Tasks

Suppose you have a monorepo structured as follows:

```
my-cdk-monorepo/
├── cdk/
│   └── stack.py
├── src/
│   ├── lambdas/
│   │   ├── lambda_a/
│   │   │   ├── app.py
│   │   │   └── Dockerfile
│   │   └── lambda_b/
│   │       ├── app.py
│   │       └── Dockerfile
│   └── ecs/
│       ├── task_a/
│       │   ├── main.py
│       │   └── Dockerfile
│       └── task_b/
│           ├── main.py
│           └── Dockerfile
├── shared/
│   └── utils.py
├── pyproject.toml
└── molerat.json
```

Your `cdk/stack.py` might use [aws_cdk.aws_lambda.DockerImageFunction](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/DockerImageFunction.html) or [aws_cdk.aws_ecs.DockerImageAsset](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/DockerImageAsset.html):

```python
# cdk/stack.py
from aws_cdk import aws_lambda, aws_ecs, core

class MyStack(core.Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        lambda_fn = aws_lambda.DockerImageFunction(
            self, "LambdaA",
            code=aws_lambda.DockerImageCode.from_image_asset("../src/lambdas/lambda_a")
        )

        ecs_task = aws_ecs.DockerImageAsset(
            self, "TaskAImage",
            directory="../src/ecs/task_a"
        )
```

You can configure `molerat.json` to sync the `shared` folder into each lambda and ECS task:

```json
{
    "sync": [
        {
            "watch": "shared",
            "destinations": [
                { "path": "src/lambdas/lambda_a", "directory": "shared", "entrypoint": "src/lambdas/lambda_a/app.py" },
                { "path": "src/lambdas/lambda_b", "directory": "shared", "entrypoint": "src/lambdas/lambda_b/app.py" },
                { "path": "src/ecs/task_a", "directory": "shared", "entrypoint": "src/ecs/task_a/main.py" },
                { "path": "src/ecs/task_b", "directory": "shared", "entrypoint": "src/ecs/task_b/main.py" }
            ]
        }
    ]
}
```

### Entrypoint and Tree Shaking

The `entrypoint` config is used by an upcoming tree shaker module in molerat. This module will perform dead code elimination and tree shaking inside the synced `shared` folder, ensuring only the code actually used by each sub-project/workspace is included in the final package.

## Concepts

- **Sync Configuration:** Define which folders to watch and where to sync them using a `molerat.json` config file.
- **Entrypoint & Directory:** Specify entrypoints and subdirectories for more granular control over sync destinations.
- **Dependency Promotion:** Ensures that only the dependencies actually used in the synced code are promoted to the destination's `pyproject.toml`.

## Configuration Reference

- **watch:** Source directory to watch.
- **exclude:** (Optional) List of file or directory patterns to exclude from syncing (e.g. `["__pycache__"]`).
- **destinations:** List of destination objects.
    - **path:** Destination directory.
    - **entrypoint:** (Optional) Entrypoint file in the destination.
    - **directory:** (Optional) Subdirectory in the destination to sync into.

## License

MIT License

---

*Happy syncing!*
