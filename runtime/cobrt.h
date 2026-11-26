/* Runtime COBOL em C (cabecalho unico, incluido pelo codigo gerado).
 *
 * Modelo de dados: todo item COBOL e um "fld" (ponteiro para bytes + descritor).
 * Numericos DISPLAY guardam um digito ASCII por byte; sinal em "overpunch" no
 * ultimo byte (como o GnuCOBOL). Aritmetica usa decimais de 128 bits.
 */
#ifndef COBRT_H
#define COBRT_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>

typedef __int128 i128;

typedef struct {
    unsigned char *p;
    int len;
    char type;        /* 'A' alfanumerico/grupo, 'N' numerico, 'E' editado, 'F' figurativa */
    short digits;     /* digitos (N) / codigo da figurativa (F) */
    short scale;
    char sign;
    int stride;       /* tamanho do elemento da tabela (OCCURS) que contem o item */
    const char *pic;  /* picture de itens editados; "L" marca literal numerico */
} fld;

typedef struct { i128 v; int sc; } dec;

enum { F_SPACE, F_ZERO, F_HIGH, F_LOW, F_QUOTE, F_ALL };

static int g_comma = 0;         /* DECIMAL-POINT IS COMMA */
static int g_eof_count = 0;
#define DPCH() (g_comma ? ',' : '.')
#define GRCH() (g_comma ? '.' : ',')

static void rt_fatal(const char *msg) {
    fflush(stdout);
    fprintf(stderr, "cobrt: erro de execucao: %s\n", msg);
    exit(1);
}

/* ---------- temporarios ---------- */
#define POOL_N 128
#define POOL_SZ 2048
static unsigned char g_pool[POOL_N][POOL_SZ];
static int g_pool_i = 0;
static unsigned char *tmpbuf(void) {
    g_pool_i = (g_pool_i + 1) % POOL_N;
    return g_pool[g_pool_i];
}

/* ---------- literais e figurativas ---------- */
static fld lit_a(const char *s) {
    fld f = {(unsigned char *)s, (int)strlen(s), 'A', 0, 0, 0, 0, NULL};
    return f;
}
static fld lit_al(const char *s, int n) {
    fld f = {(unsigned char *)s, n, 'A', 0, 0, 0, 0, NULL};
    return f;
}
static fld fig(int kind) {
    fld f = {NULL, 1, 'F', (short)kind, 0, 0, 0, NULL};
    return f;
}
static fld fig_all(const char *s) {
    fld f = {(unsigned char *)s, (int)strlen(s), 'F', F_ALL, 0, 0, 0, NULL};
    return f;
}
static unsigned char figchar(int kind) {
    switch (kind) {
    case F_SPACE: return ' ';
    case F_ZERO: return '0';
    case F_HIGH: return 0xFF;
    case F_LOW: return 0x00;
    case F_QUOTE: return '"';
    }
    return ' ';
}

/* ---------- decimais ---------- */
static i128 p10(int n) {
    i128 r = 1;
    while (n-- > 0) r *= 10;
    return r;
}
static dec D(i128 v, int sc) { dec d = {v, sc}; return d; }
static void d_align(dec *a, dec *b) {
    if (a->sc < b->sc) { a->v *= p10(b->sc - a->sc); a->sc = b->sc; }
    else if (b->sc < a->sc) { b->v *= p10(a->sc - b->sc); b->sc = a->sc; }
}
static dec d_add(dec a, dec b) { d_align(&a, &b); a.v += b.v; return a; }
static dec d_sub(dec a, dec b) { d_align(&a, &b); a.v -= b.v; return a; }
static dec d_neg(dec a) { a.v = -a.v; return a; }
static dec d_mul(dec a, dec b) {
    dec r = {a.v * b.v, a.sc + b.sc};
    while (r.sc > 18) { r.v /= 10; r.sc--; }
    return r;
}
static int g_divzero = 0;
static dec d_div(dec a, dec b) {
    dec r = {0, 0};
    if (b.v == 0) { g_divzero = 1; return r; }
    int extra = 18;
    /* (a.v / 10^a.sc) / (b.v / 10^b.sc) com 'extra' casas */
    i128 num = a.v;
    int sc = a.sc - b.sc + extra;
    if (sc < 0) { num /= p10(-sc); sc = 0; }
    else num *= p10(extra);
    r.v = num / b.v;
    r.sc = a.sc - b.sc + extra;
    if (r.sc < 0) { r.v *= p10(-r.sc); r.sc = 0; }
    return r;
}
static dec d_pow(dec a, dec b) {
    dec one = {1, 0};
    /* expoente inteiro nao negativo */
    long n = (long)(b.v / p10(b.sc));
    if (n < 0) {
        dec r = one;
        for (long i = 0; i < -n; i++) r = d_mul(r, a);
        return d_div(one, r);
    }
    dec r = one;
    for (long i = 0; i < n; i++) r = d_mul(r, a);
    return r;
}
static int d_cmp(dec a, dec b) {
    d_align(&a, &b);
    return a.v < b.v ? -1 : (a.v > b.v ? 1 : 0);
}
static long d_int(dec a) { return (long)(a.v / p10(a.sc)); }

/* ---------- leitura de valores ---------- */
static dec parse_text(const unsigned char *p, int len) {
    dec d = {0, 0};
    int neg = 0, seen_dp = 0;
    for (int i = 0; i < len; i++) {
        unsigned char c = p[i];
        if (c >= '0' && c <= '9') {
            d.v = d.v * 10 + (c - '0');
            if (seen_dp) d.sc++;
        } else if (c == '-') neg = 1;
        else if (c == (unsigned char)DPCH() && !seen_dp) seen_dp = 1;
    }
    if (neg) d.v = -d.v;
    return d;
}
static dec get_dec(fld f) {
    dec d = {0, 0};
    if (f.type == 'N') {
        int neg = 0;
        for (int i = 0; i < f.len; i++) {
            unsigned char c = f.p[i];
            int dg = 0;
            if (c >= '0' && c <= '9') dg = c - '0';
            else if (c >= 'p' && c <= 'y') { dg = c - 'p'; neg = 1; }
            else if (c == '-') neg = 1;
            d.v = d.v * 10 + dg;
        }
        if (neg) d.v = -d.v;
        d.sc = f.scale;
        return d;
    }
    if (f.type == 'F') {
        return d;
    }
    if (f.type == 'E') {
        /* editado: extrai digitos, ponto decimal e sinal */
        int seen_dp = 0, neg = 0;
        for (int i = 0; i < f.len; i++) {
            unsigned char c = f.p[i];
            if (c >= '0' && c <= '9') { d.v = d.v * 10 + (c - '0'); if (seen_dp) d.sc++; }
            else if (c == (unsigned char)DPCH()) seen_dp = 1;
            else if (c == '-') neg = 1;
            else if (c == 'C' || c == 'D') neg = 1;
        }
        if (neg) d.v = -d.v;
        return d;
    }
    return parse_text(f.p, f.len);
}
static long get_int(fld f) { return d_int(get_dec(f)); }
static dec dlit(long long v, int sc) { return D(v, sc); }
static dec dlits(const char *s) {
    dec d = {0, 0};
    int neg = 0, seen = 0;
    for (; *s; s++) {
        if (*s == '-') neg = 1;
        else if (*s == '.') seen = 1;
        else if (*s >= '0' && *s <= '9') { d.v = d.v * 10 + (*s - '0'); if (seen) d.sc++; }
    }
    return neg ? d_neg(d) : d;
}
static dec dlen(fld f) { return D(f.len, 0); }

/* ---------- escrita de numericos ---------- */
static void put_digits(fld f, i128 mag, int neg) {
    /* escreve 'mag' (inteiro, ja na escala do campo) em f.len digitos */
    for (int i = f.len - 1; i >= 0; i--) {
        f.p[i] = (unsigned char)('0' + (int)(mag % 10));
        mag /= 10;
    }
    if (neg && f.sign && f.len > 0) f.p[f.len - 1] = (unsigned char)(f.p[f.len - 1] - '0' + 'p');
}

static void fmt_edit(fld f, dec v);

/* guarda dec em campo numerico/editado. rounded: arredonda; se=ponteiro p/ erro de tamanho */
static void st(fld f, dec d, int rounded, int *se) {
    if (f.type == 'A') { /* alfanumerico recebe digitos */
        fld t; unsigned char *b = tmpbuf();
        t.p = b; t.len = 18; t.type = 'N'; t.digits = 18; t.scale = 0; t.sign = 0; t.stride = 0; t.pic = NULL;
        st(t, d, 0, NULL);
        for (int i = 0; i < f.len; i++) f.p[i] = (i < 18) ? b[i] : ' ';
        return;
    }
    int sc = f.type == 'E' ? 0 : f.scale;
    if (f.type == 'E') {
        const char *q = f.pic; int seen = 0, dd = 0;
        for (; *q; q++) {
            if (*q == DPCH()) seen = 1;
            else if (seen && (*q == '9' || *q == 'Z' || *q == '*')) dd++;
            else if (seen && *q == '(') { dd--; dd += atoi(q + 1); }
        }
        sc = dd;
    }
    int neg = d.v < 0;
    i128 v = neg ? -d.v : d.v;
    if (d.sc > sc) {
        i128 div = p10(d.sc - sc);
        i128 q = v / div, r = v % div;
        if (rounded && r * 2 >= div) q++;
        v = q;
    } else if (d.sc < sc) v *= p10(sc - d.sc);
    int dig = f.type == 'E' ? 38 : f.digits;
    if (f.type == 'E') {
        /* contagem de posicoes numericas na picture */
        int cnt = 0;
        for (const char *q = f.pic; *q; q++) {
            if (*q == '(') { cnt += atoi(q + 1) - 1; }
            else if (*q == '9' || *q == 'Z' || *q == '*') cnt++;
            else if ((*q == '+' || *q == '-' || *q == '$')) cnt++;
        }
        dig = cnt;
    }
    if (dig < 38 && v >= p10(dig)) {
        if (se) { *se = 1; if (se) return; }
        v %= p10(dig);
    }
    if (f.type == 'E') {
        dec t = {neg ? -v : v, sc};
        fmt_edit(f, t);
        return;
    }
    if (v == 0) neg = 0;
    put_digits(f, v, neg);
}

/* ---------- edicao numerica ---------- */
static void fmt_edit(fld f, dec v) {
    char pic[256]; int n = 0;
    for (const char *q = f.pic; *q && n < 250; q++) {
        if (*q == '(') {
            int rep = atoi(q + 1);
            char last = n ? pic[n - 1] : ' ';
            while (*q && *q != ')') q++;
            for (int i = 1; i < rep && n < 250; i++) pic[n++] = last;
        } else pic[n++] = (char)toupper((unsigned char)*q);
    }
    pic[n] = 0;
    char dp = DPCH(), gr = GRCH();
    /* regiao de simbolo flutuante (+, - ou $ repetidos, virgulas permitidas entre eles) */
    int fl_start = -1, fl_end = -1; char flc = 0;
    for (int i = 0; i < n; i++) {
        char c = pic[i];
        if (c == '+' || c == '-' || c == '$') {
            int j = i + 1;
            while (j < n && pic[j] == gr) j++;
            if (j < n && pic[j] == c) {
                fl_start = i; flc = c; fl_end = i;
                for (int k = i; k < n && (pic[k] == c || pic[k] == gr); k++) if (pic[k] == c) fl_end = k;
            }
            break;
        }
    }
    int ndig = 0, nfrac = 0, seen = 0;
    for (int i = 0; i < n; i++) {
        char c = pic[i];
        if (c == dp) seen = 1;
        int isdig = (c == '9' || c == 'Z' || c == '*') || (fl_start >= 0 && c == flc && i > fl_start && i <= fl_end);
        if (isdig) { ndig++; if (seen) nfrac++; }
    }
    int neg = v.v < 0;
    i128 mag = neg ? -v.v : v.v;
    if (v.sc > nfrac) mag /= p10(v.sc - nfrac); else mag *= p10(nfrac - v.sc);
    char dig[64];
    for (int i = ndig - 1; i >= 0; i--) { dig[i] = (char)('0' + (int)(mag % 10)); mag /= 10; }
    int allzero = 1;
    for (int i = 0; i < ndig; i++) if (dig[i] != '0') allzero = 0;
    if (allzero) neg = 0;
    char fill = ' ';
    for (int i = 0; i < n; i++) if (pic[i] == '*') fill = '*';
    int suppress = 0;
    for (int i = 0; i < n; i++) {
        char c = pic[i];
        if (c == 'Z' || c == '*') { suppress = 1; break; }
        if (c == '9') break;
        if (fl_start >= 0 && i == fl_start) { suppress = 1; break; }
    }
    char out[256]; int on = 0, di = 0, intdig = ndig - nfrac;
    char flsign = flc == '$' ? '$' : (neg ? '-' : (flc == '+' ? '+' : ' '));
    for (int i = 0; i < n; i++) {
        char c = pic[i];
        int in_fl = fl_start >= 0 && i >= fl_start && i <= fl_end && c == flc;
        if (in_fl) {
            if (i == fl_start) out[on++] = ' ';
            else {
                char d = dig[di++];
                if (suppress && d == '0' && di <= intdig) out[on++] = ' ';
                else {
                    if (suppress) { out[on - 1] = flsign; suppress = 0; }
                    out[on++] = d;
                }
            }
        } else if (c == '9') {
            if (suppress && fl_start >= 0 && i > fl_end) out[on - 1] = flsign;
            out[on++] = dig[di++]; suppress = 0;
        } else if (c == 'Z' || c == '*') {
            char d = dig[di++];
            if (suppress && d == '0') out[on++] = fill;
            else { out[on++] = d; suppress = 0; }
        } else if (c == dp) out[on++] = dp;
        else if (c == gr) out[on++] = suppress ? (fill == '*' ? '*' : ' ') : gr;
        else if (c == 'B') out[on++] = ' ';
        else if (c == '0') out[on++] = '0';
        else if (c == '/') out[on++] = '/';
        else if (c == '+') out[on++] = neg ? '-' : '+';
        else if (c == '-') out[on++] = neg ? '-' : ' ';
        else if (c == '$') out[on++] = '$';
        else if (c == 'C' && i + 1 < n && pic[i + 1] == 'R') { out[on++] = neg ? 'C' : ' '; out[on++] = neg ? 'R' : ' '; i++; }
        else if (c == 'D' && i + 1 < n && pic[i + 1] == 'B') { out[on++] = neg ? 'D' : ' '; out[on++] = neg ? 'B' : ' '; i++; }
        else if (c == 'V' || c == 'S' || c == 'P') { }
        else out[on++] = c;
    }
    if (allzero && suppress) {
        for (int i = 0; i < on; i++) if (out[i] != '*') out[i] = (fill == '*') ? '*' : ' ';
    }
    for (int i = 0; i < f.len; i++) f.p[i] = (i < on) ? (unsigned char)out[i] : ' ';
}

/* ---------- MOVE ---------- */
static void mv_fill(fld d, unsigned char c) { memset(d.p, c, (size_t)d.len); }

static void mv(fld d, fld s) {
    if (s.type == 'F') {
        if (d.type == 'N') {
            if (s.digits == F_ZERO) { mv_fill(d, '0'); }
            else mv_fill(d, '0');
            return;
        }
        if (d.type == 'E') { dec z = {0, 0}; st(d, z, 0, NULL); return; }
        if (s.digits == F_ALL) {
            for (int i = 0; i < d.len; i++) d.p[i] = s.p[i % s.len];
        } else mv_fill(d, figchar(s.digits));
        return;
    }
    if (d.type == 'A') {
        if (s.type == 'N') {
            /* numerico para alfanumerico: digitos sem sinal nem ponto */
            for (int i = 0; i < d.len; i++) {
                unsigned char c = i < s.len ? s.p[i] : ' ';
                if (c >= 'p' && c <= 'y') c = (unsigned char)(c - 'p' + '0');
                d.p[i] = c;
            }
            if (s.pic && s.pic[0] == 'L') { /* literal: alinha a esquerda */ }
            return;
        }
        if (d.p == s.p && d.len == s.len) return;
        unsigned char *tmp = tmpbuf();
        int n = s.len < POOL_SZ ? s.len : POOL_SZ;
        memcpy(tmp, s.p, (size_t)n);
        for (int i = 0; i < d.len; i++) d.p[i] = i < n ? tmp[i] : ' ';
        return;
    }
    /* destino numerico ou editado */
    dec v = get_dec(s);
    if (d.type == 'N' || d.type == 'E') st(d, v, 0, NULL);
}

/* ---------- comparacao ---------- */
static int cmp_fig(fld a, fld f) {
    /* compara 'a' com figurativa f; retorna -1,0,1 */
    if (a.type == 'N' && f.digits == F_ZERO) {
        dec d = get_dec(a);
        return d.v < 0 ? -1 : (d.v > 0 ? 1 : 0);
    }
    for (int i = 0; i < a.len; i++) {
        unsigned char c = a.p[i];
        unsigned char x = f.digits == F_ALL ? f.p[i % f.len] : figchar(f.digits);
        if (c != x) return c < x ? -1 : 1;
    }
    return 0;
}
static int cmp(fld a, fld b) {
    if (b.type == 'F' && a.type == 'F') return 0;
    if (b.type == 'F') return cmp_fig(a, b);
    if (a.type == 'F') return -cmp_fig(b, a);
    int na = a.type == 'N' || a.type == 'E';
    int nb = b.type == 'N' || b.type == 'E';
    if (na && nb) return d_cmp(get_dec(a), get_dec(b));
    int n = a.len > b.len ? a.len : b.len;
    for (int i = 0; i < n; i++) {
        unsigned char x = i < a.len ? a.p[i] : ' ';
        unsigned char y = i < b.len ? b.p[i] : ' ';
        if (x >= 'p' && x <= 'y' && a.type == 'N') x = (unsigned char)(x - 'p' + '0');
        if (y >= 'p' && y <= 'y' && b.type == 'N') y = (unsigned char)(y - 'p' + '0');
        if (x != y) return x < y ? -1 : 1;
    }
    return 0;
}
static int is_numeric(fld f) {
    if (f.type == 'F') return 0;
    if (f.len == 0) return 0;
    for (int i = 0; i < f.len; i++) {
        unsigned char c = f.p[i];
        if (c >= '0' && c <= '9') continue;
        if (f.type == 'N' && f.sign && i == f.len - 1 && c >= 'p' && c <= 'y') continue;
        return 0;
    }
    return 1;
}
static int is_alpha(fld f) {
    for (int i = 0; i < f.len; i++) {
        unsigned char c = f.p[i];
        if (!(isalpha(c) || c == ' ')) return 0;
    }
    return 1;
}
static int sign_of(fld f) {
    dec d = get_dec(f);
    return d.v < 0 ? -1 : (d.v > 0 ? 1 : 0);
}

/* ---------- subscritos e modificacao de referencia ---------- */
static fld sub(fld f, long idx) {
    if (idx < 1) rt_fatal("subscrito fora do intervalo (< 1)");
    f.p += (idx - 1) * (long)f.stride;
    return f;
}
static fld refmod(fld f, long start, long len) {
    if (start < 1 || start > f.len) rt_fatal("modificacao de referencia fora do intervalo");
    if (len < 0 || start - 1 + len > f.len) len = f.len - (start - 1);
    f.p += start - 1;
    f.len = (int)len;
    if (f.type == 'N' || f.type == 'E' || f.type == 'F') f.type = 'A';
    return f;
}
static fld refmod_to_end(fld f, long start) { return refmod(f, start, f.len - (start - 1)); }

/* ---------- funcoes intrinsecas ---------- */
static fld fn_reverse(fld f) {
    unsigned char *b = tmpbuf();
    int n = f.len < POOL_SZ ? f.len : POOL_SZ;
    for (int i = 0; i < n; i++) b[i] = f.p[n - 1 - i];
    fld r = {b, n, 'A', 0, 0, 0, 0, NULL};
    return r;
}
static fld fn_upper(fld f) {
    unsigned char *b = tmpbuf();
    int n = f.len < POOL_SZ ? f.len : POOL_SZ;
    for (int i = 0; i < n; i++) b[i] = (unsigned char)toupper(f.p[i]);
    fld r = {b, n, 'A', 0, 0, 0, 0, NULL};
    return r;
}
static fld fn_lower(fld f) {
    unsigned char *b = tmpbuf();
    int n = f.len < POOL_SZ ? f.len : POOL_SZ;
    for (int i = 0; i < n; i++) b[i] = (unsigned char)tolower(f.p[i]);
    fld r = {b, n, 'A', 0, 0, 0, 0, NULL};
    return r;
}
static fld fn_trim(fld f, int mode) { /* 0 ambos, 1 leading, 2 trailing */
    int s = 0, e = f.len;
    if (mode != 2) while (s < e && f.p[s] == ' ') s++;
    if (mode != 1) while (e > s && f.p[e - 1] == ' ') e--;
    if (e == s) { fld r = {(unsigned char *)" ", 1, 'A', 0, 0, 0, 0, NULL}; return r; }
    fld r = {f.p + s, e - s, 'A', 0, 0, 0, 0, NULL};
    return r;
}
static fld lit_n(long long v, int sc);
static fld fn_numval(fld f) {
    dec d = parse_text(f.p, f.len);
    char s[64]; int neg = d.v < 0; i128 m = neg ? -d.v : d.v;
    (void)s;
    unsigned char *b = tmpbuf();
    int n = 18; for (int i = n - 1; i >= 0; i--) { b[i] = (unsigned char)('0' + (int)(m % 10)); m /= 10; }
    if (neg) b[n - 1] = (unsigned char)(b[n - 1] - '0' + 'p');
    fld r = {b, n, 'N', 18, (short)d.sc, 1, 0, NULL};
    return r;
}
static fld fn_current_date(void) {
    unsigned char *b = tmpbuf();
    time_t t = time(NULL); struct tm *tm = localtime(&t);
    snprintf((char *)b, 40, "%04d%02d%02d%02d%02d%02d00+0000", tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday, tm->tm_hour, tm->tm_min, tm->tm_sec);
    fld r = {b, 21, 'A', 0, 0, 0, 0, NULL};
    return r;
}

static fld from_dec(dec d);
static dec d_floor(dec a) {
    if (a.sc == 0) return a;
    i128 p = p10(a.sc);
    i128 q = a.v / p;
    if (a.v < 0 && a.v % p != 0) q--;
    return D(q, 0);
}
static fld fn_ord(fld f) { return from_dec(D(f.len ? f.p[0] + 1 : 0, 0)); }
static fld fn_char(fld f) {
    unsigned char *b = tmpbuf();
    long n = d_int(get_dec(f));
    b[0] = (unsigned char)(n - 1);
    fld r = {b, 1, 'A', 0, 0, 0, 0, NULL};
    return r;
}
static fld fn_mod(fld a, fld b) {
    dec x = get_dec(a), y = get_dec(b);
    if (y.v == 0) return from_dec(D(0, 0));
    dec q = d_floor(d_div(x, y));
    return from_dec(d_sub(x, d_mul(y, q)));
}
static fld fn_rem(fld a, fld b) {
    dec x = get_dec(a), y = get_dec(b);
    if (y.v == 0) return from_dec(D(0, 0));
    dec q = d_div(x, y);
    q.v /= p10(q.sc); q.sc = 0; /* trunca */
    return from_dec(d_sub(x, d_mul(y, q)));
}
static fld fn_abs(fld a) { dec x = get_dec(a); if (x.v < 0) x.v = -x.v; return from_dec(x); }
static fld fn_integer(fld a) { return from_dec(d_floor(get_dec(a))); }
static fld fn_integer_part(fld a) { dec x = get_dec(a); x.v /= p10(x.sc); x.sc = 0; return from_dec(x); }
/* FUNCTION RANDOM [(semente)]: número em [0, 1) com 9 casas decimais */
static unsigned long long rnd_estado = 0;
static fld fn_random(int nargs, fld semente) {
    if (nargs > 0) { dec s = get_dec(semente); i128 v = s.v; for (int i = 0; i < s.sc; i++) v /= 10;
                     rnd_estado = (unsigned long long)(v < 0 ? -v : v) * 2654435761ULL + 1; }
    else if (rnd_estado == 0) rnd_estado = (unsigned long long)time(NULL) * 2654435761ULL + 1;
    rnd_estado = rnd_estado * 6364136223846793005ULL + 1442695040888963407ULL;
    dec d = {(i128)((rnd_estado >> 11) % 1000000000ULL), 9};
    return from_dec(d);
}
static fld fn_sqrt(fld a) {
    dec x = get_dec(a);
    long double v = (long double)x.v;
    for (int i = 0; i < x.sc; i++) v /= 10.0L;
    long double r = 1;
    if (v > 0) { r = v > 1 ? v / 2 : 1; for (int i = 0; i < 80; i++) r = (r + v / r) / 2; } else r = 0;
    long long sc = 1000000000000000LL; /* 15 casas */
    dec d = {(i128)(r * sc), 15};
    return from_dec(d);
}
static fld fn_max(int n, fld *v) { dec m = get_dec(v[0]); for (int i = 1; i < n; i++) { dec x = get_dec(v[i]); if (d_cmp(x, m) > 0) m = x; } return from_dec(m); }
static fld fn_min(int n, fld *v) { dec m = get_dec(v[0]); for (int i = 1; i < n; i++) { dec x = get_dec(v[i]); if (d_cmp(x, m) < 0) m = x; } return from_dec(m); }
static fld fn_sum(int n, fld *v) { dec m = D(0, 0); for (int i = 0; i < n; i++) m = d_add(m, get_dec(v[i])); return from_dec(m); }
static long days_from_civil(long y, long m, long d) {
    y -= m <= 2;
    long era = (y >= 0 ? y : y - 399) / 400;
    long yoe = y - era * 400;
    long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}
static fld fn_integer_of_date(fld f) {
    long v = d_int(get_dec(f));
    long y = v / 10000, m = (v / 100) % 100, d = v % 100;
    return from_dec(D(days_from_civil(y, m, d) - days_from_civil(1601, 1, 1) + 1, 0));
}
static fld fn_date_of_integer(fld f) {
    long z = d_int(get_dec(f)) - 1 + days_from_civil(1601, 1, 1) + 719468;
    long era = (z >= 0 ? z : z - 146096) / 146097;
    long doe = z - era * 146097;
    long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    long y = yoe + era * 400;
    long doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    long mp = (5 * doy + 2) / 153;
    long d = doy - (153 * mp + 2) / 5 + 1;
    long m = mp < 10 ? mp + 3 : mp - 9;
    if (m <= 2) y++;
    return from_dec(D(y * 10000 + m * 100 + d, 0));
}

/* literal numerico em fld */
static fld lit_n(long long v, int sc) {
    unsigned char *b = tmpbuf();
    int neg = v < 0; unsigned long long m = neg ? (unsigned long long)(-v) : (unsigned long long)v;
    char tmp[40]; int n = 0;
    do { tmp[n++] = (char)('0' + m % 10); m /= 10; } while (m);
    while (n < sc + 1) tmp[n++] = '0';
    for (int i = 0; i < n; i++) b[i] = (unsigned char)tmp[n - 1 - i];
    if (neg) b[n - 1] = (unsigned char)(b[n - 1] - '0' + 'p');
    fld r = {b, n, 'N', (short)n, (short)sc, (char)neg, 0, "L"};
    return r;
}
static fld lit_ns(const char *s) {
    dec d = dlits(s);
    int neg = d.v < 0; i128 m = neg ? -d.v : d.v;
    unsigned char *b = tmpbuf();
    char tmp[64]; int n = 0;
    do { tmp[n++] = (char)('0' + (int)(m % 10)); m /= 10; } while (m);
    while (n < d.sc + 1) tmp[n++] = '0';
    for (int i = 0; i < n; i++) b[i] = (unsigned char)tmp[n - 1 - i];
    if (neg) b[n - 1] = (unsigned char)(b[n - 1] - '0' + 'p');
    fld r = {b, n, 'N', (short)n, (short)d.sc, (char)neg, 0, "L"};
    return r;
}
/* resultado de expressao como campo (para MOVE/DISPLAY de expressoes) */
static fld from_dec(dec d) {
    int neg = d.v < 0; i128 m = neg ? -d.v : d.v;
    unsigned char *b = tmpbuf();
    char tmp[64]; int n = 0;
    do { tmp[n++] = (char)('0' + (int)(m % 10)); m /= 10; } while (m);
    while (n < d.sc + 1) tmp[n++] = '0';
    for (int i = 0; i < n; i++) b[i] = (unsigned char)tmp[n - 1 - i];
    if (neg) b[n - 1] = (unsigned char)(b[n - 1] - '0' + 'p');
    fld r = {b, n, 'N', (short)n, (short)d.sc, (char)neg, 0, "L"};
    return r;
}

/* ---------- DISPLAY / ACCEPT ---------- */
static void disp_one(fld f) {
    if (f.type == 'F') {
        if (f.digits == F_ALL) fwrite(f.p, 1, (size_t)f.len, stdout);
        else putchar(figchar(f.digits));
        return;
    }
    if (f.type == 'N') {
        int neg = 0;
        char buf[80]; int n = 0;
        for (int i = 0; i < f.len; i++) {
            unsigned char c = f.p[i];
            if (c >= 'p' && c <= 'y') { c = (unsigned char)(c - 'p' + '0'); neg = 1; }
            buf[n++] = (char)c;
        }
        if (f.pic && f.pic[0] == 'L') {
            if (neg) putchar('-');
            if (f.scale > 0) { fwrite(buf, 1, (size_t)(n - f.scale), stdout); putchar(DPCH()); fwrite(buf + n - f.scale, 1, (size_t)f.scale, stdout); }
            else fwrite(buf, 1, (size_t)n, stdout);
            return;
        }
        /* "pretty display" do GnuCOBOL: sinal (so se o campo tem S) e ponto decimal */
        if (f.sign) putchar(neg ? '-' : '+');
        if (f.scale > 0 && f.scale < n) {
            fwrite(buf, 1, (size_t)(n - f.scale), stdout);
            putchar(DPCH());
            fwrite(buf + n - f.scale, 1, (size_t)f.scale, stdout);
        } else fwrite(buf, 1, (size_t)n, stdout);
        return;
    }
    fwrite(f.p, 1, (size_t)f.len, stdout);
}
/* DISPLAY ... AT LINE l COLUMN c: posiciona o cursor com sequência ANSI do terminal */
static void disp_at(long lin, long col) {
    if (lin < 1) lin = 1;
    if (col < 1) col = 1;
    static int tela_iniciada = 0;
    if (!tela_iniciada) { tela_iniciada = 1; printf("\033[2J"); }  /* limpa a tela na 1a vez */
    printf("\033[%ld;%ldH", lin, col);
}
static void disp_end(int adv) { if (adv) putchar('\n'); fflush(stdout); }

static void acc(fld f) {
    char line[4096];
    fflush(stdout);
    if (!fgets(line, sizeof line, stdin)) {
        if (++g_eof_count > 3) rt_fatal("fim da entrada padrao durante ACCEPT");
        line[0] = 0;
    }
    size_t n = strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
    /* como o GnuCOBOL (cob_accept): para campo numerico DISPLAY a entrada e cortada no tamanho
       do campo (os primeiros caracteres), antes da conversao */
    if (f.type == 'N') {
        if ((int)n > f.len) n = (size_t)f.len;
        /* entrada nao numerica (medido contra o GnuCOBOL 3.2): em campo com casas decimais qualquer
           caractere invalido zera o campo; sem casas, vale o prefixo valido, a menos que haja
           digitos depois do caractere invalido (ai zera). O sinal so vale no inicio. */
        char dp = DPCH(), ns = dp == ',' ? '.' : ',';
        size_t i = 0; int seen_dp = 0, zero = 0;
        while (i < n && line[i] == ' ') i++;
        if (i < n && (line[i] == '+' || line[i] == '-')) i++;
        for (size_t j = i; j < n && !zero; j++) {
            unsigned char c = (unsigned char)line[j];
            if (c >= '0' && c <= '9') continue;
            if (c == ' ' || c == (unsigned char)ns) continue;
            if (c == (unsigned char)dp && !seen_dp) { seen_dp = 1; continue; }
            if (f.scale > 0) { zero = 1; break; }
            if (c != (unsigned char)dp)
                for (size_t k = j + 1; k < n; k++) if (line[k] >= '0' && line[k] <= '9') { zero = 1; break; }
            if (!zero) n = j;
            break;
        }
        if (zero) { line[0] = '0'; n = 1; }
    }
    mv(f, lit_al(line, (int)n));
}
static void acc_date(fld f, int kind) { /* 0 DATE yymmdd, 1 TIME hhmmsscc, 2 DAY yyddd, 3 DAY-OF-WEEK, 4 YYYYMMDD */
    char b[32]; time_t t = time(NULL); struct tm *tm = localtime(&t);
    if (kind == 0) snprintf(b, sizeof b, "%02d%02d%02d", tm->tm_year % 100, tm->tm_mon + 1, tm->tm_mday);
    else if (kind == 1) snprintf(b, sizeof b, "%02d%02d%02d00", tm->tm_hour, tm->tm_min, tm->tm_sec);
    else if (kind == 2) snprintf(b, sizeof b, "%02d%03d", tm->tm_year % 100, tm->tm_yday + 1);
    else if (kind == 5) snprintf(b, sizeof b, "%04d%03d", tm->tm_year + 1900, tm->tm_yday + 1);
    else if (kind == 3) snprintf(b, sizeof b, "%d", tm->tm_wday == 0 ? 7 : tm->tm_wday);
    else snprintf(b, sizeof b, "%04d%02d%02d", tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday);
    mv(f, lit_a(b));
}

/* ---------- arquivos LINE SEQUENTIAL ---------- */
typedef struct {
    FILE *fp;
    const char *name;
    fld *path_fld;     /* nome dinamico (ASSIGN TO identificador) */
    fld rec;           /* area do registro */
    int mode;          /* 0 fechado, 1 input, 2 output, 3 extend, 4 i-o */
    fld *status;       /* FILE STATUS */
    int has_status;
    int optional;      /* SELECT OPTIONAL */
    char st[3];
} cobfile;

static cobfile *g_files[64];
static int g_nfiles = 0;
static void file_reg(cobfile *cf) { if (g_nfiles < 64) g_files[g_nfiles++] = cf; }
static void file_set(cobfile *cf, const char *s) {
    memcpy(cf->st, s, 3);
    if (cf->status) mv(*cf->status, lit_al(s, 2));
}
static void file_err(cobfile *cf, const char *code, const char *msg) {
    file_set(cf, code);
    if (!cf->has_status) {
        fflush(stdout);
        fprintf(stderr, "cobrt: erro de arquivo (status %s): %s (%s)\n", code, msg, cf->name ? cf->name : "?");
        exit(1);
    }
}
static const char *file_path(cobfile *cf, char *buf) {
    if (cf->path_fld) {
        int n = cf->path_fld->len; if (n > 500) n = 500;
        memcpy(buf, cf->path_fld->p, (size_t)n);
        while (n > 0 && buf[n - 1] == ' ') n--;
        buf[n] = 0;
        return buf;
    }
    return cf->name;
}
static void f_open(cobfile *cf, int mode) {
    char b[512];
    if (cf->mode) { file_err(cf, "41", "arquivo ja aberto"); return; }
    const char *path = file_path(cf, b);
    const char *m = mode == 1 ? "rb" : mode == 2 ? "wb" : mode == 3 ? "ab" : "r+b";
    if (mode == 3 || mode == 4 || mode == 1) {
        /* como o GnuCOBOL: EXTEND, I-O e INPUT exigem que o arquivo exista (salvo SELECT OPTIONAL) */
        FILE *t = fopen(path, "rb");
        if (!t) {
            if (!cf->optional) { file_err(cf, "35", "arquivo nao existe"); return; }
            if (mode == 1) { cf->mode = 1; cf->fp = NULL; file_set(cf, "05"); return; }
        } else fclose(t);
    }
    cf->fp = fopen(path, m);
    if (!cf->fp && mode != 1) cf->fp = fopen(path, "w+b");
    if (!cf->fp) { file_err(cf, mode == 1 ? "35" : "37", "nao foi possivel abrir o arquivo"); return; }
    cf->mode = mode;
    file_set(cf, "00");
}
static void f_close(cobfile *cf) {
    if (!cf->mode) { file_err(cf, "42", "arquivo nao esta aberto"); return; }
    if (cf->fp) fclose(cf->fp);
    cf->fp = NULL; cf->mode = 0;
    file_set(cf, "00");
}
/* retorna 1 se leu registro, 0 se fim de arquivo/erro */
static int f_read(cobfile *cf) {
    if (cf->mode != 1 && cf->mode != 4) { file_err(cf, "47", "READ em arquivo nao aberto para entrada"); return 0; }
    char line[8192]; int n = 0, c;
    if (!cf->fp) { file_set(cf, "10"); return 0; }
    c = fgetc(cf->fp);
    if (c == EOF) { file_set(cf, "10"); return 0; }
    while (c != EOF && c != '\n') { if (n < (int)sizeof line - 1) line[n++] = (char)c; c = fgetc(cf->fp); }
    while (n && line[n - 1] == '\r') n--;
    for (int i = 0; i < cf->rec.len; i++) cf->rec.p[i] = i < n ? (unsigned char)line[i] : ' ';
    file_set(cf, "00");
    return 1;
}
static void f_write(cobfile *cf) {
    if (cf->mode != 2 && cf->mode != 3 && cf->mode != 4) { file_err(cf, "48", "WRITE em arquivo nao aberto para saida"); return; }
    int n = cf->rec.len;
    while (n > 0 && cf->rec.p[n - 1] == ' ') n--;
    fwrite(cf->rec.p, 1, (size_t)n, cf->fp);
    fputc('\n', cf->fp);
    file_set(cf, "00");
}
static void files_close_all(void) {
    for (int i = 0; i < g_nfiles; i++)
        if (g_files[i]->mode && g_files[i]->fp) { fclose(g_files[i]->fp); g_files[i]->fp = NULL; g_files[i]->mode = 0; }
}
static void rt_stop(int code) { fflush(stdout); files_close_all(); exit(code); }

/* ---------- INSPECT ---------- */
/* modo: 0 ALL, 1 LEADING, 2 CHARACTERS; retorna ocorrencias */
static long insp_count(fld t, fld pat, int mode) {
    long cnt = 0;
    if (mode == 2) return t.len;
    int pl = pat.type == 'F' ? 1 : pat.len;
    for (int i = 0; i + pl <= t.len;) {
        int ok = 1;
        for (int j = 0; j < pl; j++) {
            unsigned char x = pat.type == 'F' ? figchar(pat.digits) : pat.p[j];
            if (t.p[i + j] != x) { ok = 0; break; }
        }
        if (ok) { cnt++; i += pl; }
        else { if (mode == 1) break; i++; }
    }
    return cnt;
}
/* modo: 0 ALL, 1 LEADING, 2 FIRST, 3 CHARACTERS */
static void insp_replace(fld t, fld pat, fld by, int mode) {
    int pl = pat.type == 'F' ? 1 : pat.len;
    int bl = by.type == 'F' ? 1 : by.len;
    if (mode == 3) { for (int i = 0; i < t.len; i++) t.p[i] = by.type == 'F' ? figchar(by.digits) : by.p[0]; return; }
    for (int i = 0; i + pl <= t.len;) {
        int ok = 1;
        for (int j = 0; j < pl; j++) {
            unsigned char x = pat.type == 'F' ? figchar(pat.digits) : pat.p[j];
            if (t.p[i + j] != x) { ok = 0; break; }
        }
        if (ok) {
            for (int j = 0; j < pl && j < bl; j++) t.p[i + j] = by.type == 'F' ? figchar(by.digits) : by.p[j];
            i += pl;
            if (mode == 2) return;
        } else { if (mode == 1) return; i++; }
    }
}


static void insp_convert(fld t, fld from, fld to) {
    for (int i = 0; i < t.len; i++)
        for (int j = 0; j < from.len && j < to.len; j++)
            if (t.p[i] == from.p[j]) { t.p[i] = to.p[j]; break; }
}

/* UNSTRING: divide src nos delimitadores; devolve numero de campos preenchidos */
static long unstr_run(fld src, fld *dl, int nd, fld *ds, int n) {
    int pos = 0; long filled = 0;
    for (int k = 0; k < n; k++) {
        if (pos > src.len) break;
        int start = pos, end = src.len, dlen = 0;
        for (int i = pos; i < src.len; i++) {
            int hit = 0;
            for (int d = 0; d < nd; d++) {
                int l = dl[d].type == 'F' ? 1 : dl[d].len;
                if (i + l > src.len) continue;
                int ok = 1;
                for (int j = 0; j < l; j++) {
                    unsigned char x = dl[d].type == 'F' ? figchar(dl[d].digits) : dl[d].p[j];
                    if (src.p[i + j] != x) { ok = 0; break; }
                }
                if (ok) { hit = l; break; }
            }
            if (hit) { end = i; dlen = hit; break; }
        }
        fld piece = {src.p + start, end - start, 'A', 0, 0, 0, 0, NULL};
        mv(ds[k], piece);
        filled++;
        pos = end + dlen;
        if (end == src.len) break;
    }
    return filled;
}

/* ---------- STRING / UNSTRING ---------- */
typedef struct { fld dst; int ptr; int overflow; } strctx;
static void str_begin(strctx *c, fld dst, long pointer) { c->dst = dst; c->ptr = pointer < 1 ? 1 : (int)pointer; c->overflow = 0; }
/* delim_kind: 0 SIZE, 1 delimitado por 'delim' */
static void str_add(strctx *c, fld src, int use_delim, fld delim) {
    int n = src.type == 'F' ? 1 : src.len;
    unsigned char fb = src.type == 'F' ? figchar(src.digits) : 0;
    int dl = use_delim ? (delim.type == 'F' ? 1 : delim.len) : 0;
    int take = n;
    if (use_delim) {
        for (int i = 0; i + dl <= n; i++) {
            int ok = 1;
            for (int j = 0; j < dl; j++) {
                unsigned char x = delim.type == 'F' ? figchar(delim.digits) : delim.p[j];
                unsigned char y = src.type == 'F' ? fb : src.p[i + j];
                if (x != y) { ok = 0; break; }
            }
            if (ok) { take = i; break; }
        }
    }
    for (int i = 0; i < take; i++) {
        if (c->ptr > c->dst.len) { c->overflow = 1; return; }
        c->dst.p[c->ptr - 1] = src.type == 'F' ? fb : src.p[i];
        c->ptr++;
    }
}

/* ---------- CALL ---------- */
static int g_return_code_dummy = 0;
static int call_builtin(const char *name, int nargs, fld *args, int *found) {
    *found = 1;
    if (strcmp(name, "PROGDATA") == 0) {
        if (nargs >= 1) {
            /* preenche AAAAMMDD nos primeiros 8 bytes do registro */
            char b[16]; time_t t = time(NULL); struct tm *tm = localtime(&t);
            snprintf(b, sizeof b, "%04d%02d%02d", tm->tm_year + 1900, tm->tm_mon + 1, tm->tm_mday);
            for (int i = 0; i < 8 && i < args[0].len; i++) args[0].p[i] = (unsigned char)b[i];
        }
        return 0;
    }
    *found = 0;
    return 0;
}

static fld lit_a(const char *);
#endif
