@echo off
setlocal

REM vai para a raiz do projeto (pasta deste .bat)
cd /d "%~dp0"

REM garante que a raiz entre no PYTHONPATH
set "PYTHONPATH=%CD%;%PYTHONPATH%"

if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt

streamlit run advanced_filter\ui_streamlit.py
