"""Mostra a árvore sintática (AST) produzida pelo parser.

Uso:
    python3 scripts/arvore.py programa.cbl [-I dir_copybooks] [--profundidade N]

Roda só o pré-processador (COPY) e a análise sintática; não faz análise
semântica nem gera código.
"""

from __future__ import annotations

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from src.diagnosticos import Diagnosticos  # noqa: E402
from src.parser import N, analisar_sintaxe  # noqa: E402
from src.preproc import preprocessar  # noqa: E402

IGNORAR = {"kind", "line", "sym"}


def vazio(v) -> bool:
    return v is None or v is False or v == [] or v == {} or v == ""


def escalar(v) -> bool:
    return not isinstance(v, (N, list, tuple, dict))


def resumo(v) -> str:
    if isinstance(v, N):
        campos = [f"{k}={x!r}" for k, x in v.__dict__.items()
                  if k not in IGNORAR and not vazio(x) and escalar(x)]
        return v.kind + (" " + " ".join(campos) if campos else "")
    return repr(v)


def imprimir(no, nivel: int, maxp: int, rotulo: str = "") -> None:
    pre = "  " * nivel + "├─ "
    if isinstance(no, (list, tuple)):
        for x in no:
            imprimir(x, nivel, maxp, rotulo)
        return
    if not isinstance(no, N):
        print(f"{pre}{rotulo}{no!r}")
        return
    linha = f"  (linha {no.line})" if getattr(no, "line", 0) else ""
    print(f"{pre}{rotulo}{resumo(no)}{linha}")
    if nivel >= maxp:
        return
    for k, v in no.__dict__.items():
        if k in IGNORAR or vazio(v) or escalar(v):
            continue
        if isinstance(v, dict):
            continue
        imprimir(v, nivel + 1, maxp, f"{k}: ")


def main() -> int:
    ap = argparse.ArgumentParser(description="Mostra a AST de um programa COBOL")
    ap.add_argument("fonte")
    ap.add_argument("-I", dest="dirs", action="append", default=[])
    ap.add_argument("--profundidade", type=int, default=99)
    a = ap.parse_args()

    diag = Diagnosticos()
    texto, _ = preprocessar(a.fonte, diag, a.dirs + [os.path.join(RAIZ, "copybooks")])
    prog = None if diag.falhou else analisar_sintaxe(texto, diag, a.fonte)
    for m in diag.itens:
        print(m, file=sys.stderr)
    if prog is None or diag.falhou:
        print("[parser] erro sintático; árvore não gerada", file=sys.stderr)
        return 1

    print(f"PROGRAMA {prog.name}")
    secoes = [("FILE-CONTROL / SELECT", prog.files), ("FILE SECTION", prog.items_fd),
              ("WORKING-STORAGE SECTION", prog.items_ws), ("LINKAGE SECTION", prog.items_ls),
              ("PROCEDURE DIVISION", prog.paras)]
    for titulo, itens in secoes:
        if itens:
            print(f"\n== {titulo} ==")
            imprimir(itens, 0, a.profundidade)
    c = diag.contagem()
    print(f"\n[parser] {prog.name}: {len(prog.paras)} parágrafo(s), "
          f"{c['E'] + c['S']} erro(s), {c['W']} aviso(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
