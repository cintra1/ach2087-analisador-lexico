"""Pré-processador: marcas de conflito do git e diretiva COPY.

Trabalha em texto de formato fixo (cartão de 80 colunas), linha a linha,
antes do analisador léxico.
"""

from __future__ import annotations

import os
import re

from .diagnosticos import Diagnosticos

_COPY = re.compile(r"^(.{6}[ ])\s*COPY\s+([A-Za-z0-9_-]+)\s*\.\s*$", re.IGNORECASE)
_EXTENSOES = ("", ".cpy", ".CPY", ".cbl", ".CBL", ".cob", ".COB", ".copy", ".COPY")


def ler_fonte(caminho: str) -> tuple[str, str]:
    """Lê o arquivo e devolve (texto, codificação) — UTF-8 ou Latin-1."""
    with open(caminho, "rb") as f:
        dados = f.read()
    try:
        return dados.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return dados.decode("latin-1"), "latin-1"


def resolver_conflitos(linhas: list[str], diag: Diagnosticos, arquivo: str) -> list[str]:
    """Mantém o lado HEAD de blocos <<<<<<< / ======= / >>>>>>> e avisa."""
    saida: list[str] = []
    estado = 0  # 0 normal, 1 dentro do HEAD, 2 dentro do outro lado
    for n, linha in enumerate(linhas, 1):
        corpo = linha[7:].lstrip() if len(linha) > 7 else linha.lstrip()
        sem_cartao = linha.lstrip()
        if sem_cartao.startswith("<<<<<<<") or corpo.startswith("<<<<<<<"):
            estado = 1
            diag.aviso(
                f"marca de conflito de merge do git (<<<<<<<); mantido o lado HEAD",
                n,
                arquivo,
            )
            continue
        if estado and (sem_cartao.startswith("=======") or corpo.startswith("=======")):
            estado = 2
            continue
        if estado and (sem_cartao.startswith(">>>>>>>") or corpo.startswith(">>>>>>>")):
            estado = 0
            continue
        if estado == 2:
            continue
        saida.append(linha)
    return saida


def expandir_copy(
    linhas: list[str],
    diretorios: list[str],
    diag: Diagnosticos,
    arquivo: str,
    profundidade: int = 0,
) -> list[str]:
    saida: list[str] = []
    for n, linha in enumerate(linhas, 1):
        m = _COPY.match(linha.rstrip("\r\n"))
        if m and len(linha) > 6 and linha[6] not in "*/":
            nome = m.group(2)
            achado = None
            for d in diretorios:
                for ext in _EXTENSOES:
                    cand = os.path.join(d, nome + ext)
                    if os.path.isfile(cand):
                        achado = cand
                        break
                if achado:
                    break
            if achado is None:
                diag.erro(f"copybook '{nome}' não encontrado (procurado em {', '.join(diretorios)})", n, arquivo)
                continue
            if profundidade > 8:
                diag.erro(f"COPY aninhado demais em '{nome}'", n, arquivo)
                continue
            texto, _ = ler_fonte(achado)
            sub = texto.splitlines()
            sub = resolver_conflitos(sub, diag, achado)
            saida.extend(expandir_copy(sub, diretorios, diag, achado, profundidade + 1))
            continue
        saida.append(linha)
    return saida


def preprocessar(caminho: str, diag: Diagnosticos, dirs_copy: list[str] | None = None) -> tuple[str, str]:
    texto, codificacao = ler_fonte(caminho)
    base = os.path.dirname(os.path.abspath(caminho))
    dirs = [base, os.path.join(base, "copybooks"), os.path.join(os.path.dirname(base), "copybooks")]
    dirs += dirs_copy or []
    linhas = texto.splitlines()
    linhas = resolver_conflitos(linhas, diag, caminho)
    linhas = expandir_copy(linhas, dirs, diag, caminho)
    return "\n".join(linhas) + "\n", codificacao
