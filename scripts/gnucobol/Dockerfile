# Imagem de referencia: GnuCOBOL 3.2 (cobc) + gcc + python3, sobre Debian.
# Usada por scripts/comparar_gnucobol.py: compara a execucao com a do GnuCOBOL e roda os testes
# que precisam de gcc (--testes). Construida sob demanda e removida com --limpar.
FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends gnucobol gcc libc6-dev python3 \
 && rm -rf /var/lib/apt/lists/*
