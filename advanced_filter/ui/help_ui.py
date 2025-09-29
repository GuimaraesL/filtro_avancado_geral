# help_ui.py – Guia de Ajuda unificada do FILTRO_AVANCADO (Streamlit)
# Alinhado ao projeto:
# - Saídas: Incluir / Revisar / Excluir (não existe "Sem categoria")
# - Tokens = contagem de palavras positivas/negativas por proximidade de contexto (janela de tokens)
# - Teste Rápido descrito como atalho opcional e prático
# - Perfil com: minuscula, acentos, exigir_contexto, janela_token, min_positivos, min_negativos
# - Fluxo visual atualizado e README do GitHub
# - E-mail resolvido por parâmetro > secrets > env > session_state > fallback

from __future__ import annotations
import os
import textwrap
import pandas as pd
import streamlit as st

GITHUB_README_URL = "https://github.com/GuimaraesL/filtro_avancado_geral"

# =========================
# Resolução do e-mail de contato
# =========================
def _resolve_contact_email(explicit: str | None = None) -> str:
    """Parâmetro > secrets > env > session_state > fallback."""
    if explicit and explicit.strip():
        return explicit.strip()

    # 1) st.secrets
    try:
        val = st.secrets.get("contact_email", "")
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass

    # 2) variável de ambiente
    val = os.getenv("FILTRO_SUPPORT_EMAIL", "")
    if isinstance(val, str) and val.strip():
        return val.strip()

    # 3) session_state (permite setar em runtime)
    val = st.session_state.get("contact_email", "")
    if isinstance(val, str) and val.strip():
        return val.strip()

    # 4) fallback definitivo
    return "autguim@outlook.com"

# =========================
# Exemplos reutilizáveis
# =========================
EXAMPLE_YAML = """\
# Exemplo ilustrativo de perfil
# Ajuste valores conforme seu caso real.
minuscula: true          # normaliza caixa
acentos: true            # normaliza acentos (pressão ~ pressao)
exigir_contexto: true    # se true, é obrigatório ter pelo menos 1 termo de context
janela_token: 8          # nº de tokens ao redor do contexto para contagem
min_positivos: 1         # mínimos positivos na janela para INCLUIR
min_negativos: 1         # mínimos negativos na janela para EXCLUIR

include:
  - "falha no motor"
  - "vibração excessiva"
  - "queda de pressão"

exclude:
  - "teste de motor"
  - "simulação"

context:
  - "motor elétrico principal"
  - "linha de produção 3"
"""

EXAMPLE_CASES = [
    {
        "frase": "vibração excessiva - motor elétrico principal",
        "resultado": "INCLUIR (contexto presente + positivos ≥ min_positivos)"
    },
    {
        "frase": "queda de pressão - motor elétrico principal",
        "resultado": "INCLUIR (contexto presente + positivos ≥ min_positivos)"
    },
    {
        "frase": "teste de motor",
        "resultado": "EXCLUIR (termo negativo/exclude atinge mínimo)"
    },
    {
        "frase": "simulação de falha no motor1",
        "resultado": "REVISAR (ambiguidade/conflito no entorno do contexto)"
    },
]

# =========================
# Utilidades da página
# =========================
def _readme_button():
    # Usa st.link_button se disponível; caso contrário, link normal.
    try:
        st.link_button("📖 Abrir README no GitHub", GITHUB_README_URL, use_container_width=True)
    except AttributeError:
        st.markdown(f"[📖 Abrir README no GitHub]({GITHUB_README_URL})")

# =========================
# Seções de conteúdo
# =========================
def _section_overview():
    st.subheader("O que é o FILTRO_AVANCADO?")
    st.markdown(
        "O *FILTRO_AVANCADO* classifica textos (de planilhas ou entradas livres) em "
        "*Incluir, **Revisar* ou *Excluir* com base em *perfis* configuráveis. "
        "Os perfis combinam normalização (minúscula/acentos), âncoras de *contexto* e uma "
        "*janela de tokens* ao redor do contexto onde são contadas *palavras positivas* (include) "
        "e *negativas* (exclude)."
    )

    st.markdown("#### Fluxo do processamento (visual)")
    st.graphviz_chart(
        r"""
        digraph {
          rankdir=LR;
          node [shape=box, style="rounded"];

          A [label="Entrada (Excel/CSV/Texto)"];
          B [label="Pré-processamento\n(minúscula/acentos)"];
          C [label="Localização de Contexto\n(se exigir_contexto=true, obrigatório)"];
          D [label="Janela de Tokens ao redor do contexto\n(janela_token)"];
          E [label="Contagem de palavras\nPositivas (include) vs Negativas (exclude)"];
          F [label="Decisão\n(min_positivos/min_negativos,\nlistas include/exclude)"];
          G1 [label="INCLUIR", shape=box, color=green];
          G2 [label="REVISAR", shape=box, color=orange];
          G3 [label="EXCLUIR", shape=box, color=red];

          A -> B -> C -> D -> E -> F;
          F -> G1 [label="positivos ≥ min_positivos\n e negativos < min_negativos"];
          F -> G3 [label="negativos ≥ min_negativos\n ou exclude forte"];
          F -> G2 [label="ambiguidade / sinais insuficientes"];
        }
        """
    )

def _section_rules_yaml():
    st.subheader("Regras & Perfis")
    st.markdown(
        "Um *perfil* reúne listas de termos e *opções* que controlam a decisão:"
    )
    st.markdown(
        "- *minuscula* (bool): converte tudo para minúsculas antes de comparar.\n"
        "- *acentos* (bool): normaliza acentos (ex.: “pressão” ≈ “pressao”).\n"
        "- *exigir_contexto* (bool): se *true, é obrigatório existir **pelo menos 1 termo* da lista context no texto para que *Incluir* seja possível.\n"
        "- *janela_token* (int): tamanho da *janela de proximidade* (em tokens/palavras) ao redor do contexto usada para contar *positivos* e *negativos*.\n"
        "- *min_positivos* (int): quantidade mínima de *palavras positivas* na janela para *INCLUIR*.\n"
        "- *min_negativos* (int): quantidade mínima de *palavras negativas* na janela para *EXCLUIR*.\n"
    )

    st.markdown("As listas do perfil:")
    st.markdown(
        "- *include: termos **positivos* (sinal a favor) — contam para min_positivos quando caem na janela.\n"
        "- *exclude: termos **negativos* (sinal contra) — contam para min_negativos e/ou podem acionar exclusão direta em casos fortes.\n"
        "- *context: termos que **ancoram* o cenário; abrem a *janela de tokens* e, se exigir_contexto=true, são obrigatórios."
    )

    st.markdown("#### Exemplo (estrutura do perfil)")
    st.code(EXAMPLE_YAML, language="yaml")

    st.markdown("#### Como o motor decide (ordem real)")
    st.markdown(
        "1) *Pré-processamento* → aplica minuscula e acentos ao texto e aos termos do perfil.\n"
        "2) *Contexto* → se exigir_contexto=true, deve existir *≥ 1* termo de context no texto; "
        "mesmo com exigir_contexto=false, o contexto pode ser usado como âncora para a janela.\n"
        "3) *Janela de tokens* → ao redor de cada ocorrência de contexto, abre-se uma janela de tamanho janela_token.\n"
        "4) *Contagem* → na janela, contam-se termos *positivos* (include) e *negativos* (exclude).\n"
        "5) *Decisão* →\n"
        "   - Se *negativos ≥ min_negativos* → *EXCLUIR*.\n"
        "   - Senão, se *positivos ≥ min_positivos* → *INCLUIR*.\n"
        "   - Caso contrário → *REVISAR* (ambiguidade/sinais insuficientes).\n"
        "6) *Excludes fortes* → termos particularmente críticos de exclude podem (conforme seu perfil/regra) disparar *exclusão direta*."
    )

    st.info(
        "Ajuste janela_token, min_positivos e min_negativos para calibrar sensibilidade. "
        "Se houver muito ruído, aumente a janela e os mínimos; se estiver perdendo casos legítimos, reduza-os."
    )

def _section_cases_and_tutorials():
    st.subheader("Casos práticos")
    df = pd.DataFrame(EXAMPLE_CASES)
    st.dataframe(df, use_container_width=True)
    st.caption(
        "Exemplo importante: “simulação de falha no motor1” → *REVISAR* (o entorno gera ambiguidade)."
    )

    st.subheader("Tutoriais rápidos")
    with st.expander("▶ Executar Teste Rápido"):
        st.markdown(
            "Use como *atalho* para validar rapidamente uma frase com o *perfil atual*. "
            "Ajuda a iterar mais rápido nos ajustes de termos e limites, mas *não é obrigatório*."
        )
    with st.expander("▶ Executar Filtro em Arquivos"):
        st.markdown(
            "Envie Excel/CSV, escolha a *coluna de texto, selecione o **perfil* e execute. "
            "Os resultados aparecem na guia *Resultados*."
        )
    with st.expander("▶ Exportar Resultados"):
        st.markdown(
            "Após o processamento, baixe *CSV/Excel/JSON* para auditoria ou integração com BI."
        )

def _section_errors_solutions_user():
    st.subheader("Erros & Soluções (uso do dia a dia)")
    problems = [
        {
            "q": "Enviei o arquivo e não vi resultado",
            "a": [
                "Confirme que o arquivo é *Excel (.xlsx)* ou *CSV* válido.",
                "Selecione a *coluna de texto* correta.",
                "Cheque se o *perfil* está com janela_token, min_positivos e min_negativos coerentes.",
            ],
        },
        {
            "q": "Algo que deveria entrar foi para Revisar",
            "a": [
                "Aumente janela_token e/ou *reduza* min_positivos.",
                "Verifique se exigir_contexto faz sentido para esse caso.",
                "Inclua termos positivos mais *específicos* (ou sinônimos frequentes).",
            ],
        },
        {
            "q": "Entrou coisa que deveria ser Excluída",
            "a": [
                "Inclua termos em *exclude* que representem os falsos positivos.",
                "Aumente min_negativos (se sua intenção for ficar mais rígido ao excluir).",
                "Reduza min_positivos apenas se houver muitos casos legítimos indo para Revisar.",
            ],
        },
        {
            "q": "Excluiu o que eu queria incluir",
            "a": [
                "Verifique exclude — pode haver termos fortes demais colidindo.",
                "Diminua min_negativos ou remodele termos negativos ambíguos.",
                "Use context para ancorar melhor o cenário e *aumente* janela_token.",
            ],
        },
    ]
    for item in problems:
        with st.expander(f"❗ {item['q']}"):
            for step in item["a"]:
                st.markdown(f"- {step}")

def _section_faq_contact(contact_email: str | None = None):
    st.subheader("FAQ – Perguntas Frequentes")
    faq = [
        {
            "q": "O que é um *perfil*?",
            "a": (
                "É uma configuração criada *no próprio app* (e que você pode *exportar*). "
                "Define normalização (minúscula/acentos), exigir_contexto, janela_token, "
                "min_positivos, min_negativos e as listas include, exclude, context. "
                "A exportação gera um arquivo *.yaml* para versionamento e compartilhamento."
            ),
        },
        {
            "q": "Preciso de perfis diferentes por área/equipamento?",
            "a": (
                "Recomendável. Você pode reusar perfis, mas segmentar por área/linha/equipamento "
                "costuma *aumentar a precisão. Ative **acentos* se seus dados misturam "
                "formas acentuadas e não acentuadas."
            ),
        },
        {
            "q": "Como crio um perfil?",
            "a": (
                "Na guia *Perfis* do app: clique em *Novo*, ajuste as opções (minúscula, acentos, "
                "exigir_contexto, janela_token, min_positivos, min_negativos) e preencha as listas "
                "include/exclude/context. Se precisar compartilhar, *exporte* (gera um .yaml)."
            ),
        },
        {
            "q": "Os *tokens* são liga/desliga?",
            "a": (
                "Não. *Tokens* referem-se à *janela de proximidade* (definida por janela_token) "
                "usada para *contar* positivos (include) e negativos (exclude). "
                "Você configura os *mínimos* (min_positivos, min_negativos) e o *tamanho* da janela."
            ),
        },
        {
            "q": "E a diferença de acentos e maiúsculas?",
            "a": (
                "Você controla via opções do perfil: *minúscula* normaliza caixa; *acentos* "
                "normaliza diacríticos (ex.: “pressão” ≈ “pressao”)."
            ),
        },
    ]
    for item in faq:
        with st.expander(f"❓ {item['q']}"):
            st.markdown(textwrap.dedent(item["a"]))

    st.subheader("Contato")
    resolved = _resolve_contact_email(contact_email)
    st.markdown(f"📧 *E-mail*: {resolved}")

# =========================
# Layout principal (entrada única)
# =========================
def render_help(contact_email: str | None = None):
    """Renderiza a guia de Ajuda completa."""
    st.title("Ajuda")
    st.caption("Manual interativo do FILTRO_AVANCADO")
    _readme_button()

    t1, t2, t3, t4 = st.tabs([
        "Visão Geral", "Regras & Perfis", "Casos & Tutoriais", "Erros & FAQ"
    ])

    with t1:
        _section_overview()

    with t2:
        _section_rules_yaml()

    with t3:
        _section_cases_and_tutorials()

    with t4:
        _section_errors_solutions_user()
        _section_faq_contact(contact_email)