# -*- coding: utf-8 -*-
# Gerenciamento de perfis (Modo Básico)
from __future__ import annotations
from typing import Dict, Any
import streamlit as st

# ⬇️ estava ".config_loader" (mesmo nível). Corrigido para subir um nível:
from ..config_loader import config_dict_to_yaml_bytes, load_config


def _ensure_store() -> None:
    st.session_state.setdefault("__profiles_store__", {})

def get_profiles() -> Dict[str, Dict[str, Any]]:
    _ensure_store()
    return st.session_state["__profiles_store__"]

def set_profile(name: str, profile: Dict[str, Any]) -> None:
    _ensure_store()
    prof = dict(profile or {})
    prof["name"] = name
    get_profiles()[name] = prof

def make_default_profile(name: str = "Novo Perfil") -> Dict[str, Any]:
    return {
        "name": name,
        "normalization": {"lowercase": True, "strip_accents": True},
        "window": 8,
        "require_context": False,
        "negative_wins_ties": True,
        "min_pos_to_include": 1,
        "min_neg_to_exclude": 1,
        "positives": [],
        "negatives": [],
        "contexts": [],
        "notes": None,
    }

def profile_to_yaml_bytes(profile: Dict[str, Any]) -> bytes:
    return config_dict_to_yaml_bytes(profile)

def yaml_bytes_to_profile(yaml_bytes: bytes) -> Dict[str, Any]:
    prof = load_config(yaml_bytes)  # já normaliza
    if not prof.get("name"):
        prof["name"] = "Perfil"
    return prof

__all__ = ["get_profiles", "set_profile", "make_default_profile", "profile_to_yaml_bytes", "yaml_bytes_to_profile"]
