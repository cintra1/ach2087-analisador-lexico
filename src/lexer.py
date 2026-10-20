from dataclasses import dataclass

from .reservadas import RESERVADAS

PALAVRA_RESERVADA = "PALAVRA_RESERVADA"
IDENTIFICADOR = "IDENTIFICADOR"
ERRO = "ERRO"
_PONTOS = {".": "PONTO", ",": "VIRGULA", "(": "ABRE_PARENTESES", ")": "FECHA_PARENTESES"}


@dataclass(frozen=True)
class Token:
    tipo: str
    lexema: str
    linha: int
    coluna: int


@dataclass(frozen=True)
class Anotacao:
    tipo: str
    texto: str
    linha: int
    coluna: int


@dataclass(frozen=True)
class ErroLexico:
    mensagem: str
    linha: int
    coluna: int
    lexema: str = ""


@dataclass
class Resultado:
    tokens: list[Token]
    comentarios: list[Anotacao]
    erros: list[ErroLexico]
    formato: str
    formato_solicitado: str
    linhas: int

    def resumo(self) -> dict[str, int]:
        resumo: dict[str, int] = {}
        for token in self.tokens:
            resumo[token.tipo] = resumo.get(token.tipo, 0) + 1
        return dict(sorted(resumo.items()))


class AnalisadorLexico:
    def __init__(self, codigo: str, formato: str = "auto"):
        self.codigo = codigo
        self.formato_solicitado = formato

    def analisar(self) -> Resultado:
        tokens: list[Token] = []
        erros: list[ErroLexico] = []
        for numero, linha in enumerate(self.codigo.splitlines(), 1):
            indice = 0
            while indice < len(linha):
                caractere = linha[indice]
                if caractere.isspace():
                    indice += 1
                    continue
                coluna = indice + 1
                if caractere.isalnum() or caractere in "_-":
                    fim = indice + 1
                    while fim < len(linha) and (linha[fim].isalnum() or linha[fim] in "_-"):
                        fim += 1
                    lexema = linha[indice:fim]
                    tipo = PALAVRA_RESERVADA if lexema.upper() in RESERVADAS else IDENTIFICADOR
                    tokens.append(Token(tipo, lexema, numero, coluna))
                    indice = fim
                elif caractere in _PONTOS:
                    tokens.append(Token(_PONTOS[caractere], caractere, numero, coluna))
                    indice += 1
                else:
                    tokens.append(Token(ERRO, caractere, numero, coluna))
                    erros.append(ErroLexico("Caractere inválido.", numero, coluna, caractere))
                    indice += 1
        formato = self.formato_solicitado if self.formato_solicitado != "auto" else "livre"
        return Resultado(tokens, [], erros, formato, self.formato_solicitado, len(self.codigo.splitlines()))
