"""Gerador de código C a partir da AST do COBOL (seção 5 da especificação).

O programa COBOL vira uma função C com um rótulo por parágrafo. PERFORM empilha
(endereço de retorno, fim do intervalo) e salta para o parágrafo; ao chegar ao
rótulo que marca o fim do intervalo, o fluxo volta ao chamador.
"""

from __future__ import annotations

import re

from .diagnosticos import Diagnosticos
from .parser import N
from .semantica import Sym, Tabela


def c_str(texto: str, codificacao: str) -> tuple[str, int]:
    dados = texto.encode(codificacao, "replace")
    return c_bytes(dados), len(dados)


def c_bytes(dados: bytes) -> str:
    saida = ['"']
    for b in dados:
        if 32 <= b < 127 and chr(b) not in '"\\?':
            saida.append(chr(b))
        else:
            saida.append("\\%03o" % b)
    saida.append('"')
    return "".join(saida)


RELC = {"eq": "==", "ne": "!=", "gt": ">", "lt": "<", "ge": ">=", "le": "<="}
FIGC = {"SPACE": "F_SPACE", "ZERO": "F_ZERO", "HIGH": "F_HIGH", "LOW": "F_LOW", "QUOTE": "F_QUOTE"}


class GeradorC:
    def __init__(self, prog: N, tab: Tabela, diag: Diagnosticos, arquivo: str, codificacao: str = "latin-1"):
        self.prog = prog
        self.tab = tab
        self.diag = diag
        self.arquivo = arquivo
        self.enc = codificacao
        self.tab.codificacao = codificacao
        self.saida: list[str] = []
        self.nret = 0
        self.rets: list[int] = []
        self.nvar = 0
        self.ind = 1

    # ---------------- utilidades ----------------
    def erro(self, msg: str, linha: int) -> None:
        self.diag.erro(msg, linha, self.arquivo)

    def w(self, linha: str) -> None:
        self.saida.append("    " * self.ind + linha)

    def novo(self) -> int:
        self.nvar += 1
        return self.nvar

    # ---------------- expressões ----------------
    def fldx(self, r: N) -> str:
        s: Sym | None = getattr(r, "sym", None)
        if s is None:
            return "lit_a(\"\")"
        x = s.cid
        if r.subs:
            if len(r.subs) > 1:
                self.erro(f"mais de um subscrito em '{r.name}' (somente tabelas de uma dimensão)", r.line)
            if s.stride == 0:
                pass
            x = f"sub({x}, {self.idx(r.subs[0])})"
        elif s.stride and s.occurs <= 1 and not s.children and s.level != 88:
            self.erro(f"item de tabela '{r.name}' usado sem subscrito", r.line)
        if r.refmod:
            ini, comp = r.refmod
            if comp is None:
                x = f"refmod_to_end({x}, {self.idx(ini)})"
            else:
                x = f"refmod({x}, {self.idx(ini)}, {self.idx(comp)})"
        return x

    def idx(self, e: N) -> str:
        if e.kind == "num":
            return str(int(float(e.text)))
        if e.kind == "ref":
            return f"get_int({self.fldx(e)})"
        return f"d_int({self.dexp(e)})"

    def val(self, e: N) -> str:
        k = e.kind
        if k == "str":
            s, n = c_str(e.text, self.enc)
            return f"lit_al({s}, {n})"
        if k == "num":
            return f'lit_ns("{e.text}")'
        if k == "fig":
            if e.fig == "ALL":
                return f"fig_all({c_str(e.text, self.enc)[0]})"
            return f"fig({FIGC[e.fig]})"
        if k == "ref":
            return self.fldx(e)
        if k == "func":
            return self.funcao(e)
        if k in ("bin", "neg", "lenof"):
            return f"from_dec({self.dexp(e)})"
        self.erro(f"operando não suportado ({k})", e.line)
        return 'lit_a("")'

    def funcao(self, e: N) -> str:
        n = e.name
        a = [self.val(x) for x in e.args]
        if n == "REVERSE":
            return f"fn_reverse({a[0]})"
        if n == "UPPER-CASE":
            return f"fn_upper({a[0]})"
        if n == "LOWER-CASE":
            return f"fn_lower({a[0]})"
        if n == "TRIM":
            return f"fn_trim({a[0]}, 0)"
        if n == "LENGTH":
            return f"from_dec(dlen({a[0]}))"
        if n == "NUMVAL":
            return f"fn_numval({a[0]})"
        if n == "CURRENT-DATE":
            return "fn_current_date()"
        if n in ("ORD",):
            return f"fn_ord({a[0]})"
        if n == "CHAR":
            return f"fn_char({a[0]})"
        if n in ("MOD", "REM"):
            return f"fn_{n.lower()}({a[0]}, {a[1]})"
        if n in ("ABS", "INTEGER", "INTEGER-PART", "SQRT"):
            return f"fn_{n.lower().replace('-', '_')}({a[0]})"
        if n in ("MAX", "MIN", "SUM"):
            return f"fn_{n.lower()}({len(a)}, (fld[]){{{', '.join(a)}}})"
        if n == "INTEGER-OF-DATE":
            return f"fn_integer_of_date({a[0]})"
        if n == "DATE-OF-INTEGER":
            return f"fn_date_of_integer({a[0]})"
        self.erro(f"FUNCTION {n} não suportada", e.line)
        return 'lit_a("")'

    def dexp(self, e: N) -> str:
        k = e.kind
        if k == "num":
            t = e.text
            neg = t.startswith("-")
            t2 = t.lstrip("+-")
            sc = len(t2.split(".")[1]) if "." in t2 else 0
            dig = t2.replace(".", "")
            if len(dig) <= 17:
                return f"D({'-' if neg else ''}{int(dig)}LL, {sc})"
            return f'dlits("{t}")'
        if k == "ref":
            return f"get_dec({self.fldx(e)})"
        if k == "lenof":
            return f"dlen({self.fldx(e.ref)})"
        if k == "func":
            return f"get_dec({self.funcao(e)})"
        if k == "neg":
            return f"d_neg({self.dexp(e.e)})"
        if k == "bin":
            f = {"+": "d_add", "-": "d_sub", "*": "d_mul", "/": "d_div", "**": "d_pow"}[e.op]
            return f"{f}({self.dexp(e.l)}, {self.dexp(e.r)})"
        if k == "str":
            return f"get_dec({self.val(e)})"
        if k == "fig":
            return "D(0, 0)"
        self.erro(f"expressão aritmética não suportada ({k})", e.line)
        return "D(0, 0)"

    def cexp(self, c: N) -> str:
        k = c.kind
        if k == "rel":
            return f"(cmp({self.val(c.l)}, {self.val(c.r)}) {RELC[c.op]} 0)"
        if k == "and":
            return f"({self.cexp(c.l)} && {self.cexp(c.r)})"
        if k == "or":
            return f"({self.cexp(c.l)} || {self.cexp(c.r)})"
        if k == "not":
            return f"(!{self.cexp(c.e)})"
        if k == "class":
            return self.classe(self.val(c.e), c.cls, c.neg)
        if k == "sign":
            x = self.val(c.e)
            if c.cls == "POSITIVE":
                t = f"(sign_of({x}) > 0)"
            elif c.cls == "NEGATIVE":
                t = f"(sign_of({x}) < 0)"
            else:
                t = f"(sign_of({x}) == 0)"
            return f"(!{t})" if c.neg else t
        if k == "condname":
            return self.condname(c.ref)
        self.erro(f"condição não suportada ({k})", c.line)
        return "0"

    def classe(self, x: str, cls: str, neg: bool) -> str:
        if cls == "NUMERIC":
            t = f"is_numeric({x})"
        elif cls == "ALPHABETIC":
            t = f"is_alpha({x})"
        elif cls == "ALPHABETIC-LOWER":
            t = f"is_alpha({x})"
        else:
            t = f"is_alpha({x})"
        return f"(!{t})" if neg else f"({t})"

    def condname(self, r: N) -> str:
        s: Sym | None = getattr(r, "sym", None)
        if s is None or s.parent is None:
            return "0"
        pai = s.parent.cid
        if r.subs:
            pai = f"sub({pai}, {self.idx(r.subs[0])})"
        partes = []
        for a, b in s.values88:
            if b is None:
                partes.append(f"cmp({pai}, {self.val(a)}) == 0")
            else:
                partes.append(f"(cmp({pai}, {self.val(a)}) >= 0 && cmp({pai}, {self.val(b)}) <= 0)")
        return "(" + " || ".join(partes or ["0"]) + ")"

    # ---------------- comandos ----------------
    def stmts(self, lista: list[N] | None) -> None:
        for s in lista or []:
            self.stmt(s)

    def stmt(self, s: N) -> None:
        m = getattr(self, "g_" + s.kind, None)
        if m is None:
            self.erro(f"geração de código para '{s.kind}' não implementada", s.line)
            return
        m(s)

    def g_endsent(self, s):
        pass

    def g_continue(self, s):
        self.w(";")

    def g_display(self, s):
        for it in s.items:
            self.w(f"disp_one({self.val(it)});")
        self.w(f"disp_end({1 if s.advancing else 0});")

    def g_accept(self, s):
        alvo = self.fldx(s.target)
        if s.source is None:
            self.w(f"acc({alvo});")
        else:
            cod = {"DATE": 0, "TIME": 1, "DAY": 2, "DAY-OF-WEEK": 3, "DATE8": 4, "DAY8": 5}.get(s.source)
            if cod is None:
                self.erro(f"ACCEPT FROM {s.source} não suportado", s.line)
            else:
                self.w(f"acc_date({alvo}, {cod});")

    @staticmethod
    def _pares_corr(a, b):
        """Pares (origem, destino) de MOVE CORRESPONDING: itens de mesmo nome (exceto FILLER) nos dois
        grupos, em qualquer nível; grupos de mesmo nome são percorridos por dentro."""
        def valido(x):
            return (x.name and x.name.upper() != "FILLER" and x.level not in (66, 77, 88)
                    and x.redefines is None and x.occurs <= 1 and not x.stride)
        saida = []
        for ca in a.children:
            if not valido(ca):
                continue
            for cb in b.children:
                if valido(cb) and cb.name.upper() == ca.name.upper():
                    if ca.children and cb.children:
                        saida += GeradorC._pares_corr(ca, cb)
                    else:
                        saida.append((ca, cb))
                    break
        return saida

    def _move_corr(self, s):
        origem = getattr(s.src, "sym", None)
        if origem is None or not origem.children:
            self.erro("MOVE CORRESPONDING exige itens de grupo", s.line)
            return
        for t in s.targets:
            destino = getattr(t, "sym", None)
            if destino is None or not destino.children:
                self.erro("MOVE CORRESPONDING exige itens de grupo", s.line)
                continue
            for a, b in self._pares_corr(origem, destino):
                self.w(f"mv({b.cid}, {a.cid});")

    def g_move(self, s):
        if getattr(s, "corr", False):
            self._move_corr(s)
            return
        v = self.val(s.src)
        for t in s.targets:
            self.w(f"mv({self.fldx(t)}, {v});")

    def _soma(self, vals: list[N]) -> str:
        if not vals:
            return "D(0, 0)"
        x = self.dexp(vals[0])
        for v in vals[1:]:
            x = f"d_add({x}, {self.dexp(v)})"
        return x

    def _tratar_se(self, s: N, corpo) -> None:
        """Emite bloco aritmético com ON SIZE ERROR / NOT ON SIZE ERROR."""
        self.w("{")
        self.ind += 1
        self._com_se = s.se is not None or s.nse is not None
        self.w("int se = 0; g_divzero = 0;")
        corpo()
        if s.se is not None or s.nse is not None:
            self.w("if (se) {")
            self.ind += 1
            self.stmts(s.se)
            self.ind -= 1
            if s.nse is not None:
                self.w("} else {")
                self.ind += 1
                self.stmts(s.nse)
                self.ind -= 1
            self.w("}")
        self.ind -= 1
        self.w("}")

    def _guardar(self, alvo: N, expr: str, arred: bool) -> None:
        # sem ON SIZE ERROR o resultado é truncado (nao ha erro de tamanho); divisao por zero deixa o destino intacto
        sep = "&se" if self._com_se else "NULL"
        self.w(f"{{ dec v_ = {expr}; if (g_divzero) se = 1; else st({self.fldx(alvo)}, v_, {1 if arred else 0}, {sep}); }}")

    def g_add(self, s):
        def corpo():
            self.w(f"dec soma = {self._soma(s.vals)};")
            if s.giving:
                for a, r in s.giving:
                    self._guardar(a, "soma", r)
            else:
                for a, r in s.to:
                    self._guardar(a, f"d_add(get_dec({self.fldx(a)}), soma)", r)
        self._tratar_se(s, corpo)

    def g_sub(self, s):
        def corpo():
            self.w(f"dec soma = {self._soma(s.vals)};")
            if s.giving:
                base = self.dexp(s.minuendo) if s.minuendo is not None else "D(0, 0)"
                for a, r in s.giving:
                    self._guardar(a, f"d_sub({base}, soma)", r)
            else:
                for a, r in s.frm:
                    self._guardar(a, f"d_sub(get_dec({self.fldx(a)}), soma)", r)
        self._tratar_se(s, corpo)

    def g_mul(self, s):
        def corpo():
            a = self.dexp(s.a)
            if s.giving:
                b = self.dexp(s.b) if s.b is not None else "D(1, 0)"
                for g, r in s.giving:
                    self._guardar(g, f"d_mul({a}, {b})", r)
            else:
                for g, r in s.bys:
                    self._guardar(g, f"d_mul(get_dec({self.fldx(g)}), {a})", r)
        self._tratar_se(s, corpo)

    def g_div(self, s):
        def corpo():
            a = self.dexp(s.a)
            if s.giving:
                b = self.dexp(s.b) if s.b is not None else "D(1, 0)"
                if s.mode == "into":
                    dividendo, divisor = b, a
                else:
                    dividendo, divisor = a, b
                self.w(f"dec dvd = {dividendo}, dvs = {divisor};")
                for g, r in s.giving:
                    self._guardar(g, "d_div(dvd, dvs)", r)
                if s.rem is not None:
                    q = self.fldx(s.giving[0][0])
                    self.w(f"if (!g_divzero) st({self.fldx(s.rem)}, d_sub(dvd, d_mul(get_dec({q}), dvs)), 0, NULL);")
            else:
                for g, r in s.into:
                    self._guardar(g, f"d_div(get_dec({self.fldx(g)}), {a})", r)
        self._tratar_se(s, corpo)

    def g_compute(self, s):
        def corpo():
            self.w(f"dec res = {self.dexp(s.expr)};")
            for a, r in s.targets:
                self._guardar(a, "res", r)
        self._tratar_se(s, corpo)

    def g_if(self, s):
        self.w(f"if ({self.cexp(s.cond)}) {{")
        self.ind += 1
        self.stmts(s.then)
        self.w(";")
        self.ind -= 1
        if s.orelse is not None:
            self.w("} else {")
            self.ind += 1
            self.stmts(s.orelse)
            self.w(";")
            self.ind -= 1
        self.w("}")

    def g_exit(self, s):
        if s.what == "PROGRAM":
            self.g_goback(s)
        elif s.what == "PARAGRAPH":
            self.w(f"goto P{self._para_atual + 1};")
        elif s.what == "SECTION":
            p = self.prog.paras[self._para_atual]
            fim = self.tab.secoes[p.section][1] + 1 if p.section else self._para_atual + 1
            self.w(f"goto P{fim};")
        else:
            self.w(";")

    def g_stop(self, s):
        self.w(f"rt_stop(get_int({self.rc()}));")

    def rc(self) -> str:
        return self.tab.syms[0].cid

    def g_goback(self, s):
        if self.prog.using:
            self.w(f"return (int)get_int({self.rc()});")
        else:
            self.w(f"rt_stop(get_int({self.rc()}));")

    def alvo_indice(self, nome: str, linha: int) -> int:
        if nome in self.tab.secoes:
            return self.tab.secoes[nome][0]
        return self.tab.paras[nome]

    def g_goto(self, s):
        if s.depending is None:
            self.w(f"goto P{self.alvo_indice(s.names[0], s.line)};")
        else:
            self.w(f"switch (get_int({self.fldx(s.depending)})) {{")
            for i, nome in enumerate(s.names, 1):
                self.w(f"    case {i}: goto P{self.alvo_indice(nome, s.line)};")
            self.w("    default: break;")
            self.w("}")

    def _chamar(self, nome: str, ate: str | None) -> None:
        ini = self.alvo_indice(nome, 0)
        ref_fim = ate or nome
        if ref_fim in self.tab.secoes:
            fim = self.tab.secoes[ref_fim][1] + 1
        else:
            fim = self.tab.paras[ref_fim] + 1
        self.nret += 1
        k = self.nret
        self.rets.append(k)
        self.w(f"perf_ret[sp] = {k}; perf_end[sp] = {fim}; if (++sp >= MAXP) rt_fatal(\"pilha de PERFORM cheia\");")
        self.w(f"goto P{ini};")
        self.w(f"R{k}: ;")

    def _corpo_perform(self, s: N) -> None:
        if s.target is not None:
            self._chamar(s.target, s.thru)
        else:
            self.stmts(s.body)
            self.w(";")

    def g_perform(self, s):
        if s.times is not None:
            v = self.novo()
            self.w(f"for (long k{v} = 0, n{v} = d_int({self.dexp(s.times)}); k{v} < n{v}; k{v}++) {{")
            self.ind += 1
            self._corpo_perform(s)
            self.ind -= 1
            self.w("}")
            return
        if s.varying is not None:
            var, ini, passo = s.varying
            niveis = [(var, ini, passo, s.until)] + [(v, i, p, c) for v, i, p, c in getattr(s, "after", [])]
            for (v, i, p, c) in niveis:
                self.w(f"st({self.fldx(v)}, {self.dexp(i)}, 0, NULL);")
                self.w("for (;;) {")
                self.ind += 1
                self.w(f"if ({self.cexp(c)}) break;")
            self._corpo_perform(s)
            for (v, i, p, c) in reversed(niveis):
                self.w(f"st({self.fldx(v)}, d_add(get_dec({self.fldx(v)}), {self.dexp(p)}), 0, NULL);")
                self.ind -= 1
                self.w("}")
            return
        if s.until is not None:
            self.w("for (;;) {")
            self.ind += 1
            if not s.test_after:
                self.w(f"if ({self.cexp(s.until)}) break;")
            self._corpo_perform(s)
            if s.test_after:
                self.w(f"if ({self.cexp(s.until)}) break;")
            self.ind -= 1
            self.w("}")
            return
        self._corpo_perform(s)

    def g_evaluate(self, s):
        sujs = s.subjects
        primeiro = True
        outro = None
        for wh in s.whens:
            conds = []
            for head in wh.heads:
                if head is None:
                    outro = wh
                    continue
                partes = []
                for j, obj in enumerate(head):
                    sj = sujs[j] if j < len(sujs) else sujs[-1]
                    partes.append(self.objcond(sj, obj))
                conds.append("(" + " && ".join(partes) + ")")
            if wh.other and not conds:
                continue
            c = " || ".join(conds) if conds else "0"
            self.w(("" if primeiro else "else ") + f"if ({c}) {{")
            primeiro = False
            self.ind += 1
            self.stmts(wh.body)
            self.w(";")
            self.ind -= 1
            self.w("}")
        if outro is not None:
            if primeiro:
                self.w("{")
            else:
                self.w("else {")
            self.ind += 1
            self.stmts(outro.body)
            self.w(";")
            self.ind -= 1
            self.w("}")

    def objcond(self, sj: N, o: N) -> str:
        k = o.kind
        if k == "any":
            return "1"
        if k == "cond":
            c = self.cexp(o.cond)
            if sj.kind == "bool" and not sj.value:
                return f"(!{c})"
            return c
        x = self.val(sj)
        if k == "value":
            t = f"(cmp({x}, {self.val(o.value)}) == 0)"
            return f"(!{t})" if o.neg else t
        if k == "cmp":
            return f"(cmp({x}, {self.val(o.value)}) {RELC[o.op]} 0)"
        if k == "class":
            return self.classe(x, o.cls, o.neg)
        if k == "range":
            t = f"(cmp({x}, {self.val(o.lo)}) >= 0 && cmp({x}, {self.val(o.hi)}) <= 0)"
            return f"(!{t})" if o.neg else t
        self.erro(f"WHEN não suportado ({k})", o.line)
        return "0"

    # arquivos
    def arq(self, nome: str) -> str:
        return self.tab.arquivos[nome].cid

    def g_open(self, s):
        modos = {"INPUT": 1, "OUTPUT": 2, "EXTEND": 3, "I-O": 4}
        for modo, nome in s.files:
            self.w(f"f_open(&{self.arq(nome)}, {modos.get(modo, 1)});")

    def g_close(self, s):
        for nome in s.files:
            self.w(f"f_close(&{self.arq(nome)});")

    def g_read(self, s):
        f = self.arq(s.file)
        self.w(f"if (f_read(&{f})) {{")
        self.ind += 1
        if s.into is not None:
            reg = self.tab.arquivos[s.file].record
            if reg is not None:
                self.w(f"mv({self.fldx(s.into)}, {reg.cid});")
        self.stmts(s.not_at_end)
        self.stmts(s.not_invalid)
        self.w(";")
        self.ind -= 1
        self.w("} else {")
        self.ind += 1
        self.stmts(s.at_end)
        self.stmts(s.invalid)
        self.w(";")
        self.ind -= 1
        self.w("}")

    def g_write(self, s):
        f = getattr(s, "file", None) or getattr(s.record, "file", None)
        if f is None:
            return
        if s.source is not None:
            self.w(f"mv({self.fldx(s.record)}, {self.val(s.source)});")
        self.w(f"f_write(&{f.cid});")
        if s.not_invalid:
            self.stmts(s.not_invalid)

    def g_rewrite(self, s):
        self.erro("REWRITE não suportado (arquivos indexados/relativos não são implementados)", s.line)

    def g_initialize(self, s):
        for t in s.targets:
            sym = getattr(t, "sym", None)
            if sym is None:
                continue
            if sym.area != "WS":
                self.w(f"mv({self.fldx(t)}, fig({'F_ZERO' if sym.type == 'N' else 'F_SPACE'}));")
                continue
            n = sym.size * (sym.occurs if (sym.occurs > 1 and not t.subs) else 1)
            self.w(f"memcpy(({self.fldx(t)}).p, {self.tab.pfx}DEF + {sym.off}, {n});")

    def g_inspect(self, s):
        alvo = self.val(s.target)
        self.w("{")
        self.ind += 1
        self.w(f"fld tg = {alvo};")
        modos = {"ALL": 0, "LEADING": 1, "CHARACTERS": 2}
        for cont, modo, pat in s.tally:
            p = self.val(pat) if pat is not None else "fig(F_SPACE)"
            self.w(f"st({self.fldx(cont)}, d_add(get_dec({self.fldx(cont)}), D(insp_count(tg, {p}, {modos[modo]}), 0)), 0, NULL);")
        mods = {"ALL": 0, "LEADING": 1, "FIRST": 2, "CHARACTERS": 3}
        for modo, pat, by in s.repl:
            p = self.val(pat) if pat is not None else "fig(F_SPACE)"
            self.w(f"insp_replace(tg, {p}, {self.val(by)}, {mods[modo]});")
        if s.conv is not None:
            self.w(f"insp_convert(tg, {self.val(s.conv[0])}, {self.val(s.conv[1])});")
        self.ind -= 1
        self.w("}")

    def g_string(self, s):
        self.w("{")
        self.ind += 1
        self.w("strctx sc;")
        ptr = f"get_int({self.fldx(s.ptr)})" if s.ptr is not None else "1"
        self.w(f"str_begin(&sc, {self.fldx(s.dst)}, {ptr});")
        for src, delim in s.parts:
            if delim is None:
                self.w(f"str_add(&sc, {self.val(src)}, 0, lit_a(\"\"));")
            else:
                self.w(f"str_add(&sc, {self.val(src)}, 1, {self.val(delim)});")
        if s.ptr is not None:
            self.w(f"st({self.fldx(s.ptr)}, D(sc.ptr, 0), 0, NULL);")
        if s.ov is not None or s.nov is not None:
            self.w("if (sc.overflow) {")
            self.ind += 1
            self.stmts(s.ov)
            self.ind -= 1
            self.w("} else {")
            self.ind += 1
            self.stmts(s.nov)
            self.ind -= 1
            self.w("}")
        self.ind -= 1
        self.w("}")

    def g_unstring(self, s):
        self.w("{")
        self.ind += 1
        n = len(s.targets)
        self.w(f"fld ds[{n}] = {{" + ", ".join(self.fldx(t) for t in s.targets) + "};")
        dl = ", ".join(self.val(d) for d in s.delims) or 'lit_a(" ")'
        nd = max(1, len(s.delims))
        self.w(f"fld dl[{nd}] = {{{dl}}};")
        self.w(f"long cnt = unstr_run({self.val(s.src)}, dl, {nd}, ds, {n});")
        if s.tally is not None:
            self.w(f"st({self.fldx(s.tally)}, d_add(get_dec({self.fldx(s.tally)}), D(cnt, 0)), 0, NULL);")
        self.ind -= 1
        self.w("}")

    def g_search(self, s):
        sym = getattr(s.table, "sym", None)
        if sym is None:
            return
        alvo = sym
        while alvo is not None and alvo.occurs <= 1:
            alvo = alvo.parent
        if alvo is None:
            self.erro(f"SEARCH em '{s.table.name}', que não é uma tabela (OCCURS)", s.line)
            return
        nome_idx = (alvo.indexes[0] if alvo.indexes else None)
        if s.varying is not None:
            idx = s.varying
        elif nome_idx is not None:
            idx = N("ref", s.line, name=nome_idx, quals=[], subs=[], refmod=None)
            idx.sym = self.tab.por_nome[nome_idx][0]
        else:
            self.erro(f"SEARCH em '{s.table.name}' exige INDEXED BY ou VARYING", s.line)
            return
        ix = self.fldx(idx)
        if s.all:
            # SEARCH ALL (busca binaria) ignora o valor inicial do indice: percorre a tabela toda.
            # Para chaves ordenadas o resultado e o da busca binaria.
            self.w(f"st({ix}, D(1, 0), 0, NULL);")
        self.w("for (;;) {")
        self.ind += 1
        self.w(f"if (get_int({ix}) > {alvo.occurs}) {{")
        self.ind += 1
        self.stmts(s.at_end)
        self.w("break;")
        self.ind -= 1
        self.w("}")
        primeiro = True
        for c, corpo in s.whens:
            self.w(("" if primeiro else "else ") + f"if ({self.cexp(c)}) {{")
            primeiro = False
            self.ind += 1
            self.stmts(corpo)
            self.w("break;")
            self.ind -= 1
            self.w("}")
        self.w(f"st({ix}, d_add(get_dec({ix}), D(1, 0)), 0, NULL);")
        self.ind -= 1
        self.w("}")

    def g_set(self, s):
        for t in s.targets:
            x = self.fldx(t)
            if s.op == "to":
                self.w(f"mv({x}, {self.val(s.value)});")
            elif s.op == "up":
                self.w(f"st({x}, d_add(get_dec({x}), {self.dexp(s.value)}), 0, NULL);")
            else:
                self.w(f"st({x}, d_sub(get_dec({x}), {self.dexp(s.value)}), 0, NULL);")

    def g_set_cond(self, s):
        for t in s.targets:
            sym = getattr(t, "sym", None)
            if sym is None or sym.level != 88 or not sym.values88:
                self.erro("SET ... TO TRUE exige um nome de condição (nível 88)", s.line)
                continue
            pai = sym.parent.cid
            if t.subs:
                pai = f"sub({pai}, {self.idx(t.subs[0])})"
            if s.value:
                self.w(f"mv({pai}, {self.val(sym.values88[0][0])});")
            else:
                self.erro("SET ... TO FALSE não suportado", s.line)

    def g_call(self, s):
        if s.target.kind != "str":
            self.erro("CALL com nome de programa em variável não é suportado", s.line)
            return
        nome = s.target.text
        if nome.upper() in self.conhecidos:
            cn = self.conhecidos[nome.upper()]
            n = len(s.args)
            self.w("{")
            self.ind += 1
            if n:
                self.w(f"fld ca[{n}] = {{" + ", ".join(self.val(a) for a in s.args) + "};")
                self.w(f"unsigned char *pa[{n}] = {{" + ", ".join(f"ca[{i}].p" for i in range(n)) + "};")
            else:
                self.w("unsigned char *pa[1] = {NULL};")
            self.w(f"int rcx = prog_{cn}(pa, {n});")
            self.w(f"st({self.rc()}, D(rcx, 0), 0, NULL);")
            if s.returning is not None:
                self.w(f"st({self.fldx(s.returning)}, D(rcx, 0), 0, NULL);")
            self.stmts(s.nexc)
            self.ind -= 1
            self.w("}")
            return
        self.w("{")
        self.ind += 1
        n = len(s.args)
        if n:
            self.w(f"fld ca[{n}] = {{" + ", ".join(self.val(a) for a in s.args) + "};")
        else:
            self.w("fld ca[1];")
        self.w(f"int found = 0; int rcx = call_builtin({c_str(nome, self.enc)[0]}, {n}, ca, &found);")
        self.w("if (found) {")
        self.ind += 1
        self.w(f"st({self.rc()}, D(rcx, 0), 0, NULL);")
        if s.returning is not None:
            self.w(f"st({self.fldx(s.returning)}, D(rcx, 0), 0, NULL);")
        self.stmts(s.nexc)
        self.ind -= 1
        self.w("} else {")
        self.ind += 1
        if s.exc is not None:
            self.stmts(s.exc)
        else:
            self.w(f"rt_fatal(\"programa chamado nao encontrado: {nome}\");")
        self.ind -= 1
        self.w("}")
        self.ind -= 1
        self.w("}")

    # ---------------- programa ----------------
    PRELUDIO = '#include "cobrt.h"\n#define MAXP 20000\n'

    def nome_c(self) -> str:
        return re.sub(r"\W", "_", self.prog.name.upper())

    def gerar(self, principal: bool = True, conhecidos: dict | None = None) -> str:
        self.conhecidos = conhecidos or {}
        tab, prog = self.tab, self.prog
        P = tab.pfx
        img = tab.imagem("WS")
        # imagem "padrão" (sem VALUE) para INITIALIZE
        import copy
        sem_valor = copy.copy(tab)
        defimg = self._imagem_padrao()
        out = []
        out.append(f"/* gerado de {prog.name} */")
        out.append(f"static unsigned char {P}WS[{max(1, len(img))}] = {{{self._hex(img)}}};")
        out.append(f"static const unsigned char {P}DEF[{max(1, len(defimg))}] = {{{self._hex(defimg)}}};")
        if tab.areas["LS"]:
            limg = tab.imagem("LS")
            out.append(f"static unsigned char {P}LSBUF[{max(1, len(limg))}] = {{{self._hex(limg)}}};")
        for s in tab.syms:
            if s.level == 88:
                continue
            base = "WS" if s.area == "WS" else "NULL"
            ptr = f"{P}WS + {s.off}" if s.area == "WS" else "NULL"
            pic = c_str(s.pic or "", "latin-1")[0] if s.type == "E" else "NULL"
            out.append(
                f"static fld {s.cid} = {{{ptr}, {s.size}, '{s.type}', {s.digits}, {s.scale}, {1 if s.signed else 0}, {s.stride}, {pic}}};"
            )
        for f in tab.arquivos.values():
            out.append(f"static cobfile {f.cid};")
        # corpo
        self.saida = []
        self.ind = 1
        self.corpo()
        out.append("")
        nome_c = self.nome_c()
        out.append(f"int prog_{nome_c}(unsigned char **args, int nargs) {{")
        if prog.comma:
            out.append("    g_comma = 1;")
        out.append("    int perf_ret[MAXP], perf_end[MAXP]; int sp = 0; (void)args; (void)nargs;")
        # ligação dos parâmetros
        for s in tab.syms:
            if s.area == "LS" and s.level != 88:
                raiz = s
                while raiz.parent is not None:
                    raiz = raiz.parent
                if raiz.name in prog.using:
                    k = prog.using.index(raiz.name)
                    out.append(f"    if (args) {s.cid}.p = args[{k}] + {s.off - raiz.off};")
                else:
                    out.append(f"    {s.cid}.p = {P}LSBUF + {s.off};")
        out.extend(self.saida)
        out.append("}")
        out.append("")
        out.append(f"void init_{nome_c}(void) {{")
        for f in tab.arquivos.values():
            self.arq_init(out, f)
        out.append("}")
        if not principal:
            return "\n".join(out) + "\n"
        return "\n".join(out) + "\n" + self._main(nome_c)

    def _main(self, nome_c: str) -> str:
        tab, prog = self.tab, self.prog
        P = tab.pfx
        out = []
        out.append("int main(int argc, char **argv) {")
        out.append("    (void)argc; (void)argv;")
        out.append("    INIT_ALL")
        if prog.using:
            ptrs = []
            for nome in prog.using:
                raiz = next((x for x in tab.por_nome.get(nome, []) if x.area == "LS"), None)
                ptrs.append(f"{P}LSBUF + {raiz.off}" if raiz is not None else "NULL")
            out.append(f"    unsigned char *a[{len(ptrs)}] = {{{', '.join(ptrs)}}};")
            out.append(f"    int r = prog_{nome_c}(a, {len(ptrs)});")
        else:
            out.append(f"    int r = prog_{nome_c}(NULL, 0);")
        out.append("    rt_stop(r);")
        out.append("    return r;")
        out.append("}")
        return "\n".join(out) + "\n"

    def arq_init(self, out: list[str], f) -> None:
        if f.record is None:
            return
        nome, n = c_str(f.assign, self.enc)
        if f.assign_lit:
            out.append(f"    {f.cid}.name = {nome};")
        else:
            alvo = [s for s in self.tab.por_nome.get(f.assign, [])]
            if alvo:
                out.append(f"    {f.cid}.path_fld = &{alvo[0].cid};")
            else:
                self.diag.erro(f"ASSIGN TO '{f.assign}': nome de dados não declarado", f.line, self.arquivo)
        out.append(f"    {f.cid}.rec = {f.record.cid};")
        if f.optional:
            out.append(f"    {f.cid}.optional = 1;")
        if f.status:
            alvo = self.tab.por_nome.get(f.status)
            if alvo:
                out.append(f"    {f.cid}.status = &{alvo[0].cid}; {f.cid}.has_status = 1;")
            else:
                self.diag.erro(f"FILE STATUS '{f.status}' não declarado", f.line, self.arquivo)
        out.append(f"    memcpy({f.cid}.st, \"00\", 3); file_reg(&{f.cid});")

    def _hex(self, img: bytes) -> str:
        if not img:
            return "0"
        linhas = []
        for i in range(0, len(img), 24):
            linhas.append(",".join(f"0x{b:02x}" for b in img[i:i + 24]))
        return "\n" + ",\n".join(linhas) + "\n"

    def _imagem_padrao(self) -> bytes:
        tab = self.tab
        # imagem sem VALUE: temporariamente anula os valores
        guardados = [(s, s.value) for s in tab.syms]
        for s, _ in guardados:
            s.value = None
        img = bytes(tab.imagem("WS"))
        for s, v in guardados:
            s.value = v
        return img

    def corpo(self) -> None:
        paras = self.prog.paras
        self.ind = 1
        for i, p in enumerate(paras):
            self._para_atual = i
            self.w(f"/* {p.name} */")
            self.saida.append(f"P{i}:")
            self.w("if (sp > 0 && perf_end[sp - 1] == %d) goto do_return;" % i)
            self.stmts(p.stmts)
        n = len(paras)
        self.saida.append(f"P{n}:")
        self.w("if (sp > 0 && perf_end[sp - 1] == %d) goto do_return;" % n)
        if self.prog.using:
            self.w(f"return (int)get_int({self.rc()});")
        else:
            self.w(f"rt_stop(get_int({self.rc()}));")
        self.w("return 0;")
        self.saida.append("do_return:")
        self.w("sp--;")
        self.w("switch (perf_ret[sp]) {")
        for k in self.rets:
            self.w(f"    case {k}: goto R{k};")
        self.w("    default: break;")
        self.w("}")
        self.w("return 0;")
