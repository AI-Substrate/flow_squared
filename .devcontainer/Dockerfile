# Base image: Python 3.12 on Debian Bookworm
FROM mcr.microsoft.com/devcontainers/python:2-3.12-bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Remove the Yarn apt source shipped in the base image — its GPG key
# (62D54FD4003F6525) is no longer valid and breaks apt-get update.
# Yarn is not needed for this project.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && rm -f /usr/share/keyrings/yarn-keyring.gpg 2>/dev/null || true

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
        openssh-server \
        openssh-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH server for remote access on port 2225
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#Port 22/Port 2225/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config && \
    echo "PermitRootLogin no" >> /etc/ssh/sshd_config

# Create SSH auto-start script (checks if process is running, not just PID file)
RUN echo '#!/bin/bash\nif ! pgrep -x sshd > /dev/null 2>&1; then\n    sudo service ssh start\nfi' > /usr/local/share/ssh-init.sh && \
    chmod +x /usr/local/share/ssh-init.sh

# Allow vscode user to start SSH without password
RUN echo "vscode ALL=(ALL) NOPASSWD: /usr/sbin/service ssh start" >> /etc/sudoers.d/vscode-ssh && \
    chmod 0440 /etc/sudoers.d/vscode-ssh

# Build tmux 3.4 from source (Debian Bookworm only has 3.3a)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libevent-dev libncurses-dev build-essential bison pkg-config \
    && cd /tmp \
    && curl -sL https://github.com/tmux/tmux/releases/download/3.4/tmux-3.4.tar.gz | tar xz \
    && cd tmux-3.4 \
    && ./configure --quiet \
    && make -j"$(nproc)" --quiet \
    && make install \
    && cd / && rm -rf /tmp/tmux-3.4 \
    && apt-get purge -y --auto-remove build-essential bison pkg-config \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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
