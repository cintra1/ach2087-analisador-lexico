"""Gera relatorio.md com o fluxo de tokens dos exemplos e dos erros inseridos."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.lexer import AnalisadorLexico
from src.relatorio import formatar

PASTA = RAIZ / "cobol-exemplos-master"
SAIDA = RAIZ / "resultados"
NARRATIVA = RAIZ / "relatorio_narrativa.md"
RELATORIO = RAIZ / "relatorio.md"


def bloco(titulo: str, texto: str) -> str:
    return f"### {titulo}\n\n```text\n{texto.rstrip()}\n```\n"


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    programas = []
    for caminho in sorted(PASTA.glob("*.cob")):
        codigo = caminho.read_text(encoding="utf-8")
        resultado = AnalisadorLexico(codigo).analisar()
        texto = formatar(resultado, caminho.name)
        (SAIDA / f"{caminho.stem}.txt").write_text(texto, encoding="utf-8")
        programas.append(bloco(caminho.name, texto))

    erros_caminho = RAIZ / "erros-inseridos" / "erros_lexicos.cob"
    erros = AnalisadorLexico(
        erros_caminho.read_text(encoding="utf-8"), formato="fixo"
    ).analisar()
    nome_erros = "erros-inseridos/erros_lexicos.cob"
    texto_erros = formatar(erros, nome_erros)
    (SAIDA / "erros_lexicos.txt").write_text(texto_erros, encoding="utf-8")

    narrativa = NARRATIVA.read_text(encoding="utf-8")
    relatorio = narrativa.replace("{{PROGRAMAS}}", "\n".join(programas).rstrip())
    relatorio = relatorio.replace("{{ERROS}}", bloco(nome_erros, texto_erros).rstrip())
    if "{{" in relatorio:
        raise SystemExit("placeholders restantes no relatorio")
    RELATORIO.write_text(relatorio.rstrip() + "\n", encoding="utf-8")
    print(f"escreveu {RELATORIO} ({len(erros.erros)} erros inseridos)")


if __name__ == "__main__":
    main()
