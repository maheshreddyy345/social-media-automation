import os
from pydantic import BaseModel
from typing import List

class CurationResult(BaseModel):
    headline: str
    key_fact: str
    primary_politician_involved: str
    url: str

class ThreadResult(BaseModel):
    tweets: List[str]
    media_path: str = ""
