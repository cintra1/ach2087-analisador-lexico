"""Apresentação do resultado do analisador, em texto ou JSON."""

from __future__ import annotations

import json
from dataclasses import asdict

from .lexer import Resultado


def formatar(resultado: Resultado, arquivo: str) -> str:
    linhas: list[str] = [
        "Analisador léxico COBOL",
        f"Arquivo: {arquivo}",
        _linha_formato(resultado),
        f"Linhas: {resultado.linhas}",
        "",
        _tabela_tokens(resultado),
    ]

    if resultado.comentarios:
        linhas.extend(["", "Comentários e diretivas", _tabela_anotacoes(resultado)])

    if resultado.erros:
        linhas.extend(["", "Erros léxicos"])
        for erro in resultado.erros:
            linhas.append(
                f"  Linha {erro.linha}, coluna {erro.coluna}: {erro.mensagem}"
            )

    linhas.extend(["", "Resumo"])
    resumo = resultado.resumo()
    if not resumo:
        linhas.append("  (nenhum token)")
    for tipo, quantidade in resumo.items():
        linhas.append(f"  {tipo}: {quantidade}")
    linhas.append(f"  Tokens: {len(resultado.tokens)}")
    linhas.append(f"  Comentários: {_contar(resultado, 'COMENTARIO')}")
    linhas.append(f"  Diretivas: {_contar(resultado, 'DIRETIVA')}")
    linhas.append(f"  Erros: {len(resultado.erros)}")
    linhas.append("")
    return "\n".join(linhas)


def para_json(resultado: Resultado, arquivo: str) -> str:
    return json.dumps(_para_dict(resultado, arquivo), ensure_ascii=False, indent=2)


def _para_dict(resultado: Resultado, arquivo: str) -> dict:
    return {
        "arquivo": arquivo,
        "formato": resultado.formato,
        "formato_solicitado": resultado.formato_solicitado,
        "linhas": resultado.linhas,
        "tokens": [asdict(token) for token in resultado.tokens],
        "comentarios": [asdict(item) for item in resultado.comentarios],
        "erros": [asdict(erro) for erro in resultado.erros],
        "resumo": resultado.resumo(),
    }


def _linha_formato(resultado: Resultado) -> str:
    if resultado.formato_solicitado == "auto":
        return f"Formato: {resultado.formato} (detecção automática)"
    return f"Formato: {resultado.formato}"


def _contar(resultado: Resultado, tipo: str) -> int:
    return sum(1 for item in resultado.comentarios if item.tipo == tipo)


def _tabela_tokens(resultado: Resultado) -> str:
    cabecalho = ("Linha", "Coluna", "Token", "Lexema")
    dados = [
        (str(token.linha), str(token.coluna), token.tipo, _visivel(token.lexema))
        for token in resultado.tokens
    ]
    return _tabela(cabecalho, dados)


def _tabela_anotacoes(resultado: Resultado) -> str:
    cabecalho = ("Linha", "Coluna", "Tipo", "Texto")
    dados = [
        (str(item.linha), str(item.coluna), item.tipo, _visivel(item.texto))
        for item in resultado.comentarios
    ]
    return _tabela(cabecalho, dados)


def _tabela(cabecalho: tuple[str, ...], dados: list[tuple[str, ...]]) -> str:
    larguras = [len(coluna) for coluna in cabecalho]
    for linha in dados:
        for indice, celula in enumerate(linha):
            larguras[indice] = max(larguras[indice], len(celula))

    def formatar_linha(celulas: tuple[str, ...]) -> str:
        partes = []
        for indice, celula in enumerate(celulas):
            if indice < 2:
                partes.append(celula.rjust(larguras[indice]))
            else:
                partes.append(celula.ljust(larguras[indice]))
        return "  ".join(partes).rstrip()

    separador = "  ".join("-" * largura for largura in larguras)
    linhas = [formatar_linha(cabecalho), separador]
    linhas.extend(formatar_linha(linha) for linha in dados)
    if not dados:
        linhas.append("(vazio)")
    return "\n".join(linhas)


def _visivel(texto: str) -> str:
    return texto.replace("\n", "\\n").replace("\t", "\\t")
