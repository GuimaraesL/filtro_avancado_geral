from __future__ import annotations
import io
import pandas as pd

_EXCEL_EXTS = ('.xls', '.xlsx', '.xlsm')

def read_table(path_or_buf, sheet: str | None = None) -> pd.DataFrame:
    """
    Lê CSV/Excel. Se for Excel e 'sheet' informado, abre a aba específica.
    Aceita caminho (str) ou bytes/arquivo (BytesIO, file-like).
    """
    # Caminho em string
    if isinstance(path_or_buf, str):
        lower = path_or_buf.lower()
        if lower.endswith(_EXCEL_EXTS):
            return pd.read_excel(path_or_buf, sheet_name=sheet) if sheet else pd.read_excel(path_or_buf)
        return pd.read_csv(path_or_buf)

    # Bytes ou file-like
    if isinstance(path_or_buf, (bytes, bytearray)):
        buf = io.BytesIO(path_or_buf)
    else:
        buf = path_or_buf  # file-like

    # Tenta Excel primeiro
    try:
        return pd.read_excel(buf, sheet_name=sheet) if sheet else pd.read_excel(buf)
    except Exception:
        # volta ao início e tenta CSV
        try:
            if hasattr(buf, "seek"):
                buf.seek(0)
            return pd.read_csv(buf)
        except Exception as e:
            raise e

def write_output(incluidos, revisar, excluidos, out_path: str):
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        incluidos.to_excel(xw, index=False, sheet_name="Incluidos")
        revisar.to_excel(xw, index=False, sheet_name="Revisar")
        excluidos.to_excel(xw, index=False, sheet_name="Excluidos_do_Filtro")
