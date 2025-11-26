# Base image: Python 3.12 on Debian Bullseye
FROM mcr.microsoft.com/devcontainers/python:2-3.12-bullseye

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install common utilities and configure zsh
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        zsh \
        curl \
        wget \
        git \
        ca-certificates \
        locales \
        sudo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x (LTS) from NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up locale
RUN localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG=en_US.UTF-8

# Switch to vscode user
USER vscode

# Oh My Zsh is already installed in the base devcontainer image

# Install uv (which includes uvx)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set zsh as default shell for vscode user
USER root
RUN chsh -s /usr/bin/zsh vscode

# Switch back to vscode user
USER vscode

# Set default shell to zsh
ENV SHELL=/usr/bin/zsh

# Set working directory
WORKDIR /workspaces/flow_squared

# Copy post-install script
USER root
COPY post-install.sh /usr/local/bin/post-install.sh
RUN chmod +x /usr/local/bin/post-install.sh

# Switch to vscode user and create ~/.claude directory for mounts
USER vscode
RUN mkdir -p /home/vscode/.claude
