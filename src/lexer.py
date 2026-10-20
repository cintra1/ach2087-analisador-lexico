from dataclasses import dataclass

from .reservadas import RESERVADAS

PALAVRA_RESERVADA = "PALAVRA_RESERVADA"
IDENTIFICADOR = "IDENTIFICADOR"
NUMERO_INTEIRO = "NUMERO_INTEIRO"
NUMERO_DECIMAL = "NUMERO_DECIMAL"
LITERAL = "LITERAL"
ERRO = "ERRO"
_PONTOS = {".": "PONTO", ",": "VIRGULA", "(": "ABRE_PARENTESES", ")": "FECHA_PARENTESES"}
_OPERADORES = ("**", ">=", "<=", "<>", "+", "-", "*", "/", ">", "<", "=", "&")


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
                if caractere in "\"'":
                    fim = indice + 1
                    while fim < len(linha) and linha[fim] != caractere:
                        fim += 1
                    if fim < len(linha):
                        fim += 1
                        tokens.append(Token(LITERAL, linha[indice:fim], numero, coluna))
                    else:
                        tokens.append(Token(ERRO, linha[indice:], numero, coluna))
                        erros.append(ErroLexico("Literal não terminado.", numero, coluna, linha[indice:]))
                    indice = fim
                elif caractere.isdigit() or (caractere in "+-" and indice + 1 < len(linha) and linha[indice + 1].isdigit()):
                    fim = indice + 1
                    while fim < len(linha) and linha[fim].isdigit():
                        fim += 1
                    tipo = NUMERO_INTEIRO
                    if fim + 1 < len(linha) and linha[fim] == "." and linha[fim + 1].isdigit():
                        tipo = NUMERO_DECIMAL
                        fim += 1
                        while fim < len(linha) and linha[fim].isdigit():
                            fim += 1
                    tokens.append(Token(tipo, linha[indice:fim], numero, coluna))
                    indice = fim
                elif caractere.isalpha() or caractere in "_-":
                    fim = indice + 1
                    while fim < len(linha) and (linha[fim].isalnum() or linha[fim] in "_-"):
                        fim += 1
                    lexema = linha[indice:fim]
                    tipo = PALAVRA_RESERVADA if lexema.upper() in RESERVADAS else IDENTIFICADOR
                    tokens.append(Token(tipo, lexema, numero, coluna))
                    indice = fim
                else:
                    operador = next((op for op in _OPERADORES if linha.startswith(op, indice)), None)
                    if operador:
                        tokens.append(Token("OPERADOR", operador, numero, coluna))
                        indice += len(operador)
                    elif caractere in _PONTOS:
                        tokens.append(Token(_PONTOS[caractere], caractere, numero, coluna))
                        indice += 1
                    else:
                        tokens.append(Token(ERRO, caractere, numero, coluna))
                        erros.append(ErroLexico("Caractere inválido.", numero, coluna, caractere))
                        indice += 1
        formato = self.formato_solicitado if self.formato_solicitado != "auto" else "livre"
        return Resultado(tokens, [], erros, formato, self.formato_solicitado, len(self.codigo.splitlines()))
