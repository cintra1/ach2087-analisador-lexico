"""Análise semântica: tabela de símbolos, layout de memória e verificações.

Verificações da seção 4 da especificação:
  1. compatibilidade de MOVE (PIC A para PIC 9 é proibido);
  2. unicidade de identificadores (duplicados só podem ser usados com OF/IN);
  3. destinos de PERFORM / GO TO devem existir na PROCEDURE DIVISION;
  4. OPEN/READ/WRITE/CLOSE exigem SELECT (FILE-CONTROL) e FD.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .diagnosticos import Diagnosticos
from .parser import N


@dataclass
class Sym:
    name: str | None
    level: int
    line: int
    parent: "Sym | None" = None
    children: list["Sym"] = field(default_factory=list)
    pic: str | None = None
    usage: str = "DISPLAY"
    type: str = "A"            # A alfanumérico/grupo, N numérico, E editado
    cat: str = "alnum"         # alnum, alpha, numeric, edited, group
    digits: int = 0
    scale: int = 0
    signed: bool = False
    size: int = 0              # tamanho de UMA ocorrência
    occurs: int = 1
    rel: int = 0               # deslocamento dentro do pai (primeira ocorrência)
    off: int = 0               # deslocamento absoluto na área
    area: str = "WS"
    fd: str | None = None
    value: N | None = None
    redefines: "Sym | None" = None
    redefines_name: str | None = None
    values88: list = field(default_factory=list)
    cid: str = ""
    stride: int = 0
    blank_zero: bool = False
    implicit: bool = False
    indexes: list = field(default_factory=list)

    @property
    def is_group(self) -> bool:
        return bool(self.children)

    def path(self) -> list[str]:
        p = []
        s = self.parent
        while s is not None:
            if s.name:
                p.append(s.name)
            s = s.parent
        return p


@dataclass
class Arquivo:
    name: str
    assign: str
    assign_lit: bool
    org: str
    status: str | None
    record: Sym | None
    cid: str
    line: int
    fd_visto: bool = False
    optional: bool = False


class Tabela:
    def __init__(self, diag: Diagnosticos, arquivo: str, pfx: str = ""):
        self.pfx = pfx
        self.diag = diag
        self.arquivo = arquivo
        self.syms: list[Sym] = []
        self.por_nome: dict[str, list[Sym]] = {}
        self.arquivos: dict[str, Arquivo] = {}
        self.areas = {"WS": 0, "LS": 0}
        self.paras: dict[str, int] = {}
        self.secoes: dict[str, tuple[int, int]] = {}
        self.comma = False
        self._n = 0

    # ---------------- construção ----------------
    def construir(self, prog: N) -> None:
        self.comma = prog.comma
        # implícitos
        rc = Sym("RETURN-CODE", 77, 0, pic="S9(4)", usage="COMP", implicit=True)
        self._registrar_raiz(rc, "WS")
        self.arquivos_declarados(prog)
        for it in prog.items_fd + prog.items_ws + prog.items_ls:
            for nome in getattr(it, "indexes", []):
                if nome not in self.por_nome:
                    x = Sym(nome, 77, it.line, pic="9(9)", implicit=True)
                    self._registrar_raiz(x, "WS")
        for area, itens in (("FD", prog.items_fd), ("WS", prog.items_ws), ("LS", prog.items_ls)):
            raiz_stack: list[Sym] = []
            for it in itens:
                self._item(it, "LS" if area == "LS" else "WS", raiz_stack)
        for raiz in [s for s in self.syms if s.parent is None and s.name != "RETURN-CODE"]:
            self._layout_raiz(raiz)
        rc_sym = self.syms[0]
        self._layout_raiz(rc_sym)
        # arquivos: registro = primeiro 01 do FD
        for f in self.arquivos.values():
            recs = [s for s in self.syms if s.parent is None and s.fd == f.name]
            if recs:
                f.record = recs[0]
                f.fd_visto = True
        fds = getattr(prog, "fds", [])
        for nome in fds:
            if nome not in self.arquivos:
                self.diag.erro(f"FD '{nome}' sem SELECT correspondente em FILE-CONTROL", prog.line, self.arquivo)
            else:
                self.arquivos[nome].fd_visto = True
        for f in self.arquivos.values():
            if not f.fd_visto:
                self.diag.erro(f"arquivo '{f.name}' tem SELECT mas não tem FD na DATA DIVISION", f.line, self.arquivo)
            elif f.record is None:
                self.diag.erro(f"FD '{f.name}' sem descrição de registro (01)", f.line, self.arquivo)
            if f.org not in ("LINE SEQUENTIAL", "SEQUENTIAL"):
                self.diag.erro(f"organização '{f.org}' do arquivo '{f.name}' não suportada (somente SEQUENTIAL/LINE SEQUENTIAL)", f.line, self.arquivo)
        # paragrafos
        for i, p in enumerate(prog.paras):
            if p.is_section_start:
                self.secoes[p.name] = tuple(prog.sections[p.name])
                self.paras.setdefault(p.name, i)
            else:
                if p.name in self.paras and p.name != "$MAIN":
                    self.diag.erro(f"parágrafo '{p.name}' declarado mais de uma vez", p.line, self.arquivo)
                self.paras[p.name] = i

    def arquivos_declarados(self, prog: N) -> None:
        for f in prog.files:
            if f.name in self.arquivos:
                self.diag.erro(f"arquivo '{f.name}' declarado mais de uma vez em FILE-CONTROL", f.line, self.arquivo)
            self._n += 1
            self.arquivos[f.name] = arq = Arquivo(
                f.name, f.assign or f.name, f.assign_lit, f.org, f.status, None, f"{self.pfx}file{self._n}_" + re.sub(r"\W", "_", f.name), f.line
            )
            arq.optional = bool(f.optional)

    def _registrar_raiz(self, s: Sym, area: str) -> None:
        s.area = area
        self._cid(s)
        self.syms.append(s)
        if s.name:
            self.por_nome.setdefault(s.name, []).append(s)

    def _cid(self, s: Sym) -> None:
        self._n += 1
        base = re.sub(r"\W", "_", s.name or "FILLER")
        s.cid = f"{self.pfx}f{self._n}_{base}"

    def _item(self, it: N, area: str, stack: list[Sym]) -> None:
        s = Sym(it.name, it.level, it.line, pic=it.pic, usage=it.usage, occurs=it.occurs,
                fd=it.fd, value=it.value, redefines_name=it.redefines, values88=it.values88,
                blank_zero=it.blank_zero)
        s.indexes = list(getattr(it, "indexes", []))
        s.area = area
        if it.level == 88:
            if not stack:
                self.diag.erro("nível 88 sem item pai", it.line, self.arquivo)
                return
            s.parent = stack[-1]
            self._cid(s)
            self.syms.append(s)
            if s.name:
                self.por_nome.setdefault(s.name, []).append(s)
            return
        if it.level in (1, 77):
            stack.clear()
            s.parent = None
        else:
            while stack and (stack[-1].level >= it.level or stack[-1].level in (1, 77) and False):
                stack.pop()
            if not stack:
                self.diag.erro(f"item de nível {it.level:02d} sem item de nível 01 anterior", it.line, self.arquivo)
                return
            s.parent = stack[-1]
            if stack[-1].level == 88:
                pass
            s.parent.children.append(s)
        if it.level not in (1, 77) and s.parent is not None and s.parent.pic is not None and not s.parent.children[:-1]:
            self.diag.erro(f"item '{s.parent.name}' tem PICTURE e também itens subordinados", it.line, self.arquivo)
        stack.append(s)
        self._cid(s)
        self.syms.append(s)
        if s.name:
            # unicidade (regra 2)
            outros = self.por_nome.get(s.name, [])
            for o in outros:
                if o.level in (88,):
                    continue
                mesmo_pai = o.parent is s.parent
                if (s.parent is None and o.parent is None) or mesmo_pai:
                    self.diag.erro(
                        f"identificador '{s.name}' duplicado no mesmo escopo (linha {o.line}); só pode ser repetido em grupos diferentes e usado com OF",
                        it.line, self.arquivo)
                else:
                    self.diag.aviso(f"nome '{s.name}' repetido (linha {o.line}); referências devem ser qualificadas com OF", it.line, self.arquivo)
                break
            self.por_nome.setdefault(s.name, []).append(s)

    # ---------------- picture ----------------
    def _analisar_pic(self, s: Sym) -> None:
        pic = s.pic or ""
        exp = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic)
        up = exp.upper()
        s.cat = "alnum"
        if s.usage in ("COMP-1", "COMP-2", "COMPUTATIONAL-1", "COMPUTATIONAL-2"):
            self.diag.erro(f"USAGE {s.usage} (ponto flutuante) não suportado", s.line, self.arquivo)
        letras = set(up)
        if letras <= set("9SVP"):
            s.type = "N"
            s.cat = "numeric"
            s.signed = "S" in up
            dig = up.count("9") + up.count("P")
            depois_v = 0
            if "V" in up:
                depois_v = len(up.split("V", 1)[1].replace("S", ""))
            s.digits = dig
            s.scale = depois_v
            s.size = dig
            return
        if letras & set("AXGN"):
            s.type = "A"
            s.cat = "alpha" if letras <= set("AB") else "alnum"
            s.size = len(up) - up.count("V")
            return
        # editado numérico
        s.type = "E"
        s.cat = "edited"
        n = 0
        i = 0
        while i < len(up):
            c = up[i]
            if c in "VSP":
                i += 1
                continue
            if c in "CD" and i + 1 < len(up) and up[i + 1] in "RB":
                n += 2
                i += 2
                continue
            n += 1
            i += 1
        s.size = n

    # ---------------- layout ----------------
    def _tamanho(self, s: Sym) -> int:
        """Calcula s.size (uma ocorrência) e s.rel dos filhos."""
        if s.level == 88:
            return 0
        if not s.children:
            if s.pic is None:
                if s.usage == "INDEX":
                    s.type, s.cat, s.digits, s.size = "N", "numeric", 9, 9
                    return s.size
                self.diag.erro(f"item elementar '{s.name or 'FILLER'}' sem cláusula PICTURE", s.line, self.arquivo)
                s.size = 1
                return 1
            self._analisar_pic(s)
            if s.usage in ("COMP-3", "COMPUTATIONAL-3", "PACKED-DECIMAL") and s.type == "N":
                pass  # armazenado como DISPLAY (ver README)
            return s.size
        s.type = "A"
        s.cat = "group"
        off = 0
        fim = 0
        for c in s.children:
            self._tamanho(c)
            if c.redefines_name:
                alvo = None
                for o in s.children:
                    if o is c:
                        break
                    if o.name == c.redefines_name:
                        alvo = o
                if alvo is None:
                    self.diag.erro(f"REDEFINES '{c.redefines_name}' não encontrado no mesmo nível", c.line, self.arquivo)
                    alvo = c
                c.redefines = alvo
                c.rel = alvo.rel
                fim = max(fim, c.rel + c.size * c.occurs)
            else:
                c.rel = off
                off += c.size * c.occurs
                fim = max(fim, off)
        s.size = fim
        return s.size

    def _layout_raiz(self, raiz: Sym) -> None:
        self._tamanho(raiz)
        area = raiz.area
        raiz.off = self.areas[area]
        self.areas[area] += raiz.size * raiz.occurs
        self._offsets(raiz, raiz.off, None)

    def _offsets(self, s: Sym, base: int, occ_pai: Sym | None) -> None:
        s.off = base
        ocup = occ_pai
        if s.occurs > 1:
            if occ_pai is not None:
                self.diag.erro(f"OCCURS aninhado em '{s.name}' (apenas um nível de tabela é suportado)", s.line, self.arquivo)
            s.stride = s.size
            ocup = s
        else:
            s.stride = occ_pai.stride if occ_pai is not None else 0
        for c in s.children:
            self._offsets(c, base + c.rel, ocup)
        # filhos precisam herdar o stride da tabela mais próxima
        for c in s.children:
            if c.occurs <= 1 and ocup is not None:
                self._herdar(c, ocup.stride)

    def _herdar(self, s: Sym, stride: int) -> None:
        s.stride = stride
        for c in s.children:
            if c.occurs <= 1:
                self._herdar(c, stride)

    # ---------------- resolução ----------------
    def resolver(self, ref: N) -> Sym | None:
        cands = self.por_nome.get(ref.name, [])
        if ref.quals:
            filtrados = []
            for c in cands:
                anc = c.path()
                pos = 0
                ok = True
                for q in ref.quals:
                    try:
                        pos = anc.index(q, pos) + 1
                    except ValueError:
                        ok = False
                        break
                if ok:
                    filtrados.append(c)
            cands = filtrados
        if not cands:
            self.diag.erro(f"nome de dados '{ref.name}'{' OF ' + ' OF '.join(ref.quals) if ref.quals else ''} não declarado", ref.line, self.arquivo)
            return None
        if len(cands) > 1:
            self.diag.erro(f"referência ambígua a '{ref.name}': declarado em {len(cands)} lugares; qualifique com OF", ref.line, self.arquivo)
        return cands[0]

    # ---------------- imagem inicial ----------------
    def imagem(self, area: str) -> bytearray:
        buf = bytearray(self.areas[area])
        for raiz in [s for s in self.syms if s.parent is None and s.area == area and s.level != 88]:
            self._preencher(buf, raiz, raiz.off, raiz.size, 0)
        return buf

    def _preencher(self, buf: bytearray, s: Sym, base: int, _a: int, _b: int) -> None:
        for k in range(s.occurs):
            off = base + k * s.size
            if s.children:
                if s.value is not None:
                    self._escrever(buf, s, off)
                for c in s.children:
                    if c.level == 88:
                        continue
                    self._preencher(buf, c, off + c.rel, 0, 0)
            else:
                if s.redefines is not None and s.value is None:
                    continue
                self._escrever(buf, s, off)

    def _escrever(self, buf: bytearray, s: Sym, off: int) -> None:
        dados = self.valor_bytes(s)
        buf[off: off + len(dados)] = dados

    def valor_bytes(self, s: Sym) -> bytes:
        v = s.value
        n = s.size
        if s.type == "N":
            base = b"0" * n
            if v is None:
                return base
            if v.kind == "fig":
                return b"0" * n if v.fig == "ZERO" else base
            if v.kind == "num":
                return self.num_bytes(v.text, s)
            if v.kind == "str":
                return self.num_bytes(v.text, s) if re.fullmatch(r"[+-]?\d+(\.\d+)?", v.text) else base
            return base
        if s.type == "E":
            return b" " * n
        # alfanumérico
        if v is None:
            return b" " * n
        if v.kind == "fig":
            if v.fig == "SPACE":
                return b" " * n
            if v.fig == "ZERO":
                return b"0" * n
            if v.fig == "HIGH":
                return b"\xff" * n
            if v.fig == "LOW":
                return b"\x00" * n
            if v.fig == "QUOTE":
                return b'"' * n
            if v.fig == "ALL":
                t = v.text.encode("latin-1", "replace") or b" "
                return (t * (n // len(t) + 1))[:n]
        if v.kind == "num":
            t = v.text.encode("latin-1")
        else:
            t = v.text.encode(self.codificacao, "replace") if hasattr(self, "codificacao") else v.text.encode("latin-1", "replace")
        return (t + b" " * n)[:n]

    codificacao = "latin-1"

    def num_bytes(self, texto: str, s: Sym) -> bytes:
        neg = texto.startswith("-")
        t = texto.lstrip("+-")
        if "." in t:
            ip, fp = t.split(".", 1)
        else:
            ip, fp = t, ""
        fp = (fp + "0" * s.scale)[: s.scale]
        dig = (ip + fp).lstrip("0") or "0"
        dig = dig.rjust(s.digits, "0")[-s.digits:] if s.digits else dig
        b = bytearray(dig.encode())
        if neg and s.signed and b:
            b[-1] = b[-1] - ord("0") + ord("p")
        return bytes(b)


# ---------------------------------------------------------------------------
# verificações sobre a AST
# ---------------------------------------------------------------------------
def _walk(no, fn):
    if isinstance(no, N):
        fn(no)
        for k, v in no.__dict__.items():
            if k in ("kind", "line", "sym"):
                continue
            _walk(v, fn)
    elif isinstance(no, (list, tuple)):
        for x in no:
            _walk(x, fn)


class Semantico:
    def __init__(self, tab: Tabela, prog: N, diag: Diagnosticos, arquivo: str):
        self.tab = tab
        self.prog = prog
        self.diag = diag
        self.arquivo = arquivo

    def executar(self) -> None:
        paras = self.prog.paras
        if not paras:
            return
        _walk(paras, self._no)
        # USING deve apontar para LINKAGE
        for nome in self.prog.using:
            ss = [s for s in self.tab.por_nome.get(nome, []) if s.area == "LS"]
            if not ss:
                self.diag.erro(f"parâmetro '{nome}' de PROCEDURE DIVISION USING não está na LINKAGE SECTION", self.prog.line, self.arquivo)

    # ------------------------------------------------------------
    def res(self, r: N):
        if not hasattr(r, "sym"):
            r.sym = self.tab.resolver(r)
        return r.sym

    def _no(self, n: N) -> None:
        k = n.kind
        if k == "ref":
            self.res(n)
            if n.sym is not None:
                if len(n.subs) > 0 and n.sym.occurs <= 1 and not self._em_tabela(n.sym):
                    self.diag.erro(f"'{n.name}' usado com subscrito mas não é uma tabela (OCCURS)", n.line, self.arquivo)
                if not n.subs and self._em_tabela(n.sym) and n.sym.occurs <= 1 + 0 and n.sym.level != 88:
                    pass
            return
        if k == "condname":
            self.res(n.ref)
            if n.ref.sym is not None and n.ref.sym.level != 88:
                self.diag.erro(f"'{n.ref.name}' usado como condição mas não é um nome de condição (nível 88)", n.line, self.arquivo)
            return
        if k == "perform":
            for nome in (n.target, n.thru):
                if nome and nome not in self.tab.paras:
                    self.diag.erro(f"PERFORM de '{nome}': parágrafo/seção não declarado na PROCEDURE DIVISION", n.line, self.arquivo)
        elif k == "goto":
            for nome in n.names:
                if nome not in self.tab.paras:
                    self.diag.erro(f"GO TO '{nome}': parágrafo/seção não declarado na PROCEDURE DIVISION", n.line, self.arquivo)
        elif k == "move":
            self._move(n)
        elif k in ("open", "close"):
            for item in n.files:
                nome = item[1] if isinstance(item, tuple) else item
                self._arquivo(nome, n.line, k.upper())
        elif k == "read":
            self._arquivo(n.file, n.line, "READ")
        elif k in ("write", "rewrite"):
            s = self.res(n.record)
            if s is not None:
                raiz = s
                while raiz.parent is not None:
                    raiz = raiz.parent
                f = next((f for f in self.tab.arquivos.values() if f.record is raiz), None)
                if f is None:
                    self.diag.erro(f"WRITE '{n.record.name}': registro não pertence a nenhum arquivo (FD)", n.line, self.arquivo)
                n.file = f
        elif k in ("add", "sub", "mul", "div", "compute"):
            self._aritmetica(n)

    def _em_tabela(self, s: Sym) -> bool:
        while s is not None:
            if s.occurs > 1:
                return True
            s = s.parent
        return False

    def _arquivo(self, nome: str, linha: int, op: str) -> None:
        if nome not in self.tab.arquivos:
            self.diag.erro(f"{op} em '{nome}': arquivo sem SELECT em FILE-CONTROL", linha, self.arquivo)
        elif not self.tab.arquivos[nome].fd_visto:
            self.diag.erro(f"{op} em '{nome}': arquivo sem FD na DATA DIVISION", linha, self.arquivo)

    def _cat(self, e: N) -> str | None:
        if e.kind == "ref":
            s = self.res(e)
            if s is None:
                return None
            if e.refmod:
                return "alnum"
            return s.cat
        if e.kind == "str":
            return "lit-alnum"
        if e.kind == "num":
            return "numeric"
        if e.kind == "fig":
            return "fig"
        return None

    def _move(self, n: N) -> None:
        # resolve primeiro para obter os símbolos
        _walk(n.src, lambda x: None)
        origem = self._cat(n.src)
        for dst in n.targets:
            self.res(dst)
        for dst in n.targets:
            d = dst.sym
            if d is None:
                continue
            if d.level == 88:
                self.diag.erro("MOVE para nome de condição (nível 88)", n.line, self.arquivo)
        for dst in n.targets:
            d = dst.sym
            if d is None or dst.refmod:
                continue
            if origem == "alpha" and d.cat in ("numeric", "edited"):
                self.diag.erro(
                    f"MOVE incompatível: item alfabético (PIC A) '{n.src.name}' para item numérico '{dst.name}' (PIC {d.pic})",
                    n.line, self.arquivo)
            elif origem == "lit-alnum" and d.cat == "numeric":
                txt = n.src.text
                if not re.fullmatch(r"\s*[+-]?\d+(\.\d+)?\s*", txt):
                    self.diag.aviso(f"MOVE de literal não numérico '{txt}' para item numérico '{dst.name}'", n.line, self.arquivo)
            elif origem in ("numeric", "edited") and d.cat == "alpha":
                self.diag.erro(
                    f"MOVE incompatível: item numérico para item alfabético (PIC A) '{dst.name}'", n.line, self.arquivo)

    def _aritmetica(self, n: N) -> None:
        alvos = []
        if n.kind == "add":
            alvos = [a for a, _ in n.to] + [a for a, _ in n.giving]
        elif n.kind == "sub":
            alvos = [a for a, _ in n.frm] + [a for a, _ in n.giving]
        elif n.kind == "mul":
            alvos = [a for a, _ in n.bys] + [a for a, _ in n.giving]
        elif n.kind == "div":
            alvos = [a for a, _ in n.into] + [a for a, _ in n.giving]
        elif n.kind == "compute":
            alvos = [a for a, _ in n.targets]
        for a in alvos:
            s = self.res(a)
            if s is not None and s.cat in ("alnum", "alpha", "group") and not a.refmod and n.kind != "compute" or (
                    s is not None and n.kind == "compute" and s.cat in ("alnum", "alpha")):
                if s.cat != "group":
                    self.diag.erro(f"operação aritmética sobre item não numérico '{a.name}' (PIC {s.pic})", n.line, self.arquivo)
