       IDENTIFICATION DIVISION.
       PROGRAM-ID. OLA.
       AUTHOR. GRUPO.
      * Exemplo em formato fixo. A area A comeca na coluna 8.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-MENSAGEM PIC X(20) VALUE "OLA, MUNDO".
       01 WS-NUM1 PIC S9(4)V99 VALUE -10.50.
       01 WS-NUM2 PIC 9(4)V99 VALUE 2.5.
       01 WS-RESULTADO PIC S9(6)V99 VALUE ZEROS.
       01 WS-EDITADO PIC ZZ,ZZ9.99.
       01 WS-REGISTRO.
           05 WS-NOME PIC X(15).
           05 WS-IDADE PIC 99.
       PROCEDURE DIVISION.
           DISPLAY WS-MENSAGEM.
           COMPUTE WS-RESULTADO = (WS-NUM1 + WS-NUM2) * 2.
           IF WS-RESULTADO >= 0 AND WS-NUM1 <> 0
               DISPLAY "POSITIVO"
           ELSE
               DISPLAY "OUTRO"
           END-IF.
           MOVE "TEXTO" TO WS-NOME.
           STOP RUN.
