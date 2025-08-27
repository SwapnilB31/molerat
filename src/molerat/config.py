from pydantic import BaseModel, Field
from typing import List, Optional


class MoleRatConfig(BaseModel):
    sync: List["Sync"]


class Sync(BaseModel):
    watch: str
    exclude: Optional[List[str]] = Field(default_factory=list)
    destinations: List["Destination"]


class Destination(BaseModel):
    path: str
    entrypoint: Optional[str] = None
    directory: Optional[str] = None


if __name__ == "__main__":
    config = {
        "sync": [
            {
                "watch": "shared",
                "exclude": ["__pycache__"],
                "destinations": [
                    {
                        "path": "module_a",
                        "entrypoint": "module_a/mod.py",
                        "directory": "app/shared",
                    }
                ],
            }
        ]
    }

    validated = MoleRatConfig(**config)

    print(validated)
