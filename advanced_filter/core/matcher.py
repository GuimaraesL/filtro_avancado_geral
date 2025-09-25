from __future__ import annotations
from typing import List, Tuple, Dict, Iterable
import regex as re

Span = Tuple[int,int]

def _compile(pattern: str, kind: str) -> re.Pattern:
    if kind == "literal":
        esc = re.escape(pattern)
        return re.compile(rf"\b{esc}\b", flags=re.IGNORECASE)
    elif kind == "phrase":
        esc = re.escape(pattern)
        return re.compile(esc, flags=re.IGNORECASE)
    elif kind == "regex":
        return re.compile(pattern, flags=re.IGNORECASE)
    else:
        raise ValueError(f"Tipo de padrão inválido: {kind}")

class PatternIndex:
    def __init__(self, specs: Iterable[dict]):
        self.specs = list(specs)
        self.compiled: List[Tuple[re.Pattern, dict]] = [
            (_compile(s["pattern"], s.get("type","literal")), s) for s in self.specs
        ]

    def findall(self, text: str) -> List[Tuple[Span, dict]]:
        hits: List[Tuple[Span, dict]] = []
        for rx, meta in self.compiled:
            for m in rx.finditer(text):
                hits.append(((m.start(), m.end()), meta))
        return hits

def build_indices(config) -> Dict[str, PatternIndex]:
    idx = {}
    idx["positives"] = PatternIndex([s.dict() for s in config.matchers.positives])
    idx["negatives"] = PatternIndex([s.dict() for s in config.matchers.negatives])

    ctx = {}
    for name, specs in config.matchers.contexts.items():
        ctx[name] = PatternIndex([s.dict() for s in specs])
    idx["contexts"] = ctx
    return idx
