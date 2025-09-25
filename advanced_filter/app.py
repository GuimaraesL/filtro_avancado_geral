# streamlit_app.py  (na raiz do repositório)
from pathlib import Path
import sys
from runpy import run_path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP = ROOT / "advanced_filter" / "ui_streamlit.py"
assert APP.exists(), f"Arquivo não encontrado: {APP}"

# Executa o UI como script principal (garante que tudo rode igual ao local)
run_path(str(APP), run_name="__main__")
