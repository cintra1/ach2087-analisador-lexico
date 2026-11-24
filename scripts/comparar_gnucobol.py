"""Compara a execução do nosso compilador com a do GnuCOBOL 3.2 (em Docker).

Pré-requisitos: Docker em execução e a imagem `gnucobol-ref` (debian + apt install gnucobol).
Para cada caso, roda o mesmo stdin e os mesmos arquivos de entrada nos dois lados e compara
a saída padrão e os arquivos gerados.

Uso: py scripts/comparar_gnucobol.py [filtro]
"""

from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROG = os.path.join(RAIZ, "programas")
REF = os.path.join(tempfile.gettempdir(), "ref_gnucobol")


def reg(nome, idade, cpf):
    return nome.ljust(30) + f"{idade:02d}" + f"{cpf:011d}" + "\n"


CASOS = {
    "aritmetica": dict(fonte=os.path.join(RAIZ, "testes", "cobol", "aritmetica.cbl"), entrada=""),
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


def rodar_nosso(prog: str, entrada: str, work: str) -> str:
    exe = os.path.join(RAIZ, "build", prog + ".exe")
    p = subprocess.run([exe], input=entrada.encode("utf-8"), capture_output=True, cwd=work, timeout=60)
    return p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def rodar_ref(prog: str, entrada: str, work: str) -> str:
    cmd = ["docker", "run", "--rm", "-i", "-v", f"{work}:/work", "-v", f"{REF}:/ref:ro", "-w", "/work",
           "-e", "COB_LIBRARY_PATH=/ref", "gnucobol-ref", f"/ref/{prog}.bin"]
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    p = subprocess.run(cmd, input=entrada.encode("utf-8"), capture_output=True, timeout=120, env=env)
    return p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def main() -> int:
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    falhas = 0
    for nome, caso in CASOS.items():
        if filtro and filtro not in nome:
            continue
        prog = caso.get("prog", nome.split("_")[0])
        if "fonte" in caso:
            subprocess.run([sys.executable, os.path.join(RAIZ, "cobc.py"), caso["fonte"], "--build-dir",
                            os.path.join(RAIZ, "build")], capture_output=True)
            prog = os.path.splitext(os.path.basename(caso["fonte"]))[0]
        wa = tempfile.mkdtemp(prefix="nosso_")
        wb = tempfile.mkdtemp(prefix="ref_")
        preparar(wa, caso.get("arquivos"))
        preparar(wb, caso.get("arquivos"))
        sa = rodar_nosso(prog, caso["entrada"], wa)
        sb = rodar_ref(prog, caso["entrada"], wb)
        difs = []
        if caso.get("ignora_data"):
            import re
            sa = re.sub(r"\d\d/\d\d/\d{4}", "DD/MM/AAAA", sa)
            sb = re.sub(r"\d\d/\d\d/\d{4}", "DD/MM/AAAA", sb)
        if sa != sb:
            difs.append("stdout")
        for f in sorted(set(os.listdir(wa)) | set(os.listdir(wb))):
            pa, pb = os.path.join(wa, f), os.path.join(wb, f)
            if not (os.path.exists(pa) and os.path.exists(pb)):
                difs.append(f"arquivo {f} só de um lado")
                continue
            da, db = open(pa, "rb").read(), open(pb, "rb").read()
            if caso.get("ignora_data"):
                import re
                da = re.sub(rb"\d\d/\d\d/\d{4}", b"DD/MM/AAAA", da)
                db = re.sub(rb"\d\d/\d\d/\d{4}", b"DD/MM/AAAA", db)
            if da != db:
                difs.append(f"arquivo {f}")
        status = "IGUAL" if not difs else "DIFERE (" + ", ".join(difs) + ")"
        print(f"{nome:24s} {status}")
        if difs:
            falhas += 1
            import difflib
            for linha in list(difflib.unified_diff(sb.splitlines(), sa.splitlines(), "gnucobol", "nosso", lineterm="", n=0))[:14]:
                print("    " + linha)
        shutil.rmtree(wa, ignore_errors=True)
        shutil.rmtree(wb, ignore_errors=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
