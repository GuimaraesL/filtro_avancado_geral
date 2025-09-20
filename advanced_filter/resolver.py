from __future__ import annotations
from typing import List, Tuple
from .preprocessor import tokens_with_offsets, sentences

Span = Tuple[int,int]

def within_tokens(text: str, spans_a: List[Span], spans_b: List[Span], n: int) -> bool:
    toks = tokens_with_offsets(text)
    def span_to_token_index(span: Span):
        s, e = span
        for i, (_, ts, te) in enumerate(toks):
            if ts <= s < te or ts < e <= te or (s <= ts and te <= e):
                return i
        dists = [(i, min(abs(ts - s), abs(te - e))) for i,(_,ts,te) in enumerate(toks)]
        return min(dists, key=lambda x:x[1])[0] if dists else 0

    idx_a = [span_to_token_index(s) for s in spans_a]
    idx_b = [span_to_token_index(s) for s in spans_b]
    for ia in idx_a:
        for ib in idx_b:
            if abs(ia - ib) <= n:
                return True
    return False

def within_sentence(text: str, spans_a: List[Span], spans_b: List[Span]) -> bool:
    sent_spans = sentences(text)
    def in_same_sentence(sa: Span, sb: Span):
        for ss,se in sent_spans:
            if (ss <= sa[0] < se) and (ss <= sb[0] < se):
                return True
        return False
    for sa in spans_a:
        for sb in spans_b:
            if in_same_sentence(sa, sb):
                return True
    return False
