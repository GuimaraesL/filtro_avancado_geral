# FILTRO_AVANCADO — Advanced, Configurable Text Filtering (Streamlit App)

[![Streamlit App](https://img.shields.io/badge/Streamlit-Live%20Demo-red)](https://filtro-avancado.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

> **Filtro Avançado** é um aplicativo em **Streamlit** para **filtragem inteligente e configurável** de bases de texto (planilhas CSV/Excel). Ele permite criar **regras flexíveis** de inclusão/expulsão por palavras‑chave, contextos e exceções (anti‑padrões), testá‑las rapidamente e **exportar os resultados** em planilhas limpas para análise e reporte.

---

## 🧭 Sumário
- [Visão Geral](#-visão-geral)
- [Principais Recursos](#-principais-recursos)
- [Como Funciona](#-como-funciona)
- [Comece Agora](#-comece-agora)
  - [Usar no Navegador (Deploy Streamlit)](#usar-no-navegador-deploy-streamlit)
  - [Instalar e Rodar Localmente](#instalar-e-rodar-localmente)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Gráficos Mermaid](#-gráficos-mermaid)
- [Boas Práticas de Configuração](#-boas-práticas-de-configuração)
- [Exportação e Relatórios](#-exportação-e-relatórios)
- [Perguntas Frequentes](#-perguntas-frequentes)
- [Roadmap](#-roadmap)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## 🔎 Visão Geral

O **Filtro Avançado** nasceu para acelerar a análise de **registros textuais** (ex.: ocorrências, relatórios, logs, descrições de incidentes, pedidos de manutenção). Em vez de fórmulas complexas, você define **regras de filtragem** (palavras, frases, stems, *wildcards*, e **exceções** como “contramão”) e acompanha **em tempo real** os resultados: contagens, amostras e planilhas para download.

---

## 🚀 Principais Recursos

- **Interface intuitiva em Streamlit**: carregue CSV/Excel e configure tudo pela UI.
- **Regras flexíveis**: listas de termos de **INCLUSÃO** e **EXCLUSÃO** (anti‑padrões), com suporte a variações e pluralizações.
- **Contexto**: combine termos para reduzir falsos positivos (ex.: “luva” **e** “EPI”).
- **Teste Rápido**: escreva uma frase e veja se/por que ela “bate” nas regras.
- **Execução guiada**: botões claros, guia de **Resultados** e arquivos prontos para baixar.
- **Exportação**: resultados segmentados (full, hits, não‑hits, auditoria).
- **Performance**: processamento vetorizado com pandas e *caching* inteligente.
- **Reprodutível**: regras salvas e reutilizáveis (YAML/JSON).

---

## 🧠 Como Funciona

1. **Ingestão**: você carrega um CSV/Excel e escolhe a coluna de texto alvo.
2. **Configuração**: define regras de **inclusão**, **exclusão** (ex.: “contramão”), e **contextos** opcionais.
3. **Processamento**: o motor aplica normalização (minúsculas, *strip*, remoção de ruído opcional), avalia regras e marca *hits*.
4. **Validação**: use o **Teste Rápido** para checar frases e depurar regras.
5. **Resultados**: visualize contagens, amostras e baixe as planilhas finais.

> A lógica foca em **clareza e auditabilidade**. Cada registro filtrado pode ser explicado por qual regra o capturou (quando auditoria está ativa).

---

## ✳️ Comece Agora

### Usar no Navegador (Deploy Streamlit)

Abra a aplicação: **https://filtro-avancado.streamlit.app**  
> Não precisa instalar nada. Faça upload da planilha, configure as regras e exporte os resultados.

### Instalar e Rodar Localmente

**Requisitos**: Python 3.10+ (recomendado 64‑bit), `pip` e virtualenv.

```bash
# 1) Clone o repositório
git clone https://github.com/SEU_USUARIO/FILTRO_AVANCADO.git
cd FILTRO_AVANCADO

# 2) Crie e ative um ambiente virtual
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3) Instale as dependências
pip install -U pip
pip install -r requirements.txt

# 4) Rode o app Streamlit
streamlit run advanced_filter/ui_streamlit.py
```

> Se preferir **modo pacote**, use `pip install -e .` (se o `pyproject.toml` estiver configurado) e rode o entry‑point indicado no projeto.

---

## 🗂 Estrutura do Projeto

Exemplo ilustrativo (pode variar conforme seu repo):

```
FILTRO_AVANCADO/
├─ advanced_filter/
│  ├─ engine/                 # Lógica de filtragem (normalização, matching, contexto, auditoria)
│  ├─ data/                   # Exemplos e assets
│  ├─ ui_streamlit.py         # Interface Streamlit
│  ├─ config/                 # Regras salvas (YAML/JSON)
│  └─ utils/                  # Funções auxiliares
├─ tests/                     # Testes unitários
├─ requirements.txt
├─ pyproject.toml / setup.cfg # (opcional) instalação como pacote
└─ README.md
```

---

## 📊 Gráficos Mermaid

### 1) Fluxo de Alto Nível
```mermaid
flowchart LR
    A[Upload CSV/Excel] --> B[Selecionar Coluna de Texto]
    B --> C[Configurar Regras<br/>Inclusão/Exclusão/Contexto]
    C --> D[Processar]
    D --> E{Teste Rápido?}
    E -- Sim --> F[Depurar Regras]
    E -- Não --> G[Resultados & Métricas]
    G --> H[Exportar Planilhas]
```

### 2) Sequência de Execução (Usuário → App)
```mermaid
sequenceDiagram
    actor U as Usuário
    participant UI as UI Streamlit
    participant ENG as Motor de Filtro
    participant FS as Sistema de Arquivos

    U->>UI: Upload Planilha / Escolhe Coluna
    U->>UI: Define Regras (inclui, exclui, contexto)
    UI->>ENG: Normaliza texto & aplica regras
    ENG-->>UI: Marca "hits", contagens, amostras
    U->>UI: Teste Rápido (frase)
    UI->>ENG: Validar frase contra regras
    ENG-->>UI: Explicação de quais regras bateram
    U->>UI: Exportar
    UI->>FS: Gerar arquivos (full/hits/auditoria)
    FS-->>U: Downloads
```

### 3) Mapa de Regras (Inclusão x Exclusão)
```mermaid
graph TD
    INC[INCLUSÃO] -->|captura| TEXTO[Texto Avaliado]
    EXC[EXCLUSÃO] -->|anula| TEXTO
    CTX[CONTEXTO] -->|refina| INC
    TEXTO -->|resultado| OUT[Hit / Não Hit]
```

---

## ✅ Boas Práticas de Configuração

- **Especifique exceções** para reduzir falsos positivos (ex.: capturar “mão”/“mãos” mas **excluir** “contramão”).  
- **Contexto**: combine termos (ex.: `luva` **E** `EPI`) para sinalizar ocorrências realmente relevantes.
- **Normalização**: mantenha tudo minúsculo e sem acentos quando possível para aumentar *recall*.
- **Teste Rápido**: sempre valide uma amostra de frases típicas antes de processar tudo.
- **Versão de regras**: salve suas listas (YAML/JSON) com data e descrição da mudança.

Exemplo YAML simples:
```yaml
include:
  - "mão"
  - "mãos"
  - "dedo*"
exclude:
  - "contramão"
context_any:      # pelo menos um contexto deve aparecer
  - "EPI"
  - "proteção"
context_all: []   # se necessário, todos devem aparecer
```

---

## 📤 Exportação e Relatórios

Ao finalizar o processamento, a guia **Resultados** disponibiliza:
- **Full**: base original com colunas auxiliares (marcação de *hit*, regra, etc.).
- **Hits**: somente registros capturados.
- **No‑Hits**: registros não capturados (para auditoria inversa).
- **Auditoria**: mapeamento “registro → regra(s) que bateram)”.

> Os arquivos são gerados em memória e disponibilizados para **download** direto na UI.

---

## ❓ Perguntas Frequentes

**1) O app roda offline?**  
Sim, localmente ele roda offline após instalar dependências. O deploy em Streamlit Cloud requer Internet.

**2) Quais formatos de arquivo?**  
`.csv`, `.xlsx` (planilha com uma coluna de texto alvo).

**3) Dá para salvar e reutilizar regras?**  
Sim, exporte/import seu YAML/JSON de regras via UI.

**4) Como evitar falsos positivos com “luva”?**  
Use **contexto** (ex.: `luva` + `EPI`) e **exceções** para frases conhecidamente irrelevantes.

---

## 🗺 Roadmap

- [ ] Regras com expressões regulares avançadas (opcional).
- [ ] Dicionário de sinônimos e *stemming* leve.
- [ ] Modo lote (vários arquivos de uma vez).
- [ ] Painel de métricas (tendências, KPIs).
- [ ] Exportação em JSON/Parquet além de Excel/CSV.

---

## 🤝 Contribuindo

Sinta‑se à vontade para abrir **Issues** e **Pull Requests**.  
Para PRs, inclua testes e descreva o impacto nas regras/engine.

---

## 📄 Licença

Este projeto está licenciado sob a **MIT License**. Veja `LICENSE` para mais detalhes.

---

### 💡 Dúvidas?
Abra uma issue ou acesse o **[Deploy no Streamlit](https://filtro-avancado.streamlit.app)**.
