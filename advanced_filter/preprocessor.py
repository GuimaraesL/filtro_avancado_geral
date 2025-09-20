from __future__ import annotations
from typing import List, Tuple
from unidecode import unidecode

def normalize(text: str, lowercase: bool = True, strip_accents: bool = True) -> str:
    if strip_accents:
        text = unidecode(text)
    if lowercase:
        text = text.lower()
    return text

def simple_tokenize(text: str) -> List[str]:
    return text.split()

def tokens_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    tokens = []
    idx = 0
    for part in text.split():
        start = text.find(part, idx)
        end = start + len(part)
        tokens.append((part, start, end))
        idx = end
    return tokens

def sentences(text: str) -> List[Tuple[int,int]]:
    spans = []
    start = 0
    for i, ch in enumerate(text):
        if ch in ".!?":
            spans.append((start, i+1))
            start = i+1
    if start < len(text):
        spans.append((start, len(text)))
    return spans
