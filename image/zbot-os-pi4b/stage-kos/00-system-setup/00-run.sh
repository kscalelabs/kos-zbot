#!/bin/bash -e

# Copy files to the rootfs
echo "Installing custom firstboot service"
install -m 644 files/kos-firstboot.service "${ROOTFS_DIR}/etc/systemd/system/"
install -m 644 files/set-irq-affinity.service "${ROOTFS_DIR}/etc/systemd/system/"

echo "Installing custom boot files"
# Copy custom boot files
install -m 755 files/cmdline.txt "${ROOTFS_DIR}/boot/firmware/"
install -m 644 files/config.txt "${ROOTFS_DIR}/boot/firmware/"

