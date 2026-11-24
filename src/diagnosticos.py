"""Mensagens do compilador com severidade I / W / E / S (seção 6 da especificação)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mensagem:
    severidade: str  # I, W, E, S
    texto: str
    linha: int = 0
    arquivo: str = ""

    def __str__(self) -> str:
        onde = f"{self.arquivo}:{self.linha}" if self.linha else self.arquivo
        return f"{onde}: [{self.severidade}] {self.texto}"


@dataclass
class Diagnosticos:
    itens: list[Mensagem] = field(default_factory=list)

    def info(self, texto: str, linha: int = 0, arquivo: str = "") -> None:
        self.itens.append(Mensagem("I", texto, linha, arquivo))

    def aviso(self, texto: str, linha: int = 0, arquivo: str = "") -> None:
        self.itens.append(Mensagem("W", texto, linha, arquivo))

    def erro(self, texto: str, linha: int = 0, arquivo: str = "") -> None:
        self.itens.append(Mensagem("E", texto, linha, arquivo))

    def grave(self, texto: str, linha: int = 0, arquivo: str = "") -> None:
        self.itens.append(Mensagem("S", texto, linha, arquivo))

    @property
    def falhou(self) -> bool:
        return any(m.severidade in ("E", "S") for m in self.itens)

    def contagem(self) -> dict[str, int]:
        c = {"I": 0, "W": 0, "E": 0, "S": 0}
        for m in self.itens:
            c[m.severidade] += 1
        return c
