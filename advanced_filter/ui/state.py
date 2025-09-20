# -*- coding: utf-8 -*-
# advanced_filter/ui/state.py
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import os, io, zipfile, pathlib
import streamlit as st

from .profiles import profile_to_yaml_bytes, yaml_bytes_to_profile

PROFILE_DIR = pathlib.Path.home() / ".filtro_avancado" / "perfis"

# ---- sessão ----
def ensure_init():
    st.session_state.setdefault("profiles", {})         # nome -> dict perfil
    st.session_state.setdefault("active_profile", None) # nome ativo
    st.session_state.setdefault("cfg_bytes", None)      # bytes do YAML ativo
    st.session_state.setdefault("cfg_name", "config.yaml")
    st.session_state.setdefault("_profiles_bootstrapped", False)

def set_profile(name: str, data: dict):
    ensure_init()
    st.session_state["profiles"][name] = data
    # se esse perfil está ativo, atualizamos cfg_bytes imediatamente
    if st.session_state.get("active_profile") == name:
        yb = profile_to_yaml_bytes(data)
        st.session_state["cfg_bytes"] = yb
        st.session_state["cfg_name"]  = f"perfil_{name}.yaml"

def get_profiles() -> Dict[str, dict]:
    ensure_init()
    return st.session_state["profiles"]

def get_active_profile_name() -> Optional[str]:
    ensure_init()
    return st.session_state.get("active_profile")

def set_active_profile(name: Optional[str]) -> Tuple[Optional[bytes], str]:
    """
    Ativa um perfil pelo nome. Se name=None, desativa e usa apenas o YAML da barra lateral.
    Retorna (cfg_bytes, cfg_name) atuais.
    """
    ensure_init()
    st.session_state["active_profile"] = name
    if not name:
        st.session_state["cfg_bytes"] = None
        st.session_state["cfg_name"]  = "config.yaml"
        return None, "config.yaml"

    prof = st.session_state["profiles"].get(name)
    if not prof:
        st.session_state["cfg_bytes"] = None
        st.session_state["cfg_name"]  = "config.yaml"
        return None, "config.yaml"
    yb = profile_to_yaml_bytes(prof)
    st.session_state["cfg_bytes"] = yb
    st.session_state["cfg_name"]  = f"perfil_{name}.yaml"
    return yb, st.session_state["cfg_name"]

def get_active_cfg() -> Tuple[Optional[bytes], str]:
    ensure_init()
    return st.session_state.get("cfg_bytes"), st.session_state.get("cfg_name", "config.yaml")

# ---- disco (persistência local) ----
def _ensure_dir(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)

def save_profile_to_disk(name: str, base_dir: pathlib.Path = PROFILE_DIR) -> pathlib.Path:
    ensure_init(); _ensure_dir(base_dir)
    prof = st.session_state["profiles"].get(name, {})
    yb = profile_to_yaml_bytes(prof)
    out = base_dir / f"{name}.yaml"
    out.write_bytes(yb)
    return out

def save_all_profiles_to_disk(base_dir: pathlib.Path = PROFILE_DIR) -> List[pathlib.Path]:
    ensure_init(); _ensure_dir(base_dir)
    out = []
    for name in st.session_state["profiles"].keys():
        out.append(save_profile_to_disk(name, base_dir))
    return out

def load_profiles_from_disk(base_dir: pathlib.Path = PROFILE_DIR, overwrite: bool = False) -> List[str]:
    ensure_init()
    if not base_dir.exists():
        return []
    loaded = []
    for p in base_dir.glob("*.yaml"):
        try:
            prof = yaml_bytes_to_profile(p.read_bytes())
            name = prof.get("name") or p.stem
            if overwrite or name not in st.session_state["profiles"]:
                prof["name"] = name
                st.session_state["profiles"][name] = prof
                loaded.append(name)
        except Exception:
            continue
    return loaded

def export_profiles_zip(base_dir: pathlib.Path = PROFILE_DIR) -> bytes:
    """
    Gera um .zip com TODOS os perfis atualmente na sessão (não depende do disco).
    """
    ensure_init()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, prof in st.session_state["profiles"].items():
            z.writestr(f"{name}.yaml", profile_to_yaml_bytes(prof))
    buf.seek(0)
    return buf.getvalue()

def import_profiles_zip(zip_bytes: bytes, overwrite: bool = False) -> List[str]:
    """
    Importa vários perfis de um .zip (cada arquivo .yaml é um perfil).
    """
    ensure_init()
    buf = io.BytesIO(zip_bytes)
    names = []
    with zipfile.ZipFile(buf, "r") as z:
        for info in z.infolist():
            if not info.filename.lower().endswith((".yaml", ".yml")):
                continue
            data = z.read(info.filename)
            prof = yaml_bytes_to_profile(data)
            name = prof.get("name") or pathlib.Path(info.filename).stem
            if overwrite or name not in st.session_state["profiles"]:
                prof["name"] = name
                st.session_state["profiles"][name] = prof
                names.append(name)
    return names

# ---- bootstrap opcional (carrega do disco na 1ª vez) ----
def ensure_bootstrap(auto_load_from_disk: bool = True):
    ensure_init()
    if auto_load_from_disk and not st.session_state["_profiles_bootstrapped"]:
        try:
            load_profiles_from_disk(PROFILE_DIR, overwrite=False)
        finally:
            st.session_state["_profiles_bootstrapped"] = True
