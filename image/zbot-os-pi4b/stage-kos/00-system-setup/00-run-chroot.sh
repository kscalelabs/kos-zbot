#!/bin/bash

# Install rustup if not already installed
if ! command -v rustup &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

# Set Rust to stable
if command -v rustup &> /dev/null; then
    rustup default stable
fi

# Enable the firstboot service (file was copied by 00-run.sh)
systemctl enable kos-firstboot.service
systemctl enable set-irq-affinity.service