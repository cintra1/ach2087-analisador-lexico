"""Analisador léxico de COBOL.

O fluxo é:
1. Detectar formato fixo (colunas) ou livre, se o chamador não escolheu.
2. Montar um texto lógico, descartando área de sequência, área de
   identificação e comentários de coluna 7, e juntando continuações.
3. Varrer esse texto e classificar cada lexema.
"""

from __future__ import annotations

from dataclasses import dataclass

from .reservadas import FIGURATIVAS, RESERVADAS

PALAVRA_RESERVADA = "PALAVRA_RESERVADA"
IDENTIFICADOR = "IDENTIFICADOR"
CONSTANTE_FIGURATIVA = "CONSTANTE_FIGURATIVA"
NUMERO_INTEIRO = "NUMERO_INTEIRO"
NUMERO_DECIMAL = "NUMERO_DECIMAL"
NUMERO_DE_NIVEL = "NUMERO_DE_NIVEL"
LITERAL = "LITERAL"
CADEIA_PICTURE = "CADEIA_PICTURE"
OPERADOR_ARITMETICO = "OPERADOR_ARITMETICO"
OPERADOR_RELACIONAL = "OPERADOR_RELACIONAL"
OPERADOR_CONCATENACAO = "OPERADOR_CONCATENACAO"
PONTO = "PONTO"
VIRGULA = "VIRGULA"
PONTO_E_VIRGULA = "PONTO_E_VIRGULA"
ABRE_PARENTESES = "ABRE_PARENTESES"
FECHA_PARENTESES = "FECHA_PARENTESES"
DOIS_PONTOS = "DOIS_PONTOS"
ERRO = "ERRO"

FORMATOS = ("auto", "fixo", "livre")

# O que pode aparecer imediatamente depois de um número de nível.
_SEGUIDORES_DE_NIVEL = frozenset(
    {
        "BINARY",
        "BLANK",
        "COMP",
        "COMP-1",
        "COMP-2",
        "COMP-3",
        "COMP-4",
        "COMP-5",
        "COMPUTATIONAL",
        "COMPUTATIONAL-1",
        "COMPUTATIONAL-2",
        "COMPUTATIONAL-3",
        "COMPUTATIONAL-4",
        "COMPUTATIONAL-5",
        "DISPLAY",
        "EXTERNAL",
        "FILLER",
        "GLOBAL",
        "INDEX",
        "JUST",
        "JUSTIFIED",
        "LEADING",
        "OCCURS",
        "PACKED-DECIMAL",
        "PIC",
        "PICTURE",
        "POINTER",
        "REDEFINES",
        "RENAMES",
        "SIGN",
        "SYNC",
        "SYNCHRONIZED",
        "TRAILING",
        "USAGE",
        "VALUE",
        "VALUES",
    }
)

_PREFIXOS_LITERAIS = frozenset({"X", "N", "Z", "B", "G", "NX", "BX"})
_OPERADORES_DUPLOS = {
    "**": OPERADOR_ARITMETICO,
    ">=": OPERADOR_RELACIONAL,
    "<=": OPERADOR_RELACIONAL,
    "<>": OPERADOR_RELACIONAL,
}
_OPERADORES_SIMPLES = {
    "+": OPERADOR_ARITMETICO,
    "-": OPERADOR_ARITMETICO,
    "*": OPERADOR_ARITMETICO,
    "/": OPERADOR_ARITMETICO,
    ">": OPERADOR_RELACIONAL,
    "<": OPERADOR_RELACIONAL,
    "=": OPERADOR_RELACIONAL,
    "&": OPERADOR_CONCATENACAO,
    ".": PONTO,
    ",": VIRGULA,
    ";": PONTO_E_VIRGULA,
    "(": ABRE_PARENTESES,
    ")": FECHA_PARENTESES,
    ":": DOIS_PONTOS,
}
_LETRAS_PICTURE = frozenset("ABEGNPSVXZ9")
_SINAIS_PICTURE = frozenset("0/+-*$")


@dataclass(frozen=True)
class Token:
    tipo: str
    lexema: str
    linha: int
    coluna: int


@dataclass(frozen=True)
class Anotacao:
    """Comentário ou diretiva de compilação fora do fluxo de tokens."""

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
        contagem: dict[str, int] = {}
        for token in self.tokens:
            contagem[token.tipo] = contagem.get(token.tipo, 0) + 1
        return dict(sorted(contagem.items()))


@dataclass
class _Fonte:
    texto: str
    mapa: list[tuple[int, int]]
    comentarios: list[Anotacao]
    erros: list[ErroLexico]
    formato: str
    linhas: int


def _letra(caractere: str) -> bool:
    return len(caractere) == 1 and ("A" <= caractere <= "Z" or "a" <= caractere <= "z")


def _digito(caractere: str) -> bool:
    return len(caractere) == 1 and "0" <= caractere <= "9"


def _valor_de_nivel(lexema: str) -> int | None:
    if not lexema.isdigit():
        return None
    valor = int(lexema)
    if 1 <= valor <= 49 or valor in (66, 77, 88):
        return valor
    return None


def detectar_formato(linhas: list[str]) -> str:
    """Escolhe fixo ou livre a partir do próprio fonte.

    Uma diretiva ``>>SOURCE FORMAT`` tem prioridade. Sem ela, cada linha
    vota: o cartão clássico (colunas 1-6 em branco ou numéricas e coluna 7
    com indicador válido) vota em fixo; código que começa antes da coluna 8
    vota em livre. Empate fica com o formato fixo, que é o tradicional.
    """

    expandidas = [linha.expandtabs(8) for linha in linhas]
    for linha in expandidas:
        comando = linha.lstrip(" ").upper()
        if comando.startswith(">>") and "SOURCE" in comando and "FORMAT" in comando:
            if "FREE" in comando:
                return "livre"
            if "FIXED" in comando:
                return "fixo"

    votos_fixo = 0
    votos_livre = 0
    for linha in expandidas:
        if not linha.strip():
            continue
        if _parece_linha_fixa(linha):
            votos_fixo += 1
            continue
        if _parece_linha_livre(linha):
            votos_livre += 1

    if votos_livre > votos_fixo:
        return "livre"
    return "fixo"


def _parece_linha_fixa(linha: str) -> bool:
    if len(linha) < 7:
        return False
    sequencia, indicador = linha[:6], linha[6]
    sequencia_valida = sequencia.strip() == "" or sequencia.strip().isdigit()
    indicador_valido = indicador in " */Dd-"
    tem_codigo = len(linha) > 7 and linha[7:].strip() != ""
    comentario = indicador in "*/"
    return sequencia_valida and indicador_valido and (tem_codigo or comentario)


def _parece_linha_livre(linha: str) -> bool:
    if not linha.strip() or _parece_linha_fixa(linha):
        return False
    if linha[0] not in " \t":
        return True
    return len(linha) >= 7


class AnalisadorLexico:
    def __init__(self, codigo: str, formato: str = "auto"):
        if formato not in FORMATOS:
            raise ValueError("formato deve ser 'auto', 'fixo' ou 'livre'")
        self.codigo = codigo
        self.formato_solicitado = formato

    def analisar(self) -> Resultado:
        linhas = self.codigo.splitlines()
        formato = (
            self.formato_solicitado
            if self.formato_solicitado != "auto"
            else detectar_formato(linhas)
        )
        fonte = _montar_fonte(linhas, formato)
        return _varrer(fonte, self.formato_solicitado)


def _montar_fonte(linhas: list[str], formato: str) -> _Fonte:
    caracteres: list[str] = []
    mapa: list[tuple[int, int]] = []
    comentarios: list[Anotacao] = []
    erros: list[ErroLexico] = []
    pode_continuar = False

    def adicionar(caractere: str, linha: int, coluna: int) -> None:
        caracteres.append(caractere)
        mapa.append((linha, coluna))

    def quebrar(linha: int) -> None:
        adicionar("\n", linha, 1)

    for numero, bruta in enumerate(linhas, start=1):
        linha = bruta.expandtabs(8)
        if linha.strip() == "":
            quebrar(numero)
            pode_continuar = False
            continue

        sem_recuo = linha.lstrip(" ")
        if sem_recuo.startswith(">>"):
            coluna = len(linha) - len(sem_recuo) + 1
            comentarios.append(Anotacao("DIRETIVA", sem_recuo.rstrip(), numero, coluna))
            quebrar(numero)
            pode_continuar = False
            continue

        if formato == "livre":
            for indice, caractere in enumerate(linha):
                adicionar(caractere, numero, indice + 1)
            quebrar(numero)
            pode_continuar = True
            continue

        if len(linha) < 7:
            if any(_letra(caractere) for caractere in linha):
                erros.append(
                    ErroLexico(
                        "Linha curta demais para o formato fixo; o código começa na coluna 8.",
                        numero,
                        1,
                        linha.strip(),
                    )
                )
            quebrar(numero)
            pode_continuar = False
            continue

        indicador = linha[6]
        corpo = linha[7:72]

        if indicador in "*/":
            comentarios.append(
                Anotacao("COMENTARIO", (indicador + corpo).rstrip(), numero, 7)
            )
            quebrar(numero)
            pode_continuar = False
            continue

        if indicador == "-":
            if not pode_continuar:
                erros.append(
                    ErroLexico(
                        "Linha de continuação sem linha de código imediatamente anterior.",
                        numero,
                        7,
                        "-",
                    )
                )
            else:
                aspas = _aspas_aberta(caracteres)
                if caracteres and caracteres[-1] == "\n":
                    caracteres.pop()
                    mapa.pop()
                if not aspas:
                    while caracteres and caracteres[-1] == " ":
                        caracteres.pop()
                        mapa.pop()
                util = corpo.lstrip(" ")
                coluna = 8 + (len(corpo) - len(util))
                if aspas and util.startswith(aspas):
                    util = util[1:]
                    coluna += 1
                for deslocamento, caractere in enumerate(util):
                    adicionar(caractere, numero, coluna + deslocamento)
                quebrar(numero)
                pode_continuar = True
                continue

            for indice, caractere in enumerate(corpo):
                adicionar(caractere, numero, 8 + indice)
            quebrar(numero)
            pode_continuar = True
            continue

        if indicador not in " Dd":
            erros.append(
                ErroLexico(
                    f"Indicador inválido na coluna 7: {indicador!r}.",
                    numero,
                    7,
                    indicador,
                )
            )

        for indice, caractere in enumerate(corpo):
            adicionar(caractere, numero, 8 + indice)
        quebrar(numero)
        pode_continuar = True

    if len(caracteres) != len(mapa):
        raise RuntimeError("mapa de colunas inconsistente com o texto lógico")

    return _Fonte("".join(caracteres), mapa, comentarios, erros, formato, len(linhas))


def _aspas_aberta(caracteres: list[str]) -> str | None:
    aberta: str | None = None
    indice = 0
    total = len(caracteres)
    while indice < total:
        caractere = caracteres[indice]
        if aberta:
            if caractere == "\n":
                indice += 1
                continue
            if caractere == aberta:
                if indice + 1 < total and caracteres[indice + 1] == aberta:
                    indice += 2
                    continue
                aberta = None
            indice += 1
            continue
        if caractere in "\"'":
            aberta = caractere
        indice += 1
    return aberta


def _varrer(fonte: _Fonte, formato_solicitado: str) -> Resultado:
    scanner = _Scanner(fonte)
    scanner.varrer()
    comentarios = sorted(
        scanner.comentarios, key=lambda item: (item.linha, item.coluna, item.texto)
    )
    erros = sorted(scanner.erros, key=lambda item: (item.linha, item.coluna, item.mensagem))
    return Resultado(
        tokens=scanner.tokens,
        comentarios=comentarios,
        erros=erros,
        formato=fonte.formato,
        formato_solicitado=formato_solicitado,
        linhas=fonte.linhas,
    )


class _Scanner:
    def __init__(self, fonte: _Fonte):
        self.texto = fonte.texto
        self.mapa = fonte.mapa
        self.formato = fonte.formato
        self.tokens: list[Token] = []
        self.comentarios = list(fonte.comentarios)
        self.erros = list(fonte.erros)
        self.i = 0
        self.no_inicio = True
        self.apos_ponto = False
        self.esperando_picture = False
        self.viu_is = False

    def varrer(self) -> None:
        while self.i < len(self.texto):
            self._avancar_ignoraveis()
            if self.i >= len(self.texto):
                break

            if self.esperando_picture and not self.viu_is and self._a_frente_e("IS"):
                self._avancar_ignoraveis()
                self._emitir(self._token_palavra())
                self.viu_is = True
                continue

            if self.esperando_picture and self._inicia_picture(self.i):
                self.esperando_picture = False
                self.viu_is = False
                self._emitir(self._token_picture())
                continue

            if self.esperando_picture:
                self.erros.append(
                    ErroLexico("Cadeia de picture ausente.", *self._pos(), "")
                )
                self.esperando_picture = False
                self.viu_is = False

            posicao = self.i
            token = self._proximo_token()
            if self.i == posicao:
                self.i += 1
            self._emitir(token)

        if self.esperando_picture:
            self.erros.append(
                ErroLexico("Cadeia de picture ausente.", *self._pos(), "")
            )

    def _emitir(self, token: Token) -> None:
        self.tokens.append(token)
        self.no_inicio = False
        self.apos_ponto = token.tipo == PONTO
        if token.tipo == PALAVRA_RESERVADA and token.lexema.upper() in {"PIC", "PICTURE"}:
            # PIC / PICTURE abre um contexto: o próximo lexema é uma cadeia de picture,
            # que não é uma palavra nem um número comum.
            self.esperando_picture = True
            self.viu_is = False

    def _pos(self, indice: int | None = None) -> tuple[int, int]:
        if indice is None:
            indice = self.i
        if not self.mapa:
            return 1, 1
        if indice < 0:
            return self.mapa[0]
        if indice >= len(self.mapa):
            return self.mapa[-1]
        return self.mapa[indice]

    def _avancar_ignoraveis(self) -> None:
        self.i, self.no_inicio = self._pular(self.i, True, self.no_inicio)

    def _pular(self, indice: int, registrar: bool, no_inicio: bool) -> tuple[int, bool]:
        total = len(self.texto)
        while indice < total:
            caractere = self.texto[indice]
            if caractere in " \t\r\f":
                indice += 1
                continue
            if caractere == "\n":
                indice += 1
                no_inicio = True
                continue
            if self.texto.startswith("*>", indice):
                indice = self._pular_comentario(indice, registrar)
                no_inicio = True
                continue
            if (
                self.formato == "livre"
                and no_inicio
                and caractere == "*"
                and self._estrela_de_comentario(indice)
            ):
                indice = self._pular_comentario(indice, registrar)
                no_inicio = True
                continue
            break
        return indice, no_inicio

    def _estrela_de_comentario(self, indice: int) -> bool:
        if indice >= len(self.texto) or self.texto[indice] != "*":
            return False
        if indice + 1 >= len(self.texto):
            return True
        return self.texto[indice + 1] in " \t\r\f\n"

    def _pular_comentario(self, indice: int, registrar: bool) -> int:
        inicio = indice
        linha, coluna = self._pos(inicio)
        while indice < len(self.texto) and self.texto[indice] != "\n":
            indice += 1
        if registrar:
            self.comentarios.append(
                Anotacao("COMENTARIO", self.texto[inicio:indice].rstrip(), linha, coluna)
            )
        if indice < len(self.texto) and self.texto[indice] == "\n":
            indice += 1
        return indice

    def _a_frente_e(self, palavra: str) -> bool:
        indice, _ = self._pular(self.i, False, self.no_inicio)
        if indice >= len(self.texto) or not _letra(self.texto[indice]):
            return False
        lexema, _ = self._ler_palavra_desde(indice)
        return lexema.upper() == palavra

    def _proximo_token(self) -> Token:
        caractere = self.texto[self.i]
        if caractere in "\"'":
            return self._token_literal()
        if self._comeca_palavra():
            return self._token_palavra()
        if self._comeca_numero():
            return self._token_numero()
        if self.texto.startswith("--", self.i):
            linha, coluna = self._pos()
            self.i += 2
            self.erros.append(
                ErroLexico(
                    "Hífen duplicado. Identificadores COBOL não contêm '--'.",
                    linha,
                    coluna,
                    "--",
                )
            )
            return Token(ERRO, "--", linha, coluna)
        par = self.texto[self.i : self.i + 2]
        if par in _OPERADORES_DUPLOS:
            linha, coluna = self._pos()
            self.i += 2
            return Token(_OPERADORES_DUPLOS[par], par, linha, coluna)
        if caractere in _OPERADORES_SIMPLES:
            linha, coluna = self._pos()
            self.i += 1
            return Token(_OPERADORES_SIMPLES[caractere], caractere, linha, coluna)

        linha, coluna = self._pos()
        self.i += 1
        self.erros.append(
            ErroLexico(f"Caractere inválido: {caractere!r}.", linha, coluna, caractere)
        )
        return Token(ERRO, caractere, linha, coluna)

    def _comeca_palavra(self) -> bool:
        caractere = self.texto[self.i]
        if _letra(caractere):
            return True
        if not _digito(caractere):
            return False
        lexema, _ = self._ler_palavra_desde(self.i)
        return any(_letra(caractere) for caractere in lexema)

    def _comeca_numero(self) -> bool:
        caractere = self.texto[self.i]
        if _digito(caractere):
            return True
        if caractere in "+-" and self.i + 1 < len(self.texto):
            return _digito(self.texto[self.i + 1])
        return False

    def _token_numero(self) -> Token:
        linha, coluna = self._pos()
        inicio = self.i
        indice = self.i
        if self.texto[indice] in "+-":
            indice += 1
        while indice < len(self.texto) and _digito(self.texto[indice]):
            indice += 1
        decimal = False
        if (
            indice + 1 < len(self.texto)
            and self.texto[indice] == "."
            and _digito(self.texto[indice + 1])
        ):
            decimal = True
            indice += 1
            while indice < len(self.texto) and _digito(self.texto[indice]):
                indice += 1
        self.i = indice
        lexema = self.texto[inicio:indice]
        if decimal:
            tipo = NUMERO_DECIMAL
        elif (
            _valor_de_nivel(lexema) is not None
            and (self.no_inicio or self.apos_ponto)
            and self._seguido_por_item_de_dados()
        ):
            tipo = NUMERO_DE_NIVEL
        else:
            tipo = NUMERO_INTEIRO
        return Token(tipo, lexema, linha, coluna)

    def _seguido_por_item_de_dados(self) -> bool:
        indice, _ = self._pular(self.i, False, self.no_inicio)
        if indice >= len(self.texto):
            return False
        caractere = self.texto[indice]
        if not (_letra(caractere) or _digito(caractere)):
            return False
        lexema, _ = self._ler_palavra_desde(indice)
        if not any(_letra(caractere) for caractere in lexema):
            return False
        maiusculas = lexema.upper()
        if maiusculas not in RESERVADAS:
            return True
        return maiusculas in _SEGUIDORES_DE_NIVEL

    def _token_palavra(self) -> Token:
        linha, coluna = self._pos()
        lexema, self.i = self._ler_palavra_desde(self.i)
        maiusculas = lexema.upper()
        if (
            maiusculas in _PREFIXOS_LITERAIS
            and self.i < len(self.texto)
            and self.texto[self.i] in "\"'"
        ):
            literal, fechou = self._ler_literal()
            lexema = lexema + literal
            if not fechou:
                self.erros.append(
                    ErroLexico("Literal não terminado.", linha, coluna, lexema)
                )
            return Token(LITERAL, lexema, linha, coluna)
        if maiusculas in FIGURATIVAS:
            tipo = CONSTANTE_FIGURATIVA
        elif maiusculas in RESERVADAS:
            tipo = PALAVRA_RESERVADA
        else:
            tipo = IDENTIFICADOR
            if len(lexema) > 30:
                self.erros.append(
                    ErroLexico(
                        "Identificador com mais de 30 caracteres.",
                        linha,
                        coluna,
                        lexema,
                    )
                )
        return Token(tipo, lexema, linha, coluna)

    def _ler_palavra_desde(self, indice: int) -> tuple[str, int]:
        inicio = indice
        indice += 1
        total = len(self.texto)
        while indice < total:
            caractere = self.texto[indice]
            if _letra(caractere) or _digito(caractere) or caractere == "_":
                indice += 1
                continue
            if caractere == "-":
                proximo = self.texto[indice + 1] if indice + 1 < total else ""
                if _letra(proximo) or _digito(proximo) or proximo == "_":
                    indice += 1
                    continue
            break
        return self.texto[inicio:indice], indice

    def _token_literal(self) -> Token:
        linha, coluna = self._pos()
        lexema, fechou = self._ler_literal()
        if not fechou:
            self.erros.append(ErroLexico("Literal não terminado.", linha, coluna, lexema))
        return Token(LITERAL, lexema, linha, coluna)

    def _ler_literal(self) -> tuple[str, bool]:
        inicio = self.i
        aspas = self.texto[self.i]
        self.i += 1
        fechou = False
        while self.i < len(self.texto):
            caractere = self.texto[self.i]
            if caractere == "\n":
                break
            if caractere == aspas:
                if self.i + 1 < len(self.texto) and self.texto[self.i + 1] == aspas:
                    self.i += 2
                    continue
                self.i += 1
                fechou = True
                break
            self.i += 1
        return self.texto[inicio : self.i], fechou

    def _inicia_picture(self, indice: int) -> bool:
        if indice >= len(self.texto):
            return False
        caractere = self.texto[indice]
        if caractere.upper() in _LETRAS_PICTURE or caractere in _SINAIS_PICTURE:
            return True
        return self.texto[indice : indice + 2].upper() in {"CR", "DB"}

    def _token_picture(self) -> Token:
        linha, coluna = self._pos()
        inicio = self.i
        indice = self.i
        total = len(self.texto)
        while indice < total:
            caractere = self.texto[indice]
            if self.texto[indice : indice + 2].upper() in {"CR", "DB"}:
                indice += 2
                continue
            if caractere.upper() in _LETRAS_PICTURE or caractere in _SINAIS_PICTURE:
                indice += 1
                continue
            if caractere == "(":
                fim = indice + 1
                while fim < total and _digito(self.texto[fim]):
                    fim += 1
                if fim == indice + 1:
                    break
                if fim < total and self.texto[fim] == ")":
                    indice = fim + 1
                    continue
                self.erros.append(
                    ErroLexico(
                        "Parênteses não fechados na cadeia de picture.",
                        *self._pos(indice),
                        self.texto[inicio:fim],
                    )
                )
                indice = fim
                break
            if caractere in ",." and self._inicia_picture(indice + 1):
                indice += 1
                continue
            break
        self.i = indice
        return Token(CADEIA_PICTURE, self.texto[inicio:indice], linha, coluna)
