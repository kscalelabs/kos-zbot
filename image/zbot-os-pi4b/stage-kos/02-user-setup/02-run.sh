#!/bin/bash -e

# Copy MOTD file
install -m 644 files/motd "${ROOTFS_DIR}/etc/motd"

# Copy the setup scripts
install -m 755 files/setup-conda.sh "${ROOTFS_DIR}/home/kos/setup-conda.sh"
# Create kscale directory
mkdir -p "${ROOTFS_DIR}/home/kos/kscale"

# Set proper ownership
chown -R 1000:1000 "${ROOTFS_DIR}/home/kos/kscale"
chown 1000:1000 "${ROOTFS_DIR}/home/kos/setup-conda.sh"

# Run conda installation as kos user in chroot
chroot "$ROOTFS_DIR" /bin/bash -c "su - kos -c '/home/kos/setup-conda.sh'"