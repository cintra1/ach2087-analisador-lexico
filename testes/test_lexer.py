import unittest

from src.lexer import AnalisadorLexico, ERRO


class TestComentariosEErros(unittest.TestCase):
    def test_comentario_inline_fica_fora_dos_tokens(self):
        resultado = AnalisadorLexico(
            "DISPLAY X. *> observacao", formato="livre"
        ).analisar()
        self.assertEqual([token.lexema for token in resultado.tokens], ["DISPLAY", "X", "."])
        self.assertEqual(resultado.comentarios[0].tipo, "COMENTARIO")

    def test_erro_lexico_nao_interrompe_a_linha(self):
        resultado = AnalisadorLexico("DISPLAY @ X.", formato="livre").analisar()
        self.assertIn((ERRO, "@"), [(token.tipo, token.lexema) for token in resultado.tokens])
        self.assertIn("X", [token.lexema for token in resultado.tokens])
        self.assertEqual(len(resultado.erros), 1)


if __name__ == "__main__":
    unittest.main()
