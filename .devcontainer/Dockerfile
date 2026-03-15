# syntax=docker/dockerfile:1
# ============================================================================
# qdrant-indexer 開発コンテナ
# Megurip devcontainer から Go / Terraform / AWS 関連を除去した軽量版
# ============================================================================
FROM ubuntu:24.04

LABEL maintainer="Megurip Team"
LABEL description="Development container for qdrant-indexer CLI"

ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash

# パイプ失敗時にエラーを検出する（DL4006 対策）
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# --------------------------------------------------------------------------
# Layer 1: builder ユーザー作成 + sudo 設定
# --------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN userdel -r ubuntu \
    && groupadd --gid 1000 builder \
    && useradd -s /bin/bash --uid 1000 --gid 1000 -m builder \
    && apt-get update \
    && apt-get install -y --no-install-recommends sudo \
    && echo "builder ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/builder \
    && chmod 0440 /etc/sudoers.d/builder \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------
# Layer 2: システムパッケージ
# --------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    openssh-client \
    xz-utils \
    unzip \
    jq \
    ripgrep \
    fd-find \
    python3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------
# Layer 3: Node.js（Claude Code の npm 依存）
# --------------------------------------------------------------------------
# renovate: datasource=node-version depName=node
ARG NODE_VERSION=24.14.0
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/

# --------------------------------------------------------------------------
# Layer 4: uv（Python パッケージマネージャ）
# --------------------------------------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && mv /root/.local/bin/uvx /usr/local/bin/uvx

# --------------------------------------------------------------------------
# Layer 5: ターミナル開発ツール
# --------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends bat file \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/batcat /usr/local/bin/bat \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd

# renovate: datasource=github-releases depName=junegunn/fzf
ARG FZF_VERSION=0.70.0
RUN curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_amd64.tar.gz" \
    | tar -xz -C /usr/local/bin/ fzf

# renovate: datasource=github-releases depName=helix-editor/helix
ARG HELIX_VERSION=25.07.1
RUN mkdir -p /opt/helix \
    && curl -fsSL "https://github.com/helix-editor/helix/releases/download/${HELIX_VERSION}/helix-${HELIX_VERSION}-x86_64-linux.tar.xz" \
    | tar -xJ --strip-components=1 -C /opt/helix/ \
    && ln -s /opt/helix/hx /usr/local/bin/hx

ENV HELIX_RUNTIME=/opt/helix/runtime

# renovate: datasource=github-releases depName=jesseduffield/lazygit
ARG LAZYGIT_VERSION=0.60.0
RUN curl -fsSL "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_linux_x86_64.tar.gz" \
    | tar -xz -C /usr/local/bin/ lazygit

# renovate: datasource=github-releases depName=sxyazi/yazi
ARG YAZI_VERSION=26.1.22
RUN curl -fsSL "https://github.com/sxyazi/yazi/releases/download/v${YAZI_VERSION}/yazi-x86_64-unknown-linux-gnu.zip" \
    -o /tmp/yazi.zip \
    && unzip -q /tmp/yazi.zip -d /tmp/yazi \
    && mv /tmp/yazi/yazi-x86_64-unknown-linux-gnu/yazi /usr/local/bin/yazi \
    && rm -rf /tmp/yazi /tmp/yazi.zip

# renovate: datasource=github-releases depName=zellij-org/zellij
ARG ZELLIJ_VERSION=0.43.1
RUN curl -fsSL "https://github.com/zellij-org/zellij/releases/download/v${ZELLIJ_VERSION}/zellij-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin/ zellij

# --------------------------------------------------------------------------
# Layer 6: ユーザー設定
# --------------------------------------------------------------------------
WORKDIR /workspace

RUN mkdir -p /home/builder/.config \
    && mkdir -p /home/builder/.local/bin \
    && chown -R builder:builder /home/builder /workspace

# --------------------------------------------------------------------------
# Layer 7: Entrypoint + Healthcheck
# --------------------------------------------------------------------------
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER builder

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD uv --version || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
