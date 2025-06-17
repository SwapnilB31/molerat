from pydantic import BaseModel
from typing import List, Optional


class MoleRatConfig(BaseModel):
    sync: List["Sync"]


class Sync(BaseModel):
    watch: str
    exclude: Optional[List[str]]
    destinations: List["Destination"]


class Destination(BaseModel):
    path: str
    entrypoint: Optional[str]
    directory: Optional[str]
