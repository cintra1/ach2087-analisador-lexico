# Relatório - Compilador COBOL (analisador léxico, sintático, semântico e gerador de código)

Integrantes do grupo:
• Mateus Freitas Cintra - NUSP 14597677
• Cauã Gabriel Muniz dos Santos - NUSP 14564405

## 1.1 Código

O código do analisador léxico e do compilador completo está no GitHub:

https://github.com/cintra1/ach2087-analisador-lexico

## 2.1 Introdução

COBOL (Common Business-Oriented Language) é uma linguagem de 1959 feita para programas de negócio: cadastro, folha, estoque, cobrança. Continua em bancos, governos e seguradoras porque esses sistemas já estão corretos, movimentam dinheiro com aritmética decimal e descrevem arquivos e registros no próprio fonte. Trocar um programa desses por outra linguagem é caro e arriscado. A sintaxe parece inglês (`MOVE`, `ADD`, `DISPLAY`), o que ajuda quem mantém o código décadas depois.

Essa mesma forma, porém, complica o analisador léxico. O formato fixo não é texto livre: as colunas 1-6 são número de sequência, a coluna 7 diz se a linha é comentário (`*` ou `/`), continuação (`-`) ou depuração (`D`), o código útil vai da coluna 8 à 72 e as colunas 73-80 são ignoradas. O ponto final tanto termina uma sentença quanto é o ponto decimal de um número ou de uma picture (`ZZ9.99`). O hífen entra no nome (`WS-VALOR`, `00000-CALCULADORA`) e também é o sinal de menos (`-10`). A picture reaproveita letras, dígitos, parênteses, vírgula e ponto, então `PIC` abre um contexto que um autômato só de palavras não resolve. Maiúsculas e minúsculas são a mesma palavra. Um inteiro na área A pode ser número de nível (`01`, `77`) ou um valor comum (`MOVE 20 TO X`). Os programas de teste ainda quebram uma palavra entre duas linhas (`T` + `AB-TRABALHADOR`) e dão a parágrafos nomes que começam com dígito.

A primeira etapa do trabalho foi o analisador léxico: transformar o fonte em tokens (seções 2.2 a 2.4). Na etapa final, descrita na seção 3, o léxico passou a alimentar um analisador sintático, uma análise semântica e um gerador de código C, de modo que o grupo compila e executa programas COBOL.

## 2.2 Implementação

O analisador está em Python 3, só com a biblioteca padrão. Não usamos Flex nem outro gerador. As regras que mais importam nos exemplos (colunas, continuação, picture e número de nível) dependem de um pouco de contexto. Num scanner escrito à mão isso fica explícito e dá para testar com `py -m unittest discover -s testes -t .`. O ponto de entrada é `analisador.py`.

O fluxo é o seguinte. O fonte é lido em UTF-8 (ou Latin-1). Se o formato não for forçado, o programa reconhece o cartão de 80 colunas. Nos sete exemplos o resultado é o formato fixo. Em seguida monta-se um texto lógico: colunas 1-6 e 73-80 saem, comentário de coluna 7 vai para uma lista à parte, e a linha com `-` na coluna 7 continua a anterior. Fora de um literal, os espaços do fim da linha são descartados e o texto é colado sem espaço novo, como em `TAB-TRABALHADOR`. Dentro de um literal, a aspa que abre a continuação não entra na string. A varredura então classifica cada lexema.

A seção 2.2 da especificação lista um núcleo de palavras reservadas: `IDENTIFICATION`, `ENVIRONMENT`, `DATA`, `PROCEDURE`, `DIVISION`, `SECTION`, `DISPLAY`, `ACCEPT`, `PERFORM`, `STOP`, `RUN`, `IF`, `ELSE` e `MOVE`. O restante da especificação e os sete programas usam muito mais palavras (`PROGRAM-ID`, `PIC`, `VALUE`, `ADD`, `SELECT`, `OPEN`, `READ`, `WRITE`, `EVALUATE`). O léxico adotado é o COBOL 85 mais extensões frequentes do GnuCOBOL, conjunto que contém aquele núcleo. Sem isso, `PIC` seria um identificador e a picture não seria isolada.

A pontuação da especificação é `. , ; ( )`. Os exemplos também usam `+ - * / ** = > < >= <= <>`. Esses operadores são tokens. Se fossem recusados, programas válidos apareceriam como erro de caractere. O sublinhado não está no alfabeto descrito na especificação (letra, dígito e hífen), mas `PROG006_FILES`, `PROG007_LOJA` e `PROG008_STRING` o usam. Ele entra no identificador para o nome continuar sendo um único token. Um nome com mais de 30 caracteres, limite da especificação, é emitido e também registrado como erro.

Um inteiro de 01 a 49, 66, 77 ou 88 vira `NUMERO_DE_NIVEL` quando é o primeiro token da linha, ou vem logo depois de um ponto, e o token seguinte é um nome ou uma cláusula de dados (`PIC`, `VALUE`, `OCCURS`, `FILLER` e as demais). `VALUE 10` e `ADD 1 TO X` continuam números comuns. Comentários não entram na tabela de tokens.

Um erro léxico não interrompe o arquivo. O analisador registra a mensagem, segue na coluna seguinte e, no fim, devolve código de saída 1. Assim dá para ver, no mesmo relatório, o ponto da falha e os tokens que ainda foram reconhecidos.

Os diagnósticos seguem os níveis da especificação: informação (`I`), aviso (`W`), erro léxico (`E`) e falha severa (`S`). O nível `S` fica para falhas que interrompem a análise, como arquivo de entrada ausente, copybook ausente ou ciclo de inclusão. No formato fixo, os avisos verificam o posicionamento de cabeçalhos e níveis `01`, `66`, `77` e `88` na área A, níveis `02`-`49` e comandos na área B. A linha de comando também expande instruções `COPY` simples, procurando o copybook ao lado do fonte ou nos diretórios passados com `-I`. A posição dos tokens incluídos é a do texto expandido.

**Ferramenta de IA.** O grupo definiu a estratégia (Python, scanner manual, léxico COBOL 85 com extensões do GnuCOBOL, recuperação de erro e os doze casos de `erros-inseridos/erros_lexicos.cob`) e conferiu cada saída contra a especificação e os exemplos. O Cursor, com o modelo Grok 4.7, foi usado como apoio: gerou o rascunho do scanner e dos testes, ajustou a continuação de linha e os parágrafos numéricos depois da execução dos exemplos e montou as tabelas da seção 2.3 a partir da saída do programa.

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


## 3. Compilador completo (etapa final)

A especificação do compilador COBOL pede quatro passos: análise léxica, sintática, semântica e geração de código. O léxico das seções anteriores é o primeiro passo. Esta seção descreve os outros três, o runtime e os resultados da execução dos programas de teste. O código fica no mesmo repositório (`cobc.py`, `src/parser.py`, `src/semantica.py`, `src/gerador_c.py`, `src/preproc.py`, `runtime/cobrt.h`).

### 3.1 Arquitetura

```text
fonte .cbl -> preproc.py -> lexer.py -> parser.py -> semantica.py -> gerador_c.py -> gcc -> executável
              (COPY)        (tokens)    (AST)        (símbolos,       (código C +
                                                      verificações)    runtime)
```

O destino é C, uma das duas abordagens de backend que a especificação cita (seção 5). O gerador produz um arquivo `.c` que inclui `runtime/cobrt.h`, e o `gcc` gera o executável. Comando: `py cobc.py programas/CALCMD01.cbl --run`.

**Pré-processador.** Expande `COPY NOME.` procurando o copybook ao lado do fonte e em `copybooks/`. Se não acha, é erro. Também trata blocos de conflito do git (`<<<<<<<`, `=======`, `>>>>>>>`), que aparecem em um dos programas de teste (`CAD0005A.cbl`): mantém o lado HEAD e emite um aviso.

**Severidades.** As mensagens usam os níveis da especificação (seção 6): `I`, `W`, `E` e `S`. Erro (`E`) ou grave (`S`) impede a geração de código, como pede a especificação.

### 3.2 Análise sintática

O parser é de descida recursiva, escrito à mão sobre o fluxo de tokens do léxico, e segue `<Program> ::= <IdentificationDivision> [<EnvironmentDivision>] [<DataDivision>] <ProcedureDivision>`. Ele produz uma árvore sintática abstrata (AST) com:

- ENVIRONMENT: `SELECT ... ASSIGN TO ... ORGANIZATION ... FILE STATUS`, `DECIMAL-POINT IS COMMA`.
- DATA: `FILE SECTION` com `FD`, `WORKING-STORAGE`, `LINKAGE`; níveis 01 a 49, 77 e 88; `PIC`, `USAGE`, `VALUE`, `OCCURS ... INDEXED BY`, `REDEFINES`, `FILLER`.
- PROCEDURE: seções e parágrafos, `DISPLAY`, `ACCEPT`, `MOVE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `COMPUTE` (com `ROUNDED` e `ON SIZE ERROR`), `IF/ELSE`, `EVALUATE`, `PERFORM` (parágrafo, `THRU`, `UNTIL`, `VARYING`, `TIMES` e em linha), `GO TO`, `SEARCH`, `STRING`, `UNSTRING`, `INSPECT`, `INITIALIZE`, `SET`, `CALL`, `OPEN/READ/WRITE/CLOSE`, `STOP RUN`, `GOBACK`, `EXIT`, `CONTINUE`.
- Expressões aritméticas com precedência (`**`, depois `* /`, depois `+ -`), condições com `AND`, `OR`, `NOT`, comparações por palavra (`EQUAL`, `GREATER THAN`) ou símbolo, classes (`IS NUMERIC`), nomes de condição (nível 88), subscritos e referência modificada (`NOME(I:2)`).

Um erro sintático é registrado com a linha e o parser recomeça na próxima sentença (ponto), para listar vários erros numa execução. Um `IF` sem `END-IF` fechado por `END-PERFORM` ou por ponto é aceito com aviso `W`, porque aparece em programas reais de teste.

### 3.3 Análise semântica

A tabela de símbolos calcula o tamanho e a posição de cada item (grupos, `OCCURS`, `REDEFINES`), o tipo (alfanumérico, numérico ou editado) e a imagem inicial da memória a partir dos `VALUE`. As quatro verificações da especificação (seção 4) estão implementadas:

1. **Compatibilidade de `MOVE`.** Mover item alfabético (`PIC A`) para numérico (`PIC 9`) é erro. Mover literal não numérico para item numérico gera aviso.
2. **Unicidade de identificadores.** Nome repetido no mesmo grupo (ou entre dois níveis 01) é erro. Nome repetido em grupos diferentes é permitido, mas a referência sem qualificação `OF` é erro de ambiguidade.
3. **Destinos de controle.** `PERFORM` e `GO TO` só podem apontar para parágrafos ou seções declarados.
4. **Associação de arquivos.** `OPEN`, `READ`, `WRITE` e `CLOSE` exigem o `SELECT` em `FILE-CONTROL` e o `FD` com seu registro.

Também são verificados: nome de dados não declarado, operação aritmética sobre item não numérico, `SEARCH` em item que não é tabela e `USING` sem item correspondente na `LINKAGE SECTION`.

**Erros semânticos inseridos.** O arquivo `erros-inseridos/erros_semanticos.cob` tem sete erros. Saída real do compilador:

```text
erros_semanticos.cob:12: [E] identificador 'WS-REPETIDO' duplicado no mesmo escopo (linha 11); só pode ser repetido em grupos diferentes e usado com OF
erros_semanticos.cob:6:  [E] arquivo 'ARQ-SEM-FD' tem SELECT mas não tem FD na DATA DIVISION
erros_semanticos.cob:15: [E] MOVE incompatível: item alfabético (PIC A) 'WS-LETRAS' para item numérico 'WS-NUMERO' (PIC 9(5))
erros_semanticos.cob:16: [E] PERFORM de '9999-NAO-EXISTE': parágrafo/seção não declarado na PROCEDURE DIVISION
erros_semanticos.cob:17: [E] GO TO '8888-TAMBEM-NAO': parágrafo/seção não declarado na PROCEDURE DIVISION
erros_semanticos.cob:18: [E] OPEN em 'ARQ-SEM-SELECT': arquivo sem SELECT em FILE-CONTROL
erros_semanticos.cob:19: [E] nome de dados 'WS-FANTASMA' não declarado
[cobc] 7 erro(s), 0 aviso(s) - compilação interrompida (nenhum código gerado)
```

### 3.4 Geração de código e runtime

**Dados.** A memória do programa é um vetor de bytes em C, inicializado com os `VALUE`, e cada item COBOL é um descritor `fld` (ponteiro, tamanho, tipo, dígitos, escala, sinal). Numéricos `DISPLAY` guardam um dígito ASCII por byte, com o sinal no último byte, como o GnuCOBOL. Campos `COMP` e `COMP-3` também são guardados como `DISPLAY`.

**Aritmética.** Usa decimais de 128 bits (`__int128` com escala), sem `double`. Assim `10 / 3` truncado em duas casas dá `3.33`, e `ROUNDED` arredonda corretamente. Estouro de tamanho trunca os dígitos mais altos, ou executa `ON SIZE ERROR` se houver. Divisão por zero também dispara `ON SIZE ERROR` e deixa o destino intacto.

**Controle de fluxo.** Cada parágrafo vira um rótulo C. `PERFORM` empilha o ponto de retorno e o fim do intervalo e salta para o parágrafo; ao chegar ao fim do intervalo, o fluxo volta. Isso trata `GO TO`, recursão (programas de menu que se chamam) e `PERFORM ... THRU` sobre seções. `PERFORM UNTIL`, `VARYING` e `TIMES` viram laços C.

**Arquivos.** `LINE SEQUENTIAL` com `OPEN INPUT/OUTPUT/EXTEND`, `READ ... AT END`, `WRITE` (sem espaços finais, como o GnuCOBOL) e `CLOSE`, com `FILE STATUS`. Sem `FILE STATUS`, erro de arquivo interrompe o programa com mensagem, como o GnuCOBOL.

**Edição numérica.** Máscaras como `ZZZ.ZZZ.ZZZ,ZZ`, `ZZ,ZZ9.99`, `$$,$$9.99` e `-(5)9.99`, com `DECIMAL-POINT IS COMMA` trocando os papéis de ponto e vírgula. `DISPLAY` de campo numérico mostra o ponto decimal e o sinal (comportamento de "pretty display" do GnuCOBOL).

**Subprogramas.** `CALL 'NOME'` liga automaticamente `NOME.cbl` do mesmo diretório e passa os argumentos por referência. `PROG024A` chama `PROGDATA` assim.

### 3.5 Resultados: programas de teste

Os sete programas entregues pelo professor (`programas/`) compilam sem erro e foram executados com entradas simuladas. Os testes automáticos estão em `testes/test_compilador.py` (`py -m unittest discover -s testes -t .`, 66 testes, incluindo os do léxico).

| Programa | O que exercita | Resultado |
| --- | --- | --- |
| `BUSCA01A` | `READ` em loop até `AT END`, busca por CPF, `DECIMAL-POINT IS COMMA` | Compila e executa. Acha o CPF no arquivo e informa "não encontrado" quando não existe; conta os registros lidos. |
| `CAD0002A` | Subprograma com `LINKAGE`, `COPY COPY002A`, `EVALUATE`, `GO TO`, `INSPECT`, `FUNCTION REVERSE`, referência modificada, `IS NUMERIC` | Compila e executa. Valida nome, idade, data e e-mail; rejeita menor de 18, dia 32 e e-mail inválido. |
| `CAD0004A` | Escrita em arquivo, `PERFORM UNTIL`, `ACCEPT` | Compila e executa. Grava os registros em `CADASTRO.dat` com os tamanhos dos campos. |
| `CAD0005A` | Tabela `OCCURS`, `PERFORM VARYING`, `EVALUATE`, `DISPLAY ... WITH NO ADVANCING`, literal em continuação de linha, arquivo lido e regravado | Compila e executa. Cadastra, lista e detecta telefone repetido. O fonte tem marcas de conflito do git; o compilador mantém o lado HEAD e avisa. |
| `CAIXAREG` | `COMPUTE`, `ADD`, máscara `ZZZ.ZZZ.ZZZ,ZZ`, `PERFORM UNTIL` | Compila e executa. Total `35,50` e final `32,25` com desconto de `3,25`. |
| `CALCMD01` | `COMPUTE` com divisão, `PERFORM` recursivo de seções, `IF` aninhado | Compila e executa. Soma e média com validação; divisão por zero não altera o destino. |
| `PROG024A` | Menu recursivo, tabela com 50 posições, dois arquivos, `CALL 'PROGDATA'`, `COPY COD001A` | Compila e executa. Cadastra, empresta, devolve, lista e busca livros; grava `BIBLIOTECA.dat` e o log `BIBLIOTECA.txt`. |

Observações sobre a execução:

- `CAD0002A` é um subprograma (`PROCEDURE DIVISION USING`). O compilador gera um `main` de teste que passa uma área zerada como parâmetro.
- Os copybooks `COPY002A` e `COD001A` e o programa `PROGDATA` vêm do repositório Coboldicas, citado no enunciado.
- Programas que abrem arquivo de entrada precisam do arquivo (`CADASTRO2.dat`, `CADAGENDA.dat`, `BIBLIOTECA.dat`) na pasta de execução. Sem ele, o programa para com erro de arquivo, como no GnuCOBOL sem `FILE STATUS`.

### 3.5.1 Validação contra o GnuCOBOL 3.2

Para não depender só do nosso julgamento, a execução foi comparada com a do GnuCOBOL 3.2.0 (`cobc`, pacote `gnucobol` do Debian, num container Docker). O script `scripts/comparar_gnucobol.py` compila cada programa nos dois lados (o nosso por COBOL → C → `gcc`, o de referência por `cobc -x`), roda com o mesmo `stdin` e os mesmos arquivos de entrada e compara a saída padrão e os arquivos gerados byte a byte. Tudo roda no Docker: a imagem `gnucobol-ref` é construída a partir de `scripts/gnucobol/Dockerfile` (Debian com GnuCOBOL 3.2.0, `gcc` e Python) e removida com `--limpar`, sem instalar nada na máquina. O teste automatizado é `testes/test_gnucobol.py`, e `--testes` roda a suíte `unittest` inteira no container, inclusive os testes de execução que dependem do `gcc`.

Foram 16 casos: os sete programas do enunciado (com cenários de sucesso e de erro, como CPF encontrado e não encontrado, desconto com e sem valor, divisão por zero e telefone repetido), mais um programa de aritmética e edição numérica (`testes/cobol/aritmetica.cbl`), um programa que chama o subprograma `CAD0002A` e um de regressão com os defeitos achados nos programas do Coboldicas (`testes/cobol/regressao_coboldicas.cbl`). Os 16 casos produziram saída e arquivos idênticos nos dois compiladores.

A comparação cobre também o formato de `DISPLAY` de campos numéricos (ponto decimal e sinal), as máscaras de edição e o truncamento sem `ON SIZE ERROR`. O GnuCOBOL se recusa a compilar `CAD0005A.cbl` por causa das marcas de conflito do git (`<<<<<<< HEAD`); o nosso compilador tolera, mantém o lado HEAD e avisa. A comparação do `CAD0005A` foi feita com o arquivo já sem as marcas.

### 3.6 Programas do repositório Coboldicas

O professor escolherá três programas semelhantes de `github.com/Coboldicas/codigo_fonte_cobol`. Para ter confiança, o grupo passou o compilador por todos os 83 fontes `.cbl` e `.cob` do repositório, da análise léxica até a geração de C:

- **74 de 83** passam por todas as fases e o `gcc` compila o C gerado sem erro.
- **9 falham**, por estes motivos:

| Programa | Motivo | Tipo |
| --- | --- | --- |
| `CLIESQL01` | arquivo vazio (0 bytes) | defeito do fonte |
| `TELABMS` | mapa BMS do CICS (macros de assembler), não é COBOL | não é COBOL |
| `ASCII001` | usa `WS-CODIGO` sem declarar; o compilador acusa o erro, como deve | defeito do fonte |
| `PROG006A`, `clientes-sql` | `EXEC SQL` (precisa de pré-compilador SQL) | fora do escopo |
| `PROGTEST` | `SCREEN SECTION` (telas) | fora do escopo |
| `PROG018A` | comando `ALTER`, removido do COBOL moderno | não implementado |
| `GAMESNAK` | `FUNCTION RANDOM` e posicionamento de tela | não implementado |
| `CBREAKEX` | código a partir da coluna 7, que não é formato fixo válido | defeito do fonte |

Nenhum desses nove é do tipo dos sete programas do enunciado (menus, cadastros, arquivos de texto, cálculos).

### 3.6.1 Execução dos programas do Coboldicas contra o GnuCOBOL

Compilar sem erro não prova que o programa executa certo. Os 74 programas aceitos foram compilados e executados nos dois lados (nosso compilador e `cobc` 3.2.0, ambos no Docker) com as mesmas oito entradas: vazia, um roteiro de menu e seis sequências pseudoaleatórias de nomes, números, datas e S/N. O GnuCOBOL compila sozinho 63 deles. Dos outros 11, oito são subprogramas com `USING` (cobertos pelos programas que os chamam), `PROG008A` e `PROG017A` têm sintaxe que o GnuCOBOL recusa e `PROGVSAM` é arquivo indexado.

A primeira rodada achou três defeitos nossos, todos corrigidos e cobertos por `testes/cobol/regressao_coboldicas.cbl`:

1. **`ACCEPT` em campo numérico.** O GnuCOBOL corta a linha digitada ao tamanho do campo antes de converter, e texto inválido zera o campo (com casas decimais) ou vale só até o primeiro caractere inválido (sem casas, e zera se houver dígito depois). O nosso convertia a linha inteira. A regra foi medida contra o GnuCOBOL em 34 entradas de teste, e afetava `CAIXAREG` e `CALCMD01` com entradas fora do esperado.
2. **`SEARCH ALL`** sem `SET` prévio do índice abortava com "subscrito fora do intervalo" quando o valor não existia.
3. **`MOVE CORRESPONDING`** não estava implementado: era tratado como `MOVE` de grupo e gravava nos deslocamentos errados quando o destino tem `FILLER`.

Depois das correções, 60 dos 63 programas dão saída idêntica em todas as entradas. Em 20 execuções o GnuCOBOL entra em laço infinito quando a entrada acaba (`ACCEPT` sem dados), e o nosso runtime encerra com erro depois de três leituras vazias; elas não contam como diferença. Os três que diferem não têm relação com o compilador: `PROG016A` imprime a hora com centésimos de segundo, `TESTE002` usa `DISPLAY ... AT` e o GnuCOBOL falha sem terminal, e `REL0002A` depende de um arquivo de entrada ausente (num `OPEN INPUT ... OUTPUT ...` de dois arquivos o GnuCOBOL só acusa o erro no fim do comando, e o nosso aborta no primeiro).

### 3.7 Limitações

- Sem arquivos indexados ou relativos, `SORT`, `EXEC SQL`, `SCREEN SECTION`, `ALTER` e tabelas de duas dimensões.
- `COMP` e `COMP-3` são guardados como `DISPLAY`: o resultado dos cálculos é o mesmo, mas o layout em memória é diferente.
- `INSPECT ... BEFORE/AFTER` é ignorado, com aviso.
- Arquivos: só `LINE SEQUENTIAL`. Como no GnuCOBOL, `OPEN INPUT`, `OPEN I-O` e `OPEN EXTEND` em arquivo que não existe falham (status 35), salvo `SELECT OPTIONAL`.

### 3.8 Ferramentas de IA (etapa final)

**Ferramenta de IA.** O grupo definiu a estratégia (gerar código C e compilar com `gcc`, a divisão em pré-processador, parser, análise semântica, gerador e runtime, as quatro verificações semânticas da especificação, o suporte aos sete programas do enunciado e os casos de `erros-inseridos/erros_semanticos.cob`) e conferiu cada saída contra a especificação e os programas. O Claude Code, com o modelo Claude Sonnet 5.5, foi usado como apoio: gerou o rascunho do parser, da análise semântica, do gerador de C, do runtime e dos testes, compilou e executou os sete programas com entradas simuladas, corrigiu os erros que apareceram (por exemplo, a edição `$$,$$9.99` e o truncamento sem `ON SIZE ERROR`) e rodou o compilador nos 83 fontes do repositório Coboldicas para achar construções que faltavam. O código está no repositório do grupo.
