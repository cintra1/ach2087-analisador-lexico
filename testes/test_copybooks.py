from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.copybooks import CopybookError, expandir_copys

RAIZ = Path(__file__).resolve().parents[1]


class TestCopybooks(unittest.TestCase):
    def test_expande_copy_na_mesma_pasta_e_extensao_cpy(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            (raiz / "DADOS.cpy").write_text(
                "       01 WS-CODIGO PIC 9.\n", encoding="utf-8"
            )
            codigo = "       DATA DIVISION.\n       COPY DADOS.\n"

            expandido = expandir_copys(codigo, fonte)

            self.assertIn("       01 WS-CODIGO PIC 9.", expandido)
            self.assertNotIn("COPY DADOS", expandido)

    def test_expande_copy_aninhado_de_diretorio_adicional(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            biblioteca = raiz / "copybooks"
            biblioteca.mkdir()
            (biblioteca / "OUTER.cpy").write_text(
                "COPY INNER.\n", encoding="utf-8"
            )
            (biblioteca / "INNER.cpy").write_text(
                'DISPLAY "INCLUIDO".\n', encoding="utf-8"
            )

            expandido = expandir_copys(
                "COPY OUTER.\n", fonte, [biblioteca]
            )

            self.assertIn('DISPLAY "INCLUIDO".', expandido)
            self.assertNotIn("COPY", expandido)

    def test_nao_expande_copy_em_comentario(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            codigo = "*> COPY AUSENTE.\n       * COPY AUSENTE.\n"

            self.assertEqual(expandir_copys(codigo, fonte), codigo)

    def test_cli_analisa_o_copybook_expandido(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            biblioteca = raiz / "copybooks"
            biblioteca.mkdir()
            (biblioteca / "DADOS.cpy").write_text(
                "01 WS-CODIGO PIC 9.\n", encoding="utf-8"
            )
            fonte.write_text(
                "COPY DADOS.\nDISPLAY WS-CODIGO.\n", encoding="utf-8"
            )

            processo = subprocess.run(
                [
                    sys.executable,
                    str(RAIZ / "analisador.py"),
                    "-I",
                    str(biblioteca),
                    str(fonte),
                ],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(processo.returncode, 0, processo.stderr)
            self.assertIn("WS-CODIGO", processo.stdout)
            self.assertNotIn("COPY DADOS", processo.stdout)

    def test_cli_classifica_copybook_ausente_como_severo(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            fonte.write_text("COPY AUSENTE.\n", encoding="utf-8")
            processo = subprocess.run(
                [
                    sys.executable,
                    str(RAIZ / "analisador.py"),
                    str(fonte),
                ],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(processo.returncode, 2)
            self.assertIn("[S]", processo.stderr)

    def test_copy_ausente_e_ciclo_sao_erros_explicitos(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            fonte = raiz / "programa.cob"
            with self.assertRaisesRegex(CopybookError, "não encontrado"):
                expandir_copys("COPY AUSENTE.\n", fonte)

            (raiz / "A.cpy").write_text("COPY B.\n", encoding="utf-8")
            (raiz / "B.cpy").write_text("COPY A.\n", encoding="utf-8")
            with self.assertRaisesRegex(CopybookError, "Ciclo de COPY"):
                expandir_copys("COPY A.\n", fonte)


if __name__ == "__main__":
    unittest.main()
