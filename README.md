# Analisador léxico de COBOL

Analisador léxico para programas COBOL nos formatos fixo (cartão de 80 colunas) e livre. Ele separa o fonte em tokens, comentários, diretivas e erros léxicos. A classificação não depende de maiúsculas ou minúsculas, e o lexema guardado é o texto original.

O trabalho usa apenas a biblioteca padrão do Python 3.10 ou superior. Neste Windows o interpretador é o `py`.

## Como executar

```text
py analisador.py exemplos/ola.cob
py analisador.py exemplos/livre.cob
py analisador.py --formato fixo exemplos/ola.cob
py analisador.py --formato livre exemplos/livre.cob
py analisador.py --json exemplos/ola.cob
py analisador.py -o saida.txt exemplos/ola.cob
py -m unittest discover -s testes -t .
```

O formato padrão é `auto`: uma diretiva `>>SOURCE FORMAT FREE` ou `FIXED` manda no arquivo; sem ela, o programa observa se o código está no cartão clássico ou se começa antes da coluna 8.

A saída de texto traz a tabela de tokens (linha, coluna, classe e lexema), os comentários, os erros e um resumo. `--json` emite a mesma informação para comparar com os testes do curso. O processo termina com código 0 quando não há erro léxico, 1 quando há, e 2 quando o arquivo não existe.

## Tokens

| Classe | Exemplos |
| --- | --- |
| `PALAVRA_RESERVADA` | `MOVE`, `IF`, `WORKING-STORAGE`, `END-IF` |
| `IDENTIFICADOR` | `WS-NOME`, `CONTADOR` |
| `CONSTANTE_FIGURATIVA` | `ZERO`, `ZEROS`, `SPACES`, `HIGH-VALUES`, `QUOTE` |
| `NUMERO_INTEIRO` | `10`, `+2` |
| `NUMERO_DECIMAL` | `-10.50`, `2.5` |
| `NUMERO_DE_NIVEL` | `01`, `05`, `77`, `88` |
| `LITERAL` | `"OLA"`, `'ABC'`, `X"4F"` |
| `CADEIA_PICTURE` | `9(5)`, `X(10)`, `S9(4)V99`, `ZZ,ZZ9.99` |
| `OPERADOR_ARITMETICO` | `+` `-` `*` `/` `**` |
| `OPERADOR_RELACIONAL` | `=` `>` `<` `>=` `<=` `<>` |
| `OPERADOR_CONCATENACAO` | `&` |
| `PONTO` `VIRGULA` `PONTO_E_VIRGULA` | `.` `,` `;` |
| `ABRE_PARENTESES` `FECHA_PARENTESES` `DOIS_PONTOS` | `(` `)` `:` |
| `ERRO` | caractere que não pertence à linguagem |

Comentários e diretivas `>>` ficam fora da tabela de tokens, numa lista própria. Eles não têm papel sintático.

As palavras reservadas estão em `src/reservadas.py`: COBOL 85 e extensões comuns de GnuCOBOL e IBM (`COMP-3`, `GOBACK`, `END-PROGRAM`, `FUNCTION`, `EXEC SQL`, abreviação `ID`). Constantes figurativas são reservadas, mas recebem classe própria.

## Regras léxicas

Identificador, com pelo menos uma letra e no máximo 30 caracteres. Pode começar com dígito, como os parágrafos `00000-CALCULADORA`, e pode conter `_`, usado nos nomes dos exemplos:

```text
(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_]+(-[A-Za-z0-9_]+)*
```

O hífen só liga letras ou dígitos. `--` não faz parte de um nome e vira erro. A comparação com a lista de reservadas ignora maiúsculas e minúsculas.

Número inteiro e decimal. O sinal só entra no número quando está colado no primeiro dígito. O ponto só é decimal quando o caractere seguinte é um dígito; senão é o ponto que encerra o comando COBOL.

```text
[+-]?[0-9]+
[+-]?[0-9]+\.[0-9]+
```

Literal entre aspas simples ou duplas. Uma aspa duplicada dentro do literal representa uma aspa (`"A""B"` vale A"B). Os prefixos `X`, `N`, `Z`, `B`, `G`, `NX` e `BX` colados na aspa formam um único literal (`X"4F"`).

Comentário até o fim da linha: `*>`. No formato fixo, `*` ou `/` na coluna 7 também comentam a linha. No formato livre, uma linha cujo primeiro caractere não branco é `*` seguido de espaço é comentário. `**` no início da linha continua sendo o operador de potência.

Operadores, do mais longo para o mais curto: `**`, `>=`, `<=`, `<>`, depois `+ - * / > < = &`. Separadores: `. , ; ( ) :`.

Depois de `PIC` ou `PICTURE` (e de um `IS` opcional), o próximo lexema é uma cadeia de picture: letras `A B E G N P S V X Z 9`, os sinais `0 / + - * $`, os pares `CR` e `DB`, e repetições `(n)`. Vírgula e ponto entram na picture quando o caractere seguinte ainda faz parte dela (`ZZ,ZZ9.99`). O ponto de `PIC 9(5).` permanece separador.

Um inteiro de 01 a 49, 66, 77 ou 88 é `NUMERO_DE_NIVEL` quando é o primeiro token da linha, ou vem logo após um ponto, e o token seguinte é um nome de dados, `FILLER` ou uma cláusula de descrição (`PIC`, `VALUE`, `REDEFINES`, `USAGE`, `OCCURS` e as demais listadas no código). `VALUE 10` e `ADD 1 TO X` continuam sendo números comuns.

## Formato do fonte

No formato fixo:

- colunas 1–6: área de sequência, ignorada
- coluna 7: indicador (` ` código, `*` ou `/` comentário, `-` continuação, `D` linha de depuração)
- colunas 8–72: código
- colunas 73–80: identificação, ignorada

Tabulação vale 8 colunas. Uma continuação com `-` na coluna 7 precisa seguir imediatamente a linha continuada. Fora de um literal, os espaços finais da linha anterior são descartados e o texto seguinte é colado no último caractere, sem inserir espaço (`T` + `AB-NOME` forma `TAB-NOME`). Dentro de um literal, os espaços finais permanecem e a aspa inicial da linha seguinte não entra no texto.

No formato livre não há colunas. A quebra de linha só separa tokens.

## Estrutura

```text
analisador.py          linha de comando
src/lexer.py           formato do cartão e varredura
src/reservadas.py      palavras reservadas e constantes figurativas
src/relatorio.py       tabela de texto e JSON
exemplos/              programas de demonstração
testes/test_lexer.py   testes automatizados
```

## Limitações

- Não abre arquivos citados por `COPY`.
- Não valida se um literal hexadecimal contém só dígitos hexadecimais.
- A vírgula fora de uma picture é sempre separador. `DECIMAL-POINT IS COMMA` não é aplicado.
- Diretivas `>>` só são reconhecidas quando começam a linha.
- A continuação com hífen na coluna 7 existe apenas no formato fixo.
- Um nome com mais de 30 caracteres é aceito como identificador e também registrado como erro léxico.
- Nomes de dados são ASCII. Acento dentro de um literal é aceito; fora dele, é caractere inválido.

## Relatório

O texto para a entrega está em `relatorio.md`. Ele usa os sete programas de `cobol-exemplos-master` e os doze erros de `erros-inseridos/erros_lexicos.cob`. Para regenerar as listagens:

```text
py scripts/montar_relatorio.py
```

## Exemplos

`exemplos/ola.cob` está no formato fixo e exercita níveis, pictures, literal, constante figurativa e operadores. `exemplos/livre.cob` está no formato livre. `exemplos/erros.cob` tem um literal sem fechar, um `--` e um caractere inválido, para mostrar que a análise segue depois do erro.

Os sete programas usados no relatório estão em `cobol-exemplos-master`. A tabela de tokens de cada um, junto com os doze erros de `erros-inseridos/erros_lexicos.cob`, está em `relatorio.md`.
