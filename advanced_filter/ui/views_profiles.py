# -*- coding: utf-8 -*-
from __future__ import annotations
import io
import yaml
import streamlit as st

from .profile_views.create import render_create_tab
from .profile_views.edit_existing import render_edit_existing_tab
from .profile_views.edit_file import render_edit_file_tab

# ============================================================
# Sidebar: fonte da configuração (Perfil ou YAML via upload)
# ============================================================
def render_sidebar_profile_selector(cfg_file_upload):
    """
    Renderiza seletor de PERFIL ou YAML na sidebar.
    Retorna (cfg_bytes, cfg_name, cfg_source_label).
    """
    st.markdown("### Fonte da configuração")
    src = st.radio(
        "Escolha a origem da configuração",
        options=["Perfil", "YAML"],
        horizontal=True,
        key="__cfg_source_radio",
    )

    cfg_bytes = None
    cfg_name = None
    label = None

    if src == "Perfil":
        from .profiles import get_profiles
        profiles = get_profiles()
        names = sorted(profiles.keys())
        if not names:
            st.info("Nenhum perfil salvo. Use a aba **Perfis** para criar/editar.")
        else:
            sel = st.selectbox("Perfil", names, key="__sel_profile_use")
            if sel:
                cfg = profiles[sel]
                cfg_name = sel
                label = "Perfil"
                # serializar para bytes YAML para usar no restante do app
                from .profiles import profile_to_yaml_bytes
                cfg_bytes = profile_to_yaml_bytes(cfg)

    else:
        if cfg_file_upload is not None:
            try:
                cfg_bytes = cfg_file_upload.getvalue()
                meta = getattr(cfg_file_upload, "name", "config.yaml")
                cfg_name = str(meta)
                label = "YAML"
            except Exception as e:
                st.error(f"Falha ao ler YAML: {e}")

    return cfg_bytes, (cfg_name or "config.yaml"), (label or "-")

# ============================================================
# Aba PERFIS (criar/editar básico)
# ============================================================
def render_profiles_tab():
    tab_create, tab_edit = st.tabs(["Criar", "Editar"])

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
