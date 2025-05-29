#!/bin/bash -e

# Create network config for USB gadget mode
mkdir -p "${ROOTFS_DIR}/etc/systemd/network/"
install -m 644 files/usb0.network "${ROOTFS_DIR}/etc/systemd/network/"

# Configure DHCP for USB gadget
mkdir -p "${ROOTFS_DIR}/etc/dnsmasq.d/"
install -m 644 files/usb0.conf "${ROOTFS_DIR}/etc/dnsmasq.d/"