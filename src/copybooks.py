"""Expansão de instruções COPY simples antes da análise léxica."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from .lexer import detectar_formato

_COPY = re.compile(
    r"""^\s*COPY\s+(?P<nome>'[^']+'|"[^"]+"|[A-Za-z0-9_./\\-]+)\s*\.\s*(?:\*>.*)?$""",
    re.IGNORECASE,
)
_EXTENSOES = ("", ".cpy", ".cob", ".cbl", ".copy")


class CopybookError(Exception):
    """Erro ao localizar ou expandir um copybook."""


def expandir_copys(
    codigo: str,
    arquivo_fonte: Path,
    diretorios: Sequence[Path] = (),
) -> str:
    """Expande COPY standalone, inclusive recursivo, em código COBOL."""

    diretorios_resolucao = [arquivo_fonte.resolve().parent]
    diretorios_resolucao.extend(path.resolve() for path in diretorios)
    caminho_raiz = arquivo_fonte.resolve()
    return _expandir(codigo, caminho_raiz, diretorios_resolucao, ())


def _expandir(
    codigo: str,
    arquivo: Path,
    diretorios: list[Path],
    pilha: tuple[Path, ...],
) -> str:
    caminho = arquivo.resolve()
    if caminho in pilha:
        ciclo = " -> ".join(item.name for item in (*pilha, caminho))
        raise CopybookError(f"Ciclo de COPY detectado: {ciclo}.")

    formato = detectar_formato(codigo.splitlines())
    linhas_expandidas: list[str] = []
    for numero, linha in enumerate(codigo.splitlines(), start=1):
        instrucao = _instrucao_de_codigo(linha, formato)
        correspondencia = _COPY.fullmatch(instrucao)
        if correspondencia is None:
            linhas_expandidas.append(linha)
            continue

        nome = correspondencia.group("nome").strip("'\"")
        copybook = _localizar(nome, diretorios)
        if copybook is None:
            raise CopybookError(
                f"{caminho}:{numero}: copybook {nome!r} não encontrado."
            )
        try:
            conteudo = _ler_copybook(copybook)
        except OSError as erro:
            raise CopybookError(
                f"Não foi possível ler o copybook {copybook}: {erro}"
            ) from erro
        linhas_expandidas.extend(
            _expandir(conteudo, copybook, diretorios, (*pilha, caminho)).splitlines()
        )

    resultado = "\n".join(linhas_expandidas)
    if codigo.endswith(("\n", "\r")):
        resultado += "\n"
    return resultado


def _instrucao_de_codigo(linha: str, formato: str) -> str:
    linha_expandida = linha.expandtabs(8)
    if formato == "fixo":
        if len(linha_expandida) < 7 or linha_expandida[6] in "*/":
            return ""
        return linha_expandida[7:72]
    texto = linha_expandida.lstrip()
    if texto.startswith(("*>", "* ")):
        return ""
    return linha_expandida


def _localizar(nome: str, diretorios: list[Path]) -> Path | None:
    membro = Path(nome)
    nomes = (
        (membro,)
        if membro.suffix
        else tuple(Path(nome + extensao) for extensao in _EXTENSOES)
    )
    for diretorio in diretorios:
        for candidato in nomes:
            caminho = diretorio / candidato
            if caminho.is_file():
                return caminho.resolve()
    return None


def _ler_copybook(caminho: Path) -> str:
    dados = caminho.read_bytes()
    if dados.startswith(b"\xef\xbb\xbf"):
        dados = dados[3:]
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("latin-1")
