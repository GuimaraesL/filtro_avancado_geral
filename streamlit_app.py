# -*- coding: utf-8 -*-
# streamlit_app.py (na RAIZ do repositório)
import os, time
os.environ["APP_CLOUD"] = "1"
os.environ["STREAMLIT_STATIC_URL_VERSION"] = str(int(time.time()))

from pathlib import Path
import sys
from runpy import run_path

ROOT = Path(__file__).resolve().parent                      # .../filtro_avancado_geral
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "advanced_filter" / "ui_streamlit.py"
assert APP.exists(), f"Arquivo não encontrado: {APP}"

run_path(str(APP), run_name="__main__")
