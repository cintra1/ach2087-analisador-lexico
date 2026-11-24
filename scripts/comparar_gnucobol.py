"""Compara a execução do nosso compilador com a do GnuCOBOL 3.2 (tudo dentro do Docker).

Só precisa de Docker em execução (e de Python no host). Nada é instalado no computador:
a imagem `gnucobol-ref` (scripts/gnucobol/Dockerfile: Debian + gnucobol + gcc) é construída
na primeira execução. Nos dois lados o mesmo programa é compilado (o nosso: COBOL -> C -> gcc;
o de referência: `cobc -x`), rodado com o mesmo stdin e os mesmos arquivos de entrada, e a saída
padrão e os arquivos gerados são comparados byte a byte.

Uso:
    py scripts/comparar_gnucobol.py [filtro]          compara os casos (filtro = trecho do nome)
    py scripts/comparar_gnucobol.py --testes          roda a suite unittest no container (tem gcc)
    py scripts/comparar_gnucobol.py --limpar          remove a imagem gnucobol-ref e a base debian
    py scripts/comparar_gnucobol.py --limpar-apos     compara e remove a imagem no fim (vale p/ --testes)
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import cobc  # noqa: E402
from src.diagnosticos import Diagnosticos  # noqa: E402

PROG = os.path.join(RAIZ, "programas")
IMAGEM = "gnucobol-ref"
BASE = "debian:trixie-slim"
ENV = dict(os.environ, MSYS_NO_PATHCONV="1")


def reg(nome, idade, cpf):
    return nome.ljust(30) + f"{idade:02d}" + f"{cpf:011d}" + "\n"


CASOS = {
    "aritmetica": dict(fonte=os.path.join(RAIZ, "testes", "cobol", "aritmetica.cbl"), entrada=""),
    "regressao_coboldicas": dict(fonte=os.path.join(RAIZ, "testes", "cobol", "regressao_coboldicas.cbl"),
                                 entrada="123.456.789-09\n15/05/1990\n12a\n12a\n1.5\n7x9\n103\n999\n"),
    "CAIXAREG": dict(entrada="10,50\n0\n20,00\n5\nS\n3,25\n"),
    "CAIXAREG_sem_desc": dict(prog="CAIXAREG", entrada="1234,56\n0,99\n10\nN\n"),
    "CALCMD01": dict(entrada="10,50\n20\n0\n3\n3\n"),
    "CALCMD01_div": dict(prog="CALCMD01", entrada="99\n98\n97\n7\n"),
    "CAD0004A": dict(entrada="ANA\n30\n123.456.789-00\nS\nBRUNO\n40\n111.111.111-11\nN\n"),
    "BUSCA01A_acha": dict(prog="BUSCA01A", entrada="00000000002\n",
                          arquivos={"CADASTRO2.dat": reg("ANA", 3, 1) + reg("BRUNO", 4, 2)}),
    "BUSCA01A_nao": dict(prog="BUSCA01A", entrada="99\n",
                         arquivos={"CADASTRO2.dat": reg("ANA", 3, 1) + reg("BRUNO", 4, 2)}),
    "CAD0005A_cadastra": dict(prog="CAD0005A", entrada="1\nMARIA\n9999\n", arquivos={"CADAGENDA.dat": ""}),
    "CAD0005A_lista": dict(prog="CAD0005A", entrada="2\n",
                           arquivos={"CADAGENDA.dat": "MARIA".ljust(30) + "9999".ljust(15) + "\n"}),
    "CAD0005A_repetido": dict(prog="CAD0005A", entrada="1\nJOAO\n9999\n",
                              arquivos={"CADAGENDA.dat": "MARIA".ljust(30) + "9999".ljust(15) + "\n"}),
    "CAD0005A_invalida": dict(prog="CAD0005A", entrada="7\n", arquivos={"CADAGENDA.dat": ""}),
    "PROG024A": dict(entrada="1\n100\nDOM CASMURRO\nMACHADO\n2\n100\n4\n3\n100\n5\n100\n9\n",
                     arquivos={"BIBLIOTECA.dat": "", "BIBLIOTECA.txt": ""}, ignora_data=True),
    "DRV0002": dict(entrada="ANA\n30\n15/05/1990\nDEV\nana@x.com\n123456789\nRUA A\nCIDADE\nSP\n12345678\nFIM\n"),
    "DRV0002_validacoes": dict(prog="DRV0002",
                               entrada="B1\nBRUNO\n10\n30\n32/01/2000\n15/05/1990\nDEV\nbad.com\nok@x.com\n1\nR\nC\nSP\n1\nFIM\n"),
}


def preparar(work: str, arquivos: dict) -> None:
    os.makedirs(work, exist_ok=True)
    for nome, conteudo in (arquivos or {}).items():
        with open(os.path.join(work, nome), "w", encoding="latin-1", newline="") as f:
            f.write(conteudo)


def docker(*args: str, entrada: bytes | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], input=entrada, capture_output=True, timeout=timeout, env=ENV)


def docker_ativo() -> bool:
    try:
        return docker("info", timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def garantir_imagem() -> None:
    if docker("image", "inspect", IMAGEM).returncode == 0:
        return
    print(f"[gnucobol] construindo a imagem {IMAGEM} (só na primeira vez)...", file=sys.stderr)
    r = docker("build", "-q", "-t", IMAGEM, os.path.join(RAIZ, "scripts", "gnucobol"), timeout=900)
    if r.returncode != 0:
        raise RuntimeError("falha ao construir a imagem: " + r.stderr.decode("utf-8", "replace"))


def limpar_imagem() -> None:
    """Remove a imagem de referência e a base Debian usada por ela."""
    for img in (IMAGEM, BASE):
        r = docker("rmi", img)
        print(f"[gnucobol] rmi {img}: " + ("removida" if r.returncode == 0 else "ausente"), file=sys.stderr)


def sem_conflito(texto: str) -> str:
    """O GnuCOBOL não compila marcas de conflito do git: fica o lado HEAD (como o nosso preproc)."""
    saida, estado = [], 0
    for ln in texto.splitlines(keepends=True):
        if ln.startswith("<<<<<<<"):
            estado = 1
        elif ln.startswith("=======") and estado == 1:
            estado = 2
        elif ln.startswith(">>>>>>>") and estado == 2:
            estado = 0
        elif estado != 2:
            saida.append(ln)
    return "".join(saida)


def fonte_do_caso(nome: str, caso: dict) -> tuple[str, str]:
    if "fonte" in caso:
        return os.path.splitext(os.path.basename(caso["fonte"]))[0], caso["fonte"]
    prog = caso.get("prog", nome.split("_")[0])
    return prog, os.path.join(PROG, prog + ".cbl")


def subprogramas(fontes: dict[str, str]) -> dict[str, str]:
    """Programas chamados por CALL 'NOME' (transitivamente) cujo fonte está em programas/."""
    achados = dict(fontes)
    fila = list(fontes.values())
    while fila:
        with open(fila.pop(), encoding="latin-1") as f:
            texto = f.read()
        for nome in re.findall(r"\bCALL\s+['\"]([A-Za-z0-9-]+)['\"]", texto, re.IGNORECASE):
            caminho = os.path.join(PROG, nome.upper() + ".cbl")
            if nome.upper() not in achados and os.path.isfile(caminho):
                achados[nome.upper()] = caminho
                fila.append(caminho)
    return achados


def construir(w: str, fontes: dict[str, str], principais: set[str]) -> list[str]:
    """Gera o C do nosso compilador (no host) e compila os dois lados dentro do container.

    Devolve as falhas de compilação, de qualquer um dos lados."""
    for sub in ("src", "c", "ref", "nosso"):
        os.makedirs(os.path.join(w, sub), exist_ok=True)
    falhas = []
    for prog, caminho in fontes.items():
        diag = Diagnosticos()
        if not cobc.compilar(caminho, os.path.join(w, "c", prog + ".c"), diag):
            erros = "; ".join(str(m) for m in diag.itens if m.severidade in ("E", "S"))
            falhas.append(f"{prog}: nosso compilador recusou o programa ({erros})")
        with open(caminho, encoding="latin-1", newline="") as f:
            texto = sem_conflito(f.read())
        with open(os.path.join(w, "src", prog + ".cbl"), "w", encoding="latin-1", newline="") as f:
            f.write(texto)
    # Programas chamados por CALL entram no executável principal do nosso compilador; no GnuCOBOL
    # cada um também vira módulo (.so), achado por COB_LIBRARY_PATH.
    linhas = []
    for p in fontes:
        linhas.append(f"cobc -m -I /copybooks -o /w/ref/{p}.so /w/src/{p}.cbl >/dev/null 2>&1 || echo 'FALHA cobc -m {p}'")
        if p in principais:
            linhas += [
                f"cobc -x -I /copybooks -o /w/ref/{p}.bin /w/src/{p}.cbl >/dev/null 2>&1 || echo 'FALHA cobc -x {p}'",
                f"gcc -O1 -w -I /runtime -o /w/nosso/{p}.bin /w/c/{p}.c -lm || echo 'FALHA gcc {p}'",
            ]
    r = docker("run", "--rm", "-v", f"{w}:/w", "-v", f"{os.path.join(RAIZ, 'runtime')}:/runtime:ro",
               "-v", f"{os.path.join(RAIZ, 'copybooks')}:/copybooks:ro", IMAGEM, "sh", "-c", "\n".join(linhas),
               timeout=900)
    saida = (r.stdout + r.stderr).decode("utf-8", "replace")
    falhas += [ln for ln in saida.splitlines() if ln.startswith("FALHA")]
    return falhas


def executar(w: str, lado: str, prog: str, entrada: str, work: str) -> str:
    cmd = ["run", "--rm", "-i", "-v", f"{work}:/work", "-v", f"{w}:/w:ro", "-w", "/work",
           "-e", "COB_LIBRARY_PATH=/w/ref", IMAGEM, f"/w/{lado}/{prog}.bin"]
    p = docker(*cmd, entrada=entrada.encode("utf-8"), timeout=120)
    return p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def mascarar_data(x):
    if isinstance(x, bytes):
        return re.sub(rb"\d\d/\d\d/\d{4}", b"DD/MM/AAAA", x)
    return re.sub(r"\d\d/\d\d/\d{4}", "DD/MM/AAAA", x)


def comparar(w: str, nome: str, caso: dict) -> list[str]:
    prog, _ = fonte_do_caso(nome, caso)
    wa = tempfile.mkdtemp(prefix="nosso_")
    wb = tempfile.mkdtemp(prefix="ref_")
    try:
        preparar(wa, caso.get("arquivos"))
        preparar(wb, caso.get("arquivos"))
        sa = executar(w, "nosso", prog, caso["entrada"], wa)
        sb = executar(w, "ref", prog, caso["entrada"], wb)
        mascara = caso.get("ignora_data")
        if mascara:
            sa, sb = mascarar_data(sa), mascarar_data(sb)
        difs = []
        if sa != sb:
            difs.append("stdout")
        for f in sorted(set(os.listdir(wa)) | set(os.listdir(wb))):
            pa, pb = os.path.join(wa, f), os.path.join(wb, f)
            if not (os.path.exists(pa) and os.path.exists(pb)):
                difs.append(f"arquivo {f} só de um lado")
                continue
            da, db = open(pa, "rb").read(), open(pb, "rb").read()
            if mascara:
                da, db = mascarar_data(da), mascarar_data(db)
            if da != db:
                difs.append(f"arquivo {f}")
        if difs:
            for linha in list(difflib.unified_diff(sb.splitlines(), sa.splitlines(), "gnucobol", "nosso",
                                                   lineterm="", n=0))[:14]:
                difs.append("    " + linha)
        return difs
    finally:
        shutil.rmtree(wa, ignore_errors=True)
        shutil.rmtree(wb, ignore_errors=True)


def executar_comparacao(filtro: str = "") -> tuple[int, int]:
    """Roda os casos; devolve (casos iguais, total). A imagem é construída se não existir."""
    garantir_imagem()
    casos = {n: c for n, c in CASOS.items() if not filtro or filtro in n}
    fontes = {}
    for nome, caso in casos.items():
        prog, caminho = fonte_do_caso(nome, caso)
        fontes[prog] = caminho
    principais = set(fontes)
    fontes = subprogramas(fontes)  # módulos chamados por CALL (ex.: DRV0002 -> CAD0002A)
    w = tempfile.mkdtemp(prefix="gnucobol_")
    iguais = 0
    try:
        for erro in construir(w, fontes, principais):
            print("ERRO de compilação:", erro)
        for nome, caso in casos.items():
            difs = comparar(w, nome, caso)
            falhas = [d for d in difs if not d.startswith("    ")]
            print(f"{nome:24s} " + ("IGUAL" if not falhas else "DIFERE (" + ", ".join(falhas) + ")"))
            for d in difs:
                if d.startswith("    "):
                    print(d)
            iguais += not falhas
    finally:
        shutil.rmtree(w, ignore_errors=True)
    return iguais, len(casos)


def rodar_testes_no_container() -> int:
    """Roda a suíte unittest inteira dentro do container (que tem gcc), sem precisar de gcc no host."""
    garantir_imagem()
    r = subprocess.run(["docker", "run", "--rm", "-v", f"{RAIZ}:/repo:ro", "-w", "/repo",
                        "-e", "PYTHONDONTWRITEBYTECODE=1", IMAGEM, "python3", "-m", "unittest", "discover",
                        "-s", "testes", "-t", "."], env=ENV)
    return r.returncode


def main() -> int:
    if "--limpar" in sys.argv:
        if docker_ativo():
            limpar_imagem()
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not docker_ativo():
        print("[gnucobol] Docker não está em execução", file=sys.stderr)
        return 2
    try:
        if "--testes" in sys.argv:
            return rodar_testes_no_container()
        iguais, total = executar_comparacao(args[0] if args else "")
    finally:
        if "--limpar-apos" in sys.argv:
            limpar_imagem()
    print(f"[gnucobol] {iguais}/{total} casos iguais ao GnuCOBOL")
    return 0 if iguais == total else 1


if __name__ == "__main__":
    sys.exit(main())
