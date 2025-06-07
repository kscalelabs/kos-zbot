#!/bin/bash -e

# Copy ALSA configuration
install -m 644 files/asound.conf "${ROOTFS_DIR}/etc/asound.conf"