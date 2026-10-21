      * Erros inseridos para o relatorio. Os sete programas originais ficam intactos.
      -    DISPLAY "ORFA".
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ERROS-INSERIDOS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-OK PIC X(10) VALUE "OK".
       01 WS-TEXTO PIC X(10) VALUE "sem fechar.
       01 WS-TEXTO2 PIC X(5) VALUE 'tambem.
       01 WS-NOME-MUITO-GRANDE-DEMAIS-PARA-COBOL PIC X(5).
       01 WS-VAZIO PIC .
       01 WS-ABERTA PIC 9(4.
       01 WS-PRECO PIC 9(4) VALUE 10.
       PROCEDURE DIVISION.
           DISPLAY A--B.
           DISPLAY "CERTO" # "ERRADO".
           DISPLAY @.
           DISPLAY $.
      XDISPLAY "INDICADOR".
ABC
           STOP RUN.
