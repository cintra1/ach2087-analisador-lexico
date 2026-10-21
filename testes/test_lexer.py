import unittest
from src.lexer import AnalisadorLexico

class TestInicio(unittest.TestCase):
    def test_reconhece_tokens_basicos(self):
        resultado = AnalisadorLexico('MOVE 1 TO X.', formato='livre').analisar()
        self.assertEqual([token.lexema for token in resultado.tokens], ['MOVE', '1', 'TO', 'X', '.'])

if __name__ == '__main__':
    unittest.main()
