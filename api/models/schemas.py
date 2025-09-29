from pydantic import BaseModel
from typing import List, Dict, Any

class OutlineItem(BaseModel):
    idx: int
    heading: str
    brief: str

class Citation(BaseModel):
    url: str
    title: str

class ParagraphOut(BaseModel):
    draftMd: str
    citations: Dict[int, Citation]
    quality: float
