"""Analisador sintático de COBOL (descida recursiva) que produz uma AST.

Gramática (seção 3 da especificação):
  <Program> ::= <IdentificationDivision> [<EnvironmentDivision>]
                [<DataDivision>] <ProcedureDivision>
"""

from __future__ import annotations

from .diagnosticos import Diagnosticos
from .lexer import (
    AnalisadorLexico,
    Token,
    CADEIA_PICTURE,
    CONSTANTE_FIGURATIVA,
    IDENTIFICADOR,
    LITERAL,
    NUMERO_DECIMAL,
    NUMERO_DE_NIVEL,
    NUMERO_INTEIRO,
    PONTO,
    ABRE_PARENTESES,
    FECHA_PARENTESES,
    DOIS_PONTOS,
    VIRGULA,
    PONTO_E_VIRGULA,
    OPERADOR_ARITMETICO,
    OPERADOR_RELACIONAL,
)


class N:
    """Nó genérico da AST."""

    def __init__(self, kind: str, line: int = 0, **kw):
        self.kind = kind
        self.line = line
        self.__dict__.update(kw)

    def __repr__(self) -> str:  # pragma: no cover
        campos = {k: v for k, v in self.__dict__.items() if k not in ("kind", "line")}
        return f"{self.kind}({campos})"


class ErroSintatico(Exception):
    def __init__(self, msg: str, linha: int):
        super().__init__(msg)
        self.msg = msg
        self.linha = linha


FIG = {
    "ZERO": "ZERO", "ZEROS": "ZERO", "ZEROES": "ZERO",
    "SPACE": "SPACE", "SPACES": "SPACE",
    "HIGH-VALUE": "HIGH", "HIGH-VALUES": "HIGH",
    "LOW-VALUE": "LOW", "LOW-VALUES": "LOW",
    "QUOTE": "QUOTE", "QUOTES": "QUOTE",
}

VERBOS = {
    "ACCEPT", "ADD", "CALL", "CANCEL", "CLOSE", "COMPUTE", "CONTINUE", "DELETE", "DISPLAY", "DIVIDE",
    "EVALUATE", "EXIT", "GO", "GOBACK", "IF", "INITIALIZE", "INSPECT", "MOVE", "MULTIPLY", "OPEN",
    "PERFORM", "READ", "REWRITE", "SEARCH", "SET", "STOP", "STRING", "SUBTRACT", "UNSTRING", "WRITE",
    "NEXT", "START", "SORT", "RETURN", "RELEASE",
}

SOFT = {"ID"}  # reservadas só em contextos específicos; usáveis como nome de dados

RELOPS_SIMB = {"=": "eq", ">": "gt", "<": "lt", ">=": "ge", "<=": "le", "<>": "ne"}
CLASSES = {"NUMERIC", "ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER"}


def decodificar_literal(lex: str) -> tuple[str, bool]:
    """Devolve (texto, é_hexadecimal)."""
    i = 0
    while i < len(lex) and lex[i] not in "'\"":
        i += 1
    prefixo = lex[:i].upper()
    q = lex[i]
    corpo = lex[i + 1:]
    if corpo.endswith(q):
        corpo = corpo[:-1]
    corpo = corpo.replace(q + q, q)
    if prefixo in ("X", "BX"):
        try:
            return bytes.fromhex(corpo).decode("latin-1"), True
        except ValueError:
            return corpo, False
    return corpo, False


class Parser:
    def __init__(self, codigo: str, diag: Diagnosticos, arquivo: str):
        res = AnalisadorLexico(codigo, "auto").analisar()  # >>SOURCE FORMAT ou detecção
        self.diag = diag
        self.arquivo = arquivo
        self.lex_erros = res.erros
        for e in res.erros:
            if "mais de 30" in e.mensagem:
                diag.aviso(f"léxico: {e.mensagem}", e.linha, arquivo)
            else:
                diag.erro(f"léxico: {e.mensagem}", e.linha, arquivo)
        self.toks: list[Token] = self._normalizar(res.tokens)
        self.i = 0
        self.comma = False
        self.erros_sint = 0

    # ---------------- utilitários ----------------
    @staticmethod
    def _normalizar(toks: list[Token]) -> list[Token]:
        """Vírgula e ponto-e-vírgula valem como espaço (exceto em modo DECIMAL-POINT IS COMMA,
        onde 12,5 é um número). Remove os separadores do fluxo."""
        comma = any(
            toks[k].lexema.upper() == "DECIMAL-POINT" and k + 2 < len(toks) and toks[k + 2].lexema.upper() == "COMMA"
            for k in range(len(toks))
        )
        out: list[Token] = []
        k = 0
        while k < len(toks):
            t = toks[k]
            if comma and t.tipo in (NUMERO_INTEIRO, NUMERO_DE_NIVEL, NUMERO_DECIMAL) and k + 2 < len(toks):
                v, f = toks[k + 1], toks[k + 2]
                if (v.tipo == VIRGULA and v.linha == t.linha and v.coluna == t.coluna + len(t.lexema)
                        and f.tipo in (NUMERO_INTEIRO, NUMERO_DE_NIVEL) and f.linha == v.linha
                        and f.coluna == v.coluna + 1 and not f.lexema.startswith(("+", "-"))):
                    out.append(Token(NUMERO_DECIMAL, t.lexema + "." + f.lexema, t.linha, t.coluna))
                    k += 3
                    continue
            if t.tipo in (VIRGULA, PONTO_E_VIRGULA):
                k += 1
                continue
            # END PROGRAM nome. (marcador de fim do programa): descartado até o ponto
            lx = t.lexema.upper()
            if lx == "END-PROGRAM" or (lx == "END" and k + 1 < len(toks) and toks[k + 1].lexema.upper() == "PROGRAM"):
                while k < len(toks) and toks[k].tipo != PONTO:
                    k += 1
                k += 1
                continue
            out.append(t)
            k += 1
        return out

    def tk(self, k: int = 0) -> Token | None:
        j = self.i + k
        return self.toks[j] if 0 <= j < len(self.toks) else None

    def w(self, k: int = 0) -> str:
        t = self.tk(k)
        if t is None:
            return ""
        if t.tipo == LITERAL:
            return "\0LIT"
        return t.lexema.upper()

    def line(self) -> int:
        t = self.tk() or (self.toks[-1] if self.toks else None)
        return t.linha if t else 0

    def at(self, *palavras: str) -> bool:
        return self.w() in palavras

    def accept(self, *palavras: str) -> bool:
        if self.w() in palavras:
            self.i += 1
            return True
        return False

    def expect(self, palavra: str) -> None:
        if not self.accept(palavra):
            self.fail(f"esperava '{palavra}' e encontrou '{self.desc()}'")

    def desc(self) -> str:
        t = self.tk()
        return t.lexema if t else "fim do arquivo"

    def fail(self, msg: str):
        raise ErroSintatico(msg, self.line())

    def eof(self) -> bool:
        return self.i >= len(self.toks)

    def at_ponto(self) -> bool:
        t = self.tk()
        return t is not None and t.tipo == PONTO

    def accept_ponto(self) -> bool:
        if self.at_ponto():
            self.i += 1
            return True
        return False

    def skip_sentence(self) -> None:
        while not self.eof() and not self.at_ponto():
            self.i += 1
        self.accept_ponto()

    def is_ident(self, k: int = 0) -> bool:
        t = self.tk(k)
        return t is not None and (t.tipo == IDENTIFICADOR or t.lexema.upper() in SOFT)

    # ---------------- programa ----------------
    def parse(self) -> N:
        prog = N("program", 1, name="?", files=[], items_ws=[], items_fd=[], items_ls=[],
                 using=[], paras=[], sections={}, comma=False, has_env=False, has_data=False)
        try:
            self.identification(prog)
        except ErroSintatico as e:
            self.diag.erro(e.msg, e.linha, self.arquivo)
            return prog
        while not self.eof():
            try:
                if self.at("ENVIRONMENT"):
                    self.environment(prog)
                elif self.at("DATA"):
                    self.data_division(prog)
                elif self.at("PROCEDURE"):
                    self.procedure(prog)
                    break
                else:
                    self.fail(f"esperava ENVIRONMENT, DATA ou PROCEDURE DIVISION e encontrou '{self.desc()}'")
            except ErroSintatico as e:
                self.diag.erro(e.msg, e.linha, self.arquivo)
                self.erros_sint += 1
                self.recover_division()
        else:
            self.diag.erro("PROCEDURE DIVISION ausente (obrigatória)", self.line(), self.arquivo)
        if not prog.paras and not self.erros_sint and not self.diag.falhou:
            self.diag.erro("PROCEDURE DIVISION ausente (obrigatória)", self.line(), self.arquivo)
        prog.comma = self.comma
        return prog

    def recover_division(self) -> None:
        while not self.eof():
            if self.at("DIVISION") and self.w(-1) in ("ENVIRONMENT", "DATA", "PROCEDURE"):
                self.i -= 1
                return
            self.i += 1

    def identification(self, prog: N) -> None:
        if self.at("ID"):
            self.i += 1
        else:
            self.expect("IDENTIFICATION")
        self.expect("DIVISION")
        self.expect_ponto()
        if not self.at("PROGRAM-ID"):
            self.fail("IDENTIFICATION DIVISION exige PROGRAM-ID")
        self.i += 1
        self.expect_ponto()
        t = self.tk()
        if t is None:
            self.fail("PROGRAM-ID sem nome")
        prog.name = t.lexema.strip("'\"")
        prog.line = t.linha
        self.i += 1
        while not self.eof() and not self.at_ponto():
            self.i += 1  # IS INITIAL / COMMON ...
        self.accept_ponto()
        # parágrafos opcionais (AUTHOR, DATE-WRITTEN, ...)
        while not self.eof() and not (self.at("ENVIRONMENT", "DATA", "PROCEDURE") and self.w(1) == "DIVISION"):
            self.skip_sentence()

    def expect_ponto(self) -> None:
        if not self.accept_ponto():
            self.fail(f"esperava '.' e encontrou '{self.desc()}'")

    # ---------------- environment ----------------
    def environment(self, prog: N) -> None:
        self.i += 1
        self.expect("DIVISION")
        self.expect_ponto()
        prog.has_env = True
        while not self.eof() and not (self.at("DATA", "PROCEDURE") and self.w(1) == "DIVISION"):
            if self.at("SELECT"):
                prog.files.append(self.select())
            elif self.at("DECIMAL-POINT"):
                self.i += 1
                self.accept("IS")
                if self.accept("COMMA"):
                    self.comma = True
                self.accept_ponto()
            else:
                # CONFIGURATION SECTION, SPECIAL-NAMES etc. — consome palavra a palavra
                if self.at("SOURCE-COMPUTER", "OBJECT-COMPUTER"):
                    self.skip_sentence()
                else:
                    self.i += 1
                    self.accept_ponto()

    def select(self) -> N:
        ln = self.line()
        self.i += 1
        opcional = self.accept("OPTIONAL")
        nome = self.tk().lexema
        self.i += 1
        f = N("file", ln, name=nome.upper(), assign=None, assign_lit=True, org="LINE SEQUENTIAL", optional=opcional,
              status=None, record=None, access="SEQUENTIAL", key=None)
        while not self.eof() and not self.at_ponto():
            if self.accept("ASSIGN"):
                self.accept("TO")
                t = self.tk()
                if t.tipo == LITERAL:
                    f.assign = decodificar_literal(t.lexema)[0]
                    f.assign_lit = True
                else:
                    f.assign = t.lexema.upper()
                    f.assign_lit = False
                self.i += 1
            elif self.accept("ORGANIZATION"):
                self.accept("IS")
                partes = []
                while self.at("LINE", "SEQUENTIAL", "INDEXED", "RELATIVE", "BINARY"):
                    partes.append(self.w())
                    self.i += 1
                f.org = " ".join(partes) or "SEQUENTIAL"
            elif self.accept("ACCESS"):
                self.accept("MODE")
                self.accept("IS")
                f.access = self.w()
                self.i += 1
            elif self.accept("FILE"):
                self.accept("STATUS")
                self.accept("IS")
                f.status = self.tk().lexema.upper()
                self.i += 1
            elif self.at("RECORD") and self.w(1) in ("KEY", "IS"):
                self.i += 1
                self.accept("KEY")
                self.accept("IS")
                f.key = self.tk().lexema.upper()
                self.i += 1
            else:
                self.i += 1
        self.accept_ponto()
        return f

    # ---------------- data ----------------
    def data_division(self, prog: N) -> None:
        self.i += 1
        self.expect("DIVISION")
        self.expect_ponto()
        prog.has_data = True
        secao = None
        while not self.eof() and not (self.at("PROCEDURE") and self.w(1) == "DIVISION"):
            if self.at("FILE") and self.w(1) == "SECTION":
                self.i += 2
                self.expect_ponto()
                secao = "FILE"
            elif self.at("WORKING-STORAGE", "LOCAL-STORAGE") and self.w(1) == "SECTION":
                self.i += 2
                self.expect_ponto()
                secao = "WS"
            elif self.at("LINKAGE") and self.w(1) == "SECTION":
                self.i += 2
                self.expect_ponto()
                secao = "LS"
            elif self.at("FD", "SD"):
                self.fd(prog)
            else:
                t = self.tk()
                if t.tipo in (NUMERO_DE_NIVEL, NUMERO_INTEIRO):
                    item = self.data_item()
                    if secao == "LS":
                        prog.items_ls.append(item)
                    elif secao == "FILE":
                        item.fd = getattr(prog, "current_fd", None)
                        prog.items_fd.append(item)
                    else:
                        prog.items_ws.append(item)
                else:
                    self.fail(f"declaração de dados inválida iniciada por '{t.lexema}'")

    def fd(self, prog: N) -> None:
        self.i += 1
        nome = self.tk().lexema.upper()
        self.i += 1
        self.skip_sentence()
        # registra o FD para o semântico
        if not hasattr(prog, "fds"):
            prog.fds = []
        prog.fds.append(nome)
        prog.current_fd = nome

    def data_item(self) -> N:
        t = self.tk()
        ln = t.linha
        nivel = int(t.lexema)
        self.i += 1
        nome = None
        if self.is_ident() and self.w() not in ("PIC", "PICTURE", "FILLER"):
            nome = self.tk().lexema.upper()
            self.i += 1
        elif self.at("FILLER"):
            self.i += 1
        item = N("item", ln, level=nivel, name=nome, pic=None, usage="DISPLAY", value=None, occurs=1,
                 redefines=None, children=[], sign_sep=False, blank_zero=False, values88=[], fd=getattr(self, "_fd", None),
                 just=False, sign_lead=False, indexes=[])
        while not self.eof() and not self.at_ponto():
            if self.at("PIC", "PICTURE"):
                self.i += 1
                self.accept("IS")
                t = self.tk()
                if t.tipo == CADEIA_PICTURE:
                    item.pic = t.lexema.upper()
                else:
                    item.pic = t.lexema.upper()
                self.i += 1
            elif self.at("USAGE"):
                self.i += 1
                self.accept("IS")
            elif self.at("COMP", "COMP-1", "COMP-2", "COMP-3", "COMP-4", "COMP-5", "COMPUTATIONAL",
                         "COMPUTATIONAL-3", "COMPUTATIONAL-5", "BINARY", "PACKED-DECIMAL", "DISPLAY", "INDEX"):
                item.usage = self.w()
                self.i += 1
            elif self.at("VALUE", "VALUES"):
                self.i += 1
                self.accept("IS", "ARE")
                if nivel == 88:
                    item.values88 = self.valores88()
                else:
                    item.value = self.valor_inicial()
            elif self.at("OCCURS"):
                self.i += 1
                t = self.tk()
                item.occurs = int(t.lexema)
                self.i += 1
                if self.accept("TO"):
                    item.occurs = int(self.tk().lexema)
                    self.i += 1
                self.accept("TIMES")
                while self.at("DEPENDING", "ASCENDING", "DESCENDING", "INDEXED", "KEY", "ON", "BY", "IS"):
                    indexed = self.at("INDEXED")
                    self.i += 1
                    self.accept("BY")
                    while self.is_ident():
                        if indexed:
                            item.indexes.append(self.tk().lexema.upper())
                        self.i += 1
            elif self.at("REDEFINES"):
                self.i += 1
                item.redefines = self.tk().lexema.upper()
                self.i += 1
            elif self.at("SIGN"):
                self.i += 1
                self.accept("IS")
                if self.at("LEADING"):
                    item.sign_lead = True
                self.i += 1
                if self.accept("SEPARATE"):
                    item.sign_sep = True
                    self.accept("CHARACTER")
            elif self.at("LEADING", "TRAILING"):
                self.i += 1
                if self.accept("SEPARATE"):
                    item.sign_sep = True
                    self.accept("CHARACTER")
            elif self.at("SEPARATE"):
                self.i += 1
                item.sign_sep = True
                self.accept("CHARACTER")
            elif self.at("JUSTIFIED", "JUST"):
                self.i += 1
                self.accept("RIGHT")
                item.just = True
            elif self.at("BLANK"):
                self.i += 1
                self.accept("WHEN")
                self.accept("ZERO", "ZEROS", "ZEROES")
                item.blank_zero = True
            elif self.at("SYNC", "SYNCHRONIZED", "GLOBAL", "EXTERNAL", "IS"):
                self.i += 1
                if self.at("LEFT", "RIGHT"):
                    self.i += 1
            else:
                self.fail(f"cláusula de dados inesperada '{self.desc()}' no item {nome or 'FILLER'}")
        self.expect_ponto()
        return item

    def valor_inicial(self):
        t = self.tk()
        if t is None:
            self.fail("VALUE sem valor")
        if t.tipo == LITERAL:
            self.i += 1
            return N("str", t.linha, text=decodificar_literal(t.lexema)[0])
        if t.lexema.upper() in FIG:
            self.i += 1
            return N("fig", t.linha, fig=FIG[t.lexema.upper()])
        if t.lexema.upper() == "ALL":
            self.i += 1
            s = decodificar_literal(self.tk().lexema)[0]
            self.i += 1
            return N("fig", t.linha, fig="ALL", text=s)
        return self.numero_lit()

    def numero_lit(self):
        t = self.tk()
        txt = t.lexema
        if t.tipo in (NUMERO_INTEIRO, NUMERO_DECIMAL, NUMERO_DE_NIVEL):
            self.i += 1
            if self.comma and self.tk() and self.tk().tipo == VIRGULA and self.adjacent(t):
                # 12,5 em modo vírgula decimal
                frac = self.tk(1)
                if frac and frac.tipo in (NUMERO_INTEIRO, NUMERO_DE_NIVEL) and not frac.lexema.startswith(("+", "-")):
                    self.i += 2
                    txt = txt + "." + frac.lexema
            return N("num", t.linha, text=txt.lstrip("+"))
        if t.lexema in ("-", "+") and self.tk(1) and self.tk(1).tipo in (NUMERO_INTEIRO, NUMERO_DECIMAL):
            self.i += 2
            return N("num", t.linha, text=("-" if t.lexema == "-" else "") + self.toks[self.i - 1].lexema)
        self.fail(f"esperava um valor e encontrou '{t.lexema}'")

    def adjacent(self, t: Token) -> bool:
        nxt = self.tk()
        return nxt is not None and nxt.linha == t.linha and nxt.coluna == t.coluna + len(t.lexema)

    def valores88(self):
        vals = []
        while not self.at_ponto() and not self.eof():
            a = self.valor_inicial()
            if self.accept("THRU", "THROUGH"):
                b = self.valor_inicial()
                vals.append((a, b))
            else:
                vals.append((a, None))
            self.accept_virgula()
        return vals

    def accept_virgula(self) -> None:
        t = self.tk()
        if t is not None and t.tipo == VIRGULA:
            self.i += 1

    # ---------------- procedure ----------------
    def procedure(self, prog: N) -> None:
        self.i += 1
        self.expect("DIVISION")
        if self.accept("USING"):
            while self.is_ident() or self.at("BY", "REFERENCE", "VALUE"):
                if self.is_ident():
                    prog.using.append(self.tk().lexema.upper())
                self.i += 1
        if self.accept("RETURNING"):
            self.i += 1
        self.expect_ponto()
        cur = None
        secao = None

        def novo(nome, sec, ln, eh_secao=False):
            p = N("para", ln, name=nome, section=sec, stmts=[], is_section_start=eh_secao)
            prog.paras.append(p)
            return p

        while not self.eof():
            if self.is_ident() and self.w(1) == "SECTION":
                nome = self.tk().lexema.upper()
                ln = self.line()
                self.i += 2
                self.accept_ponto()
                secao = nome
                if nome in prog.sections:
                    self.diag.erro(f"seção '{nome}' declarada mais de uma vez", ln, self.arquivo)
                prog.sections[nome] = [len(prog.paras), len(prog.paras)]
                cur = novo(nome, secao, ln, True)
                continue
            if self.is_ident() and self.tk(1) is not None and self.tk(1).tipo == PONTO:
                nome = self.tk().lexema.upper()
                ln = self.line()
                self.i += 2
                cur = novo(nome, secao, ln)
                if secao:
                    prog.sections[secao][1] = len(prog.paras) - 1
                continue
            if cur is None:
                cur = novo("$MAIN", None, self.line())
            try:
                stmts = self.statements()
                cur.stmts.extend(stmts)
                if self.at_ponto():
                    self.i += 1
                    cur.stmts.append(N("endsent", self.line()))
                elif not self.eof() and not (self.is_ident() and self.tk(1) is not None and self.tk(1).tipo == PONTO):
                    self.fail(f"comando inesperado '{self.desc()}'")
            except ErroSintatico as e:
                self.diag.erro(e.msg, e.linha, self.arquivo)
                self.erros_sint += 1
                # recuperação: pula até o próximo ponto
                self.skip_sentence()
        if secao:
            prog.sections[secao][1] = len(prog.paras) - 1

    # ---------------- comandos ----------------
    def statements(self) -> list[N]:
        out = []
        while not self.eof():
            if self.w() in VERBOS and self.tk().tipo != LITERAL:
                out.append(self.statement())
            else:
                break
        return out

    def statement(self) -> N:
        ln = self.line()
        v = self.w()
        m = getattr(self, "st_" + v.replace("-", "_").lower(), None)
        if m is None:
            self.fail(f"comando '{v}' não suportado por este compilador")
        return m(ln)

    # operandos ---------------------------------------------------
    def operando_inicia(self) -> bool:
        t = self.tk()
        if t is None:
            return False
        if t.tipo in (LITERAL, NUMERO_INTEIRO, NUMERO_DECIMAL, CONSTANTE_FIGURATIVA, NUMERO_DE_NIVEL):
            return True
        if self.is_ident():
            return True
        return t.lexema.upper() in ("FUNCTION", "ALL", "LENGTH", "ADDRESS") or (
            t.tipo == OPERADOR_ARITMETICO and t.lexema in "+-" and self.tk(1) is not None
            and self.tk(1).tipo in (NUMERO_INTEIRO, NUMERO_DECIMAL)
        )

    def ref(self) -> N:
        t = self.tk()
        if t is None or not self.is_ident():
            self.fail(f"esperava um nome de dados e encontrou '{self.desc()}'")
        self.i += 1
        r = N("ref", t.linha, name=t.lexema.upper(), quals=[], subs=[], refmod=None)
        while self.at("OF", "IN") and self.is_ident(1):
            self.i += 1
            r.quals.append(self.tk().lexema.upper())
            self.i += 1
        if self.tk() is not None and self.tk().tipo == ABRE_PARENTESES:
            self.i += 1
            primeiro = self.arith()
            if self.tk() is not None and self.tk().tipo == DOIS_PONTOS:
                self.i += 1
                comp = None
                if not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES):
                    comp = self.arith()
                r.refmod = (primeiro, comp)
            else:
                r.subs.append(primeiro)
                while not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES) and not self.eof():
                    self.accept_virgula()
                    r.subs.append(self.arith())
            if not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES):
                self.fail("esperava ')'")
            self.i += 1
            # refmod depois de subscrito: X(I)(1:2)
            if self.tk() is not None and self.tk().tipo == ABRE_PARENTESES and r.subs and r.refmod is None:
                self.i += 1
                a = self.arith()
                if self.tk() is not None and self.tk().tipo == DOIS_PONTOS:
                    self.i += 1
                    comp = None
                    if not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES):
                        comp = self.arith()
                    r.refmod = (a, comp)
                if self.tk() is not None and self.tk().tipo == FECHA_PARENTESES:
                    self.i += 1
        return r

    def operando(self) -> N:
        """Literal, figurativa, número, referência, função ou LENGTH OF."""
        t = self.tk()
        if t is None:
            self.fail("fim inesperado do arquivo")
        ln = t.linha
        if t.tipo == LITERAL:
            self.i += 1
            txt, hexa = decodificar_literal(t.lexema)
            return N("str", ln, text=txt)
        w = t.lexema.upper()
        if t.tipo == CONSTANTE_FIGURATIVA or w in FIG:
            self.i += 1
            return N("fig", ln, fig=FIG[w])
        if w == "ALL":
            self.i += 1
            tt = self.tk()
            s = decodificar_literal(tt.lexema)[0] if tt.tipo == LITERAL else tt.lexema
            self.i += 1
            return N("fig", ln, fig="ALL", text=s)
        if w == "FUNCTION":
            self.i += 1
            nome = self.tk().lexema.upper()
            self.i += 1
            args = []
            if self.tk() is not None and self.tk().tipo == ABRE_PARENTESES:
                self.i += 1
                while not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES) and not self.eof():
                    self.accept_virgula()
                    args.append(self.arith())
                self.i += 1
            return N("func", ln, name=nome, args=args)
        if w == "LENGTH" and self.w(1) == "OF":
            self.i += 2
            return N("lenof", ln, ref=self.ref())
        if w == "LENGTH" and self.is_ident(1):
            self.i += 1
            return N("lenof", ln, ref=self.ref())
        if t.tipo in (NUMERO_INTEIRO, NUMERO_DECIMAL, NUMERO_DE_NIVEL) or (
            t.tipo == OPERADOR_ARITMETICO and w in ("+", "-")
        ):
            return self.numero_lit()
        if self.is_ident():
            return self.ref()
        self.fail(f"operando inválido '{t.lexema}'")

    # expressões aritméticas ----------------------------------------
    def arith(self) -> N:
        e = self.termo()
        while self.tk() is not None and self.tk().tipo == OPERADOR_ARITMETICO and self.tk().lexema in ("+", "-"):
            op = self.tk().lexema
            self.i += 1
            e = N("bin", e.line, op=op, l=e, r=self.termo())
        return e

    def termo(self) -> N:
        e = self.potencia()
        while self.tk() is not None and self.tk().tipo == OPERADOR_ARITMETICO and self.tk().lexema in ("*", "/"):
            op = self.tk().lexema
            self.i += 1
            e = N("bin", e.line, op=op, l=e, r=self.potencia())
        return e

    def potencia(self) -> N:
        e = self.unario()
        if self.tk() is not None and self.tk().tipo == OPERADOR_ARITMETICO and self.tk().lexema == "**":
            self.i += 1
            e = N("bin", e.line, op="**", l=e, r=self.potencia())
        return e

    def unario(self) -> N:
        t = self.tk()
        if t is not None and t.tipo == OPERADOR_ARITMETICO and t.lexema in ("+", "-"):
            self.i += 1
            e = self.primario()
            return N("neg", t.linha, e=e) if t.lexema == "-" else e
        return self.primario()

    def primario(self) -> N:
        t = self.tk()
        if t is not None and t.tipo == ABRE_PARENTESES:
            self.i += 1
            e = self.arith()
            if not (self.tk() is not None and self.tk().tipo == FECHA_PARENTESES):
                self.fail("esperava ')'")
            self.i += 1
            return e
        return self.operando()

    # condições -----------------------------------------------------
    def cond(self) -> N:
        e = self.cond_and()
        while self.at("OR"):
            self.i += 1
            e = N("or", e.line, l=e, r=self.cond_and())
        return e

    def cond_and(self) -> N:
        e = self.cond_not()
        while self.at("AND"):
            self.i += 1
            e = N("and", e.line, l=e, r=self.cond_not())
        return e

    def cond_not(self) -> N:
        if self.at("NOT") and not self.relop_ahead(1):
            ln = self.line()
            self.i += 1
            return N("not", ln, e=self.cond_not())
        return self.cond_simples()

    def relop_ahead(self, k: int) -> bool:
        w = self.w(k)
        t = self.tk(k)
        return w in ("EQUAL", "GREATER", "LESS", "IS") or (t is not None and t.tipo == OPERADOR_RELACIONAL)

    def cond_simples(self) -> N:
        t = self.tk()
        if t is not None and t.tipo == ABRE_PARENTESES:
            salvo = self.i
            try:
                self.i += 1
                c = self.cond()
                if self.tk() is not None and self.tk().tipo == FECHA_PARENTESES:
                    self.i += 1
                    nxt = self.tk()
                    if not (nxt is not None and (nxt.tipo in (OPERADOR_RELACIONAL, OPERADOR_ARITMETICO) or
                                                 self.w() in ("EQUAL", "GREATER", "LESS", "IS", "NOT"))):
                        return c
            except ErroSintatico:
                pass
            self.i = salvo
        return self.relacao()

    def relop(self) -> str | None:
        """Consome um operador relacional e devolve eq/ne/gt/lt/ge/le."""
        salvo = self.i
        self.accept("IS")
        neg = self.accept("NOT")
        t = self.tk()
        op = None
        if t is not None and t.tipo == OPERADOR_RELACIONAL:
            op = RELOPS_SIMB[t.lexema]
            self.i += 1
        elif self.at("EQUAL"):
            self.i += 1
            self.accept("TO")
            op = "eq"
        elif self.at("GREATER"):
            self.i += 1
            self.accept("THAN")
            op = "gt"
            if self.at("OR") and self.w(1) == "EQUAL":
                self.i += 2
                self.accept("TO")
                op = "ge"
        elif self.at("LESS"):
            self.i += 1
            self.accept("THAN")
            op = "lt"
            if self.at("OR") and self.w(1) == "EQUAL":
                self.i += 2
                self.accept("TO")
                op = "le"
        if op is None:
            self.i = salvo
            return None
        if neg:
            op = {"eq": "ne", "ne": "eq", "gt": "le", "le": "gt", "lt": "ge", "ge": "lt"}[op]
        return op

    def relacao(self) -> N:
        ln = self.line()
        a = self.arith()
        salvo = self.i
        # classe / sinal
        self.accept("IS")
        neg = self.accept("NOT")
        if self.at(*CLASSES):
            c = self.w()
            self.i += 1
            return N("class", ln, e=a, cls=c, neg=neg)
        if self.at("POSITIVE", "NEGATIVE", "ZERO", "ZEROS", "ZEROES") and a.kind in ("ref", "func"):
            # "X IS ZERO" (sinal); "X ZERO" sem IS não é relacional
            c = self.w()
            self.i += 1
            return N("sign", ln, e=a, cls=c, neg=neg)
        self.i = salvo
        op = self.relop()
        if op is None:
            if a.kind == "ref":
                return N("condname", ln, ref=a)
            self.fail(f"esperava operador relacional após '{self.desc()}'")
        b = self.arith()
        res = N("rel", ln, op=op, l=a, r=b)
        # condição abreviada: X = 1 OR 2 / AND ...
        while self.at("AND", "OR"):
            conj = self.w()
            k = 1
            if self.relop_ahead(k) or self.w(k) == "NOT":
                salvo2 = self.i
                self.i += 1
                op2 = self.relop()
                if op2 is None:
                    self.i = salvo2
                    break
                b2 = self.arith()
                nr = N("rel", ln, op=op2, l=a, r=b2)
                res = N("and" if conj == "AND" else "or", ln, l=res, r=nr)
                continue
            # OR <valor> sem sujeito: só se o próximo token não for início de nova relação
            salvo2 = self.i
            self.i += 1
            if self.operando_inicia():
                try:
                    b2 = self.arith()
                except ErroSintatico:
                    self.i = salvo2
                    break
                if self.relop_ahead(0) or self.at("NOT"):
                    self.i = salvo2
                    break
                if self.at(*CLASSES):
                    self.i = salvo2
                    break
                nr = N("rel", ln, op=op, l=a, r=b2)
                res = N("and" if conj == "AND" else "or", ln, l=res, r=nr)
                continue
            self.i = salvo2
            break
        return res

    # ---------- instruções ----------
    def end(self, palavra: str) -> None:
        self.accept(palavra)

    def pula_tela(self, pos: dict | None = None) -> None:
        """AT LINE n COLUMN m / LINE n COL m / AT nnmm. Se ``pos`` for dado, guarda linha e coluna
        (usados pelo DISPLAY); as demais cláusulas de tela (cores, ERASE etc.) são ignoradas."""
        while self.at("AT", "LINE", "COLUMN", "COL", "POSITION", "FOREGROUND-COLOR", "BACKGROUND-COLOR", "HIGHLIGHT",
                      "LOWLIGHT", "REVERSE-VIDEO", "BLINK", "UNDERLINE", "BELL", "ERASE", "EOL", "EOS", "AUTO", "SECURE"):
            palavra = self.w()
            self.i += 1
            t = self.tk()
            eh_num = t is not None and t.tipo in (NUMERO_INTEIRO, NUMERO_DECIMAL, NUMERO_DE_NIVEL)
            if palavra == "AT" and eh_num and len(t.lexema) == 4 and pos is not None:
                pos["line"] = N("num", t.linha, text=t.lexema[:2])
                pos["col"] = N("num", t.linha, text=t.lexema[2:])
                self.i += 1
            elif palavra in ("LINE", "COLUMN", "COL", "POSITION") and (eh_num or self.is_ident()):
                if self.at("NUMBER", "PLUS"):
                    self.i += 1
                op = self.operando()
                if pos is not None:
                    pos["line" if palavra == "LINE" else "col"] = op
            elif eh_num:
                self.i += 1
            elif self.is_ident() and palavra in ("FOREGROUND-COLOR", "BACKGROUND-COLOR"):
                self.i += 1

    def st_display(self, ln):
        self.i += 1
        itens = []
        avanca = True
        pos: dict = {}
        while True:
            self.pula_tela(pos)
            if self.at("UPON"):
                self.i += 2
                continue
            if self.at("WITH") and self.w(1) == "NO":
                self.i += 2
                self.accept("ADVANCING")
                avanca = False
                continue
            if self.at("NO") and self.w(1) == "ADVANCING":
                self.i += 2
                avanca = False
                continue
            if self.operando_inicia() and self.w() not in VERBOS:
                itens.append(self.operando())
            else:
                break
        if not itens:
            self.fail("DISPLAY sem operandos")
        if pos:
            avanca = False  # DISPLAY posicionado não muda de linha
        return N("display", ln, items=itens, advancing=avanca, at_line=pos.get("line"), at_col=pos.get("col"))

    def st_accept(self, ln):
        self.i += 1
        alvo = self.ref()
        self.pula_tela()
        origem = None
        if self.accept("FROM"):
            origem = self.w()
            self.i += 1
            if origem == "DAY" and self.at("YYYYDDD"):
                origem = "DAY8"
                self.i += 1
            if origem == "DATE" and self.at("YYYYMMDD"):
                origem = "DATE8"
                self.i += 1
        return N("accept", ln, target=alvo, source=origem)

    def st_move(self, ln):
        self.i += 1
        corr = bool(self.accept("CORRESPONDING", "CORR"))
        src = self.operando() if not self.at("(") else self.arith()
        self.expect("TO")
        alvos = []
        while self.is_ident():
            alvos.append(self.ref())
        if not alvos:
            self.fail("MOVE sem destino")
        return N("move", ln, src=src, targets=alvos, corr=corr)

    def alvos_arit(self):
        alvos = []
        while self.is_ident():
            r = self.ref()
            arred = self.accept("ROUNDED")
            alvos.append((r, arred))
        return alvos

    def size_error(self):
        se = None
        nse = None
        while True:
            salvo = self.i
            if self.at("ON") and self.w(1) == "SIZE":
                self.i += 1
            if self.at("SIZE") and self.w(1) == "ERROR":
                self.i += 2
                se = self.statements()
                continue
            if self.at("NOT"):
                self.i += 1
                self.accept("ON")
                if self.at("SIZE"):
                    self.i += 2
                    nse = self.statements()
                    continue
            self.i = salvo
            break
        return se, nse

    def st_add(self, ln):
        self.i += 1
        vals = []
        while not self.at("TO", "GIVING") and self.operando_inicia():
            vals.append(self.operando())
        to = []
        giving = []
        if self.accept("TO"):
            # ADD a TO b GIVING c : b é operando
            if self.is_ident() and self.at_giving_after():
                vals.append(self.operando())
            else:
                to = self.alvos_arit()
        if self.accept("GIVING"):
            giving = self.alvos_arit()
        se, nse = self.size_error()
        self.end("END-ADD")
        return N("add", ln, vals=vals, to=to, giving=giving, se=se, nse=nse)

    def at_giving_after(self) -> bool:
        k = 0
        while self.tk(k) is not None and (self.tk(k).tipo != PONTO):
            if self.w(k) == "GIVING":
                return True
            if self.w(k) in VERBOS or self.w(k).startswith("END-") or self.w(k) in ("ELSE", "WHEN", "SIZE"):
                return False
            k += 1
        return False

    def st_subtract(self, ln):
        self.i += 1
        vals = []
        while not self.at("FROM") and self.operando_inicia():
            vals.append(self.operando())
        self.expect("FROM")
        frm = []
        giving = []
        if self.is_ident() and self.at_giving_after():
            minuendo = self.operando()
        else:
            minuendo = None
            frm = self.alvos_arit()
        if self.accept("GIVING"):
            giving = self.alvos_arit()
        se, nse = self.size_error()
        self.end("END-SUBTRACT")
        return N("sub", ln, vals=vals, frm=frm, minuendo=minuendo, giving=giving, se=se, nse=nse)

    def st_multiply(self, ln):
        self.i += 1
        a = self.operando()
        self.expect("BY")
        if self.is_ident() and self.at_giving_after():
            b = self.operando()
            bys = []
        else:
            b = None
            bys = self.alvos_arit()
        giving = []
        if self.accept("GIVING"):
            giving = self.alvos_arit()
        se, nse = self.size_error()
        self.end("END-MULTIPLY")
        return N("mul", ln, a=a, b=b, bys=bys, giving=giving, se=se, nse=nse)

    def st_divide(self, ln):
        self.i += 1
        a = self.operando()
        modo = None
        if self.accept("INTO"):
            modo = "into"
        elif self.accept("BY"):
            modo = "by"
        else:
            self.fail("DIVIDE exige INTO ou BY")
        b = None
        into = []
        if self.is_ident() and self.at_giving_after() or modo == "by" or self.operando_inicia() and not self.is_ident():
            b = self.operando()
        else:
            into = self.alvos_arit()
        giving = []
        rem = None
        if self.accept("GIVING"):
            giving = self.alvos_arit()
        if self.accept("REMAINDER"):
            rem = self.ref()
        se, nse = self.size_error()
        self.end("END-DIVIDE")
        return N("div", ln, a=a, mode=modo, b=b, into=into, giving=giving, rem=rem, se=se, nse=nse)

    def st_compute(self, ln):
        self.i += 1
        alvos = self.alvos_arit()
        t = self.tk()
        if not (t is not None and (t.lexema == "=" or self.at("EQUAL"))):
            self.fail("COMPUTE exige '='")
        self.i += 1
        e = self.arith()
        se, nse = self.size_error()
        self.end("END-COMPUTE")
        return N("compute", ln, targets=alvos, expr=e, se=se, nse=nse)

    def st_if(self, ln):
        self.i += 1
        c = self.cond()
        self.accept("THEN")
        if self.at("NEXT") and self.w(1) == "SENTENCE":
            self.i += 2
            then = [N("continue", ln)]
        else:
            then = self.statements()
        senao = None
        if self.accept("ELSE"):
            if self.at("NEXT") and self.w(1) == "SENTENCE":
                self.i += 2
                senao = [N("continue", ln)]
            else:
                senao = self.statements()
        if not self.accept("END-IF"):
            if not self.at_ponto():
                self.diag.aviso("IF sem END-IF (encerrado implicitamente)", ln, self.arquivo)
        return N("if", ln, cond=c, then=then, orelse=senao)

    def st_continue(self, ln):
        self.i += 1
        return N("continue", ln)

    def st_next(self, ln):
        self.i += 1
        self.accept("SENTENCE")
        return N("continue", ln)

    def st_exit(self, ln):
        self.i += 1
        what = None
        if self.at("PROGRAM", "PARAGRAPH", "SECTION", "PERFORM"):
            what = self.w()
            self.i += 1
        return N("exit", ln, what=what)

    def st_stop(self, ln):
        self.i += 1
        if self.accept("RUN"):
            pass
        elif self.tk() is not None and self.tk().tipo == LITERAL:
            self.i += 1
        return N("stop", ln)

    def st_goback(self, ln):
        self.i += 1
        return N("goback", ln)

    def st_go(self, ln):
        self.i += 1
        self.accept("TO")
        nomes = []
        while self.is_ident():
            nomes.append(self.tk().lexema.upper())
            self.i += 1
        dep = None
        if self.accept("DEPENDING"):
            self.accept("ON")
            dep = self.ref()
        if not nomes:
            self.fail("GO TO sem destino")
        return N("goto", ln, names=nomes, depending=dep)

    def st_perform(self, ln):
        self.i += 1
        n = N("perform", ln, target=None, thru=None, times=None, until=None, test_after=False,
              varying=None, body=None)
        if self.is_ident() and self.w(1) != "TIMES" and not (self.tk(1) is not None and self.tk(1).tipo in (ABRE_PARENTESES, DOIS_PONTOS)):
            n.target = self.tk().lexema.upper()
            self.i += 1
            if self.accept("THRU", "THROUGH"):
                n.thru = self.tk().lexema.upper()
                self.i += 1
        # modificadores
        if self.at("WITH") and self.w(1) == "TEST":
            self.i += 2
            n.test_after = self.w() == "AFTER"
            self.i += 1
        elif self.at("TEST"):
            self.i += 1
            n.test_after = self.w() == "AFTER"
            self.i += 1
        if self.at("VARYING"):
            self.i += 1
            var = self.ref()
            self.expect("FROM")
            ini = self.arith()
            self.expect("BY")
            passo = self.arith()
            self.expect("UNTIL")
            c = self.cond()
            n.varying = (var, ini, passo)
            n.until = c
            # AFTER (loops aninhados)
            n.after = []
            while self.accept("AFTER"):
                v2 = self.ref()
                self.expect("FROM")
                i2 = self.arith()
                self.expect("BY")
                p2 = self.arith()
                self.expect("UNTIL")
                c2 = self.cond()
                n.after.append((v2, i2, p2, c2))
        elif self.accept("UNTIL"):
            n.until = self.cond()
        elif self.operando_inicia() and self.tk() is not None and (
            self.w(1) == "TIMES"
        ):
            n.times = self.operando()
            self.expect("TIMES")
        if n.target is None:
            n.body = self.statements()
            if not self.accept("END-PERFORM"):
                self.fail("PERFORM em linha sem END-PERFORM")
        return n

    def st_evaluate(self, ln):
        self.i += 1
        sujeitos = []
        while True:
            if self.at("TRUE", "FALSE"):
                sujeitos.append(N("bool", self.line(), value=self.w() == "TRUE"))
                self.i += 1
            else:
                sujeitos.append(self.arith_ou_cond_simples())
            if not self.accept("ALSO"):
                break
        whens = []
        while self.at("WHEN"):
            heads = []
            outros = False
            while self.accept("WHEN"):
                if self.accept("OTHER"):
                    outros = True
                    heads.append(None)
                else:
                    objs = []
                    while True:
                        objs.append(self.when_obj(sujeitos[len(objs)] if len(objs) < len(sujeitos) else sujeitos[-1]))
                        if not self.accept("ALSO"):
                            break
                    heads.append(objs)
            corpo = self.statements()
            whens.append(N("when", ln, heads=heads, body=corpo, other=outros))
        self.expect("END-EVALUATE")
        return N("evaluate", ln, subjects=sujeitos, whens=whens)

    def arith_ou_cond_simples(self):
        return self.arith()

    def when_obj(self, sujeito):
        ln = self.line()
        if self.accept("ANY"):
            return N("any", ln)
        if sujeito.kind == "bool":
            return N("cond", ln, cond=self.cond())
        salvo = self.i
        self.accept("IS")
        neg = self.accept("NOT")
        if self.at(*CLASSES):
            c = self.w()
            self.i += 1
            return N("class", ln, cls=c, neg=neg)
        self.i = salvo
        op = self.relop()
        if op is not None:
            return N("cmp", ln, op=op, value=self.arith())
        neg = self.accept("NOT")
        a = self.arith()
        if self.accept("THRU", "THROUGH"):
            b = self.arith()
            return N("range", ln, lo=a, hi=b, neg=neg)
        return N("value", ln, value=a, neg=neg)

    def st_open(self, ln):
        self.i += 1
        grupos = []
        modo = None
        while True:
            if self.at("INPUT", "OUTPUT", "I-O", "EXTEND"):
                modo = self.w()
                self.i += 1
            elif self.is_ident():
                grupos.append((modo, self.tk().lexema.upper()))
                self.i += 1
            else:
                break
        if not grupos:
            self.fail("OPEN sem arquivo")
        return N("open", ln, files=grupos)

    def st_close(self, ln):
        self.i += 1
        arqs = []
        while self.is_ident():
            arqs.append(self.tk().lexema.upper())
            self.i += 1
        if not arqs:
            self.fail("CLOSE sem arquivo")
        return N("close", ln, files=arqs)

    def st_read(self, ln):
        self.i += 1
        arq = self.tk().lexema.upper()
        self.i += 1
        self.accept("NEXT", "PREVIOUS")
        self.accept("RECORD")
        into = None
        at_end = None
        nat_end = None
        inv = None
        ninv = None
        if self.accept("INTO"):
            into = self.ref()
        while True:
            if self.at("AT") and self.w(1) == "END":
                self.i += 2
                at_end = self.statements()
            elif self.at("END") and True:
                self.i += 1
                at_end = self.statements()
            elif self.at("NOT") and self.w(1) in ("AT", "END"):
                self.i += 1
                self.accept("AT")
                self.accept("END")
                nat_end = self.statements()
            elif self.at("INVALID"):
                self.i += 1
                self.accept("KEY")
                inv = self.statements()
            elif self.at("NOT") and self.w(1) == "INVALID":
                self.i += 2
                self.accept("KEY")
                ninv = self.statements()
            else:
                break
        self.end("END-READ")
        return N("read", ln, file=arq, into=into, at_end=at_end, not_at_end=nat_end, invalid=inv, not_invalid=ninv)

    def st_write(self, ln):
        self.i += 1
        rec = self.ref()
        src = None
        adv = None
        if self.accept("FROM"):
            src = self.operando()
        if self.at("AFTER", "BEFORE"):
            self.i += 1
            self.accept("ADVANCING")
            adv = self.operando() if not self.at("PAGE") else None
            if self.at("LINE", "LINES"):
                self.i += 1
        inv = None
        ninv = None
        while True:
            if self.at("INVALID"):
                self.i += 1
                self.accept("KEY")
                inv = self.statements()
            elif self.at("NOT") and self.w(1) == "INVALID":
                self.i += 2
                self.accept("KEY")
                ninv = self.statements()
            else:
                break
        self.end("END-WRITE")
        return N("write", ln, record=rec, source=src, invalid=inv, not_invalid=ninv)

    def st_rewrite(self, ln):
        self.i += 1
        rec = self.ref()
        src = None
        if self.accept("FROM"):
            src = self.operando()
        self.end("END-REWRITE")
        return N("rewrite", ln, record=rec, source=src)

    def st_initialize(self, ln):
        self.i += 1
        alvos = []
        while self.is_ident():
            alvos.append(self.ref())
        if not alvos:
            self.fail("INITIALIZE sem destino")
        if self.accept("REPLACING"):
            while self.at("ALPHANUMERIC", "NUMERIC", "ALPHABETIC", "NATIONAL"):
                self.i += 1
                self.accept("DATA")
                self.expect("BY")
                self.operando()
        return N("initialize", ln, targets=alvos)

    def st_inspect(self, ln):
        self.i += 1
        alvo = self.operando()
        tally = []
        repl = []
        conv = None
        if self.accept("TALLYING"):
            while self.is_ident():
                cont = self.ref()
                self.expect("FOR")
                while self.at("ALL", "LEADING", "CHARACTERS"):
                    modo = self.w()
                    self.i += 1
                    pat = None if modo == "CHARACTERS" else self.operando()
                    self.inspect_limites()
                    tally.append((cont, modo, pat))
        if self.accept("REPLACING"):
            while self.at("ALL", "LEADING", "FIRST", "CHARACTERS"):
                modo = self.w()
                self.i += 1
                pat = None if modo == "CHARACTERS" else self.operando()
                self.expect("BY")
                by = self.operando()
                self.inspect_limites()
                repl.append((modo, pat, by))
        if self.accept("CONVERTING"):
            a = self.operando()
            self.expect("TO")
            b = self.operando()
            self.inspect_limites()
            conv = (a, b)
        return N("inspect", ln, target=alvo, tally=tally, repl=repl, conv=conv)

    def inspect_limites(self):
        while self.at("BEFORE", "AFTER"):
            self.diag.aviso("INSPECT ... BEFORE/AFTER ignorado", self.line(), self.arquivo)
            self.i += 1
            self.accept("INITIAL")
            self.operando()

    def st_string(self, ln):
        self.i += 1
        partes = []
        while not self.at("INTO"):
            srcs = []
            while not self.at("DELIMITED", "INTO"):
                srcs.append(self.operando())
            delim = None
            if self.accept("DELIMITED"):
                self.accept("BY")
                if self.accept("SIZE"):
                    delim = None
                else:
                    delim = self.operando()
            for s in srcs:
                partes.append((s, delim))
        self.expect("INTO")
        dst = self.ref()
        ptr = None
        if self.at("WITH") and self.w(1) == "POINTER":
            self.i += 2
            ptr = self.ref()
        elif self.accept("POINTER"):
            ptr = self.ref()
        ov = None
        nov = None
        while True:
            if self.at("ON") and self.w(1) == "OVERFLOW":
                self.i += 2
                ov = self.statements()
            elif self.at("OVERFLOW"):
                self.i += 1
                ov = self.statements()
            elif self.at("NOT"):
                self.i += 1
                self.accept("ON")
                self.accept("OVERFLOW")
                nov = self.statements()
            else:
                break
        self.end("END-STRING")
        return N("string", ln, parts=partes, dst=dst, ptr=ptr, ov=ov, nov=nov)

    def st_call(self, ln):
        self.i += 1
        t = self.tk()
        if t.tipo == LITERAL:
            alvo = N("str", t.linha, text=decodificar_literal(t.lexema)[0])
            self.i += 1
        else:
            alvo = self.ref()
        args = []
        ret = None
        if self.accept("USING"):
            while True:
                self.accept("BY")
                self.accept("REFERENCE", "CONTENT", "VALUE")
                if self.operando_inicia():
                    args.append(self.operando())
                else:
                    break
        if self.accept("RETURNING"):
            ret = self.ref()
        exc = None
        nexc = None
        while True:
            if self.at("ON") and self.w(1) == "EXCEPTION":
                self.i += 2
                exc = self.statements()
            elif self.at("EXCEPTION"):
                self.i += 1
                exc = self.statements()
            elif self.at("NOT"):
                self.i += 1
                self.accept("ON")
                self.accept("EXCEPTION")
                nexc = self.statements()
            else:
                break
        self.end("END-CALL")
        return N("call", ln, target=alvo, args=args, returning=ret, exc=exc, nexc=nexc)

    def st_cancel(self, ln):
        self.i += 1
        self.operando()
        return N("continue", ln)

    def st_set(self, ln):
        self.i += 1
        alvos = []
        while self.is_ident():
            alvos.append(self.ref())
        if self.accept("TO"):
            if self.at("TRUE", "FALSE"):
                v = self.w()
                self.i += 1
                return N("set_cond", ln, targets=alvos, value=(v == "TRUE"))
            return N("set", ln, targets=alvos, op="to", value=self.arith())
        if self.at("UP", "DOWN"):
            d = self.w()
            self.i += 1
            self.expect("BY")
            return N("set", ln, targets=alvos, op="up" if d == "UP" else "down", value=self.arith())
        self.fail("SET inválido")

    def st_unstring(self, ln):
        self.i += 1
        src = self.operando()
        delims = []
        if self.accept("DELIMITED"):
            self.accept("BY")
            self.accept("ALL")
            delims.append(self.operando())
            while self.accept("OR"):
                self.accept("ALL")
                delims.append(self.operando())
        self.expect("INTO")
        alvos = []
        while self.is_ident():
            alvos.append(self.ref())
            if self.at("DELIMITER") or self.at("COUNT"):
                self.i += 1
                self.accept("IN")
                self.ref()
        tally = None
        if self.accept("TALLYING"):
            self.accept("IN")
            tally = self.ref()
        self.end("END-UNSTRING")
        return N("unstring", ln, src=src, delims=delims, targets=alvos, tally=tally)

    def st_delete(self, ln):
        self.fail("DELETE (arquivos indexados) não suportado")

    def st_start(self, ln):
        self.fail("START (arquivos indexados) não suportado")

    def st_search(self, ln):
        self.i += 1
        todo = self.accept("ALL")
        tabela = self.ref()
        var = None
        if self.accept("VARYING"):
            var = self.ref()
        at_end = None
        whens = []
        while True:
            if self.at("AT") and self.w(1) == "END":
                self.i += 2
                at_end = self.statements()
            elif self.at("END") and self.w(1) != "-":
                self.i += 1
                at_end = self.statements()
            elif self.at("WHEN"):
                self.i += 1
                c = self.cond()
                whens.append((c, self.statements()))
            else:
                break
        self.end("END-SEARCH")
        return N("search", ln, table=tabela, all=todo, varying=var, at_end=at_end, whens=whens)

    def st_sort(self, ln):
        self.fail("SORT não suportado")

    def st_return(self, ln):
        self.fail("RETURN não suportado")

    def st_release(self, ln):
        self.fail("RELEASE não suportado")


def analisar_sintaxe(codigo: str, diag: Diagnosticos, arquivo: str) -> N:
    p = Parser(codigo, diag, arquivo)
    return p.parse()
