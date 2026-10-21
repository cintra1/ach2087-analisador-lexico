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

Os diagnósticos seguem os níveis da especificação: informação (`I`), aviso (`W`), erro léxico (`E`) e falha severa (`S`). O nível `S` é reservado a falhas que interrompem a análise, como arquivo de entrada ausente, copybook ausente ou ciclo de inclusão; uma execução bem-sucedida não é classificada como erro severo nem recebe um nível de sucesso. No formato fixo, os avisos verificam o posicionamento de cabeçalhos e níveis `01`, `66`, `77` e `88` na área A, níveis `02`–`49` e comandos na área B, sem tentar substituir um parser. A linha de comando também expande instruções `COPY` simples, procurando o copybook ao lado do fonte ou nos diretórios passados com `-I`; a posição dos tokens incluídos refere-se ao texto expandido.

**Ferramenta de IA.** O grupo definiu a estratégia (Python, scanner manual, léxico COBOL 85 com extensões do GnuCOBOL, recuperação de erro e os doze casos de `erros-inseridos/erros_lexicos.cob`) e conferiu cada saída contra a especificação e os exemplos. O Cursor, com o modelo Grok 4.7, foi usado como apoio: gerou o rascunho do scanner e dos testes, ajustou a continuação de linha e os parágrafos numéricos depois da execução dos exemplos e montou as tabelas da seção 2.3 a partir da saída do programa. O código está no repositório do grupo.

**Link do repositório:** https://github.com/cintra1/ach2087-analisador-lexico

## 2.3 Resultados dos testes

Os programas são os sete arquivos de `cobol-exemplos-master` (Enio Basso, compiláveis com GnuCOBOL). Todos foram reconhecidos como formato fixo e nenhum produziu erro léxico. A coluna **Avisos** registra declarações de nível nas áreas A/B incompatíveis com a especificação: os arquivos oficiais `prog002`, `prog003`, `prog004` e `prog006` contêm esse tipo de posicionamento. Comentários de coluna 7, inclusive a linha longa do comando `cobc` (coluna 73 em diante é descartada), ficam fora da tabela de tokens.

| Programa | Tokens | Comentários | Erros léxicos | Avisos de área |
| --- | ---: | ---: | ---: | ---: |
| prog001_divisoes.cob | 80 | 27 | 0 | 0 |
| prog002_operacoes.cob | 320 | 11 | 0 | 6 |
| prog003_calculadora.cob | 229 | 10 | 0 | 7 |
| prog004_folha_pgto.cob | 221 | 10 | 0 | 1 |
| prog005_strings.cob | 236 | 10 | 0 | 0 |
| prog006_files.cob | 225 | 11 | 0 | 6 |
| prog007_loja.cob | 566 | 27 | 0 | 0 |

Alguns lexemas merecem nota, porque mostram regras que não aparecem num exemplo mínimo:

- Em `prog001`, `2018-02-24` vira três literais numéricos: `2018`, `-02` e `-24`. O hífen colado em dígito é sinal, e a data não tem letra, então não é identificador. `ebasso(dot)net` vira identificador, parêntese, identificador, parêntese, identificador: o ponto escrito por extenso não encerra a sentença.
- Em `prog002`, `VALUES` é palavra reservada, `ZEROS` é constante figurativa e a continuação depois da string fechada traz `WRK-VALOR2` como outro token.
- Em `prog003`, `00000-CALCULADORA` é um identificador só, `**` é o operador de potência e `PIC -ZZZZZZZZZ9.99` é uma cadeia de picture, não um número negativo seguido de nome.
- Em `prog004` e `prog006`, a quebra `T` / `AB-TRABALHADOR` forma o identificador `TAB-TRABALHADOR`. `LOW-VALUES` é constante figurativa. `NOME(IDX)` e `DPTO(IDX,1)` separam nome, parênteses, número e vírgula.
- Em `prog005`, `INSPECT`, `TALLYING`, `REPLACING` e `CONVERTING` são palavras reservadas; o texto manipulado fica em literais.
- Em `prog007`, `PROG007_LOJA` é um identificador com sublinhado. `EVALUATE` / `END-EVALUATE`, `I-O`, `INVALID` e `KEY` saem como palavras reservadas.

A listagem completa de cada programa está a seguir. A coluna é a coluna original do cartão, não a posição depois de ignorar a área de sequência.

### prog001_divisoes.cob

```text
Analisador léxico COBOL
Arquivo: prog001_divisoes.cob
Formato: fixo (detecção automática)
Linhas: 58

Linha  Coluna  Token              Lexema
-----  ------  -----------------  ----------------
   15       8  PALAVRA_RESERVADA  IDENTIFICATION
   15      23  PALAVRA_RESERVADA  DIVISION
   15      31  PONTO              .
   16       8  PALAVRA_RESERVADA  PROGRAM-ID
   16      18  PONTO              .
   16      20  IDENTIFICADOR      PROG0001
   16      28  PONTO              .
   19       8  PALAVRA_RESERVADA  AUTHOR
   19      14  PONTO              .
   19      16  IDENTIFICADOR      Enio
   19      21  IDENTIFICADOR      Basso
   19      26  PONTO              .
   20       8  PALAVRA_RESERVADA  INSTALLATION
   20      20  PONTO              .
   20      22  IDENTIFICADOR      ebasso
   20      28  ABRE_PARENTESES    (
   20      29  IDENTIFICADOR      dot
   20      32  FECHA_PARENTESES   )
   20      33  IDENTIFICADOR      net
   20      36  PONTO              .
   21       8  PALAVRA_RESERVADA  DATE-WRITTEN
   21      20  PONTO              .
   21      22  NUMERO_INTEIRO     2018
   21      26  NUMERO_INTEIRO     -02
   21      29  NUMERO_INTEIRO     -24
   21      32  PONTO              .
   22       8  PALAVRA_RESERVADA  DATE-COMPILED
   22      21  PONTO              .
   22      23  NUMERO_INTEIRO     2018
   22      27  NUMERO_INTEIRO     -02
   22      30  NUMERO_INTEIRO     -24
   22      33  PONTO              .
   23       8  PALAVRA_RESERVADA  SECURITY
   23      16  PONTO              .
   23      18  IDENTIFICADOR      O
   23      20  IDENTIFICADOR      programa
   23      29  IDENTIFICADOR      usa
   23      33  IDENTIFICADOR      criptografia
   23      46  IDENTIFICADOR      XPTO
   23      50  PONTO              .
   24       8  IDENTIFICADOR      REMARKS
   24      15  PONTO              .
   24      17  IDENTIFICADOR      O
   24      19  IDENTIFICADOR      programa
   24      28  IDENTIFICADOR      recebe
   24      35  IDENTIFICADOR      um
   24      38  IDENTIFICADOR      valor
   24      44  IDENTIFICADOR      e
   24      46  IDENTIFICADOR      imprime
   24      54  IDENTIFICADOR      na
   24      57  IDENTIFICADOR      tela
   24      61  PONTO              .
   27       8  PALAVRA_RESERVADA  ENVIRONMENT
   27      20  PALAVRA_RESERVADA  DIVISION
   27      28  PONTO              .
   29       8  PALAVRA_RESERVADA  CONFIGURATION
   29      22  PALAVRA_RESERVADA  SECTION
   29      29  PONTO              .
   37       8  PALAVRA_RESERVADA  INPUT-OUTPUT
   37      21  PALAVRA_RESERVADA  SECTION
   37      28  PONTO              .
   46       8  PALAVRA_RESERVADA  DATA
   46      13  PALAVRA_RESERVADA  DIVISION
   46      21  PONTO              .
   53       8  PALAVRA_RESERVADA  PROCEDURE
   53      18  PALAVRA_RESERVADA  DIVISION
   53      26  PONTO              .
   54       8  IDENTIFICADOR      MAIN-PROCEDURE
   54      22  PONTO              .
   55      13  PALAVRA_RESERVADA  DISPLAY
   55      21  LITERAL            "Hello world"
   56      13  PALAVRA_RESERVADA  display
   56      21  LITERAL            "Enio Basso - 2"
   57      13  PALAVRA_RESERVADA  STOP
   57      18  PALAVRA_RESERVADA  RUN
   57      21  PONTO              .
   58       8  PALAVRA_RESERVADA  END
   58      12  PALAVRA_RESERVADA  PROGRAM
   58      20  IDENTIFICADOR      PROG0001
   58      28  PONTO              .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - DIVISOES DE UM PROGRAMA COBOL
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog001_divisoes -std=default prog001_divisoes.co
   10       7  COMENTARIO  ******************************************************************
   12       7  COMENTARIO  *================================================================*
   13       7  COMENTARIO  ***** identifcata a documentacao do programa
   14       7  COMENTARIO  ***** nao contem SECTION
   18       7  COMENTARIO  ***** Itens abaixo sao opcionais
   26       7  COMENTARIO  ***** descreve o computador e perifericos
   31       7  COMENTARIO  ***** Informavam qual computador ia executar. DEPRECIADO.
   32       7  COMENTARIO  *SOURCE-COMPUTER. computador Usado Para Compilar.
   33       7  COMENTARIO  *OBJECT-COMPUTER. computador Usado Para Executar.
   35       7  COMENTARIO  *SPECIAL-NAMES. relacionaNomes Internos A Equipamentos.
   39       7  COMENTARIO  *      nomeia e associa arquivos e perifericos.
   40       7  COMENTARIO  *FILE-CONTROL.
   41       7  COMENTARIO  *         SELECT XPTO00005 ASSIGN to XMS70111
   43       7  COMENTARIO  *I-O-CONTROL. define tecnicas de controle do programa.
   48       7  COMENTARIO  * FILE SECTION.  descricao dos arquivos e registros.
   49       7  COMENTARIO  * WORKING-STORAGE SECTION. aqui declara as variaveis.
   50       7  COMENTARIO  * LINKAGE SECTION. comunicaocao com outros programas.
   51       7  COMENTARIO  * SCREEN SECTION. definicao de telas

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  ABRE_PARENTESES: 1
  FECHA_PARENTESES: 1
  IDENTIFICADOR: 23
  LITERAL: 2
  NUMERO_INTEIRO: 6
  PALAVRA_RESERVADA: 24
  PONTO: 23
  Tokens: 80
  Comentários: 27
  Diretivas: 0
  Erros: 0
  Avisos: 0
```

### prog002_operacoes.cob

```text
Analisador léxico COBOL
Arquivo: prog002_operacoes.cob
Formato: fixo (detecção automática)
Linhas: 100

Linha  Coluna  Token                 Lexema
-----  ------  --------------------  -------------------------------------------------
   11       8  PALAVRA_RESERVADA     IDENTIFICATION
   11      23  PALAVRA_RESERVADA     DIVISION
   11      31  PONTO                 .
   12       8  PALAVRA_RESERVADA     PROGRAM-ID
   12      18  PONTO                 .
   12      20  IDENTIFICADOR         YOUR-PROGRAM-NAME
   12      37  PONTO                 .
   13       8  PALAVRA_RESERVADA     DATA
   13      13  PALAVRA_RESERVADA     DIVISION
   13      21  PONTO                 .
   14       8  PALAVRA_RESERVADA     FILE
   14      13  PALAVRA_RESERVADA     SECTION
   14      20  PONTO                 .
   15       8  PALAVRA_RESERVADA     WORKING-STORAGE
   15      24  PALAVRA_RESERVADA     SECTION
   15      31  PONTO                 .
   16      12  NUMERO_DE_NIVEL       77
   16      15  IDENTIFICADOR         WRK-VALOR1
   16      32  PALAVRA_RESERVADA     PIC
   16      36  CADEIA_PICTURE        9(10)
   16      42  PALAVRA_RESERVADA     VALUES
   16      49  NUMERO_INTEIRO        10
   16      51  PONTO                 .
   17      12  NUMERO_DE_NIVEL       77
   17      15  IDENTIFICADOR         WRK-VALOR2
   17      32  PALAVRA_RESERVADA     PIC
   17      36  CADEIA_PICTURE        9(10)
   17      42  PALAVRA_RESERVADA     VALUES
   17      49  CONSTANTE_FIGURATIVA  ZEROS
   17      54  PONTO                 .
   18      12  NUMERO_DE_NIVEL       77
   18      15  IDENTIFICADOR         WRK-A
   18      32  PALAVRA_RESERVADA     PIC
   18      36  CADEIA_PICTURE        9(2)
   18      41  PALAVRA_RESERVADA     VALUES
   18      48  NUMERO_INTEIRO        1
   18      49  PONTO                 .
   19      12  NUMERO_DE_NIVEL       77
   19      15  IDENTIFICADOR         WRK-B
   19      32  PALAVRA_RESERVADA     PIC
   19      36  CADEIA_PICTURE        9(2)
   19      41  PALAVRA_RESERVADA     VALUES
   19      48  NUMERO_INTEIRO        1
   19      49  PONTO                 .
   20      12  NUMERO_DE_NIVEL       77
   20      15  IDENTIFICADOR         WRK-C
   20      32  PALAVRA_RESERVADA     PIC
   20      36  CADEIA_PICTURE        9(2)
   20      41  PALAVRA_RESERVADA     VALUES
   20      48  CONSTANTE_FIGURATIVA  ZEROS
   20      53  PONTO                 .
   22      12  NUMERO_DE_NIVEL       01
   22      15  IDENTIFICADOR         WRK-TOTAIS
   22      25  PONTO                 .
   23      15  NUMERO_DE_NIVEL       05
   23      18  IDENTIFICADOR         WRK-TOTAL
   23      32  PALAVRA_RESERVADA     PIC
   23      36  CADEIA_PICTURE        9(10)
   23      42  PALAVRA_RESERVADA     VALUE
   23      48  NUMERO_INTEIRO        19
   23      50  PONTO                 .
   25       8  PALAVRA_RESERVADA     PROCEDURE
   25      18  PALAVRA_RESERVADA     DIVISION
   25      26  PONTO                 .
   26       8  IDENTIFICADOR         MAIN-PROCEDURE
   26      22  PONTO                 .
   27      12  PALAVRA_RESERVADA     DISPLAY
   27      20  LITERAL               "===== start ======="
   27      41  PONTO                 .
   28      12  PALAVRA_RESERVADA     MOVE
   28      17  NUMERO_INTEIRO        20
   28      20  PALAVRA_RESERVADA     TO
   28      23  IDENTIFICADOR         WRK-VALOR2
   28      33  PONTO                 .
   29      12  PALAVRA_RESERVADA     DISPLAY
   29      20  LITERAL               "MOVE 20 TO WRK-VALOR2 -->"
   29      48  IDENTIFICADOR         WRK-VALOR2
   29      58  PONTO                 .
   31      12  PALAVRA_RESERVADA     MOVE
   31      17  IDENTIFICADOR         WRK-VALOR1
   31      28  PALAVRA_RESERVADA     TO
   31      31  IDENTIFICADOR         WRK-VALOR2
   31      41  PONTO                 .
   32      12  PALAVRA_RESERVADA     DISPLAY
   32      20  LITERAL               "MOVE WRK-VALOR1 TO WRK-VALOR2 -->"
   32      56  IDENTIFICADOR         WRK-VALOR2
   32      66  PONTO                 .
   34      12  PALAVRA_RESERVADA     MOVE
   34      17  NUMERO_INTEIRO        70
   34      20  PALAVRA_RESERVADA     TO
   34      23  IDENTIFICADOR         WRK-VALOR1
   34      34  IDENTIFICADOR         WRK-VALOR2
   34      44  PONTO                 .
   35      12  PALAVRA_RESERVADA     DISPLAY
   35      20  LITERAL               "MOVE 70 TO WRK-VALOR1 WRK-VALOR2 -->"
   35      59  IDENTIFICADOR         WRK-VALOR2
   35      69  PONTO                 .
   37      12  PALAVRA_RESERVADA     MOVE
   37      17  IDENTIFICADOR         WRK-TOTAL
   37      27  PALAVRA_RESERVADA     OF
   37      30  IDENTIFICADOR         WRK-TOTAIS
   37      41  PALAVRA_RESERVADA     TO
   37      44  IDENTIFICADOR         WRK-VALOR2
   37      54  PONTO                 .
   38      12  PALAVRA_RESERVADA     DISPLAY
   38      20  LITERAL               "MOVE WRK-TOTAL OF WRK-TOTAIS TO WRK-VALOR2. -->"
   39      22  IDENTIFICADOR         WRK-VALOR2
   39      32  PONTO                 .
   41      12  PALAVRA_RESERVADA     DISPLAY
   41      20  LITERAL               "--------"
   41      30  PONTO                 .
   42      12  PALAVRA_RESERVADA     DISPLAY
   42      20  LITERAL               "A = 1, B = 1, C = 1"
   42      41  PONTO                 .
   44      12  PALAVRA_RESERVADA     DISPLAY
   44      20  LITERAL               " "
   44      23  PONTO                 .
   45      12  PALAVRA_RESERVADA     ADD
   45      16  NUMERO_INTEIRO        1
   45      18  NUMERO_INTEIRO        1
   45      20  PALAVRA_RESERVADA     TO
   45      23  IDENTIFICADOR         WRK-A
   45      28  PONTO                 .
   46      12  PALAVRA_RESERVADA     DISPLAY
   46      20  LITERAL               "ADD B C TO A (A = B + C + A) -->"
   46      55  IDENTIFICADOR         WRK-A
   46      60  PONTO                 .
   48      12  PALAVRA_RESERVADA     MOVE
   48      17  NUMERO_INTEIRO        1
   48      19  PALAVRA_RESERVADA     TO
   48      22  IDENTIFICADOR         WRK-A
   48      27  PONTO                 .
   49      12  PALAVRA_RESERVADA     ADD
   49      16  NUMERO_INTEIRO        1
   49      18  PALAVRA_RESERVADA     TO
   49      21  IDENTIFICADOR         WRK-A
   49      27  IDENTIFICADOR         WRK-B
   49      32  PONTO                 .
   50      12  PALAVRA_RESERVADA     DISPLAY
   50      20  LITERAL               " "
   50      23  PONTO                 .
   51      12  PALAVRA_RESERVADA     DISPLAY
   51      20  LITERAL               "ADD 1 TO A B (A = A + 1; B = B + 1) -->"
   52      12  PALAVRA_RESERVADA     DISPLAY
   52      20  LITERAL               "A= "
   52      26  IDENTIFICADOR         WRK-A
   52      32  LITERAL               " , B= "
   52      41  IDENTIFICADOR         WRK-B
   52      46  PONTO                 .
   54      12  PALAVRA_RESERVADA     DISPLAY
   54      20  LITERAL               " "
   54      23  PONTO                 .
   55      12  PALAVRA_RESERVADA     ADD
   55      16  NUMERO_INTEIRO        1
   55      18  NUMERO_INTEIRO        1
   55      20  PALAVRA_RESERVADA     GIVING
   55      27  IDENTIFICADOR         WRK-A
   55      32  PONTO                 .
   56      12  PALAVRA_RESERVADA     DISPLAY
   56      20  LITERAL               "ADD B C GIVING A (A = B + C) -->"
   56      55  IDENTIFICADOR         WRK-A
   56      60  PONTO                 .
   58      12  PALAVRA_RESERVADA     DISPLAY
   58      20  LITERAL               "============ SUBTRACT ============= "
   58      58  PONTO                 .
   59      12  PALAVRA_RESERVADA     MOVE
   59      17  NUMERO_INTEIRO        99
   59      20  PALAVRA_RESERVADA     TO
   59      23  IDENTIFICADOR         WRK-A
   59      28  PONTO                 .
   60      12  PALAVRA_RESERVADA     MOVE
   60      17  NUMERO_INTEIRO        0
   60      19  PALAVRA_RESERVADA     TO
   60      22  IDENTIFICADOR         WRK-B
   60      27  PONTO                 .
   61      12  PALAVRA_RESERVADA     DISPLAY
   61      20  LITERAL               "A= 99, B= 0"
   61      33  PONTO                 .
   62      12  PALAVRA_RESERVADA     SUBTRACT
   62      21  NUMERO_INTEIRO        30
   62      24  NUMERO_INTEIRO        23
   62      27  PALAVRA_RESERVADA     FROM
   62      32  IDENTIFICADOR         WRK-A
   63      27  PALAVRA_RESERVADA     GIVING
   63      34  IDENTIFICADOR         WRK-B
   63      39  PONTO                 .
   64      12  PALAVRA_RESERVADA     DISPLAY
   64      20  LITERAL               "SUBTRACT 30 23 FROM A GIVING B.-->"
   65      12  PALAVRA_RESERVADA     DISPLAY
   65      20  LITERAL               "A= "
   65      26  IDENTIFICADOR         WRK-A
   65      32  LITERAL               " , B= "
   65      41  IDENTIFICADOR         WRK-B
   65      46  PONTO                 .
   67      12  PALAVRA_RESERVADA     DISPLAY
   67      20  LITERAL               "============ MULTIPLY ============= "
   67      58  PONTO                 .
   68      12  PALAVRA_RESERVADA     MOVE
   68      17  NUMERO_INTEIRO        40
   68      20  PALAVRA_RESERVADA     TO
   68      23  IDENTIFICADOR         WRK-A
   68      28  PONTO                 .
   69      12  PALAVRA_RESERVADA     MOVE
   69      17  NUMERO_INTEIRO        0
   69      19  PALAVRA_RESERVADA     TO
   69      22  IDENTIFICADOR         WRK-B
   69      27  PONTO                 .
   70      12  PALAVRA_RESERVADA     DISPLAY
   70      20  LITERAL               "A= 40, B= 0"
   70      33  PONTO                 .
   71      12  PALAVRA_RESERVADA     MULTIPLY
   71      21  NUMERO_INTEIRO        2
   71      23  PALAVRA_RESERVADA     BY
   71      26  IDENTIFICADOR         WRK-A
   71      31  PONTO                 .
   72      12  PALAVRA_RESERVADA     DISPLAY
   72      20  LITERAL               "MULTIPLY A BY 2 -->"
   73      12  PALAVRA_RESERVADA     DISPLAY
   73      20  LITERAL               "A= "
   73      26  IDENTIFICADOR         WRK-A
   73      32  LITERAL               " , B= "
   73      41  IDENTIFICADOR         WRK-B
   73      46  PONTO                 .
   75      12  PALAVRA_RESERVADA     DISPLAY
   75      20  LITERAL               "============ MULTIPLY ============= "
   75      58  PONTO                 .
   76      12  PALAVRA_RESERVADA     MOVE
   76      17  NUMERO_INTEIRO        40
   76      20  PALAVRA_RESERVADA     TO
   76      23  IDENTIFICADOR         WRK-A
   76      28  PONTO                 .
   77      12  PALAVRA_RESERVADA     MOVE
   77      17  NUMERO_INTEIRO        0
   77      19  PALAVRA_RESERVADA     TO
   77      22  IDENTIFICADOR         WRK-B
   77      27  PONTO                 .
   78      12  PALAVRA_RESERVADA     DISPLAY
   78      20  LITERAL               "A= 40, B= 0"
   78      33  PONTO                 .
   79      12  PALAVRA_RESERVADA     MULTIPLY
   79      21  NUMERO_INTEIRO        2
   79      23  PALAVRA_RESERVADA     BY
   79      26  IDENTIFICADOR         WRK-A
   79      32  PALAVRA_RESERVADA     GIVING
   79      39  IDENTIFICADOR         WRK-B
   79      44  PONTO                 .
   80      12  PALAVRA_RESERVADA     DISPLAY
   80      20  LITERAL               "MULTIPLY A BY 2 GIVING B.-->"
   81      12  PALAVRA_RESERVADA     DISPLAY
   81      20  LITERAL               "A= "
   81      26  IDENTIFICADOR         WRK-A
   81      32  LITERAL               " , B= "
   81      41  IDENTIFICADOR         WRK-B
   81      46  PONTO                 .
   83      12  PALAVRA_RESERVADA     DISPLAY
   83      20  LITERAL               "============ DIVIDE ============="
   83      55  PONTO                 .
   84      12  PALAVRA_RESERVADA     MOVE
   84      17  NUMERO_INTEIRO        81
   84      20  PALAVRA_RESERVADA     TO
   84      23  IDENTIFICADOR         WRK-A
   84      28  PONTO                 .
   85      12  PALAVRA_RESERVADA     MOVE
   85      17  NUMERO_INTEIRO        0
   85      19  PALAVRA_RESERVADA     TO
   85      22  IDENTIFICADOR         WRK-B
   85      27  PONTO                 .
   86      12  PALAVRA_RESERVADA     MOVE
   86      17  NUMERO_INTEIRO        0
   86      19  PALAVRA_RESERVADA     TO
   86      22  IDENTIFICADOR         WRK-C
   86      27  PONTO                 .
   87      12  PALAVRA_RESERVADA     DISPLAY
   87      20  LITERAL               "A= 80, B= 0"
   87      33  PONTO                 .
   88      12  PALAVRA_RESERVADA     DIVIDE
   88      19  IDENTIFICADOR         WRK-A
   88      25  PALAVRA_RESERVADA     BY
   88      28  NUMERO_INTEIRO        2
   88      30  PALAVRA_RESERVADA     GIVING
   88      37  IDENTIFICADOR         WRK-B
   88      43  PALAVRA_RESERVADA     REMAINDER
   88      53  IDENTIFICADOR         WRK-C
   88      58  PONTO                 .
   89      12  PALAVRA_RESERVADA     DISPLAY
   89      20  LITERAL               "DIVIDE A BY 2 GIVING B REMAINDER C .-->"
   90      12  PALAVRA_RESERVADA     DISPLAY
   90      20  LITERAL               "A= "
   90      26  IDENTIFICADOR         WRK-A
   90      32  LITERAL               " , B= "
   90      41  IDENTIFICADOR         WRK-B
   90      47  LITERAL               " , C= "
   90      56  IDENTIFICADOR         WRK-C
   90      61  PONTO                 .
   93      12  PALAVRA_RESERVADA     DISPLAY
   93      20  LITERAL               " "
   93      23  PONTO                 .
   94      12  PALAVRA_RESERVADA     MOVE
   94      17  NUMERO_INTEIRO        99
   94      20  PALAVRA_RESERVADA     TO
   94      23  IDENTIFICADOR         WRK-A
   94      28  PONTO                 .
   95      12  PALAVRA_RESERVADA     ADD
   95      16  NUMERO_INTEIRO        1
   95      18  PALAVRA_RESERVADA     TO
   95      21  IDENTIFICADOR         WRK-A
   96      12  PALAVRA_RESERVADA     ON
   96      15  PALAVRA_RESERVADA     SIZE
   96      20  PALAVRA_RESERVADA     ERROR
   97      15  PALAVRA_RESERVADA     DISPLAY
   97      23  LITERAL               "ON SIZE ERROR -->"
   97      43  IDENTIFICADOR         WRK-A
   97      48  PONTO                 .
   99      13  PALAVRA_RESERVADA     STOP
   99      18  PALAVRA_RESERVADA     RUN
   99      21  PONTO                 .
  100       8  PALAVRA_RESERVADA     END
  100      12  PALAVRA_RESERVADA     PROGRAM
  100      20  IDENTIFICADOR         YOUR-PROGRAM-NAME
  100      37  PONTO                 .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - Operacoes em programas Cobol
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog002_operacoes.cob -std=default prog002_operac
   10       7  COMENTARIO  ******************************************************************
   92       7  COMENTARIO  ****** Tive que tirar o ponto.

Avisos de formato
  [W] Linha 16, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 17, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 18, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 19, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 20, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 22, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  CADEIA_PICTURE: 6
  CONSTANTE_FIGURATIVA: 2
  IDENTIFICADOR: 60
  LITERAL: 38
  NUMERO_DE_NIVEL: 7
  NUMERO_INTEIRO: 28
  PALAVRA_RESERVADA: 113
  PONTO: 66
  Tokens: 320
  Comentários: 11
  Diretivas: 0
  Erros: 0
  Avisos: 6
```

### prog003_calculadora.cob

```text
Analisador léxico COBOL
Arquivo: prog003_calculadora.cob
Formato: fixo (detecção automática)
Linhas: 83

Linha  Coluna  Token                 Lexema
-----  ------  --------------------  --------------------------------------------------
   11       8  PALAVRA_RESERVADA     IDENTIFICATION
   11      23  PALAVRA_RESERVADA     DIVISION
   11      31  PONTO                 .
   12       8  PALAVRA_RESERVADA     PROGRAM-ID
   12      18  PONTO                 .
   12      20  IDENTIFICADOR         CALCULADORA
   12      31  PONTO                 .
   13       8  PALAVRA_RESERVADA     DATA
   13      13  PALAVRA_RESERVADA     DIVISION
   13      21  PONTO                 .
   14       8  PALAVRA_RESERVADA     FILE
   14      13  PALAVRA_RESERVADA     SECTION
   14      20  PONTO                 .
   15       8  PALAVRA_RESERVADA     WORKING-STORAGE
   15      24  PALAVRA_RESERVADA     SECTION
   15      31  PONTO                 .
   16      12  NUMERO_DE_NIVEL       77
   16      15  IDENTIFICADOR         WKS-NUM-1
   16      35  PALAVRA_RESERVADA     PIC
   16      39  CADEIA_PICTURE        S9(05)V99
   16      52  PALAVRA_RESERVADA     VALUES
   16      59  NUMERO_INTEIRO        0
   16      60  PONTO                 .
   17      12  NUMERO_DE_NIVEL       77
   17      15  IDENTIFICADOR         WKS-NUM-2
   17      35  PALAVRA_RESERVADA     PIC
   17      39  CADEIA_PICTURE        S9(05)V9(02)
   17      52  PALAVRA_RESERVADA     VALUES
   17      59  NUMERO_INTEIRO        0
   17      60  PONTO                 .
   18      12  NUMERO_DE_NIVEL       77
   18      15  IDENTIFICADOR         WKS-RESULTADO
   18      35  PALAVRA_RESERVADA     PIC
   18      39  CADEIA_PICTURE        S9(10)V99
   18      52  PALAVRA_RESERVADA     VALUES
   18      59  CONSTANTE_FIGURATIVA  ZEROS
   18      64  PONTO                 .
   19      12  NUMERO_DE_NIVEL       77
   19      15  IDENTIFICADOR         WKS-RESTO
   19      35  PALAVRA_RESERVADA     PIC
   19      39  CADEIA_PICTURE        9(2)
   19      52  PALAVRA_RESERVADA     VALUES
   19      59  CONSTANTE_FIGURATIVA  ZEROS
   19      64  PONTO                 .
   20      12  NUMERO_DE_NIVEL       77
   20      15  IDENTIFICADOR         WKS-OPCAO
   20      35  PALAVRA_RESERVADA     PIC
   20      39  CADEIA_PICTURE        A(01)
   20      44  PONTO                 .
   21      12  NUMERO_DE_NIVEL       77
   21      15  IDENTIFICADOR         WKS-SAIR
   21      35  PALAVRA_RESERVADA     PIC
   21      39  CADEIA_PICTURE        9(1)
   21      52  PALAVRA_RESERVADA     VALUES
   21      59  CONSTANTE_FIGURATIVA  ZEROS
   21      64  PONTO                 .
   22      12  NUMERO_DE_NIVEL       77
   22      15  IDENTIFICADOR         WKS-RESULT-FORMAT
   22      35  PALAVRA_RESERVADA     PIC
   22      39  CADEIA_PICTURE        -ZZZZZZZZZ9.99
   22      53  PONTO                 .
   24       8  PALAVRA_RESERVADA     PROCEDURE
   24      18  PALAVRA_RESERVADA     DIVISION
   24      26  PONTO                 .
   25       8  IDENTIFICADOR         MAIN-PROCEDURE
   25      22  PONTO                 .
   27      12  PALAVRA_RESERVADA     PERFORM
   27      20  IDENTIFICADOR         00000-CALCULADORA
   27      38  PALAVRA_RESERVADA     UNTIL
   27      44  IDENTIFICADOR         WKS-SAIR
   27      53  OPERADOR_RELACIONAL   =
   27      55  NUMERO_INTEIRO        2
   27      56  PONTO                 .
   29      12  PALAVRA_RESERVADA     STOP
   29      17  PALAVRA_RESERVADA     RUN
   29      20  PONTO                 .
   31       8  IDENTIFICADOR         00000-CALCULADORA
   31      25  PONTO                 .
   32      12  PALAVRA_RESERVADA     DISPLAY
   32      20  LITERAL               "============ CALCULADORA ============= "
   32      61  PONTO                 .
   33      12  PALAVRA_RESERVADA     DISPLAY
   33      20  LITERAL               "1-. USAR CALCULADORA, 2-. SAIR"
   33      52  PONTO                 .
   34      12  PALAVRA_RESERVADA     ACCEPT
   34      19  IDENTIFICADOR         WKS-SAIR
   34      27  PONTO                 .
   36      12  PALAVRA_RESERVADA     IF
   36      15  IDENTIFICADOR         WKS-SAIR
   36      24  OPERADOR_RELACIONAL   =
   36      26  NUMERO_INTEIRO        1
   37      15  PALAVRA_RESERVADA     PERFORM
   37      23  IDENTIFICADOR         00001-PEDIR-DADOS
   38      15  PALAVRA_RESERVADA     PERFORM
   38      23  IDENTIFICADOR         00002-EXECUTAR-OPERACOES
   39      12  PALAVRA_RESERVADA     END-IF
   39      18  PONTO                 .
   41       8  IDENTIFICADOR         00001-PEDIR-DADOS
   41      25  PONTO                 .
   42      12  PALAVRA_RESERVADA     DISPLAY
   42      20  LITERAL               "OPERACAO: "
   42      32  PONTO                 .
   43      12  PALAVRA_RESERVADA     DISPLAY
   43      20  LITERAL               "(S)oma, s(U)btracao, (M)ultiplicacao e (D)ivisao"
   43      70  PONTO                 .
   44      12  PALAVRA_RESERVADA     DISPLAY
   44      20  LITERAL               "(P)otencia"
   44      32  PONTO                 .
   45      12  PALAVRA_RESERVADA     DISPLAY
   45      20  LITERAL               "==>"
   45      25  PONTO                 .
   46      12  PALAVRA_RESERVADA     ACCEPT
   46      19  IDENTIFICADOR         WKS-OPCAO
   46      28  PONTO                 .
   48      12  PALAVRA_RESERVADA     DISPLAY
   48      20  LITERAL               "VALOR 1:"
   48      30  PONTO                 .
   49      12  PALAVRA_RESERVADA     ACCEPT
   49      19  IDENTIFICADOR         WKS-NUM-1
   49      28  PONTO                 .
   51      12  PALAVRA_RESERVADA     DISPLAY
   51      20  LITERAL               "VALOR 2:"
   51      30  PONTO                 .
   52      12  PALAVRA_RESERVADA     ACCEPT
   52      19  IDENTIFICADOR         WKS-NUM-2
   52      28  PONTO                 .
   54       8  IDENTIFICADOR         00002-EXECUTAR-OPERACOES
   54      32  PONTO                 .
   55      12  PALAVRA_RESERVADA     MOVE
   55      17  PALAVRA_RESERVADA     FUNCTION
   55      26  IDENTIFICADOR         UPPER-CASE
   55      36  ABRE_PARENTESES       (
   55      37  IDENTIFICADOR         WKS-OPCAO
   55      46  FECHA_PARENTESES      )
   55      48  PALAVRA_RESERVADA     TO
   55      51  IDENTIFICADOR         WKS-OPCAO
   55      60  PONTO                 .
   56      12  PALAVRA_RESERVADA     IF
   56      15  IDENTIFICADOR         WKS-OPCAO
   56      25  OPERADOR_RELACIONAL   =
   56      27  LITERAL               "S"
   56      31  PALAVRA_RESERVADA     OR
   56      34  LITERAL               "s"
   57      15  PALAVRA_RESERVADA     ADD
   57      19  IDENTIFICADOR         WKS-NUM-1
   57      29  PALAVRA_RESERVADA     TO
   57      32  IDENTIFICADOR         WKS-NUM-2
   57      42  PALAVRA_RESERVADA     GIVING
   57      49  IDENTIFICADOR         WKS-RESULTADO
   58      12  PALAVRA_RESERVADA     ELSE
   59      12  PALAVRA_RESERVADA     IF
   59      15  IDENTIFICADOR         WKS-OPCAO
   59      25  OPERADOR_RELACIONAL   =
   59      27  LITERAL               "U"
   60      15  PALAVRA_RESERVADA     SUBTRACT
   60      24  IDENTIFICADOR         WKS-NUM-1
   60      34  PALAVRA_RESERVADA     FROM
   60      39  IDENTIFICADOR         WKS-NUM-2
   60      49  PALAVRA_RESERVADA     GIVING
   60      56  IDENTIFICADOR         WKS-RESULTADO
   61      12  PALAVRA_RESERVADA     ELSE
   62      12  PALAVRA_RESERVADA     IF
   62      15  IDENTIFICADOR         WKS-OPCAO
   62      25  OPERADOR_RELACIONAL   =
   62      27  LITERAL               "M"
   63      15  PALAVRA_RESERVADA     MULTIPLY
   63      24  IDENTIFICADOR         WKS-NUM-1
   63      34  PALAVRA_RESERVADA     BY
   63      37  IDENTIFICADOR         WKS-NUM-2
   63      47  PALAVRA_RESERVADA     GIVING
   63      54  IDENTIFICADOR         WKS-RESULTADO
   64      12  PALAVRA_RESERVADA     ELSE
   65      12  PALAVRA_RESERVADA     IF
   65      15  IDENTIFICADOR         WKS-OPCAO
   65      25  OPERADOR_RELACIONAL   =
   65      27  LITERAL               "D"
   66      15  PALAVRA_RESERVADA     DIVIDE
   66      22  IDENTIFICADOR         WKS-NUM-1
   66      32  PALAVRA_RESERVADA     BY
   66      35  IDENTIFICADOR         WKS-NUM-2
   66      45  PALAVRA_RESERVADA     GIVING
   66      52  IDENTIFICADOR         WKS-RESULTADO
   67      42  PALAVRA_RESERVADA     REMAINDER
   67      52  IDENTIFICADOR         WKS-RESTO
   68      12  PALAVRA_RESERVADA     ELSE
   69      12  PALAVRA_RESERVADA     IF
   69      15  IDENTIFICADOR         WKS-OPCAO
   69      25  OPERADOR_RELACIONAL   =
   69      27  LITERAL               "P"
   70      15  PALAVRA_RESERVADA     COMPUTE
   70      23  IDENTIFICADOR         WKS-RESULTADO
   70      37  OPERADOR_RELACIONAL   =
   70      39  IDENTIFICADOR         WKS-NUM-1
   70      49  OPERADOR_ARITMETICO   **
   70      52  IDENTIFICADOR         WKS-NUM-2
   71      12  PALAVRA_RESERVADA     ELSE
   72      15  PALAVRA_RESERVADA     DISPLAY
   72      23  LITERAL               "OPCAO INVALIDA"
   73      12  PALAVRA_RESERVADA     END-IF
   74      12  PALAVRA_RESERVADA     END-IF
   75      12  PALAVRA_RESERVADA     END-IF
   76      12  PALAVRA_RESERVADA     END-IF
   77      12  PALAVRA_RESERVADA     END-IF
   77      18  PONTO                 .
   78      12  PALAVRA_RESERVADA     IF
   78      15  IDENTIFICADOR         WKS-OPCAO
   78      25  OPERADOR_RELACIONAL   =
   78      27  LITERAL               "S"
   78      31  PALAVRA_RESERVADA     OR
   78      34  LITERAL               "U"
   78      38  PALAVRA_RESERVADA     OR
   78      41  LITERAL               "M"
   78      45  PALAVRA_RESERVADA     OR
   78      48  LITERAL               "D"
   78      52  PALAVRA_RESERVADA     OR
   78      55  LITERAL               "P"
   79      16  PALAVRA_RESERVADA     MOVE
   79      21  IDENTIFICADOR         WKS-RESULTADO
   79      35  PALAVRA_RESERVADA     TO
   79      38  IDENTIFICADOR         WKS-RESULT-FORMAT
   80      15  PALAVRA_RESERVADA     DISPLAY
   80      23  LITERAL               "Resultado: "
   80      37  IDENTIFICADOR         WKS-RESULT-FORMAT
   81      12  PALAVRA_RESERVADA     END-IF
   81      18  PONTO                 .
   83       8  PALAVRA_RESERVADA     END
   83      12  PALAVRA_RESERVADA     PROGRAM
   83      20  IDENTIFICADOR         CALCULADORA
   83      31  PONTO                 .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - CALCULADORA.
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog003_calculadora -std=default prog003_calculad
   10       7  COMENTARIO  ******************************************************************

Avisos de formato
  [W] Linha 16, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 17, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 18, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 19, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 20, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 21, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).
  [W] Linha 22, coluna 12: Cabeçalho ou nível COBOL deve começar na área A (colunas 8-11).

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  ABRE_PARENTESES: 1
  CADEIA_PICTURE: 7
  CONSTANTE_FIGURATIVA: 3
  FECHA_PARENTESES: 1
  IDENTIFICADOR: 50
  LITERAL: 21
  NUMERO_DE_NIVEL: 7
  NUMERO_INTEIRO: 4
  OPERADOR_ARITMETICO: 1
  OPERADOR_RELACIONAL: 9
  PALAVRA_RESERVADA: 88
  PONTO: 37
  Tokens: 229
  Comentários: 10
  Diretivas: 0
  Erros: 0
  Avisos: 7
```

### prog004_folha_pgto.cob

```text
Analisador léxico COBOL
Arquivo: prog004_folha_pgto.cob
Formato: fixo (detecção automática)
Linhas: 77

Linha  Coluna  Token                 Lexema
-----  ------  --------------------  --------------------------------------------------
   11       8  PALAVRA_RESERVADA     IDENTIFICATION
   11      23  PALAVRA_RESERVADA     DIVISION
   11      31  PONTO                 .
   12       8  PALAVRA_RESERVADA     PROGRAM-ID
   12      18  PONTO                 .
   12      20  IDENTIFICADOR         FOLHA-PGTO
   12      30  PONTO                 .
   13       8  PALAVRA_RESERVADA     DATA
   13      13  PALAVRA_RESERVADA     DIVISION
   13      21  PONTO                 .
   14       8  PALAVRA_RESERVADA     FILE
   14      13  PALAVRA_RESERVADA     SECTION
   14      20  PONTO                 .
   15       8  PALAVRA_RESERVADA     WORKING-STORAGE
   15      24  PALAVRA_RESERVADA     SECTION
   15      31  PONTO                 .
   17       8  NUMERO_DE_NIVEL       01
   17      11  IDENTIFICADOR         TAB-TRABALHADOR
   17      26  PONTO                 .
   18      11  NUMERO_DE_NIVEL       02
   18      14  IDENTIFICADOR         TRABALHADOR
   18      26  PALAVRA_RESERVADA     OCCURS
   18      33  NUMERO_INTEIRO        3
   18      35  PALAVRA_RESERVADA     TIMES
   18      41  PALAVRA_RESERVADA     INDEXED
   18      49  PALAVRA_RESERVADA     BY
   18      52  IDENTIFICADOR         TID
   18      55  PONTO                 .
   19      14  NUMERO_DE_NIVEL       03
   19      17  IDENTIFICADOR         NOME
   19      33  PALAVRA_RESERVADA     PIC
   19      37  CADEIA_PICTURE        X(5)
   19      41  PONTO                 .
   20      14  NUMERO_DE_NIVEL       03
   20      17  IDENTIFICADOR         SALARIO
   20      33  PALAVRA_RESERVADA     PIC
   20      37  CADEIA_PICTURE        9(5)V99
   20      44  PONTO                 .
   21      14  NUMERO_DE_NIVEL       03
   21      17  IDENTIFICADOR         DPTO
   21      33  PALAVRA_RESERVADA     PIC
   21      37  CADEIA_PICTURE        X(2)
   21      42  PALAVRA_RESERVADA     VALUES
   21      49  CONSTANTE_FIGURATIVA  SPACES
   21      56  PALAVRA_RESERVADA     OCCURS
   21      63  NUMERO_INTEIRO        2
   21      65  PALAVRA_RESERVADA     TIMES
   21      70  PONTO                 .
   23       8  NUMERO_DE_NIVEL       77
   23      11  IDENTIFICADOR         IDX
   23      15  PALAVRA_RESERVADA     PIC
   23      19  CADEIA_PICTURE        9(1)
   23      23  PONTO                 .
   25       8  PALAVRA_RESERVADA     PROCEDURE
   25      18  PALAVRA_RESERVADA     DIVISION
   25      26  PONTO                 .
   26       8  IDENTIFICADOR         MAIN-PROCEDURE
   26      22  PONTO                 .
   27      13  PALAVRA_RESERVADA     MOVE
   27      18  LITERAL               "JOSEA1111111A1A4MARIA2222222A2  FABIO3333333A2A3"
   27      69  PALAVRA_RESERVADA     TO
   27      72  IDENTIFICADOR         TAB-TRABALHADOR
   28      22  PONTO                 .
   29      13  PALAVRA_RESERVADA     DISPLAY
   29      21  LITERAL               " "
   29      24  PONTO                 .
   30      13  PALAVRA_RESERVADA     DISPLAY
   30      21  LITERAL               "====TAB-TRABALHADOR===="
   30      46  PONTO                 .
   31      13  PALAVRA_RESERVADA     DISPLAY
   31      21  LITERAL               "INITIAL VALUE"
   31      36  PONTO                 .
   32      13  PALAVRA_RESERVADA     DISPLAY
   32      21  IDENTIFICADOR         TAB-TRABALHADOR
   32      36  PONTO                 .
   34      13  PALAVRA_RESERVADA     MOVE
   34      18  NUMERO_INTEIRO        1
   34      20  PALAVRA_RESERVADA     TO
   34      23  IDENTIFICADOR         IDX
   34      26  PONTO                 .
   35      13  PALAVRA_RESERVADA     DISPLAY
   35      21  LITERAL               " "
   35      24  PONTO                 .
   36      13  PALAVRA_RESERVADA     DISPLAY
   36      21  LITERAL               "====00001-DISPLAY-TRABALHADOR===="
   36      56  PONTO                 .
   37      13  PALAVRA_RESERVADA     PERFORM
   37      21  IDENTIFICADOR         00001-DISPLAY-TRABALHADOR
   37      47  PALAVRA_RESERVADA     UNTIL
   37      53  IDENTIFICADOR         IDX
   37      57  OPERADOR_RELACIONAL   >
   37      59  NUMERO_INTEIRO        3
   37      60  PONTO                 .
   39      13  PALAVRA_RESERVADA     DISPLAY
   39      21  LITERAL               " "
   39      24  PONTO                 .
   40      13  PALAVRA_RESERVADA     DISPLAY
   40      21  LITERAL               "====00002-DISPLAY-BY-SEARCH===="
   40      54  PONTO                 .
   41      13  PALAVRA_RESERVADA     PERFORM
   41      21  IDENTIFICADOR         00002-DISPLAY-BY-SEARCH
   41      44  PONTO                 .
   43      13  PALAVRA_RESERVADA     DISPLAY
   43      21  LITERAL               " "
   43      24  PONTO                 .
   44      13  PALAVRA_RESERVADA     DISPLAY
   44      21  LITERAL               "====00003-REMOVE-TRABALHADOR===="
   44      55  PONTO                 .
   45      13  PALAVRA_RESERVADA     PERFORM
   45      21  IDENTIFICADOR         00003-REMOVE-TRABALHADOR
   45      45  PONTO                 .
   47      12  PALAVRA_RESERVADA     STOP
   47      17  PALAVRA_RESERVADA     RUN
   47      20  PONTO                 .
   49       8  IDENTIFICADOR         00001-DISPLAY-TRABALHADOR
   49      33  PONTO                 .
   50      12  PALAVRA_RESERVADA     DISPLAY
   50      20  LITERAL               " "
   50      23  PONTO                 .
   52      12  PALAVRA_RESERVADA     DISPLAY
   52      20  LITERAL               "IDX="
   52      27  IDENTIFICADOR         IDX
   52      30  PONTO                 .
   53      12  PALAVRA_RESERVADA     DISPLAY
   53      20  LITERAL               "TRABALHADOR(IDX)="
   53      40  IDENTIFICADOR         TRABALHADOR
   53      51  ABRE_PARENTESES       (
   53      52  IDENTIFICADOR         IDX
   53      55  FECHA_PARENTESES      )
   53      56  PONTO                 .
   54      12  PALAVRA_RESERVADA     DISPLAY
   54      20  LITERAL               "NOME(IDX)="
   54      33  IDENTIFICADOR         NOME
   54      37  ABRE_PARENTESES       (
   54      38  IDENTIFICADOR         IDX
   54      41  FECHA_PARENTESES      )
   54      42  PONTO                 .
   55      12  PALAVRA_RESERVADA     DISPLAY
   55      20  LITERAL               "SALARIO(IDX)="
   55      36  IDENTIFICADOR         SALARIO
   55      43  ABRE_PARENTESES       (
   55      44  IDENTIFICADOR         IDX
   55      47  FECHA_PARENTESES      )
   55      48  PONTO                 .
   56      12  PALAVRA_RESERVADA     DISPLAY
   56      20  LITERAL               "DPTO(IDX,1)="
   56      35  IDENTIFICADOR         DPTO
   56      39  ABRE_PARENTESES       (
   56      40  IDENTIFICADOR         IDX
   56      43  VIRGULA               ,
   56      44  NUMERO_INTEIRO        1
   56      45  FECHA_PARENTESES      )
   56      46  PONTO                 .
   57      12  PALAVRA_RESERVADA     DISPLAY
   57      20  LITERAL               "DPTO(IDX,2)="
   57      35  IDENTIFICADOR         DPTO
   57      39  ABRE_PARENTESES       (
   57      40  IDENTIFICADOR         IDX
   57      43  VIRGULA               ,
   57      44  NUMERO_INTEIRO        2
   57      45  FECHA_PARENTESES      )
   57      46  PONTO                 .
   58      12  PALAVRA_RESERVADA     ADD
   58      16  NUMERO_INTEIRO        1
   58      18  PALAVRA_RESERVADA     TO
   58      21  IDENTIFICADOR         IDX
   58      24  PONTO                 .
   60       8  IDENTIFICADOR         00002-DISPLAY-BY-SEARCH
   60      31  PONTO                 .
   62      12  PALAVRA_RESERVADA     SET
   62      16  IDENTIFICADOR         TID
   62      20  PALAVRA_RESERVADA     TO
   62      23  NUMERO_INTEIRO        1
   62      24  PONTO                 .
   63      12  PALAVRA_RESERVADA     SEARCH
   63      19  IDENTIFICADOR         TRABALHADOR
   64      15  PALAVRA_RESERVADA     AT
   64      18  PALAVRA_RESERVADA     END
   64      22  PALAVRA_RESERVADA     DISPLAY
   64      30  LITERAL               "TRABALHADOR NOT FOUND"
   65      15  PALAVRA_RESERVADA     WHEN
   65      20  IDENTIFICADOR         NOME
   65      24  ABRE_PARENTESES       (
   65      25  IDENTIFICADOR         TID
   65      28  FECHA_PARENTESES      )
   65      30  OPERADOR_RELACIONAL   =
   65      32  LITERAL               "MARIA"
   66      18  PALAVRA_RESERVADA     DISPLAY
   66      26  LITERAL               "'WHEN NOME(TID) = MARIA'"
   67      18  PALAVRA_RESERVADA     DISPLAY
   67      26  LITERAL               "TID="
   67      33  IDENTIFICADOR         TID
   68      18  PALAVRA_RESERVADA     DISPLAY
   68      26  LITERAL               "TRABALHADOR(TID)="
   68      46  IDENTIFICADOR         TRABALHADOR
   68      57  ABRE_PARENTESES       (
   68      58  IDENTIFICADOR         TID
   68      61  FECHA_PARENTESES      )
   69      12  PALAVRA_RESERVADA     END-SEARCH
   69      22  PONTO                 .
   72       8  IDENTIFICADOR         00003-REMOVE-TRABALHADOR
   72      32  PONTO                 .
   73      12  PALAVRA_RESERVADA     SET
   73      16  IDENTIFICADOR         TID
   73      20  PALAVRA_RESERVADA     TO
   73      23  NUMERO_INTEIRO        2
   73      24  PONTO                 .
   74      12  PALAVRA_RESERVADA     MOVE
   74      17  CONSTANTE_FIGURATIVA  LOW-VALUES
   74      28  PALAVRA_RESERVADA     TO
   74      31  IDENTIFICADOR         TRABALHADOR
   74      42  ABRE_PARENTESES       (
   74      43  IDENTIFICADOR         TID
   74      46  FECHA_PARENTESES      )
   75      12  PALAVRA_RESERVADA     DISPLAY
   75      20  IDENTIFICADOR         TAB-TRABALHADOR
   75      35  PONTO                 .
   77       8  PALAVRA_RESERVADA     END
   77      12  PALAVRA_RESERVADA     PROGRAM
   77      20  IDENTIFICADOR         FOLHA-PGTO
   77      30  PONTO                 .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - TABLES 1 AND 2 DIMENSIONS
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog004_folha_pgto -std=default prog004_folha_pgt
   10       7  COMENTARIO  ******************************************************************

Avisos de formato
  [W] Linha 18, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  ABRE_PARENTESES: 8
  CADEIA_PICTURE: 4
  CONSTANTE_FIGURATIVA: 2
  FECHA_PARENTESES: 8
  IDENTIFICADOR: 43
  LITERAL: 22
  NUMERO_DE_NIVEL: 6
  NUMERO_INTEIRO: 9
  OPERADOR_RELACIONAL: 2
  PALAVRA_RESERVADA: 69
  PONTO: 46
  VIRGULA: 2
  Tokens: 221
  Comentários: 10
  Diretivas: 0
  Erros: 0
  Avisos: 1
```

### prog005_strings.cob

```text
Analisador léxico COBOL
Arquivo: prog005_strings.cob
Formato: fixo (detecção automática)
Linhas: 75

Linha  Coluna  Token              Lexema
-----  ------  -----------------  ----------------------------------
   11       8  PALAVRA_RESERVADA  IDENTIFICATION
   11      23  PALAVRA_RESERVADA  DIVISION
   11      31  PONTO              .
   12       8  PALAVRA_RESERVADA  PROGRAM-ID
   12      18  PONTO              .
   12      20  IDENTIFICADOR      PROG008_STRING
   12      34  PONTO              .
   13       8  PALAVRA_RESERVADA  DATA
   13      13  PALAVRA_RESERVADA  DIVISION
   13      21  PONTO              .
   14       8  PALAVRA_RESERVADA  FILE
   14      13  PALAVRA_RESERVADA  SECTION
   14      20  PONTO              .
   15       8  PALAVRA_RESERVADA  WORKING-STORAGE
   15      24  PALAVRA_RESERVADA  SECTION
   15      31  PONTO              .
   17       8  NUMERO_DE_NIVEL    77
   17      11  IDENTIFICADOR      SAUX
   17      27  PALAVRA_RESERVADA  PIC
   17      31  CADEIA_PICTURE     X(15)
   17      36  PONTO              .
   18       8  NUMERO_DE_NIVEL    77
   18      11  IDENTIFICADOR      CONT
   18      27  PALAVRA_RESERVADA  PIC
   18      31  CADEIA_PICTURE     9(2)
   18      35  PONTO              .
   19       8  NUMERO_DE_NIVEL    77
   19      11  IDENTIFICADOR      YESNO
   19      27  PALAVRA_RESERVADA  PIC
   19      31  CADEIA_PICTURE     9
   19      32  PONTO              .
   21       8  NUMERO_DE_NIVEL    77
   21      11  IDENTIFICADOR      IDX
   21      15  PALAVRA_RESERVADA  PIC
   21      19  CADEIA_PICTURE     9(1)
   21      23  PONTO              .
   23       8  PALAVRA_RESERVADA  PROCEDURE
   23      18  PALAVRA_RESERVADA  DIVISION
   23      26  PONTO              .
   24       8  IDENTIFICADOR      MAIN-PROCEDURE
   24      22  PONTO              .
   25      13  PALAVRA_RESERVADA  MOVE
   25      18  LITERAL            "HELLO WORLD 123!!"
   25      38  PALAVRA_RESERVADA  TO
   25      41  IDENTIFICADOR      SAUX
   25      45  PONTO              .
   27      13  PALAVRA_RESERVADA  DISPLAY
   27      21  LITERAL            " "
   27      24  PONTO              .
   28      13  PALAVRA_RESERVADA  DISPLAY
   28      21  LITERAL            "==== EXEMPLO 1 ===="
   28      42  PONTO              .
   29      13  PALAVRA_RESERVADA  DISPLAY
   29      21  LITERAL            "SAUX='"
   29      30  IDENTIFICADOR      SAUX
   29      35  LITERAL            "'"
   29      38  PONTO              .
   31      13  PALAVRA_RESERVADA  MOVE
   31      18  NUMERO_INTEIRO     0
   31      20  PALAVRA_RESERVADA  TO
   31      23  IDENTIFICADOR      CONT
   31      27  PONTO              .
   32      13  PALAVRA_RESERVADA  INSPECT
   32      21  IDENTIFICADOR      SAUX
   32      26  PALAVRA_RESERVADA  TALLYING
   32      35  IDENTIFICADOR      CONT
   32      40  PALAVRA_RESERVADA  FOR
   32      44  PALAVRA_RESERVADA  CHARACTERS
   32      54  PONTO              .
   33      13  PALAVRA_RESERVADA  DISPLAY
   33      21  LITERAL            "CONT="
   33      29  IDENTIFICADOR      CONT
   33      34  LITERAL            " - FOR CHARACTERS"
   33      53  PONTO              .
   35      13  PALAVRA_RESERVADA  MOVE
   35      18  NUMERO_INTEIRO     0
   35      20  PALAVRA_RESERVADA  TO
   35      23  IDENTIFICADOR      CONT
   35      27  PONTO              .
   36      13  PALAVRA_RESERVADA  INSPECT
   36      21  IDENTIFICADOR      SAUX
   36      26  PALAVRA_RESERVADA  TALLYING
   36      35  IDENTIFICADOR      CONT
   36      40  PALAVRA_RESERVADA  FOR
   36      44  PALAVRA_RESERVADA  ALL
   36      48  LITERAL            "L"
   36      51  PONTO              .
   37      13  PALAVRA_RESERVADA  DISPLAY
   37      21  LITERAL            "CONT="
   37      29  IDENTIFICADOR      CONT
   37      34  LITERAL            " - FOR ALL 'L'"
   37      50  PONTO              .
   39      13  PALAVRA_RESERVADA  MOVE
   39      18  NUMERO_INTEIRO     0
   39      20  PALAVRA_RESERVADA  TO
   39      23  IDENTIFICADOR      CONT
   39      27  PONTO              .
   40      13  PALAVRA_RESERVADA  INSPECT
   40      21  IDENTIFICADOR      SAUX
   40      26  PALAVRA_RESERVADA  TALLYING
   40      35  IDENTIFICADOR      CONT
   41      21  PALAVRA_RESERVADA  FOR
   41      25  PALAVRA_RESERVADA  CHARACTERS
   41      36  PALAVRA_RESERVADA  BEFORE
   41      43  PALAVRA_RESERVADA  INITIAL
   41      51  LITERAL            " "
   41      54  PONTO              .
   42      13  PALAVRA_RESERVADA  DISPLAY
   42      21  LITERAL            "CONT="
   42      29  IDENTIFICADOR      CONT
   42      34  LITERAL            " - BEFORE INITIAL ' '"
   42      57  PONTO              .
   44      13  PALAVRA_RESERVADA  MOVE
   44      18  NUMERO_INTEIRO     0
   44      20  PALAVRA_RESERVADA  TO
   44      23  IDENTIFICADOR      CONT
   44      27  PONTO              .
   45      13  PALAVRA_RESERVADA  INSPECT
   45      21  IDENTIFICADOR      SAUX
   45      26  PALAVRA_RESERVADA  TALLYING
   45      35  IDENTIFICADOR      CONT
   46      21  PALAVRA_RESERVADA  FOR
   46      25  PALAVRA_RESERVADA  CHARACTERS
   46      36  PALAVRA_RESERVADA  AFTER
   46      42  PALAVRA_RESERVADA  INITIAL
   46      50  LITERAL            " "
   46      53  PONTO              .
   47      13  PALAVRA_RESERVADA  DISPLAY
   47      21  LITERAL            "CONT="
   47      29  IDENTIFICADOR      CONT
   47      34  LITERAL            " - AFTER INITIAL ' '"
   47      56  PONTO              .
   49      13  PALAVRA_RESERVADA  MOVE
   49      18  NUMERO_INTEIRO     0
   49      20  PALAVRA_RESERVADA  TO
   49      23  IDENTIFICADOR      YESNO
   49      28  PONTO              .
   50      13  PALAVRA_RESERVADA  INSPECT
   50      21  IDENTIFICADOR      SAUX
   50      26  PALAVRA_RESERVADA  TALLYING
   50      35  IDENTIFICADOR      YESNO
   51      21  PALAVRA_RESERVADA  FOR
   51      25  PALAVRA_RESERVADA  LEADING
   51      33  LITERAL            "H"
   51      36  PONTO              .
   52      13  PALAVRA_RESERVADA  DISPLAY
   52      21  LITERAL            "YESNO="
   52      30  IDENTIFICADOR      YESNO
   52      36  LITERAL            " - FOR LEADING 'H' 0=N / 1=Y"
   52      66  PONTO              .
   54      13  PALAVRA_RESERVADA  INSPECT
   54      21  IDENTIFICADOR      SAUX
   54      26  PALAVRA_RESERVADA  REPLACING
   54      36  PALAVRA_RESERVADA  FIRST
   54      42  LITERAL            "E"
   54      46  PALAVRA_RESERVADA  BY
   54      49  LITERAL            "A"
   54      52  PONTO              .
   55      13  PALAVRA_RESERVADA  DISPLAY
   55      21  LITERAL            "SAUX='"
   55      30  IDENTIFICADOR      SAUX
   55      35  LITERAL            "' - REPLACING FIRST 'E' BY 'A'"
   55      67  PONTO              .
   57      13  PALAVRA_RESERVADA  INSPECT
   57      21  IDENTIFICADOR      SAUX
   57      26  PALAVRA_RESERVADA  REPLACING
   57      36  PALAVRA_RESERVADA  ALL
   57      40  LITERAL            "LLO"
   57      46  PALAVRA_RESERVADA  BY
   57      49  LITERAL            "PPY"
   57      54  PONTO              .
   58      13  PALAVRA_RESERVADA  DISPLAY
   58      21  LITERAL            "SAUX='"
   58      30  IDENTIFICADOR      SAUX
   58      35  LITERAL            "' - REPLACING ALL 'LLO' BY 'PPY'"
   58      69  PONTO              .
   60      13  PALAVRA_RESERVADA  MOVE
   60      18  LITERAL            " HOLA-DAY"
   60      30  PALAVRA_RESERVADA  TO
   60      33  IDENTIFICADOR      SAUX
   60      37  PONTO              .
   61      13  PALAVRA_RESERVADA  INSPECT
   61      21  IDENTIFICADOR      SAUX
   61      26  PALAVRA_RESERVADA  REPLACING
   61      36  PALAVRA_RESERVADA  ALL
   61      40  LITERAL            "HOLA"
   61      47  PALAVRA_RESERVADA  BY
   61      50  LITERAL            "GOOD"
   62      21  PALAVRA_RESERVADA  AFTER
   62      27  PALAVRA_RESERVADA  INITIAL
   62      35  LITERAL            " "
   62      39  PALAVRA_RESERVADA  BEFORE
   62      46  PALAVRA_RESERVADA  INITIAL
   62      54  LITERAL            "-"
   62      57  PONTO              .
   63      13  PALAVRA_RESERVADA  DISPLAY
   63      21  LITERAL            "SAUX='"
   63      30  IDENTIFICADOR      SAUX
   63      35  LITERAL            "' - HOLA-DAY TO GOOD-DAY'"
   63      62  PONTO              .
   65      13  PALAVRA_RESERVADA  MOVE
   65      18  LITERAL            "HELLO WORLD"
   65      32  PALAVRA_RESERVADA  TO
   65      35  IDENTIFICADOR      SAUX
   65      39  PONTO              .
   66      13  PALAVRA_RESERVADA  INSPECT
   66      21  IDENTIFICADOR      SAUX
   66      26  PALAVRA_RESERVADA  CONVERTING
   66      37  LITERAL            "ABCDEFGHIJKLMNOPQRSTUVWXZ"
   67      17  PALAVRA_RESERVADA  TO
   67      20  LITERAL            "abcdefghijklmnopqrstuvwxz"
   67      47  PONTO              .
   68      13  PALAVRA_RESERVADA  DISPLAY
   68      21  LITERAL            "SAUX='"
   68      30  IDENTIFICADOR      SAUX
   68      35  LITERAL            "' - CONVERTING'"
   68      52  PONTO              .
   70      13  PALAVRA_RESERVADA  INSPECT
   70      21  IDENTIFICADOR      SAUX
   70      26  PALAVRA_RESERVADA  REPLACING
   70      36  PALAVRA_RESERVADA  CHARACTERS
   70      47  PALAVRA_RESERVADA  BY
   70      50  LITERAL            "F"
   70      53  PONTO              .
   71      13  PALAVRA_RESERVADA  DISPLAY
   71      21  LITERAL            "SAUX='"
   71      30  IDENTIFICADOR      SAUX
   71      35  LITERAL            "' - REPLACING "
   71      51  PONTO              .
   73      12  PALAVRA_RESERVADA  STOP
   73      17  PALAVRA_RESERVADA  RUN
   73      20  PONTO              .
   75       8  PALAVRA_RESERVADA  END
   75      12  PALAVRA_RESERVADA  PROGRAM
   75      20  IDENTIFICADOR      PROG008_STRING
   75      34  PONTO              .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - Strings
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog005_strings -std=default prog005_strings.cob
   10       7  COMENTARIO  ******************************************************************

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  CADEIA_PICTURE: 4
  IDENTIFICADOR: 41
  LITERAL: 42
  NUMERO_DE_NIVEL: 4
  NUMERO_INTEIRO: 5
  PALAVRA_RESERVADA: 95
  PONTO: 45
  Tokens: 236
  Comentários: 10
  Diretivas: 0
  Erros: 0
  Avisos: 0
```

### prog006_files.cob

```text
Analisador léxico COBOL
Arquivo: prog006_files.cob
Formato: fixo (detecção automática)
Linhas: 76

Linha  Coluna  Token                 Lexema
-----  ------  --------------------  --------------------------------------------------
   11       8  PALAVRA_RESERVADA     IDENTIFICATION
   11      23  PALAVRA_RESERVADA     DIVISION
   11      31  PONTO                 .
   12       8  PALAVRA_RESERVADA     PROGRAM-ID
   12      18  PONTO                 .
   12      20  IDENTIFICADOR         PROG006_FILES
   12      33  PONTO                 .
   13       8  PALAVRA_RESERVADA     ENVIRONMENT
   13      20  PALAVRA_RESERVADA     DIVISION
   13      28  PONTO                 .
   14       8  PALAVRA_RESERVADA     INPUT-OUTPUT
   14      21  PALAVRA_RESERVADA     SECTION
   14      28  PONTO                 .
   16       8  PALAVRA_RESERVADA     FILE-CONTROL
   16      20  PONTO                 .
   17      12  PALAVRA_RESERVADA     SELECT
   17      19  IDENTIFICADOR         MY-FILE
   17      27  PALAVRA_RESERVADA     ASSIGN
   17      34  PALAVRA_RESERVADA     TO
   17      37  LITERAL               "DADOS.TXT"
   17      48  PONTO                 .
   19       8  PALAVRA_RESERVADA     DATA
   19      13  PALAVRA_RESERVADA     DIVISION
   19      21  PONTO                 .
   20       8  PALAVRA_RESERVADA     FILE
   20      13  PALAVRA_RESERVADA     SECTION
   20      20  PONTO                 .
   23       8  PALAVRA_RESERVADA     FD
   23      11  IDENTIFICADOR         MY-FILE
   23      18  PONTO                 .
   24       8  NUMERO_DE_NIVEL       01
   24      11  IDENTIFICADOR         RC-TRABALHADOR
   24      25  PONTO                 .
   25      11  NUMERO_DE_NIVEL       02
   25      14  IDENTIFICADOR         RC-TID
   25      33  PALAVRA_RESERVADA     PIC
   25      37  CADEIA_PICTURE        9(5)
   25      41  PONTO                 .
   26      11  NUMERO_DE_NIVEL       02
   26      14  IDENTIFICADOR         RC-NOME
   26      33  PALAVRA_RESERVADA     PIC
   26      37  CADEIA_PICTURE        X(10)
   26      42  PONTO                 .
   27      11  NUMERO_DE_NIVEL       02
   27      14  IDENTIFICADOR         RC-SALARIO
   27      33  PALAVRA_RESERVADA     PIC
   27      37  CADEIA_PICTURE        9(10)V99
   27      45  PONTO                 .
   28      11  NUMERO_DE_NIVEL       02
   28      14  IDENTIFICADOR         RC-DPTO-1
   28      33  PALAVRA_RESERVADA     PIC
   28      37  CADEIA_PICTURE        X(2)
   28      41  PONTO                 .
   29      11  NUMERO_DE_NIVEL       02
   29      14  IDENTIFICADOR         RC-DPTO-2
   29      33  PALAVRA_RESERVADA     PIC
   29      37  CADEIA_PICTURE        X(2)
   29      41  PONTO                 .
   31       8  PALAVRA_RESERVADA     WORKING-STORAGE
   31      24  PALAVRA_RESERVADA     SECTION
   31      31  PONTO                 .
   33       8  NUMERO_DE_NIVEL       01
   33      11  IDENTIFICADOR         TAB-TRABALHADOR
   33      26  PONTO                 .
   34      11  NUMERO_DE_NIVEL       02
   34      14  IDENTIFICADOR         TRABALHADOR
   34      26  PALAVRA_RESERVADA     OCCURS
   34      33  NUMERO_INTEIRO        3
   34      35  PALAVRA_RESERVADA     TIMES
   34      41  PALAVRA_RESERVADA     INDEXED
   34      49  PALAVRA_RESERVADA     BY
   34      52  IDENTIFICADOR         TID
   34      55  PONTO                 .
   35      14  NUMERO_DE_NIVEL       03
   35      17  IDENTIFICADOR         NOME
   35      33  PALAVRA_RESERVADA     PIC
   35      37  CADEIA_PICTURE        X(5)
   35      41  PONTO                 .
   36      14  NUMERO_DE_NIVEL       03
   36      17  IDENTIFICADOR         SALARIO
   36      33  PALAVRA_RESERVADA     PIC
   36      37  CADEIA_PICTURE        9(5)V99
   36      44  PONTO                 .
   37      14  NUMERO_DE_NIVEL       03
   37      17  IDENTIFICADOR         DPTO
   37      33  PALAVRA_RESERVADA     PIC
   37      37  CADEIA_PICTURE        X(2)
   37      42  PALAVRA_RESERVADA     VALUES
   37      49  CONSTANTE_FIGURATIVA  SPACES
   37      56  PALAVRA_RESERVADA     OCCURS
   37      63  NUMERO_INTEIRO        2
   37      65  PALAVRA_RESERVADA     TIMES
   37      70  PONTO                 .
   39       8  NUMERO_DE_NIVEL       77
   39      11  IDENTIFICADOR         SAUX
   39      27  PALAVRA_RESERVADA     PIC
   39      31  CADEIA_PICTURE        X(15)
   39      36  PONTO                 .
   40       8  NUMERO_DE_NIVEL       77
   40      11  IDENTIFICADOR         CONT
   40      27  PALAVRA_RESERVADA     PIC
   40      31  CADEIA_PICTURE        9(2)
   40      35  PONTO                 .
   41       8  NUMERO_DE_NIVEL       77
   41      11  IDENTIFICADOR         YESNO
   41      27  PALAVRA_RESERVADA     PIC
   41      31  CADEIA_PICTURE        9
   41      32  PONTO                 .
   43       8  NUMERO_DE_NIVEL       77
   43      11  IDENTIFICADOR         IDX
   43      15  PALAVRA_RESERVADA     PIC
   43      19  CADEIA_PICTURE        9(1)
   43      23  PONTO                 .
   45       8  PALAVRA_RESERVADA     PROCEDURE
   45      18  PALAVRA_RESERVADA     DIVISION
   45      26  PONTO                 .
   46       8  IDENTIFICADOR         MAIN-PROCEDURE
   46      22  PONTO                 .
   48      13  PALAVRA_RESERVADA     MOVE
   48      18  LITERAL               "JOSEA1111111A1A4MARIA2222222A2  FABIO3333333A2A3"
   48      69  PALAVRA_RESERVADA     TO
   48      72  IDENTIFICADOR         TAB-TRABALHADOR
   49      22  PONTO                 .
   51      13  PALAVRA_RESERVADA     DISPLAY
   51      21  LITERAL               " "
   51      24  PONTO                 .
   52      13  PALAVRA_RESERVADA     DISPLAY
   52      21  LITERAL               "====00001-DISPLAY-TRABALHADOR===="
   52      56  PONTO                 .
   53      13  PALAVRA_RESERVADA     OPEN
   53      18  PALAVRA_RESERVADA     OUTPUT
   53      25  IDENTIFICADOR         MY-FILE
   53      32  PONTO                 .
   55      13  PALAVRA_RESERVADA     MOVE
   55      18  NUMERO_INTEIRO        1
   55      20  PALAVRA_RESERVADA     TO
   55      23  IDENTIFICADOR         IDX
   55      26  PONTO                 .
   56      13  PALAVRA_RESERVADA     PERFORM
   56      21  IDENTIFICADOR         00001-WRITE-TO-FILE
   56      41  PALAVRA_RESERVADA     UNTIL
   56      47  IDENTIFICADOR         IDX
   56      51  OPERADOR_RELACIONAL   >
   56      53  NUMERO_INTEIRO        3
   56      54  PONTO                 .
   58      13  PALAVRA_RESERVADA     CLOSE
   58      19  IDENTIFICADOR         MY-FILE
   58      26  PONTO                 .
   60      12  PALAVRA_RESERVADA     STOP
   60      17  PALAVRA_RESERVADA     RUN
   60      20  PONTO                 .
   62       8  IDENTIFICADOR         00001-WRITE-TO-FILE
   62      27  PONTO                 .
   63      12  PALAVRA_RESERVADA     DISPLAY
   63      20  LITERAL               " "
   63      23  PONTO                 .
   65      12  PALAVRA_RESERVADA     MOVE
   65      17  CONSTANTE_FIGURATIVA  LOW-VALUES
   65      28  PALAVRA_RESERVADA     TO
   65      31  IDENTIFICADOR         RC-TRABALHADOR
   65      45  PONTO                 .
   66      12  PALAVRA_RESERVADA     DISPLAY
   66      20  LITERAL               "IDX="
   66      27  IDENTIFICADOR         IDX
   66      30  PONTO                 .
   67      12  PALAVRA_RESERVADA     DISPLAY
   67      20  LITERAL               "TRABALHADOR(IDX)="
   67      40  IDENTIFICADOR         TRABALHADOR
   67      51  ABRE_PARENTESES       (
   67      52  IDENTIFICADOR         IDX
   67      55  FECHA_PARENTESES      )
   67      56  PONTO                 .
   68      12  PALAVRA_RESERVADA     MOVE
   68      17  IDENTIFICADOR         IDX
   68      21  PALAVRA_RESERVADA     TO
   68      24  IDENTIFICADOR         RC-TID
   68      30  PONTO                 .
   69      12  PALAVRA_RESERVADA     MOVE
   69      17  IDENTIFICADOR         NOME
   69      21  ABRE_PARENTESES       (
   69      22  IDENTIFICADOR         IDX
   69      25  FECHA_PARENTESES      )
   69      27  PALAVRA_RESERVADA     TO
   69      30  IDENTIFICADOR         RC-NOME
   69      37  PONTO                 .
   70      12  PALAVRA_RESERVADA     MOVE
   70      17  IDENTIFICADOR         SALARIO
   70      24  ABRE_PARENTESES       (
   70      25  IDENTIFICADOR         IDX
   70      28  FECHA_PARENTESES      )
   70      30  PALAVRA_RESERVADA     TO
   70      33  IDENTIFICADOR         RC-SALARIO
   70      43  PONTO                 .
   71      12  PALAVRA_RESERVADA     MOVE
   71      17  IDENTIFICADOR         DPTO
   71      21  ABRE_PARENTESES       (
   71      22  IDENTIFICADOR         IDX
   71      25  VIRGULA               ,
   71      26  NUMERO_INTEIRO        1
   71      27  FECHA_PARENTESES      )
   71      29  PALAVRA_RESERVADA     TO
   71      32  IDENTIFICADOR         RC-DPTO-1
   71      41  PONTO                 .
   72      12  PALAVRA_RESERVADA     MOVE
   72      17  IDENTIFICADOR         DPTO
   72      21  ABRE_PARENTESES       (
   72      22  IDENTIFICADOR         IDX
   72      25  VIRGULA               ,
   72      26  NUMERO_INTEIRO        2
   72      27  FECHA_PARENTESES      )
   72      29  PALAVRA_RESERVADA     TO
   72      32  IDENTIFICADOR         RC-DPTO-2
   72      41  PONTO                 .
   73      12  PALAVRA_RESERVADA     WRITE
   73      18  IDENTIFICADOR         RC-TRABALHADOR
   73      32  PONTO                 .
   74      12  PALAVRA_RESERVADA     ADD
   74      16  NUMERO_INTEIRO        1
   74      18  PALAVRA_RESERVADA     TO
   74      21  IDENTIFICADOR         IDX
   74      24  PONTO                 .
   76       8  PALAVRA_RESERVADA     END
   76      12  PALAVRA_RESERVADA     PROGRAM
   76      20  IDENTIFICADOR         PROG006_FILES
   76      33  PONTO                 .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - Manipulacao de arquivos
    5       7  COMENTARIO  *
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog006_files -std=default prog006_files.cob && .
   10       7  COMENTARIO  ******************************************************************
   22       7  COMENTARIO  * FILE DESCRIPTOR

Avisos de formato
  [W] Linha 25, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).
  [W] Linha 26, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).
  [W] Linha 27, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).
  [W] Linha 28, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).
  [W] Linha 29, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).
  [W] Linha 34, coluna 11: Nível de dados de 02 a 49 deve começar na área B (colunas 12-72).

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  ABRE_PARENTESES: 5
  CADEIA_PICTURE: 12
  CONSTANTE_FIGURATIVA: 2
  FECHA_PARENTESES: 5
  IDENTIFICADOR: 48
  LITERAL: 7
  NUMERO_DE_NIVEL: 15
  NUMERO_INTEIRO: 7
  OPERADOR_RELACIONAL: 1
  PALAVRA_RESERVADA: 72
  PONTO: 49
  VIRGULA: 2
  Tokens: 225
  Comentários: 11
  Diretivas: 0
  Erros: 0
  Avisos: 6
```

### prog007_loja.cob

```text
Analisador léxico COBOL
Arquivo: prog007_loja.cob
Formato: fixo (detecção automática)
Linhas: 228

Linha  Coluna  Token                 Lexema
-----  ------  --------------------  --------------------------------------------
   11       8  PALAVRA_RESERVADA     IDENTIFICATION
   11      23  PALAVRA_RESERVADA     DIVISION
   11      31  PONTO                 .
   12       8  PALAVRA_RESERVADA     PROGRAM-ID
   12      18  PONTO                 .
   12      20  IDENTIFICADOR         PROG007_LOJA
   12      32  PONTO                 .
   14       8  PALAVRA_RESERVADA     ENVIRONMENT
   14      20  PALAVRA_RESERVADA     DIVISION
   14      28  PONTO                 .
   15       8  PALAVRA_RESERVADA     INPUT-OUTPUT
   15      21  PALAVRA_RESERVADA     SECTION
   15      28  PONTO                 .
   17       8  PALAVRA_RESERVADA     FILE-CONTROL
   17      20  PONTO                 .
   18      12  PALAVRA_RESERVADA     SELECT
   18      19  IDENTIFICADOR         FD-PRODUTOS
   18      31  PALAVRA_RESERVADA     ASSIGN
   18      38  PALAVRA_RESERVADA     TO
   18      41  IDENTIFICADOR         WS-PROD-FILENAME
   19      31  PALAVRA_RESERVADA     ORGANIZATION
   19      44  PALAVRA_RESERVADA     INDEXED
   20      31  PALAVRA_RESERVADA     ACCESS
   20      38  PALAVRA_RESERVADA     MODE
   20      43  PALAVRA_RESERVADA     DYNAMIC
   21      31  PALAVRA_RESERVADA     RECORD
   21      38  PALAVRA_RESERVADA     KEY
   21      42  PALAVRA_RESERVADA     IS
   21      45  IDENTIFICADOR         RP-PID
   22      31  PALAVRA_RESERVADA     ALTERNATE
   22      41  PALAVRA_RESERVADA     RECORD
   22      48  PALAVRA_RESERVADA     KEY
   22      52  PALAVRA_RESERVADA     IS
   22      55  IDENTIFICADOR         RP-NOME
   23      31  PALAVRA_RESERVADA     FILE
   23      36  PALAVRA_RESERVADA     STATUS
   23      43  IDENTIFICADOR         WS-FILE-STATUS-PROD
   23      62  PONTO                 .
   26      12  PALAVRA_RESERVADA     SELECT
   26      19  IDENTIFICADOR         FD-PRODUTOS-KEY
   26      35  PALAVRA_RESERVADA     ASSIGN
   26      42  PALAVRA_RESERVADA     TO
   26      45  LITERAL               "PROG10-001.KEY"
   27      31  PALAVRA_RESERVADA     FILE
   27      36  PALAVRA_RESERVADA     STATUS
   27      43  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
   27      66  PONTO                 .
   29       8  PALAVRA_RESERVADA     DATA
   29      13  PALAVRA_RESERVADA     DIVISION
   29      21  PONTO                 .
   30       8  PALAVRA_RESERVADA     FILE
   30      13  PALAVRA_RESERVADA     SECTION
   30      20  PONTO                 .
   33       8  PALAVRA_RESERVADA     FD
   33      11  IDENTIFICADOR         FD-PRODUTOS
   34      11  PALAVRA_RESERVADA     BLOCK
   34      17  PALAVRA_RESERVADA     CONTAINS
   34      26  NUMERO_INTEIRO        874
   34      30  PALAVRA_RESERVADA     RECORDS
   35      11  PALAVRA_RESERVADA     RECORD
   35      18  PALAVRA_RESERVADA     CONTAINS
   35      27  NUMERO_INTEIRO        64
   35      30  PALAVRA_RESERVADA     CHARACTERS
   35      40  PONTO                 .
   46       8  NUMERO_DE_NIVEL       01
   46      11  IDENTIFICADOR         REG-PRODUTO
   46      22  PONTO                 .
   47      12  NUMERO_DE_NIVEL       02
   47      15  IDENTIFICADOR         RP-PID
   47      34  PALAVRA_RESERVADA     PIC
   47      38  CADEIA_PICTURE        9(10)
   47      43  PONTO                 .
   48      12  NUMERO_DE_NIVEL       02
   48      15  IDENTIFICADOR         RP-NOME
   48      34  PALAVRA_RESERVADA     PIC
   48      38  CADEIA_PICTURE        X(10)
   48      43  PONTO                 .
   49      12  NUMERO_DE_NIVEL       02
   49      15  IDENTIFICADOR         RP-VALOR
   49      34  PALAVRA_RESERVADA     PIC
   49      38  CADEIA_PICTURE        9(10)V9(02)
   49      49  PONTO                 .
   50      12  NUMERO_DE_NIVEL       02
   50      15  IDENTIFICADOR         RP-QTD
   50      34  PALAVRA_RESERVADA     PIC
   50      38  CADEIA_PICTURE        9(10)V9(02)
   50      49  PONTO                 .
   51      12  NUMERO_DE_NIVEL       02
   51      15  IDENTIFICADOR         RP-DESCRICAO
   51      34  PALAVRA_RESERVADA     PIC
   51      38  CADEIA_PICTURE        X(20)
   51      43  PONTO                 .
   54       8  PALAVRA_RESERVADA     FD
   54      11  IDENTIFICADOR         FD-PRODUTOS-KEY
   54      26  PONTO                 .
   55       8  NUMERO_DE_NIVEL       01
   55      11  IDENTIFICADOR         REGISTRO-CHAVE
   55      33  PALAVRA_RESERVADA     PIC
   55      37  CADEIA_PICTURE        9(10)
   55      42  PONTO                 .
   59       8  PALAVRA_RESERVADA     WORKING-STORAGE
   59      24  PALAVRA_RESERVADA     SECTION
   59      31  PONTO                 .
   62       8  NUMERO_DE_NIVEL       01
   62      11  IDENTIFICADOR         WS-PROD-FILENAME
   62      27  PONTO                 .
   63      12  NUMERO_DE_NIVEL       02
   63      15  IDENTIFICADOR         NAME
   63      34  PALAVRA_RESERVADA     PIC
   63      38  CADEIA_PICTURE        X(7)
   63      43  PALAVRA_RESERVADA     VALUES
   63      50  LITERAL               "PROG10-"
   63      59  PONTO                 .
   64      12  NUMERO_DE_NIVEL       02
   64      15  IDENTIFICADOR         NUM
   64      34  PALAVRA_RESERVADA     PIC
   64      38  CADEIA_PICTURE        9(3)
   64      43  PALAVRA_RESERVADA     VALUES
   64      50  NUMERO_INTEIRO        1
   64      51  PONTO                 .
   65      12  NUMERO_DE_NIVEL       02
   65      15  IDENTIFICADOR         EXT
   65      34  PALAVRA_RESERVADA     PIC
   65      38  CADEIA_PICTURE        X(4)
   65      43  PALAVRA_RESERVADA     VALUES
   65      50  LITERAL               ".DAT"
   65      56  PONTO                 .
   67       8  NUMERO_DE_NIVEL       77
   67      11  IDENTIFICADOR         WS-FILE-STATUS-PROD
   67      37  PALAVRA_RESERVADA     PIC
   67      41  CADEIA_PICTURE        9(02)
   67      46  PONTO                 .
   68       8  NUMERO_DE_NIVEL       77
   68      11  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
   68      37  PALAVRA_RESERVADA     PIC
   68      41  CADEIA_PICTURE        9(02)
   68      46  PONTO                 .
   70       8  NUMERO_DE_NIVEL       01
   70      11  IDENTIFICADOR         WS-PRODUTO
   70      21  PONTO                 .
   71      12  NUMERO_DE_NIVEL       02
   71      15  IDENTIFICADOR         WS-PID
   71      34  PALAVRA_RESERVADA     PIC
   71      38  CADEIA_PICTURE        9(10)
   71      43  PONTO                 .
   72      12  NUMERO_DE_NIVEL       02
   72      15  IDENTIFICADOR         WS-NOME
   72      34  PALAVRA_RESERVADA     PIC
   72      38  CADEIA_PICTURE        X(10)
   72      43  PONTO                 .
   73      12  NUMERO_DE_NIVEL       02
   73      15  IDENTIFICADOR         WS-VALOR
   73      34  PALAVRA_RESERVADA     PIC
   73      38  CADEIA_PICTURE        9(10)V9(02)
   73      49  PONTO                 .
   74      12  NUMERO_DE_NIVEL       02
   74      15  IDENTIFICADOR         WS-QTD
   74      34  PALAVRA_RESERVADA     PIC
   74      38  CADEIA_PICTURE        9(10)V9(02)
   74      49  PONTO                 .
   75      12  NUMERO_DE_NIVEL       02
   75      15  IDENTIFICADOR         WS-DESCRICAO
   75      34  PALAVRA_RESERVADA     PIC
   75      38  CADEIA_PICTURE        X(20)
   75      43  PONTO                 .
   78       8  NUMERO_DE_NIVEL       77
   78      11  IDENTIFICADOR         WS-OPCAO
   78      43  PALAVRA_RESERVADA     PIC
   78      47  CADEIA_PICTURE        9(01)
   78      52  PONTO                 .
   79       8  NUMERO_DE_NIVEL       77
   79      11  IDENTIFICADOR         WS-ULTIMO-PID
   79      43  PALAVRA_RESERVADA     PIC
   79      47  CADEIA_PICTURE        9(10)
   79      52  PONTO                 .
   80       8  NUMERO_DE_NIVEL       77
   80      11  IDENTIFICADOR         WS-EXIT
   80      43  PALAVRA_RESERVADA     PIC
   80      47  CADEIA_PICTURE        9(01)
   80      53  PALAVRA_RESERVADA     VALUES
   80      60  CONSTANTE_FIGURATIVA  ZERO
   80      64  PONTO                 .
   84       8  PALAVRA_RESERVADA     PROCEDURE
   84      18  PALAVRA_RESERVADA     DIVISION
   84      26  PONTO                 .
   85       8  IDENTIFICADOR         MAIN-PROCEDURE
   85      22  PONTO                 .
   87      12  PALAVRA_RESERVADA     DISPLAY
   87      20  LITERAL               "PERFORM 00000-OPEN-FILE-PRODUTOS-KEY"
   87      58  PONTO                 .
   88      12  PALAVRA_RESERVADA     PERFORM
   88      20  IDENTIFICADOR         00000-OPEN-FILE-PRODUTOS-KEY
   88      48  PONTO                 .
   90      12  PALAVRA_RESERVADA     IF
   90      15  IDENTIFICADOR         WS-EXIT
   90      23  OPERADOR_RELACIONAL   =
   90      25  NUMERO_INTEIRO        0
   91      15  PALAVRA_RESERVADA     DISPLAY
   91      23  LITERAL               "PERFORM 00000-OPEN-FILE-PRODUTOS"
   92      15  PALAVRA_RESERVADA     PERFORM
   92      23  IDENTIFICADOR         00000-OPEN-FILE-PRODUTOS
   93      12  PALAVRA_RESERVADA     END-IF
   93      18  PONTO                 .
   95      12  PALAVRA_RESERVADA     PERFORM
   95      20  IDENTIFICADOR         00001-MENU-OPCOES
   95      38  PALAVRA_RESERVADA     UNTIL
   95      44  IDENTIFICADOR         WS-EXIT
   95      52  OPERADOR_RELACIONAL   =
   95      54  NUMERO_INTEIRO        1
   95      55  PONTO                 .
   97      12  PALAVRA_RESERVADA     WRITE
   97      18  IDENTIFICADOR         REGISTRO-CHAVE
   97      33  PALAVRA_RESERVADA     FROM
   97      38  IDENTIFICADOR         WS-ULTIMO-PID
   97      51  PONTO                 .
   98      12  PALAVRA_RESERVADA     CLOSE
   98      18  IDENTIFICADOR         FD-PRODUTOS-KEY
   98      33  PONTO                 .
   99      12  PALAVRA_RESERVADA     CLOSE
   99      18  IDENTIFICADOR         FD-PRODUTOS
   99      29  PONTO                 .
  100      12  PALAVRA_RESERVADA     DISPLAY
  100      20  LITERAL               "BYE"
  101      12  PALAVRA_RESERVADA     STOP
  101      17  PALAVRA_RESERVADA     RUN
  101      20  PONTO                 .
  103       8  IDENTIFICADOR         00000-OPEN-FILE-PRODUTOS-KEY
  103      36  PONTO                 .
  105      12  PALAVRA_RESERVADA     MOVE
  105      17  NUMERO_INTEIRO        0
  105      19  PALAVRA_RESERVADA     TO
  105      22  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  105      45  PONTO                 .
  106      12  PALAVRA_RESERVADA     OPEN
  106      17  PALAVRA_RESERVADA     INPUT
  106      23  IDENTIFICADOR         FD-PRODUTOS-KEY
  106      38  PONTO                 .
  107      12  PALAVRA_RESERVADA     IF
  107      15  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  107      39  OPERADOR_RELACIONAL   =
  107      41  NUMERO_INTEIRO        0
  108      15  PALAVRA_RESERVADA     DISPLAY
  108      23  LITERAL               "-- PROG10-001.KEY FOUND"
  109      15  PALAVRA_RESERVADA     READ
  109      20  IDENTIFICADOR         FD-PRODUTOS-KEY
  109      36  PALAVRA_RESERVADA     INTO
  109      41  IDENTIFICADOR         WS-ULTIMO-PID
  110      12  PALAVRA_RESERVADA     ELSE
  111      12  PALAVRA_RESERVADA     IF
  111      15  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  111      39  OPERADOR_RELACIONAL   =
  111      41  NUMERO_INTEIRO        35
  112      15  PALAVRA_RESERVADA     DISPLAY
  112      23  LITERAL               "-- PROG10-001.KEY NOT FOUND - CREATING NEW"
  113      15  PALAVRA_RESERVADA     OPEN
  113      20  PALAVRA_RESERVADA     OUTPUT
  113      27  IDENTIFICADOR         FD-PRODUTOS-KEY
  114      15  PALAVRA_RESERVADA     IF
  114      18  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  114      42  OPERADOR_RELACIONAL   =
  114      44  NUMERO_INTEIRO        0
  115      18  PALAVRA_RESERVADA     MOVE
  115      23  NUMERO_INTEIRO        0
  115      25  PALAVRA_RESERVADA     TO
  115      28  IDENTIFICADOR         WS-ULTIMO-PID
  116      15  PALAVRA_RESERVADA     ELSE
  117      18  PALAVRA_RESERVADA     DISPLAY
  117      26  LITERAL               "-- ERRO AO CRIAR ARQUIVO DE CHAVES -->"
  118      26  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  119      18  PALAVRA_RESERVADA     MOVE
  119      23  NUMERO_INTEIRO        1
  119      25  PALAVRA_RESERVADA     TO
  119      28  IDENTIFICADOR         WS-EXIT
  120      12  PALAVRA_RESERVADA     ELSE
  121      15  PALAVRA_RESERVADA     DISPLAY
  121      23  LITERAL               "-- ERRO AO ABRIR ARQUIVO DE CHAVES -->"
  122      21  IDENTIFICADOR         WS-FILE-STATUS-PROD-KEY
  123      15  PALAVRA_RESERVADA     MOVE
  123      20  NUMERO_INTEIRO        1
  123      22  PALAVRA_RESERVADA     TO
  123      25  IDENTIFICADOR         WS-EXIT
  123      32  PONTO                 .
  125       8  IDENTIFICADOR         00000-OPEN-FILE-PRODUTOS
  125      32  PONTO                 .
  126      12  PALAVRA_RESERVADA     MOVE
  126      17  NUMERO_INTEIRO        0
  126      19  PALAVRA_RESERVADA     TO
  126      22  IDENTIFICADOR         WS-FILE-STATUS-PROD
  126      41  PONTO                 .
  127      12  PALAVRA_RESERVADA     OPEN
  127      17  PALAVRA_RESERVADA     I-O
  127      21  IDENTIFICADOR         FD-PRODUTOS
  127      32  PONTO                 .
  129      12  PALAVRA_RESERVADA     IF
  129      15  IDENTIFICADOR         WS-FILE-STATUS-PROD
  129      35  OPERADOR_RELACIONAL   =
  129      37  NUMERO_INTEIRO        35
  130      15  PALAVRA_RESERVADA     DISPLAY
  130      23  LITERAL               "-- PROG10-001.DAT NOT FOUND - CREATING NEW"
  131      15  PALAVRA_RESERVADA     OPEN
  131      20  PALAVRA_RESERVADA     OUTPUT
  131      27  IDENTIFICADOR         FD-PRODUTOS
  132      15  PALAVRA_RESERVADA     IF
  132      18  IDENTIFICADOR         WS-FILE-STATUS-PROD
  132      38  OPERADOR_RELACIONAL   =
  132      40  NUMERO_INTEIRO        0
  133      18  PALAVRA_RESERVADA     MOVE
  133      23  NUMERO_INTEIRO        0
  133      25  PALAVRA_RESERVADA     TO
  133      28  IDENTIFICADOR         WS-ULTIMO-PID
  134      15  PALAVRA_RESERVADA     ELSE
  135      18  PALAVRA_RESERVADA     DISPLAY
  135      26  LITERAL               "-- ERRO AO CRIAR ARQUIVO DE DADOS -->"
  136      26  IDENTIFICADOR         WS-FILE-STATUS-PROD
  137      18  PALAVRA_RESERVADA     MOVE
  137      23  NUMERO_INTEIRO        1
  137      25  PALAVRA_RESERVADA     TO
  137      28  IDENTIFICADOR         WS-EXIT
  138      12  PALAVRA_RESERVADA     ELSE
  139      12  PALAVRA_RESERVADA     IF
  139      15  IDENTIFICADOR         WS-FILE-STATUS-PROD
  139      35  OPERADOR_RELACIONAL   =
  139      37  NUMERO_INTEIRO        0
  140      15  PALAVRA_RESERVADA     DISPLAY
  140      23  LITERAL               "-- PROG10-001.DAT FOUND"
  141      15  PALAVRA_RESERVADA     IF
  141      18  IDENTIFICADOR         WS-ULTIMO-PID
  141      32  OPERADOR_RELACIONAL   =
  141      34  NUMERO_INTEIRO        0
  142      18  PALAVRA_RESERVADA     MOVE
  142      23  NUMERO_INTEIRO        0
  142      25  PALAVRA_RESERVADA     TO
  142      28  IDENTIFICADOR         WS-ULTIMO-PID
  143      15  PALAVRA_RESERVADA     ELSE
  144      18  PALAVRA_RESERVADA     MOVE
  144      23  IDENTIFICADOR         WS-ULTIMO-PID
  144      37  PALAVRA_RESERVADA     TO
  144      40  IDENTIFICADOR         RP-PID
  146      18  PALAVRA_RESERVADA     START
  146      24  IDENTIFICADOR         FD-PRODUTOS
  146      36  PALAVRA_RESERVADA     KEY
  146      40  PALAVRA_RESERVADA     EQUAL
  146      46  IDENTIFICADOR         RP-PID
  147      22  PALAVRA_RESERVADA     INVALID
  147      30  PALAVRA_RESERVADA     KEY
  148      25  PALAVRA_RESERVADA     DISPLAY
  148      33  LITERAL               "ERRO AO REGISTRO"
  149      12  PALAVRA_RESERVADA     ELSE
  150      14  PALAVRA_RESERVADA     DISPLAY
  150      22  LITERAL               "-- ERRO AO ABRIR ARQUIVO DE PRODUTOS"
  151      26  IDENTIFICADOR         WS-FILE-STATUS-PROD
  152      14  PALAVRA_RESERVADA     MOVE
  152      19  NUMERO_INTEIRO        1
  152      21  PALAVRA_RESERVADA     TO
  152      24  IDENTIFICADOR         WS-EXIT
  152      31  PONTO                 .
  155       8  IDENTIFICADOR         00001-MENU-OPCOES
  155      25  PONTO                 .
  156      12  PALAVRA_RESERVADA     DISPLAY
  156      20  LITERAL               " "
  156      23  PONTO                 .
  157      12  PALAVRA_RESERVADA     DISPLAY
  157      20  LITERAL               "====00001-MENU-OPCOES===="
  157      47  PONTO                 .
  158      12  PALAVRA_RESERVADA     DISPLAY
  158      20  LITERAL               "OPCOES:"
  158      29  PONTO                 .
  159      12  PALAVRA_RESERVADA     DISPLAY
  159      20  LITERAL               "1) ADICIONA PRODUTO"
  159      41  PONTO                 .
  160      12  PALAVRA_RESERVADA     DISPLAY
  160      20  LITERAL               "2) REMOVE PRODUTO - NOT IMPLEMENTED"
  160      57  PONTO                 .
  161      12  PALAVRA_RESERVADA     DISPLAY
  161      20  LITERAL               "3) ATUALIZA PRODUTO - NOT IMPLEMENTED"
  161      59  PONTO                 .
  162      12  PALAVRA_RESERVADA     DISPLAY
  162      20  LITERAL               "4) CONSULTA PRODUTO"
  162      41  PONTO                 .
  163      12  PALAVRA_RESERVADA     DISPLAY
  163      20  LITERAL               " "
  163      23  PONTO                 .
  164      12  PALAVRA_RESERVADA     DISPLAY
  164      20  LITERAL               "5) SAIR DO PROGRAMA"
  164      41  PONTO                 .
  165      12  PALAVRA_RESERVADA     ACCEPT
  165      20  IDENTIFICADOR         WS-OPCAO
  165      28  PONTO                 .
  167      12  PALAVRA_RESERVADA     EVALUATE
  167      21  IDENTIFICADOR         WS-OPCAO
  168      15  PALAVRA_RESERVADA     WHEN
  168      20  NUMERO_INTEIRO        1
  168      22  PALAVRA_RESERVADA     PERFORM
  168      30  IDENTIFICADOR         00002-CREATE-PRODUTO
  169      15  PALAVRA_RESERVADA     WHEN
  169      20  NUMERO_INTEIRO        2
  170      18  PALAVRA_RESERVADA     DISPLAY
  170      26  LITERAL               "DELETE"
  171      15  PALAVRA_RESERVADA     WHEN
  171      20  NUMERO_INTEIRO        3
  172      18  PALAVRA_RESERVADA     DISPLAY
  172      26  LITERAL               "UPDATE"
  173      15  PALAVRA_RESERVADA     WHEN
  173      20  NUMERO_INTEIRO        4
  173      22  PALAVRA_RESERVADA     PERFORM
  173      30  IDENTIFICADOR         00002-SELECT-PRODUTO
  174      15  PALAVRA_RESERVADA     WHEN
  174      20  NUMERO_INTEIRO        5
  175      18  PALAVRA_RESERVADA     MOVE
  175      23  NUMERO_INTEIRO        1
  175      25  PALAVRA_RESERVADA     TO
  175      28  IDENTIFICADOR         WS-EXIT
  176      15  PALAVRA_RESERVADA     WHEN
  176      20  PALAVRA_RESERVADA     OTHER
  177      18  PALAVRA_RESERVADA     DISPLAY
  177      26  LITERAL               "OPCAO INVALIDA."
  178      12  PALAVRA_RESERVADA     END-EVALUATE
  178      24  PONTO                 .
  180       8  IDENTIFICADOR         00002-CREATE-PRODUTO
  180      28  PONTO                 .
  181      12  PALAVRA_RESERVADA     DISPLAY
  181      20  LITERAL               "CRIA UM NOVO PRODUTO"
  181      42  PONTO                 .
  182      12  PALAVRA_RESERVADA     DISPLAY
  182      20  LITERAL               "NOME: "
  182      29  PALAVRA_RESERVADA     WITH
  182      34  PALAVRA_RESERVADA     NO
  182      37  PALAVRA_RESERVADA     ADVANCING
  182      46  PONTO                 .
  183      12  PALAVRA_RESERVADA     ACCEPT
  183      19  IDENTIFICADOR         WS-NOME
  183      26  PONTO                 .
  184      12  PALAVRA_RESERVADA     DISPLAY
  184      20  LITERAL               "VALOR: "
  184      30  PALAVRA_RESERVADA     WITH
  184      35  PALAVRA_RESERVADA     NO
  184      38  PALAVRA_RESERVADA     ADVANCING
  184      47  PONTO                 .
  185      12  PALAVRA_RESERVADA     ACCEPT
  185      19  IDENTIFICADOR         WS-VALOR
  185      27  PONTO                 .
  186      12  PALAVRA_RESERVADA     DISPLAY
  186      20  LITERAL               "QUANTIDADE: "
  186      35  PALAVRA_RESERVADA     WITH
  186      40  PALAVRA_RESERVADA     NO
  186      43  PALAVRA_RESERVADA     ADVANCING
  186      52  PONTO                 .
  187      12  PALAVRA_RESERVADA     ACCEPT
  187      19  IDENTIFICADOR         WS-QTD
  187      25  PONTO                 .
  188      12  PALAVRA_RESERVADA     DISPLAY
  188      20  LITERAL               "DESCRICAO: "
  188      34  PALAVRA_RESERVADA     WITH
  188      39  PALAVRA_RESERVADA     NO
  188      42  PALAVRA_RESERVADA     ADVANCING
  188      51  PONTO                 .
  189      12  PALAVRA_RESERVADA     ACCEPT
  189      19  IDENTIFICADOR         WS-DESCRICAO
  189      31  PONTO                 .
  191      12  PALAVRA_RESERVADA     ADD
  191      16  NUMERO_INTEIRO        1
  191      18  PALAVRA_RESERVADA     TO
  191      21  IDENTIFICADOR         WS-ULTIMO-PID
  191      34  PONTO                 .
  192      12  PALAVRA_RESERVADA     MOVE
  192      17  IDENTIFICADOR         WS-ULTIMO-PID
  192      31  PALAVRA_RESERVADA     TO
  192      34  IDENTIFICADOR         WS-PID
  192      40  PONTO                 .
  194      12  PALAVRA_RESERVADA     DISPLAY
  194      20  LITERAL               "--------------"
  195      12  PALAVRA_RESERVADA     DISPLAY
  195      20  IDENTIFICADOR         WS-PRODUTO
  195      30  PONTO                 .
  196      12  PALAVRA_RESERVADA     DISPLAY
  196      20  LITERAL               "--------------"
  198      12  PALAVRA_RESERVADA     WRITE
  198      18  IDENTIFICADOR         REG-PRODUTO
  198      30  PALAVRA_RESERVADA     FROM
  198      35  IDENTIFICADOR         WS-PRODUTO
  199      15  PALAVRA_RESERVADA     INVALID
  199      23  PALAVRA_RESERVADA     KEY
  200      18  PALAVRA_RESERVADA     DISPLAY
  200      26  LITERAL               "CODIGO DE PRODUTO JAH EXISTE"
  200      57  IDENTIFICADOR         WS-ULTIMO-PID
  201      18  PALAVRA_RESERVADA     MOVE
  201      23  NUMERO_INTEIRO        1
  201      25  PALAVRA_RESERVADA     TO
  201      28  IDENTIFICADOR         WS-EXIT
  202      15  PALAVRA_RESERVADA     NOT
  202      19  PALAVRA_RESERVADA     INVALID
  202      27  PALAVRA_RESERVADA     KEY
  203      18  PALAVRA_RESERVADA     DISPLAY
  203      26  LITERAL               "PRODUTO ARMAZENADO"
  203      46  PONTO                 .
  205       8  IDENTIFICADOR         00002-SELECT-PRODUTO
  205      28  PONTO                 .
  206      12  PALAVRA_RESERVADA     DISPLAY
  206      20  LITERAL               "CONSULTA PRODUTO"
  206      38  PONTO                 .
  207      12  PALAVRA_RESERVADA     DISPLAY
  207      20  LITERAL               "WS-ULTIMO-PID --> "
  207      41  IDENTIFICADOR         WS-ULTIMO-PID
  207      54  PONTO                 .
  208      12  PALAVRA_RESERVADA     DISPLAY
  208      20  LITERAL               "PID: "
  208      27  PONTO                 .
  209      12  PALAVRA_RESERVADA     ACCEPT
  209      19  IDENTIFICADOR         WS-PID
  209      25  PONTO                 .
  211      12  PALAVRA_RESERVADA     MOVE
  211      17  IDENTIFICADOR         WS-PID
  211      24  PALAVRA_RESERVADA     TO
  211      27  IDENTIFICADOR         RP-PID
  211      33  PONTO                 .
  213      12  PALAVRA_RESERVADA     READ
  213      17  IDENTIFICADOR         FD-PRODUTOS
  213      29  PALAVRA_RESERVADA     RECORD
  213      36  PALAVRA_RESERVADA     KEY
  213      40  IDENTIFICADOR         RP-PID
  214      17  PALAVRA_RESERVADA     INVALID
  214      25  PALAVRA_RESERVADA     KEY
  215      21  PALAVRA_RESERVADA     DISPLAY
  215      29  LITERAL               "ERRO AO LOCALIZAR REGISTRO"
  216      17  PALAVRA_RESERVADA     NOT
  216      21  PALAVRA_RESERVADA     INVALID
  216      29  PALAVRA_RESERVADA     KEY
  217      21  PALAVRA_RESERVADA     MOVE
  217      26  IDENTIFICADOR         REG-PRODUTO
  217      38  PALAVRA_RESERVADA     TO
  217      41  IDENTIFICADOR         WS-PRODUTO
  218      21  PALAVRA_RESERVADA     DISPLAY
  218      29  LITERAL               " "
  219      21  PALAVRA_RESERVADA     DISPLAY
  219      29  LITERAL               "NOME: "
  219      38  PALAVRA_RESERVADA     WITH
  219      43  PALAVRA_RESERVADA     NO
  219      46  PALAVRA_RESERVADA     ADVANCING
  220      21  PALAVRA_RESERVADA     DISPLAY
  220      29  IDENTIFICADOR         WS-NOME
  221      21  PALAVRA_RESERVADA     DISPLAY
  221      29  LITERAL               "VALOR: "
  221      39  PALAVRA_RESERVADA     WITH
  221      44  PALAVRA_RESERVADA     NO
  221      47  PALAVRA_RESERVADA     ADVANCING
  222      21  PALAVRA_RESERVADA     DISPLAY
  222      29  IDENTIFICADOR         WS-VALOR
  223      21  PALAVRA_RESERVADA     DISPLAY
  223      29  LITERAL               "QUANTIDADE: "
  223      44  PALAVRA_RESERVADA     WITH
  223      49  PALAVRA_RESERVADA     NO
  223      52  PALAVRA_RESERVADA     ADVANCING
  224      21  PALAVRA_RESERVADA     DISPLAY
  224      29  IDENTIFICADOR         WS-QTD
  225      21  PALAVRA_RESERVADA     DISPLAY
  225      29  LITERAL               "DESCRICAO: "
  225      43  PALAVRA_RESERVADA     WITH
  225      48  PALAVRA_RESERVADA     NO
  225      51  PALAVRA_RESERVADA     ADVANCING
  226      21  PALAVRA_RESERVADA     DISPLAY
  226      29  IDENTIFICADOR         WS-DESCRICAO
  226      41  PONTO                 .
  228       8  PALAVRA_RESERVADA     END
  228      12  PALAVRA_RESERVADA     PROGRAM
  228      20  IDENTIFICADOR         PROG007_LOJA
  228      32  PONTO                 .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  ******************************************************************
    2       7  COMENTARIO  * Author: ENIO BASSO
    3       7  COMENTARIO  * Date: 2018-02-26
    4       7  COMENTARIO  * Purpose: COBOL STUDY - Progama Loja ou Cadastro de Produtos
    5       7  COMENTARIO  *          Le os produtos e faz o cadastro e consulta de produtos
    6       7  COMENTARIO  * Para programar sugiro: o OpenCobolIDE para o Visual Studio Code
    7       7  COMENTARIO  *
    8       7  COMENTARIO  * Compilo com o gnu-cobol usando a seguinte command line:
    9       7  COMENTARIO  * cobc -x -o bin/prog007_loja.cob -std=default prog007_loja.cob.co
   10       7  COMENTARIO  ******************************************************************
   25       7  COMENTARIO  * ARMAZENA A ULTIMA CHAVE DO ARQUIVO DE DADOS.
   32       7  COMENTARIO  * FILE DESCRIPTOR
   36       7  COMENTARIO  *   TAMANHO MAXIMO 27998 POSICOES(CARACTERES)
   37       7  COMENTARIO  *   1 CARACTERES = 8 BITS - 1 BYTE.
   38       7  COMENTARIO  *   TAMANHO DE REGISTRO 64 POSICOES
   39       7  COMENTARIO  *   TAMANHO DE BLOCO IDEAL -> TAMANHO MAXIMO/TAMANHO DO REGISTRO
   40       7  COMENTARIO  *                             27998/64 => 437.4675
   41       7  COMENTARIO  *                             437 X 64 = 27968
   42       7  COMENTARIO  *   BLOQUEIO OTIMO -> 27966 POSICIOES
   43       7  COMENTARIO  *   TRACK COMPLETO -> 2 * 27996 => 55,9992 POSICOES
   44       7  COMENTARIO  *   FATOR DE BLOQUEIO = 437 * 2 = 874 REGISTROS.
   60       7  COMENTARIO  ************ VARIAVES PARA OS ARQUIVOS ************
   61       7  COMENTARIO  * EXEMPLO PARA NOMES DE ARQUIVO COMO VARIAVEL
   77       7  COMENTARIO  ************* VARIAVEIS PARA USO GERAL ************
   82       7  COMENTARIO  ************* VARIAVEIS PARA CONTADORES ************
  145       7  COMENTARIO  *          POSICIONA NO REGISTRO DO ARQUIVO
  212       7  COMENTARIO  *          POSICIONA NO REGISTRO DO ARQUIVO

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  CADEIA_PICTURE: 19
  CONSTANTE_FIGURATIVA: 1
  IDENTIFICADOR: 107
  LITERAL: 45
  NUMERO_DE_NIVEL: 22
  NUMERO_INTEIRO: 29
  OPERADOR_RELACIONAL: 9
  PALAVRA_RESERVADA: 247
  PONTO: 87
  Tokens: 566
  Comentários: 27
  Diretivas: 0
  Erros: 0
  Avisos: 0
```

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

### erros-inseridos/erros_lexicos.cob

```text
Analisador léxico COBOL
Arquivo: erros-inseridos/erros_lexicos.cob
Formato: fixo
Linhas: 21

Linha  Coluna  Token              Lexema
-----  ------  -----------------  --------------------------------------
    2      12  PALAVRA_RESERVADA  DISPLAY
    2      20  LITERAL            "ORFA"
    2      26  PONTO              .
    3       8  PALAVRA_RESERVADA  IDENTIFICATION
    3      23  PALAVRA_RESERVADA  DIVISION
    3      31  PONTO              .
    4       8  PALAVRA_RESERVADA  PROGRAM-ID
    4      18  PONTO              .
    4      20  IDENTIFICADOR      ERROS-INSERIDOS
    4      35  PONTO              .
    5       8  PALAVRA_RESERVADA  DATA
    5      13  PALAVRA_RESERVADA  DIVISION
    5      21  PONTO              .
    6       8  PALAVRA_RESERVADA  WORKING-STORAGE
    6      24  PALAVRA_RESERVADA  SECTION
    6      31  PONTO              .
    7       8  NUMERO_DE_NIVEL    01
    7      11  IDENTIFICADOR      WS-OK
    7      17  PALAVRA_RESERVADA  PIC
    7      21  CADEIA_PICTURE     X(10)
    7      27  PALAVRA_RESERVADA  VALUE
    7      33  LITERAL            "OK"
    7      37  PONTO              .
    8       8  NUMERO_DE_NIVEL    01
    8      11  IDENTIFICADOR      WS-TEXTO
    8      20  PALAVRA_RESERVADA  PIC
    8      24  CADEIA_PICTURE     X(10)
    8      30  PALAVRA_RESERVADA  VALUE
    8      36  LITERAL            "sem fechar.
    9       8  NUMERO_DE_NIVEL    01
    9      11  IDENTIFICADOR      WS-TEXTO2
    9      21  PALAVRA_RESERVADA  PIC
    9      25  CADEIA_PICTURE     X(5)
    9      30  PALAVRA_RESERVADA  VALUE
    9      36  LITERAL            'tambem.
   10       8  NUMERO_DE_NIVEL    01
   10      11  IDENTIFICADOR      WS-NOME-MUITO-GRANDE-DEMAIS-PARA-COBOL
   10      50  PALAVRA_RESERVADA  PIC
   10      54  CADEIA_PICTURE     X(5)
   10      58  PONTO              .
   11       8  NUMERO_DE_NIVEL    01
   11      11  IDENTIFICADOR      WS-VAZIO
   11      20  PALAVRA_RESERVADA  PIC
   11      24  PONTO              .
   12       8  NUMERO_DE_NIVEL    01
   12      11  IDENTIFICADOR      WS-ABERTA
   12      21  PALAVRA_RESERVADA  PIC
   12      25  CADEIA_PICTURE     9(4
   12      28  PONTO              .
   13       8  NUMERO_DE_NIVEL    01
   13      11  IDENTIFICADOR      WS-PRECO
   13      20  PALAVRA_RESERVADA  PIC
   13      24  CADEIA_PICTURE     9(4)
   13      29  PALAVRA_RESERVADA  VALUE
   13      35  NUMERO_INTEIRO     10
   13      37  PONTO              .
   14       8  PALAVRA_RESERVADA  PROCEDURE
   14      18  PALAVRA_RESERVADA  DIVISION
   14      26  PONTO              .
   15      12  PALAVRA_RESERVADA  DISPLAY
   15      20  IDENTIFICADOR      A
   15      21  ERRO               --
   15      23  IDENTIFICADOR      B
   15      24  PONTO              .
   16      12  PALAVRA_RESERVADA  DISPLAY
   16      20  LITERAL            "CERTO"
   16      28  ERRO               #
   16      30  LITERAL            "ERRADO"
   16      38  PONTO              .
   17      12  PALAVRA_RESERVADA  DISPLAY
   17      20  ERRO               @
   17      21  PONTO              .
   18      12  PALAVRA_RESERVADA  DISPLAY
   18      20  ERRO               $
   18      21  PONTO              .
   19       8  PALAVRA_RESERVADA  DISPLAY
   19      16  LITERAL            "INDICADOR"
   19      27  PONTO              .
   21      12  PALAVRA_RESERVADA  STOP
   21      17  PALAVRA_RESERVADA  RUN
   21      20  PONTO              .

Comentários e diretivas
Linha  Coluna  Tipo        Texto
-----  ------  ----------  ------------------------------------------------------------------
    1       7  COMENTARIO  * Erros inseridos para o relatorio. Os sete programas originais fi

Erros léxicos
  [E] Linha 2, coluna 7: Linha de continuação sem linha de código imediatamente anterior.
  [E] Linha 8, coluna 36: Literal não terminado.
  [E] Linha 9, coluna 36: Literal não terminado.
  [E] Linha 10, coluna 11: Identificador com mais de 30 caracteres.
  [E] Linha 11, coluna 24: Cadeia de picture ausente.
  [E] Linha 12, coluna 26: Parênteses não fechados na cadeia de picture.
  [E] Linha 15, coluna 21: Hífen duplicado. Identificadores COBOL não contêm '--'.
  [E] Linha 16, coluna 28: Caractere inválido: '#'.
  [E] Linha 17, coluna 20: Caractere inválido: '@'.
  [E] Linha 18, coluna 20: Caractere inválido: '$'.
  [E] Linha 19, coluna 7: Indicador inválido na coluna 7: 'X'.
  [E] Linha 20, coluna 1: Linha curta demais para o formato fixo; o código começa na coluna 8.

Avisos de formato
  [W] Linha 19, coluna 8: Comando COBOL deve começar na área B (colunas 12-72).

Informações da análise
  [I] Formato de fonte: fixo.

Resumo
  CADEIA_PICTURE: 6
  ERRO: 4
  IDENTIFICADOR: 10
  LITERAL: 7
  NUMERO_DE_NIVEL: 7
  NUMERO_INTEIRO: 1
  PALAVRA_RESERVADA: 28
  PONTO: 18
  Tokens: 81
  Comentários: 1
  Diretivas: 0
  Erros: 12
  Avisos: 1
```
