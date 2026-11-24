"""Teste de conformidade com o GnuCOBOL 3.2: mesma entrada, mesma saída e mesmos arquivos.

Precisa de Docker em execução. A primeira execução constrói a imagem `gnucobol-ref`
(scripts/gnucobol/Dockerfile), o que leva alguns minutos; por isso o teste só roda quando a
imagem já existe ou quando GNUCOBOL_TESTE=1. Sem Docker, é ignorado.

    set GNUCOBOL_TESTE=1 && py -m unittest testes.test_gnucobol     (PowerShell: $env:GNUCOBOL_TESTE=1)
"""

from __future__ import annotations

import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import comparar_gnucobol as gc  # noqa: E402


def _disponivel() -> bool:
    if not gc.docker_ativo():
        return False
    imagem_pronta = gc.docker("image", "inspect", gc.IMAGEM).returncode == 0
    return imagem_pronta or os.environ.get("GNUCOBOL_TESTE") == "1"


@unittest.skipUnless(_disponivel(), "Docker/imagem gnucobol-ref indisponível (use GNUCOBOL_TESTE=1)")
class ConformidadeGnuCOBOLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gc.garantir_imagem()

    def test_casos_iguais_ao_gnucobol(self):
        iguais, total = gc.executar_comparacao()
        self.assertEqual(total, len(gc.CASOS))
        self.assertEqual(iguais, total, "algum caso difere do GnuCOBOL (veja a saída acima)")


if __name__ == "__main__":
    unittest.main()
