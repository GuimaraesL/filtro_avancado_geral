from __future__ import annotations
from typing import List, Tuple, Dict
from .resolver import within_tokens, within_sentence

Span = Tuple[int,int]

class DSLContext:
    def __init__(self, text: str, pos_spans: List[Span], neg_spans: List[Span], ctx_spans: Dict[str, List[Span]]):
        self.text = text
        self.pos_spans = pos_spans
        self.neg_spans = neg_spans
        self.ctx_spans = ctx_spans

    def POS(self) -> List[Span]:
        return self.pos_spans
    def NEG(self) -> List[Span]:
        return self.neg_spans
    def CTX(self, name: str) -> List[Span]:
        return self.ctx_spans.get(name, [])

    @staticmethod
    def ANY(spans: List[Span]) -> bool:
        return bool(spans)

    def WITHIN(self, n: int, spansA: List[Span], spansB: List[Span], scope: str = "tokens") -> bool:
        if scope == "tokens":
            return within_tokens(self.text, spansA, spansB, n)
        elif scope == "sentence":
            return within_sentence(self.text, spansA, spansB)
        elif scope == "paragraph":
            return within_sentence(self.text, spansA, spansB)
        else:
            raise ValueError("scope inválido")

def eval_equation(equation: str, ctx: DSLContext) -> bool:
    safe_globals = {
        "__builtins__": {},
        "POS": ctx.POS,
        "NEG": ctx.NEG,
        "CTX": ctx.CTX,
        "ANY": ctx.ANY,
        "WITHIN": ctx.WITHIN,
        "True": True,
        "False": False,
        "None": None,
    }
    return bool(eval(equation, safe_globals, {}))
