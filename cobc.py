"""Compilador COBOL -> C.

Uso:
    py cobc.py programa.cbl                 gera programa.c e o executavel
    py cobc.py programa.cbl -o saida.exe    escolhe o nome do executavel
    py cobc.py programa.cbl --so-c          so gera o .c
    py cobc.py programa.cbl --run           compila e executa
    py cobc.py programa.cbl --fases         mostra tokens/AST/tabela de simbolos resumidos
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

from src.diagnosticos import Diagnosticos
from src.gerador_c import GeradorC
from src.parser import analisar_sintaxe
from src.preproc import preprocessar
from src.semantica import Semantico, Tabela

RAIZ = os.path.dirname(os.path.abspath(__file__))


def achar_gcc() -> str | None:
    g = shutil.which("gcc")
    if g:
        return g
    cand = os.path.expanduser(r"~\scoop\apps\gcc\current\bin\gcc.exe")
    return cand if os.path.isfile(cand) else None


def _achar_fonte(nome: str, dirs: list[str]) -> str | None:
    for d in dirs:
        try:
            for f in os.listdir(d):
                base, ext = os.path.splitext(f)
                if base.upper() == nome.upper() and ext.lower() in (".cbl", ".cob", ".cobol"):
                    return os.path.join(d, f)
        except OSError:
            pass
    return None


def _chamadas(no, achados: set[str]) -> None:
    from src.parser import N
    if isinstance(no, N):
        if no.kind == "call" and no.target.kind == "str":
            achados.add(no.target.text.upper())
        for k, v in no.__dict__.items():
            if k not in ("kind", "line", "sym"):
                _chamadas(v, achados)
    elif isinstance(no, (list, tuple)):
        for x in no:
            _chamadas(x, achados)


def compilar(caminho: str, saida_c: str, diag: Diagnosticos, dirs_copy: list[str] | None = None) -> bool:
    """Compila o programa principal e, automaticamente, os programas chamados por CALL 'NOME'
    cujo fonte (NOME.cbl/.cob) esteja no mesmo diretorio."""
    base = os.path.dirname(os.path.abspath(caminho))
    dirs = [base] + (dirs_copy or [])
    fila = [caminho]
    vistos = {os.path.abspath(caminho)}
    unidades = []
    while fila:
        fonte = fila.pop(0)
        texto, enc = preprocessar(fonte, diag, dirs_copy)
        if diag.falhou:
            return False
        prog = analisar_sintaxe(texto, diag, fonte)
        if diag.falhou:
            return False
        tab = Tabela(diag, fonte, pfx=f"u{len(unidades)}_")
        tab.construir(prog)
        Semantico(tab, prog, diag, fonte).executar()
        if diag.falhou:
            return False
        unidades.append((prog, tab, fonte, enc))
        chamados: set[str] = set()
        _chamadas(prog.paras, chamados)
        for nome in sorted(chamados):
            f = _achar_fonte(nome, dirs)
            if f and os.path.abspath(f) not in vistos:
                vistos.add(os.path.abspath(f))
                fila.append(f)
    conhecidos = {}
    for prog, _, _, _ in unidades:
        conhecidos[prog.name.upper()] = re.sub(r"\W", "_", prog.name.upper())
    partes = [GeradorC.PRELUDIO]
    for nome_c in conhecidos.values():
        partes.append(f"int prog_{nome_c}(unsigned char **args, int nargs);")
        partes.append(f"void init_{nome_c}(void);")
    partes.append("#define INIT_ALL " + " ".join(f"init_{n}();" for n in conhecidos.values()))
    for i, (prog, tab, fonte, enc) in enumerate(unidades):
        g = GeradorC(prog, tab, diag, fonte, enc)
        partes.append(g.gerar(principal=(i == 0), conhecidos=conhecidos))
    if diag.falhou:
        return False
    with open(saida_c, "w", encoding="latin-1", newline="\n") as f:
        f.write("\n".join(partes))
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compilador COBOL para C")
    ap.add_argument("fonte")
    ap.add_argument("-o", "--saida")
    ap.add_argument("--so-c", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("-I", dest="copy_dirs", action="append", default=[])
    ap.add_argument("--build-dir", default=None)
    a = ap.parse_args(argv)

    nome = os.path.splitext(os.path.basename(a.fonte))[0]
    bdir = a.build_dir or os.path.join(RAIZ, "build")
    os.makedirs(bdir, exist_ok=True)
    c_path = os.path.join(bdir, nome + ".c")
    exe = a.saida or os.path.join(bdir, nome + (".exe" if os.name == "nt" else ""))
    diag = Diagnosticos()
    ok = compilar(a.fonte, c_path, diag, a.copy_dirs)
    for m in diag.itens:
        print(m, file=sys.stderr)
    c = diag.contagem()
    print(f"[cobc] {a.fonte}: {c['E'] + c['S']} erro(s), {c['W']} aviso(s)", file=sys.stderr)
    if not ok:
        print("[cobc] compilacao interrompida (nenhum codigo gerado)", file=sys.stderr)
        return 1
    if a.so_c:
        print(f"[cobc] C gerado em {c_path}", file=sys.stderr)
        return 0
    gcc = achar_gcc()
    if not gcc:
        print("[cobc] gcc nao encontrado (instale com: scoop install gcc)", file=sys.stderr)
        return 2
    r = subprocess.run([gcc, "-O1", "-w", "-I", os.path.join(RAIZ, "runtime"), "-o", exe, c_path])
    if r.returncode != 0:
        print("[cobc] falha no gcc", file=sys.stderr)
        return 3
    print(f"[cobc] executavel: {exe}", file=sys.stderr)
    if a.run:
        return subprocess.run([exe]).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
