# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st

from ..profiles import profile_to_yaml_bytes, yaml_bytes_to_profile, make_default_profile
from ..state import set_profile

def _rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def render_edit_file_tab():
    st.session_state.setdefault("__file_open", False)
    st.session_state.setdefault("__file_draft", None)

    if not st.session_state["__file_open"]:
        up = st.file_uploader("Enviar YAML", type=["yaml", "yml"], key="upload_yaml_file")
        if up is None:
            st.info("Envie um arquivo YAML v2 para editar/importar.")
            return
        data = up.getvalue()
        try:
            prof = yaml_bytes_to_profile(data)
        except Exception as e:
            st.error(f"YAML inválido: {e}")
            return
        st.session_state["__file_open"] = True
        st.session_state["__file_draft"] = prof
        _rerun()
        return

    draft = dict(st.session_state["__file_draft"] or make_default_profile("Perfil_importado"))

    # ====== FORM (sem download_button dentro) ======
    with st.form("form_edit_file", clear_on_submit=False):
        c1, c2 = st.columns([2,1])
        with c1:
            draft["name"] = st.text_input("Nome do perfil", value=draft.get("name") or "Perfil_importado", key="file_name")
        with c2:
            st.write(" ")

        st.markdown("#### Normalização e janela")
        c1, c2, c3 = st.columns(3)
        with c1:
            draft.setdefault("normalization", {})
            draft["normalization"]["lowercase"] = st.checkbox(
                "lowercase", value=bool(draft["normalization"].get("lowercase", True)), key="file_lowercase"
            )
        with c2:
            draft["normalization"]["strip_accents"] = st.checkbox(
                "strip_accents", value=bool(draft["normalization"].get("strip_accents", True)), key="file_strip"
            )
        with c3:
            draft["window"] = st.number_input(
                "window (janela tokens)", value=int(draft.get("window") or 8), min_value=1, step=1, key="file_window"
            )

        st.markdown("#### Positivos")
        draft["positives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("positives_text") or "", height=120, key="file_pos"
        )

        st.markdown("#### Negativos")
        draft["negatives_text"] = st.text_area(
            "1 por linha (pattern | type | weight | tag)",
            value=draft.get("negatives_text") or "", height=100, key="file_neg"
        )

        st.markdown("#### Grupos de Contexto")
        st.caption("Colunas: group, category, patterns (múltiplos por linha, vírgula ou ';').")
        ctx_df = pd.DataFrame(draft.get("contexts_rows") or [{"group":"","category":"","patterns":""}])
        ctx_df = st.data_editor(ctx_df, num_rows="dynamic", use_container_width=True, key="file_ctx")
        draft["contexts_rows"] = ctx_df.to_dict(orient="records")

        st.markdown("#### Regras")
        st.caption("Decisão ∈ {INCLUI, REVISA, EXCLUI}. min_score e assign_category são opcionais.")
        rules_df = pd.DataFrame(draft.get("rules_rows") or [{
            "name":"","equation":"","decision":"REVISA","min_score":None,"assign_category":""
        }])
        rules_df = st.data_editor(rules_df, num_rows="dynamic", use_container_width=True, key="file_rules")
        draft["rules_rows"] = rules_df.to_dict(orient="records")

        # ⚠️ sem 'key' (compat Streamlit)
        saved_as_profile = st.form_submit_button("Salvar como Perfil", use_container_width=True)
        canceled = st.form_submit_button("Cancelar", use_container_width=True)

    # ====== AÇÕES FORA DO FORM ======
    c1, c2 = st.columns([1,1])
    with c1:
        st.download_button(
            "Baixar YAML do rascunho",
            profile_to_yaml_bytes(draft),
            file_name=f"{draft['name']}.yaml",
            use_container_width=True,
            key="btn_file_download_yaml"
        )
    with c2:
        if st.button("Fechar editor", use_container_width=True, key="btn_file_close"):
            st.session_state["__file_open"] = False
            st.session_state["__file_draft"] = None
            _rerun()

    if saved_as_profile:
        name = draft["name"] or "Perfil_importado"
        set_profile(name, draft)
        st.session_state["__profiles_version"] = st.session_state.get("__profiles_version", 0) + 1
        st.success(f"Perfil salvo: {name}")

    if canceled:
        st.info("Edição cancelada.")
        st.session_state["__file_open"] = False
        st.session_state["__file_draft"] = None
        _rerun()
