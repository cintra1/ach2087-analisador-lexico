"""Testes do analisador léxico de COBOL."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.lexer import (  # noqa: E402
    AnalisadorLexico,
    CADEIA_PICTURE,
    CONSTANTE_FIGURATIVA,
    ERRO,
    IDENTIFICADOR,
    LITERAL,
    NUMERO_DECIMAL,
    NUMERO_DE_NIVEL,
    NUMERO_INTEIRO,
    OPERADOR_ARITMETICO,
    OPERADOR_CONCATENACAO,
    OPERADOR_RELACIONAL,
    PALAVRA_RESERVADA,
    PONTO,
    detectar_formato,
)
from src.relatorio import formatar, para_json  # noqa: E402


def analisar(codigo: str, formato: str = "livre"):
    return AnalisadorLexico(codigo, formato=formato).analisar()


def pares(codigo: str, formato: str = "livre"):
    resultado = analisar(codigo, formato)
    return [(token.tipo, token.lexema) for token in resultado.tokens], resultado


class TestClassificacao(unittest.TestCase):
    def test_palavras_identificadores_e_figurativas(self):
        tokens, resultado = pares("MOVE SPACES TO WS-NOME.")
        self.assertEqual(
            tokens,
            [
                (PALAVRA_RESERVADA, "MOVE"),
                (CONSTANTE_FIGURATIVA, "SPACES"),
                (PALAVRA_RESERVADA, "TO"),
                (IDENTIFICADOR, "WS-NOME"),
                (PONTO, "."),
            ],
        )
        self.assertEqual(resultado.erros, [])

    def test_maiusculas_e_minusculas_sao_a_mesma_palavra(self):
        tokens, _ = pares("move zeros to contador.")
        self.assertEqual(tokens[0], (PALAVRA_RESERVADA, "move"))
        self.assertEqual(tokens[1], (CONSTANTE_FIGURATIVA, "zeros"))
        self.assertEqual(tokens[3], (IDENTIFICADOR, "contador"))

    def test_palavra_reservada_com_hifen(self):
        tokens, _ = pares("END-IF")
        self.assertEqual(tokens, [(PALAVRA_RESERVADA, "END-IF")])

    def test_numeros_sinal_e_ponto_separador(self):
        tokens, _ = pares("ADD -10.50 TO X. MOVE 2 TO Y.")
        self.assertEqual(
            tokens,
            [
                (PALAVRA_RESERVADA, "ADD"),
                (NUMERO_DECIMAL, "-10.50"),
                (PALAVRA_RESERVADA, "TO"),
                (IDENTIFICADOR, "X"),
                (PONTO, "."),
                (PALAVRA_RESERVADA, "MOVE"),
                (NUMERO_INTEIRO, "2"),
                (PALAVRA_RESERVADA, "TO"),
                (IDENTIFICADOR, "Y"),
                (PONTO, "."),
            ],
        )

    def test_ponto_final_nao_entra_no_inteiro(self):
        tokens, _ = pares("MOVE 10. TO X.")
        self.assertEqual(tokens[1], (NUMERO_INTEIRO, "10"))
        self.assertEqual(tokens[2], (PONTO, "."))

    def test_operadores(self):
        tokens, _ = pares("IF A >= B AND C <= D AND E <> F COMPUTE G = H ** 2 + I - J / K * L & M.")
        lexemas = [lexema for _, lexema in tokens]
        self.assertIn(">=", lexemas)
        self.assertIn("<=", lexemas)
        self.assertIn("<>", lexemas)
        self.assertIn("**", lexemas)
        self.assertIn("&", lexemas)
        self.assertEqual(tokens[tokens.index((OPERADOR_ARITMETICO, "**")) + 1][0], NUMERO_INTEIRO)
        self.assertIn((OPERADOR_RELACIONAL, ">="), tokens)
        self.assertIn((OPERADOR_CONCATENACAO, "&"), tokens)

    def test_literais(self):
        tokens, resultado = pares("""MOVE "A""B" TO X. MOVE 'ABC' TO Y. MOVE X\"4F\" TO Z.""")
        literais = [lexema for tipo, lexema in tokens if tipo == LITERAL]
        self.assertEqual(literais, ['"A""B"', "'ABC'", 'X"4F"'])
        self.assertEqual(resultado.erros, [])

    def test_literal_nao_terminado(self):
        _, resultado = pares('DISPLAY "sem fechar.\nSTOP RUN.')
        self.assertTrue(any("não terminado" in erro.mensagem for erro in resultado.erros))
        lexemas = [token.lexema for token in resultado.tokens]
        self.assertIn("STOP", lexemas)
        self.assertIn("RUN", lexemas)

    def test_hifen_duplicado_e_caractere_invalido(self):
        tokens, resultado = pares("DISPLAY A--B @ 1.")
        self.assertIn((ERRO, "--"), tokens)
        self.assertIn((ERRO, "@"), tokens)
        self.assertGreaterEqual(len(resultado.erros), 2)

    def test_picture_e_periodo_seguinte(self):
        tokens, resultado = pares("01 CAMPO PIC 9(5). 05 NOME PICTURE IS X(10).")
        pictures = [lexema for tipo, lexema in tokens if tipo == CADEIA_PICTURE]
        self.assertEqual(pictures, ["9(5)", "X(10)"])
        self.assertEqual(resultado.erros, [])
        self.assertIn((PALAVRA_RESERVADA, "IS"), tokens)
        self.assertEqual(tokens[2], (PALAVRA_RESERVADA, "PIC"))
        self.assertEqual(tokens[3], (CADEIA_PICTURE, "9(5)"))
        self.assertEqual(tokens[4], (PONTO, "."))

    def test_picture_editada(self):
        casos = {
            "S9(4)V99": "S9(4)V99",
            "ZZ,ZZ9.99": "ZZ,ZZ9.99",
            "$$$,$$9.99": "$$$,$$9.99",
            "-ZZ9": "-ZZ9",
            "+9(4)": "+9(4)",
            "99": "99",
        }
        for cadeia, esperado in casos.items():
            tokens, resultado = pares(f"01 X PIC {cadeia}.")
            self.assertEqual(tokens[3], (CADEIA_PICTURE, esperado), cadeia)
            self.assertEqual(tokens[4], (PONTO, "."), cadeia)
            self.assertEqual(resultado.erros, [], cadeia)

    def test_picture_ausente(self):
        tokens, resultado = pares("01 X PIC .")
        self.assertTrue(any("picture ausente" in erro.mensagem for erro in resultado.erros))
        self.assertIn((PONTO, "."), tokens)

    def test_parenteses_de_picture_sem_fechar(self):
        _, resultado = pares("01 X PIC 9(5")
        self.assertTrue(any("Parênteses" in erro.mensagem for erro in resultado.erros))

    def test_numeros_de_nivel(self):
        tokens, _ = pares(
            "\n".join(
                [
                    "01 WS-REGISTRO.",
                    "    05 WS-NOME PIC X.",
                    "    05 PIC 9.",
                    "77 WS-CONTADOR PIC 99 VALUE 10.",
                    "    88 WS-CHEIO VALUE 1.",
                    "ADD",
                    "    1 TO WS-CONTADOR.",
                ]
            )
        )
        niveis = [lexema for tipo, lexema in tokens if tipo == NUMERO_DE_NIVEL]
        inteiros = [lexema for tipo, lexema in tokens if tipo == NUMERO_INTEIRO]
        self.assertEqual(niveis, ["01", "05", "05", "77", "88"])
        self.assertIn("10", inteiros)
        self.assertIn("1", inteiros)
        self.assertNotIn("10", niveis)
        self.assertNotIn("1", niveis)

    def test_nivel_depois_de_ponto_na_mesma_linha(self):
        tokens, _ = pares("01 A. 05 B PIC X.")
        niveis = [lexema for tipo, lexema in tokens if tipo == NUMERO_DE_NIVEL]
        self.assertEqual(niveis, ["01", "05"])

    def test_comentario_inline_nao_vira_token(self):
        tokens, resultado = pares('DISPLAY "A". *> texto\nSTOP RUN.')
        lexemas = [token.lexema for token in resultado.tokens]
        self.assertNotIn("*>", "".join(lexemas))
        self.assertNotIn("texto", lexemas)
        self.assertEqual(len(resultado.comentarios), 1)
        self.assertIn("texto", resultado.comentarios[0].texto)
        self.assertIn("STOP", lexemas)

    def test_comentario_de_linha_livre_preserva_potencia(self):
        tokens, resultado = pares("* este e um comentario\nCOMPUTE X = Y\n** 2.")
        self.assertEqual(len(resultado.comentarios), 1)
        lexemas = [token.lexema for token in resultado.tokens]
        self.assertIn("**", lexemas)
        self.assertNotIn("comentario", lexemas)

    def test_diretiva_de_formato(self):
        codigo = '>>SOURCE FORMAT FREE\nDISPLAY "A".\n'
        resultado = analisar(codigo, formato="auto")
        self.assertEqual(resultado.formato, "livre")
        self.assertEqual(resultado.comentarios[0].tipo, "DIRETIVA")
        self.assertEqual(resultado.tokens[0].lexema, "DISPLAY")
        self.assertEqual(resultado.erros, [])


class TestFormatoFixo(unittest.TestCase):
    def test_colunas_classicas(self):
        resultado = analisar("       IDENTIFICATION DIVISION.\n", formato="fixo")
        self.assertEqual(resultado.tokens[0].lexema, "IDENTIFICATION")
        self.assertEqual(resultado.tokens[0].coluna, 8)
        self.assertEqual(resultado.tokens[0].linha, 1)
        self.assertEqual(resultado.tokens[1].lexema, "DIVISION")
        self.assertEqual(resultado.tokens[1].coluna, 23)

    def test_comentario_na_coluna_7(self):
        codigo = "      * comentario\n       STOP RUN.\n"
        resultado = analisar(codigo, formato="fixo")
        self.assertEqual([token.lexema for token in resultado.tokens], ["STOP", "RUN", "."])
        self.assertEqual(resultado.comentarios[0].coluna, 7)
        self.assertTrue(resultado.comentarios[0].texto.startswith("*"))

    def test_area_de_sequencia_e_identificacao(self):
        corpo = "       MOVE 1 TO X."
        linha = corpo + " " * (72 - len(corpo)) + "NAOENTRA"
        resultado = analisar(linha + "\n", formato="fixo")
        self.assertEqual(
            [token.lexema for token in resultado.tokens],
            ["MOVE", "1", "TO", "X", "."],
        )
        self.assertEqual(resultado.erros, [])

    def test_numeros_de_sequencia(self):
        codigo = "000010 IDENTIFICATION DIVISION.\n000020 PROGRAM-ID. SEQ.\n"
        resultado = analisar(codigo, formato="auto")
        self.assertEqual(resultado.formato, "fixo")
        lexemas = [token.lexema for token in resultado.tokens]
        self.assertNotIn("000010", lexemas)
        self.assertNotIn("000020", lexemas)
        self.assertEqual(lexemas[0], "IDENTIFICATION")
        self.assertEqual(resultado.tokens[0].coluna, 8)

    def test_continuacao_de_codigo_e_de_literal(self):
        codigo = "\n".join(
            [
                '       MOVE "OLA" TO T',
                "      -AB-NOME.",
                '       01 MSG PIC X(20) VALUE "OLA',
                '      -    " MUNDO".',
            ]
        )
        resultado = analisar(codigo + "\n", formato="fixo")
        lexemas = [token.lexema for token in resultado.tokens]
        self.assertEqual(lexemas[:5], ["MOVE", '"OLA"', "TO", "TAB-NOME", "."])
        self.assertIn('"OLA MUNDO"', lexemas)
        self.assertEqual(resultado.erros, [])

    def test_sublinhado_em_identificador(self):
        tokens, resultado = pares("PROGRAM-ID. PROG008_STRING.")
        self.assertIn((IDENTIFICADOR, "PROG008_STRING"), tokens)
        self.assertEqual(resultado.erros, [])

    def test_paragrafo_que_comeca_com_digito(self):
        tokens, resultado = pares("PERFORM 00000-CALCULADORA UNTIL X = 2.")
        self.assertIn((IDENTIFICADOR, "00000-CALCULADORA"), tokens)
        self.assertNotIn((NUMERO_INTEIRO, "00000"), tokens)
        self.assertEqual(resultado.erros, [])

    def test_identificador_com_mais_de_30_caracteres(self):
        nome = "WS-" + ("NOME-" * 5) + "EXTRA"
        self.assertGreater(len(nome), 30)
        tokens, resultado = pares(f"MOVE 1 TO {nome}.")
        self.assertIn((IDENTIFICADOR, nome), tokens)
        self.assertTrue(any("30 caracteres" in erro.mensagem for erro in resultado.erros))

    def test_continuacao_orfa(self):
        resultado = analisar("      -    DISPLAY X.\n", formato="fixo")
        self.assertTrue(any("continuação" in erro.mensagem for erro in resultado.erros))
        self.assertIn("DISPLAY", [token.lexema for token in resultado.tokens])

    def test_linha_de_depuracao(self):
        resultado = analisar("      DDISPLAY X.\n", formato="fixo")
        self.assertEqual([token.lexema for token in resultado.tokens], ["DISPLAY", "X", "."])
        self.assertEqual(resultado.erros, [])

    def test_indicador_invalido_nao_esconde_o_resto(self):
        resultado = analisar("      XDISPLAY X.\n", formato="fixo")
        self.assertTrue(any("Indicador" in erro.mensagem for erro in resultado.erros))
        self.assertIn("DISPLAY", [token.lexema for token in resultado.tokens])


class TestDeteccao(unittest.TestCase):
    def test_exemplo_fixo_e_livre(self):
        fixo = (RAIZ / "exemplos" / "ola.cob").read_text(encoding="utf-8").splitlines()
        livre = (RAIZ / "exemplos" / "livre.cob").read_text(encoding="utf-8").splitlines()
        self.assertEqual(detectar_formato(fixo), "fixo")
        self.assertEqual(detectar_formato(livre), "livre")

    def test_exemplos_prontos(self):
        ola = analisar((RAIZ / "exemplos" / "ola.cob").read_text(encoding="utf-8"), "auto")
        livre = analisar((RAIZ / "exemplos" / "livre.cob").read_text(encoding="utf-8"), "auto")
        erros = analisar((RAIZ / "exemplos" / "erros.cob").read_text(encoding="utf-8"), "auto")

        self.assertEqual(ola.formato, "fixo")
        self.assertEqual(ola.erros, [])
        self.assertIn("ZZ,ZZ9.99", [token.lexema for token in ola.tokens])
        self.assertIn("S9(4)V99", [token.lexema for token in ola.tokens])
        self.assertEqual(ola.tokens[0].coluna, 8)
        self.assertTrue(any(item.tipo == "COMENTARIO" for item in ola.comentarios))

        self.assertEqual(livre.formato, "livre")
        self.assertEqual(livre.erros, [])
        self.assertIn("77", [token.lexema for token in livre.tokens if token.tipo == NUMERO_DE_NIVEL])

        self.assertGreaterEqual(len(erros.erros), 3)
        self.assertIn("STOP", [token.lexema for token in erros.tokens])

    def test_relatorio_e_json(self):
        resultado = analisar("MOVE 1 TO X.")
        texto = formatar(resultado, "exemplo.cob")
        self.assertIn("PALAVRA_RESERVADA", texto)
        self.assertIn("Erros: 0", texto)
        dados = json.loads(para_json(resultado, "exemplo.cob"))
        self.assertEqual(dados["tokens"][0]["lexema"], "MOVE")
        self.assertEqual(dados["erros"], [])


class TestProgramasDaDisciplina(unittest.TestCase):
    def test_exemplos_oficiais_sem_erro_lexico(self):
        pasta = RAIZ / "cobol-exemplos-master"
        programas = sorted(pasta.glob("*.cob"))
        self.assertEqual(len(programas), 7)
        for caminho in programas:
            resultado = analisar(caminho.read_text(encoding="utf-8"), "auto")
            self.assertEqual(resultado.formato, "fixo", caminho.name)
            self.assertEqual(resultado.erros, [], caminho.name)

    def test_erros_inseridos_passam_de_dez(self):
        caminho = RAIZ / "erros-inseridos" / "erros_lexicos.cob"
        resultado = analisar(caminho.read_text(encoding="utf-8"), "fixo")
        self.assertGreaterEqual(len(resultado.erros), 10)


class TestLinhaDeComando(unittest.TestCase):
    def test_cli_nos_exemplos(self):
        pronto = subprocess.run(
            [sys.executable, str(RAIZ / "analisador.py"), str(RAIZ / "exemplos" / "ola.cob")],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(pronto.returncode, 0, pronto.stderr)
        self.assertIn("IDENTIFICATION", pronto.stdout)
        self.assertIn("Erros: 0", pronto.stdout)

        com_erro = subprocess.run(
            [sys.executable, str(RAIZ / "analisador.py"), "--json", str(RAIZ / "exemplos" / "erros.cob")],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(com_erro.returncode, 1, com_erro.stderr)
        dados = json.loads(com_erro.stdout)
        self.assertGreaterEqual(len(dados["erros"]), 1)

        ausente = subprocess.run(
            [sys.executable, str(RAIZ / "analisador.py"), str(RAIZ / "nao-existe.cob")],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(ausente.returncode, 2)


if __name__ == "__main__":
    unittest.main()
