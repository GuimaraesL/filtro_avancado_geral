# -*- coding: utf-8 -*-
from __future__ import annotations
import io
import yaml
import streamlit as st

from .state import ensure_bootstrap
from .profile_views.create import render_create_tab
from .profile_views.edit_existing import render_edit_existing_tab
from .profile_views.edit_file import render_edit_file_tab

# ============================================================
# Sidebar: fonte da configuração (Perfil ou YAML via upload)
# ============================================================
def render_sidebar_profile_selector(cfg_file_upload):
    """
    Retorna a configuração efetiva (bytes, nome, rótulo).
    - Perfil: escolhe entre os salvos.
    - YAML: exige upload na própria sidebar (sem usar memória do editor).
    """
    ensure_bootstrap()

    from .state import get_profiles
    from .profiles import profile_to_yaml_bytes

    st.markdown("### Fonte da configuração")

    profiles = get_profiles()
    has_profiles = len(profiles) > 0

    if "__cfg_source" not in st.session_state:
        st.session_state["__cfg_source"] = "Perfil" if has_profiles else "YAML"

    if st.session_state["__cfg_source"] == "Perfil" and not has_profiles:
        st.session_state["__cfg_source"] = "YAML"

    source = st.radio(
        "Escolha a fonte",
        options=["Perfil", "YAML"],
        horizontal=True,
        key="__cfg_source",
    )

    # -------- PERFIL --------
    if source == "Perfil":
        if not has_profiles:
            st.warning("Nenhum perfil disponível. Usando **YAML** (envie um arquivo).")
            st.session_state["__cfg_source"] = "YAML"
        else:
            names = sorted(profiles.keys())
            default_name = st.session_state.get("__cfg_profile_choice") or names[0]
            if default_name not in names:
                default_name = names[0]
            sel = st.selectbox("Perfil", names, index=names.index(default_name), key="__cfg_profile_choice")

            prof = profiles.get(sel)
            if not prof:
                return None, "config.yaml", "Perfil (inválido)"

            cfg_bytes = profile_to_yaml_bytes(prof)
            cfg_name  = f"perfil_{sel}.yaml"
            label     = f"Perfil: {sel}"
            return cfg_bytes, cfg_name, label

    # -------- YAML (upload na sidebar) --------
    if cfg_file_upload is None:
        st.info("Envie um arquivo YAML para usar como configuração.")
        return None, "config.yaml", "YAML (nenhum arquivo)"

    data = cfg_file_upload.getvalue()
    cfg_name = cfg_file_upload.name or "config.yaml"
    try:
        y = yaml.safe_load(io.BytesIO(data).read()) or {}
        inner_name = (y.get("name") or "").strip() if isinstance(y, dict) else ""
    except Exception:
        inner_name = ""

    label = f"YAML (perfil: {inner_name})" if inner_name else f"YAML (arquivo: {cfg_name})"
    return data, cfg_name, label


# ============================================================
# Abas: Perfis (Create/Edit) — orquestrador enxuto
# ============================================================
def render_profiles_tab():
    ensure_bootstrap()
    st.subheader("Perfis de Filtro")

    tab_create, tab_edit = st.tabs(["Criar perfil", "Editar perfil"])

    with tab_create:
        render_create_tab()

    with tab_edit:
        st.markdown("#### Origem para editar")
        edit_source = st.radio(
            "Escolha o que deseja editar",
            options=["Perfil existente", "Arquivo YAML"],
            horizontal=True,
            key="__edit_source",
        )

        if edit_source == "Perfil existente":
            render_edit_existing_tab()
        else:
            render_edit_file_tab()
