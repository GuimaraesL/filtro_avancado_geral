import argparse
from .excel_io import read_table, write_output
from .engine import run_filter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Caminho para CSV/Excel com uma coluna de texto")
    ap.add_argument("--text-col", default="texto", help="Nome da coluna com os relatos (padrão: 'texto')")
    ap.add_argument("--config", required=True, help="Caminho para o YAML de configuração")
    ap.add_argument("--out", default="saida.xlsx", help="Arquivo Excel de saída")
    args = ap.parse_args()

    df = read_table(args.input)
    result = run_filter(df, args.text_col, args.config)
    write_output(result["incluidos"], result["revisar"], result["excluidos"], args.out)
    print(f"OK! Saída gravada em: {args.out}")

if __name__ == "__main__":
    main()
