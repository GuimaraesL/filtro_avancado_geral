# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st

from ..profiles import profile_to_yaml_bytes
from ..state import get_profiles, set_profile
from .common import rerun_safe

# ---------- helpers de estado/flash ----------
def _flash_existing(msg: str, kind: str = "info"):
    st.session_state["__existing_flash"] = (kind, msg)

def _show_flash_existing():
    kind_msg = st.session_state.pop("__existing_flash", None)
    if not kind_msg:
        return
    kind, msg = kind_msg
    if kind == "success":
        st.success(msg)
    elif kind == "warning":
        st.warning(msg)
    else:
        st.info(msg)

def _clear_existing_editor_state():
    # limpa somente o que pertence ao editor "perfil existente"
    for k in list(st.session_state.keys()):
        if k.startswith("existing_"):
            del st.session_state[k]
    st.session_state["__existing_name"] = None
    st.session_state["__existing_draft"] = None
    st.session_state["__existing_mode_active"] = False
    st.session_state["__existing_form_nonce"] = st.session_state.get("__existing_form_nonce", 0) + 1

def render_edit_existing_tab():
    """Editar um perfil salvo (sem importar YAML no rascunho)."""
    profiles = get_profiles()
    if not profiles:
        st.info("Nenhum perfil salvo. Crie um perfil na aba **Criar perfil**.")
        return

    # Estado base do modo
    st.session_state.setdefault("__existing_name", None)
    st.session_state.setdefault("__existing_draft", None)
    st.session_state.setdefault("__existing_mode_active", False)
    st.session_state.setdefault("__existing_form_nonce", 0)

    # Mostra flash (feedback pós-rerun)
    _show_flash_existing()

    # -------- UI: seleção do perfil --------
    names = sorted(profiles.keys())
    default_name = st.session_state.get("__existing_name") or names[0]
    if default_name not in names:
        default_name = names[0]

    sel = st.selectbox(
        "Selecionar perfil",
        names,
        index=names.index(default_name),
        key="__edit_select_existing",
    )

    cols = st.columns([1, 1, 3])
    open_clicked = cols[0].button("Editar perfil selecionado", key="__btn_open_existing")
    if open_clicked:
        st.session_state["__existing_name"] = sel
        st.session_state["__existing_draft"] = dict(profiles[sel])
        st.session_state["__existing_form_nonce"] += 1
        st.session_state["__existing_mode_active"] = True
        rerun_safe(); st.stop()

    # Se o editor não está ativo, encerra aqui
    if not st.session_state["__existing_mode_active"]:
        st.caption("Selecione um perfil e clique em **Editar perfil selecionado** para abrir o editor.")
        return

    # ------- Editor ativo -------
    # se trocar seleção com editor aberto, sincroniza rascunho
    if st.session_state.get("__existing_name") != sel:
        st.session_state["__existing_name"] = sel
        st.session_state["__existing_draft"] = dict(profiles[sel])
        st.session_state["__existing_form_nonce"] += 1

    draft = st.session_state["__existing_draft"]
    editing_name = st.session_state["__existing_name"]
    nonce = st.session_state["__existing_form_nonce"]

    def k(suffix: str) -> str:
        return f"existing_{suffix}_{nonce}"

    st.markdown("### Editar perfil existente")
    with st.form(f"edit_form_existing_{nonce}"):
        draft["name"] = st.text_input(
            "Nome do perfil",
            value=draft.get("name") or editing_name,
            key=k("name")
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase",
                value=bool(draft["normalization"].get("lowercase", True)),
                key=k("lower"),
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents",
                value=bool(draft["normalization"].get("strip_accents", True)),
                key=k("strip"),
            )
        with c3:
            draft["window"] = st.number_input(
                "window (janela tokens)",
                value=int(draft.get("window") or 8),
                min_value=1,
                step=1,
                key=k("window"),
            )

        st.markdown("#### Positivos")
        draft["positives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("positives_text") or "",
            height=120,
            key=k("pos"),
        )

        st.markdown("#### Negativos")
        draft["negatives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("negatives_text") or "",
            height=100,
            key=k("neg"),
        )

        st.markdown("#### Grupos de Contexto")
        st.caption("Colunas: group, category, patterns (múltiplos por linha, vírgula ou ';').")
        ctx_df = pd.DataFrame(draft.get("contexts_rows") or [{"group":"","category":"","patterns":""}])
        ctx_df = st.data_editor(ctx_df, num_rows="dynamic", use_container_width=True, key=k("ctx_editor"))
        draft["contexts_rows"] = ctx_df.to_dict(orient="records")

        st.markdown("#### Regras")
        st.caption("Decisão ∈ {INCLUI, REVISA, EXCLUI}. min_score e assign_category são opcionais.")
        rules_df = pd.DataFrame(draft.get("rules_rows") or [{
            "name":"","equation":"","decision":"REVISA","min_score":None,"assign_category":""
        }])
        rules_df = st.data_editor(rules_df, num_rows="dynamic", use_container_width=True, key=k("rules_editor"))
        draft["rules_rows"] = rules_df.to_dict(orient="records")

        csave, ccancel, cdel = st.columns([1, 1, 1])
        saved    = csave.form_submit_button("Salvar alterações", use_container_width=True, key=k("btn_save"))
        canceled = ccancel.form_submit_button("Cancelar edição", use_container_width=True, key=k("btn_cancel"))
        delete   = cdel.form_submit_button("Excluir perfil", use_container_width=True, key=k("btn_del"))

    # ---- Ações fora do form (somente download; sem importar YAML no rascunho) ----
    st.download_button(
        "Baixar YAML do rascunho",
        profile_to_yaml_bytes(draft),
        file_name=f"{draft['name']}.yaml",
        use_container_width=True,
        key=k("dl"),
    )

    # ---- Handlers ----
    if saved:
        new_name = draft["name"]
        if new_name != editing_name and editing_name in profiles:
            del profiles[editing_name]
        set_profile(new_name, draft)
        try: st.toast("✅ Perfil salvo", icon="👍")
        except Exception: pass
        _flash_existing(f"Perfil salvo: {new_name}", "success")
        _clear_existing_editor_state()
        rerun_safe(); st.stop()

    if canceled:
        _flash_existing("Edição cancelada.", "info")
        _clear_existing_editor_state()
        rerun_safe(); st.stop()

    if delete:
        if editing_name in profiles:
            del profiles[editing_name]
        _flash_existing(f"Perfil '{editing_name}' excluído.", "warning")
        _clear_existing_editor_state()
        rerun_safe(); st.stop()
