#!/usr/bin/env bash
set -e

# ─── 0. Install Dependencies ────────────────────────────
apt-get update
apt-get install -y --no-install-recommends \
  build-essential git bc bison flex libssl-dev libncurses-dev \
  gcc-aarch64-linux-gnu g++-aarch64-linux-gnu

# ─── 1. Prepare Workspace ───────────────────────────────
WORKDIR=/work/kernel-rt
mkdir -p "$WORKDIR" && cd "$WORKDIR"

# ─── 2. Clone Kernel Source ─────────────────────────────
if [ ! -d linux ]; then
  git clone --depth=1 --branch rpi-6.12.y https://github.com/raspberrypi/linux.git linux
fi
cd linux

# ─── 3. Configure Kernel ────────────────────────────────
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
make bcm2711_defconfig

# Apply essential RT settings
./scripts/config -e CONFIG_PREEMPT_RT
./scripts/config --set-val CONFIG_HZ 1000
./scripts/config -d CONFIG_DEBUG_PREEMPT
./scripts/config -d CONFIG_PREEMPT_VOLUNTARY
./scripts/config -d CONFIG_PREEMPT_NONE
./scripts/config --set-str CONFIG_LOCALVERSION "-rt"

# ─── Disable initramfs support ────────────
./scripts/config -d CONFIG_BLK_DEV_INITRD
./scripts/config -d CONFIG_RD_GZIP
./scripts/config -d CONFIG_DECOMPRESS_GZIP

make olddefconfig

# ─── 4. Build Kernel ────────────────────────────────────
make -j"$(nproc)" Image modules dtbs

# ─── 5. Install Directly to RootFS ──────────────────────
# Clean existing modules
rm -rf "${ROOTFS_DIR}/lib/modules"/*

# Install modules
make INSTALL_MOD_PATH="${ROOTFS_DIR}" modules_install

# Install kernel
mkdir -p "${ROOTFS_DIR}/boot/firmware"
cp arch/arm64/boot/Image "${ROOTFS_DIR}/boot/firmware/kernel8-rt.img"

# Install DTBs
cp arch/arm64/boot/dts/broadcom/*.dtb "${ROOTFS_DIR}/boot/firmware/"
mkdir -p "${ROOTFS_DIR}/boot/firmware/overlays"
cp arch/arm64/boot/dts/overlays/*.dtbo "${ROOTFS_DIR}/boot/firmware/overlays/"

# Install kernel config
KERNEL_VER=$(ls "${ROOTFS_DIR}/lib/modules")
cp .config "${ROOTFS_DIR}/boot/config-${KERNEL_VER}"

# ─── 6. Configure Bootloader ────────────────────────────
cat > "${ROOTFS_DIR}/boot/firmware/config.txt" << EOF
# Minimal RT configuration
arm_64bit=1
kernel=kernel8-rt.img
EOF

# ─── Skip initramfs generation ────────────
echo "Skipping initramfs generation for Preempt-RT kernel"

# ─── 7. Final Verification ──────────────────────────────
echo "=== KERNEL BUILD VERIFICATION ==="
echo "Kernel Version: $KERNEL_VER"
strings arch/arm64/boot/Image | grep -m1 "Linux version"
strings arch/arm64/boot/Image | grep -m1 "PREEMPT_RT"
ls -l "${ROOTFS_DIR}/boot/firmware/kernel8-rt.img"
ls -ld "${ROOTFS_DIR}/lib/modules"/*
