       IDENTIFICATION DIVISION.
       PROGRAM-ID. ARITM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 A        PIC 9(3) VALUE 5.
       01 B        PIC S9(3)V99 VALUE -12.5.
       01 C        PIC 9(4)V99 VALUE 0.
       01 D        PIC 99 VALUE 0.
       01 E        PIC S9(5) VALUE 0.
       01 ED1      PIC ZZ,ZZ9.99.
       01 ED2      PIC -(5)9.99.
       01 ED3      PIC $$,$$9.99.
       01 ED4      PIC 9(4)V99 VALUE 1234.5.
       01 X5       PIC X(5) VALUE 'ABCDEFG'.
       01 R        PIC 9(3)V9 VALUE 0.
       PROCEDURE DIVISION.
           DISPLAY 'A=' A ' B=' B.
           ADD 1 TO A.
           ADD A B GIVING C.
           DISPLAY 'C=' C.
           COMPUTE C = 10 / 3.
           DISPLAY 'C=' C.
           COMPUTE C ROUNDED = 10 / 3.
           DISPLAY 'C=' C.
           COMPUTE D = 123.
           DISPLAY 'D=' D.
           COMPUTE D = 7 * 8 - 60 / 4.
           DISPLAY 'D=' D.
           COMPUTE E = 2 ** 10 - 1.
           DISPLAY 'E=' E.
           SUBTRACT 2000 FROM E.
           DISPLAY 'E=' E.
           MOVE 1234.5 TO ED1.
           DISPLAY 'ED1=[' ED1 ']'.
           MOVE 0 TO ED1.
           DISPLAY 'ED1=[' ED1 ']'.
           MOVE -3.456 TO ED2.
           DISPLAY 'ED2=[' ED2 ']'.
           MOVE 12.3 TO ED3.
           DISPLAY 'ED3=[' ED3 ']'.
           MOVE ED4 TO ED1.
           DISPLAY 'ED1=[' ED1 ']'.
           DISPLAY 'X5=' X5.
           MOVE 'AB' TO X5.
           DISPLAY 'X5=[' X5 ']'.
           MOVE 123456 TO D.
           DISPLAY 'D=' D.
           DIVIDE 7 BY 2 GIVING R.
           DISPLAY 'R=' R.
           DIVIDE 7 BY 0 GIVING R ON SIZE ERROR DISPLAY 'DIV0'.
           MULTIPLY 3 BY A.
           DISPLAY 'A=' A.
           IF A > 10 AND NOT A = 18 DISPLAY 'GT10' ELSE DISPLAY 'LE10'.
           IF X5 = 'AB' DISPLAY 'IGUAL' END-IF.
           STOP RUN.
