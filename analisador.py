"""Ponto de entrada do analisador léxico de COBOL.

Uso:
    py analisador.py exemplos/ola.cob
    py analisador.py --formato livre exemplos/livre.cob
    py analisador.py --json exemplos/ola.cob
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.copybooks import CopybookError, expandir_copys
from src.lexer import AnalisadorLexico
from src.relatorio import formatar, para_json


def main(argumentos: list[str] | None = None) -> int:
    _configurar_saida()
    parser = argparse.ArgumentParser(
        description="Analisador léxico para programas COBOL, nos formatos fixo e livre."
    )
    parser.add_argument("arquivos", nargs="+", help="Arquivos-fonte COBOL (.cob, .cbl, ...)")
    parser.add_argument(
        "-f",
        "--formato",
        choices=("auto", "fixo", "livre"),
        default="auto",
        help="Formato do fonte. 'auto' reconhece cartão de 80 colunas ou código livre (padrão: auto).",
    )
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez da tabela de texto.")
    parser.add_argument("-o", "--saida", help="Grava o relatório neste arquivo.")
    parser.add_argument(
        "-I",
        "--diretorio-copybook",
        dest="diretorios_copybook",
        action="append",
        type=Path,
        default=[],
        help="Procura copybooks também neste diretório; pode ser informado mais de uma vez.",
    )
    opcoes = parser.parse_args(argumentos)

    blocos: list[str] = []
    objetos: list[str] = []
    houve_erro_lexico = False
    codigo_saida = 0

    for nome in opcoes.arquivos:
        caminho = Path(nome)
        if not caminho.is_file():
            print(f"[S] Arquivo de entrada não encontrado: {caminho}", file=sys.stderr)
            codigo_saida = 2
            continue
        codigo = _ler_fonte(caminho)
        try:
            codigo = expandir_copys(
                codigo, caminho, opcoes.diretorios_copybook
            )
        except CopybookError as erro:
            print(f"[S] Falha ao expandir COPY: {erro}", file=sys.stderr)
            codigo_saida = 2
            continue
        resultado = AnalisadorLexico(codigo, formato=opcoes.formato).analisar()
        if resultado.erros:
            houve_erro_lexico = True
        if opcoes.json:
            objetos.append(para_json(resultado, str(caminho)))
        else:
            blocos.append(formatar(resultado, str(caminho)))

    if opcoes.json:
        if len(objetos) == 1:
            texto = objetos[0] + "\n"
        else:
            texto = "[\n" + ",\n".join(objetos) + "\n]\n"
    else:
        texto = "\n".join(blocos)

    if opcoes.saida:
        Path(opcoes.saida).write_text(texto, encoding="utf-8")
    elif texto:
        sys.stdout.write(texto)

    if codigo_saida == 0 and houve_erro_lexico:
        return 1
    return codigo_saida


def _ler_fonte(caminho: Path) -> str:
    dados = caminho.read_bytes()
    if dados.startswith(b"\xef\xbb\xbf"):
        dados = dados[3:]
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def _configurar_saida() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
