from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

import yaml

class PatternSpec(BaseModel):
    pattern: str
    type: Literal["literal", "phrase", "regex"] = "literal"
    weight: Optional[float] = None
    tag: Optional[str] = None

class NormalizationCfg(BaseModel):
    lowercase: bool = True
    strip_accents: bool = True
    lemmatize: bool = False

class TokenizationCfg(BaseModel):
    type: Literal["simple"] = "simple"

class MatchersCfg(BaseModel):
    positives: List[PatternSpec] = Field(default_factory=list)
    negatives: List[PatternSpec] = Field(default_factory=list)
    contexts: Dict[str, List[PatternSpec]] = Field(default_factory=dict)

class ScoringCfg(BaseModel):
    default_positive_weight: float = 1.0
    default_negative_weight: float = 1.0
    context_weight: float = 0.5

class RuleCfg(BaseModel):
    name: str
    equation: str
    min_score: Optional[float] = None
    decision: Literal["INCLUI", "REVISA", "EXCLUI"] = "INCLUI"
    assign_category: Optional[str] = None

class OutputCfg(BaseModel):
    assign_first_matching_rule: bool = True
    audit_fields: List[str] = Field(default_factory=lambda: ["matches","windows","rule_fired","reason","category"])

class AppConfig(BaseModel):
    language: Literal["pt", "en"] = "pt"
    normalization: NormalizationCfg = NormalizationCfg()
    tokenization: TokenizationCfg = TokenizationCfg()
    matchers: MatchersCfg = MatchersCfg()
    scoring: ScoringCfg = ScoringCfg()
    rules: List[RuleCfg] = Field(default_factory=list)
    output: OutputCfg = OutputCfg()

def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AppConfig(**data)
