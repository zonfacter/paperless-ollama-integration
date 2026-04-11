FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git ripgrep less procps \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g opencode-ai@latest

COPY docker/opencode/opencode-default.sh /usr/local/bin/opencode-default
COPY docker/opencode/opencode-selftest.sh /usr/local/bin/opencode-selftest
RUN chmod 755 /usr/local/bin/opencode-default /usr/local/bin/opencode-selftest

RUN useradd -m -s /bin/bash opencode
USER opencode
WORKDIR /workspace

ENV HOME=/home/opencode

CMD ["sleep", "infinity"]
