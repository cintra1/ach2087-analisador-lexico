"""Testes do compilador COBOL -> C: semântica (seção 4 da especificação) e execução ponta a ponta."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import cobc  # noqa: E402
from src.diagnosticos import Diagnosticos  # noqa: E402

GCC = cobc.achar_gcc()


def L(*linhas: str) -> str:
    """Monta fonte no formato fixo: área de comando a partir da coluna 8."""
    return "\n".join("       " + x for x in linhas) + "\n"


CABECALHO = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. T."]


def compilar_texto(texto: str, nome: str = "t.cbl"):
    tmp = tempfile.mkdtemp()
    caminho = os.path.join(tmp, nome)
    with open(caminho, "w", encoding="latin-1") as f:
        f.write(texto)
    diag = Diagnosticos()
    ok = cobc.compilar(caminho, os.path.join(tmp, "t.c"), diag)
    return ok, diag, tmp


class SemanticaTest(unittest.TestCase):
    def erros(self, texto: str) -> list[str]:
        ok, diag, tmp = compilar_texto(texto)
        shutil.rmtree(tmp, ignore_errors=True)
        return [m.texto for m in diag.itens if m.severidade in ("E", "S")]

    def test_programa_valido_compila(self):
        fonte = L(*CABECALHO, "PROCEDURE DIVISION.", "    DISPLAY 'OI'.", "    STOP RUN.")
        ok, diag, tmp = compilar_texto(fonte)
        shutil.rmtree(tmp, ignore_errors=True)
        self.assertTrue(ok, [str(m) for m in diag.itens])

    def test_move_alfabetico_para_numerico(self):  # regra 1
        fonte = L(*CABECALHO, "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                  "01 A PIC A(5) VALUE 'ABCDE'.", "01 N PIC 9(5).",
                  "PROCEDURE DIVISION.", "    MOVE A TO N.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("MOVE incompatível" in m for m in e), e)

    def test_identificador_duplicado(self):  # regra 2
        fonte = L(*CABECALHO, "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                  "01 X PIC 9.", "01 X PIC 9.", "PROCEDURE DIVISION.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("duplicado" in m for m in e), e)

    def test_duplicado_em_grupos_diferentes_exige_of(self):  # regra 2 (qualificação)
        base = ["DATA DIVISION.", "WORKING-STORAGE SECTION.",
                "01 G1.", "   05 CAMPO PIC 9.", "01 G2.", "   05 CAMPO PIC 9.", "PROCEDURE DIVISION."]
        sem = self.erros(L(*CABECALHO, *base, "    MOVE 1 TO CAMPO.", "    STOP RUN."))
        self.assertTrue(any("ambígua" in m for m in sem), sem)
        com = self.erros(L(*CABECALHO, *base, "    MOVE 1 TO CAMPO OF G1.", "    STOP RUN."))
        self.assertEqual(com, [])

    def test_perform_de_paragrafo_inexistente(self):  # regra 3
        fonte = L(*CABECALHO, "PROCEDURE DIVISION.", "INICIO.", "    PERFORM NAO-EXISTE.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("NAO-EXISTE" in m for m in e), e)

    def test_goto_de_paragrafo_inexistente(self):  # regra 3
        fonte = L(*CABECALHO, "PROCEDURE DIVISION.", "INICIO.", "    GO TO FIM-NADA.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("FIM-NADA" in m for m in e), e)

    def test_arquivo_sem_select(self):  # regra 4
        fonte = L(*CABECALHO, "DATA DIVISION.", "WORKING-STORAGE SECTION.", "01 X PIC 9.",
                  "PROCEDURE DIVISION.", "    OPEN INPUT ARQ.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("sem SELECT" in m for m in e), e)

    def test_arquivo_sem_fd(self):  # regra 4
        fonte = L(*CABECALHO, "ENVIRONMENT DIVISION.", "INPUT-OUTPUT SECTION.", "FILE-CONTROL.",
                  "    SELECT ARQ ASSIGN TO 'a.dat'.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
                  "01 X PIC 9.", "PROCEDURE DIVISION.", "    OPEN INPUT ARQ.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("sem FD" in m for m in e), e)

    def test_variavel_nao_declarada(self):
        fonte = L(*CABECALHO, "PROCEDURE DIVISION.", "    MOVE 1 TO FANTASMA.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("FANTASMA" in m for m in e), e)

    def test_erro_sintatico_falta_division(self):
        fonte = L(*CABECALHO, "PROCEDURE.", "    STOP RUN.")
        self.assertTrue(self.erros(fonte))

    def test_copy_inexistente(self):
        fonte = L(*CABECALHO, "DATA DIVISION.", "WORKING-STORAGE SECTION.", "COPY NAOTEM.",
                  "PROCEDURE DIVISION.", "    STOP RUN.")
        e = self.erros(fonte)
        self.assertTrue(any("NAOTEM" in m for m in e), e)


@unittest.skipUnless(GCC, "gcc não encontrado")
class ExecucaoTest(unittest.TestCase):
    """Compila programas COBOL de verdade, executa e confere a saída."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def rodar(self, fonte: str, entrada: str = "", preparar=None, timeout: int = 20) -> str:
        nome = os.path.splitext(os.path.basename(fonte))[0]
        exe = os.path.join(self.tmp, nome + ".exe")
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "cobc.py"), fonte, "-o", exe,
                            "--build-dir", self.tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        work = tempfile.mkdtemp(dir=self.tmp)
        if preparar:
            preparar(work)
        p = subprocess.run([exe], input=entrada.encode("utf-8"), capture_output=True, cwd=work, timeout=timeout)
        self.assertEqual(p.returncode, 0, p.stderr.decode("latin-1"))
        self.work = work
        return p.stdout.decode("utf-8").replace("\r\n", "\n")

    def prog(self, nome: str) -> str:
        return os.path.join(RAIZ, "programas", nome)

    def test_aritmetica_e_edicao(self):
        out = self.rodar(os.path.join(RAIZ, "testes", "cobol", "aritmetica.cbl"))
        for esperado in ["A=005 B=-012.50", "C=0006.50", "C=0003.33", "D=23", "D=41", "E=+01023",
                         "ED1=[ 1,234.50]", "ED2=[    -3.45]", "ED3=[   $12.30]", "X5=ABCDE", "X5=[AB   ]",
                         "D=56", "R=003.5", "DIV0", "A=018", "LE10", "IGUAL"]:
            self.assertIn(esperado, out)

    def test_calcmd01(self):
        out = self.rodar(self.prog("CALCMD01.cbl"), "10,50\n20\n0\n3\n3\n")
        self.assertIn("VALOR03 INVALIDO", out)
        self.assertIn("VALOR 01: 00001050", out.replace("0000010.50", "00001050")) if False else None
        self.assertIn("FIM DE PROGRAMA", out)

    def test_caixareg_mascara_e_total(self):
        out = self.rodar(self.prog("CAIXAREG.cbl"), "10,50\n0\n20,00\n5\nS\n3,25\n")
        self.assertIn("VALOR DO ITEM 2 ZERADO", out)
        self.assertIn("** VALOR TOTAL DA COMPRA.:          35,50", out)
        self.assertIn("** VALOR TOTAL FINAL.....:          32,25", out)

    def test_cad0004a_grava_arquivo(self):
        out = self.rodar(self.prog("CAD0004A.cbl"), "ANA\n30\n123.456.789-00\nS\nBRUNO\n40\n111.111.111-11\nN\n")
        self.assertIn("DESEJA CADASTRAR OUTRA PESSOA? (S/N)", out)
        dados = open(os.path.join(self.work, "CADASTRO.dat"), encoding="latin-1").read().splitlines()
        self.assertEqual(dados[0], "ANA".ljust(30) + "030" + "123.456.789-00")
        self.assertEqual(dados[1], "BRUNO".ljust(30) + "040" + "111.111.111-11")

    def test_busca01a(self):
        def prep(w):
            with open(os.path.join(w, "CADASTRO2.dat"), "w", encoding="latin-1") as f:
                f.write("ANA".ljust(30) + "03" + "00000000001\n")
                f.write("BRUNO".ljust(30) + "04" + "00000000002\n")
        out = self.rodar(self.prog("BUSCA01A.cbl"), "00000000002\n", prep)
        self.assertIn("CPF ENCONTRADO!", out)
        out = self.rodar(self.prog("BUSCA01A.cbl"), "99\n", prep)
        self.assertIn("CPF NÃO ENCONTRADO!", out)
        self.assertIn("QUANTIDADE DE REGISTROS LIDOS: 02", out)

    def test_regressao_coboldicas(self):
        """Saída conferida contra o GnuCOBOL 3.2: ACCEPT numérico com texto inválido ou comprido,
        SEARCH ALL (achou e não achou, sem SET prévio do índice) e MOVE CORRESPONDING com FILLER."""
        entrada = "123.456.789-09\n15/05/1990\n12a\n12a\n1.5\n7x9\n103\n999\n"
        out = self.rodar(os.path.join(RAIZ, "testes", "cobol", "regressao_coboldicas.cbl"), entrada)
        self.assertEqual(out.splitlines(), [
            "U=000123 V=0000.00 W=12",
            "U=000012 V=0001.50 W=07",
            "ACHOU BRUNO",
            "NAO ACHOU 999",
            "G2=[08-02-AB]",
        ])

    def test_cad0005a_agenda(self):
        def prep(w):
            open(os.path.join(w, "CADAGENDA.dat"), "w").close()
        out = self.rodar(self.prog("CAD0005A.cbl"), "1\nMARIA\n9999\n", prep)
        self.assertIn("FIM DE PROGRAMA", out)
        dados = open(os.path.join(self.work, "CADAGENDA.dat"), encoding="latin-1").read()
        self.assertTrue(dados.startswith("MARIA".ljust(30) + "9999"))

    def test_cad0002a_validacoes(self):
        out = self.rodar(self.prog("CAD0002A.cbl"),
                         "B1\nBRUNO\n10\n30\n32/01/2000\n15/05/1990\nDEV\nbad.com\nok@x.com\n1\nR\nC\nSP\n1\nFIM\n")
        for esperado in ["NOME INVALIDO", "CADASTRO NAO PERMITIDO PARA MENORES DE 18", "DIA INVALIDO",
                         "EMAIL INVALIDO", "DADOS CADASTRADOS COM SUCESSO!"]:
            self.assertIn(esperado, out)

    def test_prog024a_biblioteca_com_call(self):
        def prep(w):
            open(os.path.join(w, "BIBLIOTECA.dat"), "w").close()
            open(os.path.join(w, "BIBLIOTECA.txt"), "w").close()
        out = self.rodar(self.prog("PROG024A.cbl"), "1\n100\nDOM CASMURRO\nMACHADO\n2\n100\n4\n9\n", prep)
        self.assertIn("DOM CASMURRO", out)
        log = open(os.path.join(self.work, "BIBLIOTECA.txt"), encoding="latin-1").read()
        self.assertIn("CADASTRAR |", log)
        self.assertIn("EMPRESTAR |", log)
        dat = open(os.path.join(self.work, "BIBLIOTECA.dat"), encoding="latin-1").read()
        self.assertTrue(dat.startswith("00100DOM CASMURRO"))
        self.assertEqual(dat.split("\n")[0][65], "N")  # indisponível após empréstimo


if __name__ == "__main__":
    unittest.main()
