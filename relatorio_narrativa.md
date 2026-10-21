# Relatório — Analisador léxico COBOL

## 2.1 Introdução

COBOL (Common Business-Oriented Language) é uma linguagem de 1959 feita para programas de negócio: cadastro, folha, estoque, cobrança. Continua em bancos, governos e seguradoras porque esses sistemas já estão corretos, movimentam dinheiro com aritmética decimal e descrevem arquivos e registros no próprio fonte. Trocar um programa desses por outra linguagem é caro e arriscado. A sintaxe parece inglês (`MOVE`, `ADD`, `DISPLAY`), o que ajuda quem mantém o código décadas depois.

Essa mesma forma, porém, complica o analisador léxico. O formato fixo não é texto livre: as colunas 1–6 são número de sequência, a coluna 7 diz se a linha é comentário (`*` ou `/`), continuação (`-`) ou depuração (`D`), o código útil vai da coluna 8 à 72 e as colunas 73–80 são ignoradas. O ponto final tanto termina uma sentença quanto é o ponto decimal de um número ou de uma picture (`ZZ9.99`). O hífen entra no nome (`WS-VALOR`, `00000-CALCULADORA`) e também é o sinal de menos (`-10`). A picture reaproveita letras, dígitos, parênteses, vírgula e ponto, então `PIC` abre um contexto que um autômato só de palavras não resolve. Maiúsculas e minúsculas são a mesma palavra. Um inteiro na área A pode ser número de nível (`01`, `77`) ou um valor comum (`MOVE 20 TO X`). Os programas de teste ainda quebram uma palavra entre duas linhas (`T` + `AB-TRABALHADOR`) e dão a parágrafos nomes que começam com dígito.

O trabalho pedido nesta etapa é só o analisador léxico: transformar o fonte em tokens. A especificação descreve também o parser, a semântica e a geração de código; esses passos não foram implementados.

## 2.2 Implementação

O analisador está em Python 3, só com a biblioteca padrão. Não usamos Flex nem outro gerador. As regras que mais importam nos exemplos — colunas, continuação, picture e número de nível — dependem de um pouco de contexto. Num scanner escrito à mão isso fica explícito e dá para testar com `py -m unittest discover -s testes -t .`. O ponto de entrada é `analisador.py`.

O fluxo é o seguinte. O fonte é lido em UTF-8 (ou Latin-1). Se o formato não for forçado, o programa reconhece o cartão de 80 colunas. Nos sete exemplos o resultado é o formato fixo. Em seguida monta-se um texto lógico: colunas 1–6 e 73–80 saem, comentário de coluna 7 vai para uma lista à parte, e a linha com `-` na coluna 7 continua a anterior. Fora de um literal, os espaços do fim da linha são descartados e o texto é colado sem espaço novo, como em `TAB-TRABALHADOR`. Dentro de um literal, a aspa que abre a continuação não entra na string. A varredura então classifica cada lexema.

A seção 2.2 da especificação, na parte legível, lista um núcleo de palavras reservadas: `IDENTIFICATION`, `ENVIRONMENT`, `DATA`, `PROCEDURE`, `DIVISION`, `SECTION`, `DISPLAY`, `ACCEPT`, `PERFORM`, `STOP`, `RUN`, `IF`, `ELSE` e `MOVE`. O resto dessa página está coberto por marca d'água. O restante da especificação e os sete programas usam muito mais palavras (`PROGRAM-ID`, `PIC`, `VALUE`, `ADD`, `SELECT`, `OPEN`, `READ`, `WRITE`, `EVALUATE`). O léxico adotado é o COBOL 85 mais extensões frequentes do GnuCOBOL, conjunto que contém aquele núcleo. Sem isso, `PIC` seria um identificador e a picture não seria isolada.

A pontuação legível na especificação é `. , ; ( )`. Os exemplos também usam `+ - * / ** = > < >= <= <>`. Esses operadores são tokens. Se fossem recusados, programas válidos apareceriam como erro de caractere. O sublinhado não está no alfabeto descrito na especificação (letra, dígito e hífen), mas `PROG006_FILES`, `PROG007_LOJA` e `PROG008_STRING` o usam. Ele entra no identificador para o nome continuar sendo um único token. Um nome com mais de 30 caracteres, limite da especificação, é emitido e também registrado como erro.

Um inteiro de 01 a 49, 66, 77 ou 88 vira `NUMERO_DE_NIVEL` quando é o primeiro token da linha, ou vem logo depois de um ponto, e o token seguinte é um nome ou uma cláusula de dados (`PIC`, `VALUE`, `OCCURS`, `FILLER` e as demais). `VALUE 10` e `ADD 1 TO X` continuam números comuns. Comentários não entram na tabela de tokens.

Um erro léxico não interrompe o arquivo. O analisador registra a mensagem, segue na coluna seguinte e, no fim, devolve código de saída 1. Assim dá para ver, no mesmo relatório, o ponto da falha e os tokens que ainda foram reconhecidos.

**Ferramenta de IA.** O grupo definiu a estratégia (Python, scanner manual, léxico COBOL 85 com extensões do GnuCOBOL, recuperação de erro e os doze casos de `erros-inseridos/erros_lexicos.cob`) e conferiu cada saída contra a especificação e os exemplos. O Cursor, com o modelo Grok 4.7, foi usado como apoio: gerou o rascunho do scanner e dos testes, ajustou a continuação de linha e os parágrafos numéricos depois da execução dos exemplos e montou as tabelas da seção 2.3 a partir da saída do programa. O código está no repositório do grupo.

**Link do repositório:** https://github.com/cintra1/ach2087-analisador-lexico

## 2.3 Resultados dos testes

Os programas são os sete arquivos de `cobol-exemplos-master` (Enio Basso, compiláveis com GnuCOBOL). Todos foram reconhecidos como formato fixo. Nenhum produziu erro léxico. Comentários de coluna 7, inclusive a linha longa do comando `cobc` (coluna 73 em diante é descartada), ficam fora da tabela de tokens.

| Programa | Tokens | Comentários | Erros |
| --- | ---: | ---: | ---: |
| prog001_divisoes.cob | 80 | 27 | 0 |
| prog002_operacoes.cob | 320 | 11 | 0 |
| prog003_calculadora.cob | 229 | 10 | 0 |
| prog004_folha_pgto.cob | 221 | 10 | 0 |
| prog005_strings.cob | 236 | 10 | 0 |
| prog006_files.cob | 225 | 11 | 0 |
| prog007_loja.cob | 566 | 27 | 0 |

Alguns lexemas merecem nota, porque mostram regras que não aparecem num exemplo mínimo:

- Em `prog001`, `2018-02-24` vira três literais numéricos: `2018`, `-02` e `-24`. O hífen colado em dígito é sinal, e a data não tem letra, então não é identificador. `ebasso(dot)net` vira identificador, parêntese, identificador, parêntese, identificador: o ponto escrito por extenso não encerra a sentença.
- Em `prog002`, `VALUES` é palavra reservada, `ZEROS` é constante figurativa e a continuação depois da string fechada traz `WRK-VALOR2` como outro token.
- Em `prog003`, `00000-CALCULADORA` é um identificador só, `**` é o operador de potência e `PIC -ZZZZZZZZZ9.99` é uma cadeia de picture, não um número negativo seguido de nome.
- Em `prog004` e `prog006`, a quebra `T` / `AB-TRABALHADOR` forma o identificador `TAB-TRABALHADOR`. `LOW-VALUES` é constante figurativa. `NOME(IDX)` e `DPTO(IDX,1)` separam nome, parênteses, número e vírgula.
- Em `prog005`, `INSPECT`, `TALLYING`, `REPLACING` e `CONVERTING` são palavras reservadas; o texto manipulado fica em literais.
- Em `prog007`, `PROG007_LOJA` é um identificador com sublinhado. `EVALUATE` / `END-EVALUATE`, `I-O`, `INVALID` e `KEY` saem como palavras reservadas.

A listagem completa de cada programa está a seguir. A coluna é a coluna original do cartão, não a posição depois de ignorar a área de sequência.

{{PROGRAMAS}}

## 2.4 Resultados de erros

Os sete programas da seção anterior permanecem como foram entregues. Os erros foram inseridos em `erros-inseridos/erros_lexicos.cob`, no mesmo formato fixo, para não misturar falha léxica com o fluxo limpo. São 12 erros, acima do mínimo de dez. O analisador segue até `STOP RUN`.

| # | Linha | Coluna | O que foi inserido | Mensagem |
| --- | ---: | ---: | --- | --- |
| 1 | 2 | 7 | `-` na coluna 7 depois de um comentário, sem linha de código antes | Linha de continuação sem linha de código imediatamente anterior. |
| 2 | 8 | 36 | Literal aberto com `"` e não fechado | Literal não terminado. |
| 3 | 9 | 36 | Literal aberto com `'` e não fechado | Literal não terminado. |
| 4 | 10 | 11 | Nome `WS-NOME-MUITO-GRANDE-DEMAIS-PARA-COBOL` (38 caracteres) | Identificador com mais de 30 caracteres. |
| 5 | 11 | 24 | `PIC` sem cadeia | Cadeia de picture ausente. |
| 6 | 12 | 26 | `PIC 9(4` sem o fecha-parêntese | Parênteses não fechados na cadeia de picture. |
| 7 | 15 | 21 | `A--B` | Hífen duplicado. Identificadores COBOL não contêm '--'. |
| 8 | 16 | 28 | `#` entre dois literais | Caractere inválido: '#'. |
| 9 | 17 | 20 | `@` | Caractere inválido: '@'. |
| 10 | 18 | 20 | `$` fora de uma picture | Caractere inválido: '$'. |
| 11 | 19 | 7 | `X` na coluna 7 | Indicador inválido na coluna 7: 'X'. |
| 12 | 20 | 1 | `ABC` começando na coluna 1, num fonte fixo | Linha curta demais para o formato fixo; o código começa na coluna 8. |

O nome longo demais ainda aparece como `IDENTIFICADOR`, e o `#`, o `@`, o `$` e o `--` aparecem como token `ERRO`. A picture incompleta e a linha `ABC` não viram um token útil: a primeira gera o diagnóstico e o ponto seguinte continua sendo pontuação; a segunda é descartada porque, no formato fixo, não há código antes da coluna 8. Nos dois casos a análise do resto do arquivo continua.

{{ERROS}}
