       IDENTIFICATION DIVISION.
       PROGRAM-ID. REGR1.
      * Regressoes achadas ao comparar com o GnuCOBOL nos programas do
      * repositorio Coboldicas: ACCEPT numerico, SEARCH ALL e MOVE CORR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 U            PIC 9(6).
       01 V            PIC 9(4)V99.
       01 W            PIC 99.
       01 CODIGO       PIC 9(3).
       01 TAB.
          05 ITEM OCCURS 3 TIMES ASCENDING KEY IS ID-ITEM
                INDEXED BY IX.
             10 ID-ITEM    PIC 9(3).
             10 NOME-ITEM  PIC X(5).
       01 G1.
          05 A    PIC 99 VALUE 8.
          05 B    PIC 99 VALUE 2.
          05 C    PIC XX VALUE 'AB'.
       01 G2.
          05 A    PIC 99 VALUE ZEROS.
          05 FILLER PIC X VALUE '-'.
          05 B    PIC 99 VALUE ZEROS.
          05 FILLER PIC X VALUE '-'.
          05 C    PIC XX VALUE SPACES.
       PROCEDURE DIVISION.
           ACCEPT U
           ACCEPT V
           ACCEPT W
           DISPLAY 'U=' U ' V=' V ' W=' W
           ACCEPT U
           ACCEPT V
           ACCEPT W
           DISPLAY 'U=' U ' V=' V ' W=' W
           MOVE 101 TO ID-ITEM(1)
           MOVE 'ANA'  TO NOME-ITEM(1)
           MOVE 103 TO ID-ITEM(2)
           MOVE 'BRUNO' TO NOME-ITEM(2)
           MOVE 105 TO ID-ITEM(3)
           MOVE 'CARLA' TO NOME-ITEM(3)
           PERFORM 2 TIMES
              ACCEPT CODIGO
              SEARCH ALL ITEM
                 AT END DISPLAY 'NAO ACHOU ' CODIGO
                 WHEN ID-ITEM(IX) = CODIGO
                    DISPLAY 'ACHOU ' NOME-ITEM(IX)
              END-SEARCH
           END-PERFORM
           MOVE CORRESPONDING G1 TO G2
           DISPLAY 'G2=[' G2 ']'
           STOP RUN.
