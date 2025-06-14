# PREEMPT_RT Kernel Build Guide for KOS Image

A complete, tested workflow to cross-compile a fully real-time (PREEMPT_RT) Linux 6.12.x kernel  
and deploy it into your custom **KOS** SD-card image, using Ubuntu 24.04 LTS.

---

## 📖 Technical Overview

Modern Linux kernels by default aim for maximum throughput and fairness, but not hard real-time guarantees. The **PREEMPT_RT** patchset transforms Linux into a deterministic, low-latency operating system by:

1. **Converting interrupt handlers to threads**  
   Each hardware interrupt is run in a kernel thread (IRQ thread), enabling them to be preempted by higher‑priority tasks and scheduled with real‑time priorities. This avoids long, uninterruptible interrupt contexts.

2. **Fine‑grained locking via wake‑up preemption**  
   Big kernel locks are replaced or converted to priority‑inheriting mutexes (`rtmutexes`), preventing priority inversion and ensuring high‑priority threads never wait behind lower‑priority ones.

3. **Configurable preemption points**  
   The `CONFIG_PREEMPT_RT_FULL` model inserts extra preemption checks deep inside the kernel—down to the scheduler’s internal spinlocks—so even kernel code can be preempted at nearly any point.

4. **High‑resolution timers and tickless operation**  
   PREEMPT_RT enables full high‑resolution tickless operation (`CONFIG_NO_HZ_FULL`), allowing scheduling decisions at microsecond granularity without jitter from fixed timer interrupts.

5. **Threaded softirqs and bottom halves**  
   Deferred work (softirqs, tasklets) also run in threads, making device drivers behave more predictably under load.

### Why this matters for KOS

- **Deterministic I/O:** Guarantees wake‑up latencies (e.g. < 50 µs) for sensor reads and actuator writes.  
- **Priority‑critical tasks:** Time‑sensitive threads (e.g. motor control loops) run at high `SCHED_FIFO` priorities without delays.  
- **Reduced jitter:** Removes millisecond‑scale jitter for smoother, more accurate control loops (< 20 µs on Pi4).  
- **Userland compatibility:** Drop‑in extension of mainline Linux—no driver or application changes needed.

---

## 📋 Prerequisites

- **Host:** Ubuntu 24.04.2 LTS  
- **Target image:** KOS SD‑card with two partitions:  
  - `/dev/sdX1` → FAT32 `boot`  
  - `/dev/sdX2` → ext4 `rootfs`  

---

## ⚙️ 1. Install Host Dependencies

```bash
sudo apt update
sudo apt install -y \
  git bc bison flex libssl-dev make libc6-dev libncurses-dev \
  crossbuild-essential-arm64
````

---

## 📂 2. Prepare Kernel Sources

```bash
mkdir -p ~/rpi-rt-kernel && cd ~/rpi-rt-kernel
git clone --depth=1 --branch rpi-6.12.y https://github.com/raspberrypi/linux.git
cd linux
```

> **Note:** `Makefile`’s `SUBLEVEL` line shows the exact point‑release (e.g. 32).

---

## 🛠️ 3. Configure for KOS + PREEMPT\_RT

```bash
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
make bcm2711_defconfig
```

### a) Interactive (`menuconfig`)

```bash
make menuconfig
```

* **General setup → Preemption Model → Fully Preemptible Kernel (Real‑Time)**
* **Enable High Resolution Timer Support**
* Save & Exit.

### b) Scripted

```bash
scripts/config --disable CONFIG_PREEMPT \
               --enable CONFIG_PREEMPT_RT \
               --enable CONFIG_PREEMPT_RT_FULL \
               --enable CONFIG_HIGH_RES_TIMERS
make olddefconfig
```

---

## ⚡ 4. Build

```bash
make -j$(nproc) Image modules dtbs
```

* **Image** → `arch/arm64/boot/Image`
* **DTBs** → `arch/arm64/boot/dts/broadcom/*.dtb` & overlays

---

## 💾 5. Mount KOS Image

```bash
sudo mkdir -p /mnt/kos-boot /mnt/kos-root
sudo mount /dev/sdX1 /mnt/kos-boot
sudo mount /dev/sdX2 /mnt/kos-root
```

---

## 🗃️ 6. Install Modules

```bash
sudo make INSTALL_MOD_PATH=/mnt/kos-root modules_install
```

---

## 🚀 7. Deploy Kernel & DTBs

```bash
# Backup existing
sudo mv /mnt/kos-boot/kernel8.img /mnt/kos-boot/kernel8.img.bak

# Copy new RT Image
sudo cp arch/arm64/boot/Image /mnt/kos-boot/kernel8.img

# Copy DTBs
sudo cp arch/arm64/boot/dts/broadcom/*.dtb /mnt/kos-boot/

# Copy overlays
sudo cp arch/arm64/boot/dts/overlays/*.dtb* /mnt/kos-boot/overlays/
sudo cp arch/arm64/boot/dts/overlays/README /mnt/kos-boot/overlays/
```

---

## 📝 8. Update `config.txt` for KOS

```bash
sudo sed -i \
  -e 's/^#\?arm_64bit=.*/arm_64bit=1/' \
  -e 's/^#\?kernel=.*/kernel=kernel8.img/' \
  /mnt/kos-boot/config.txt
```

---

## 🔌 9. Unmount & Boot

```bash
sync
sudo umount /mnt/kos-boot /mnt/kos-root
```

Insert the SD‑card back into your device and power it on.

---

## ✅ 10. Verify on Device

```bash
# Check embedded version:
strings /mnt/kos-boot/kernel8.img | grep -m1 "Linux version"

# Or on-device after boot:
ssh user@<kos-device>
uname -a   # should show "# SMP PREEMPT_RT"
```

Optional latency test:

```bash
sudo apt install -y rt-tests
sudo cyclictest -m -n -p 80 -i 100 -l 10000
```

---

## 🛠️ Troubleshooting

* **Unexpected SUBLEVEL?** No issue—newer 6.12.x is fine.
* **Boot failure?** Confirm DTB and `kernel=kernel8.img` in config.
* **Missing modules?** Re-run `modules_install` with correct path.
* **OOM on build?** Lower `-j` count.
* **Revert?** Restore `/mnt/kos-boot/kernel8.img.bak`.

---

### Optional: QEMU Dry‑Run Chroot

```bash
sudo apt install qemu-user-static
sudo cp /usr/bin/qemu-aarch64-static /mnt/kos-root/usr/bin/
for fs in proc sys dev; do sudo mount --bind /$fs /mnt/kos-root/$fs; done
sudo chroot /mnt/kos-root /usr/bin/qemu-aarch64-static bash
# inside:
cyclictest -m -n -p 80 -i 100 -l 1000
exit
for fs in dev sys proc; do sudo umount /mnt/kos-root/$fs; done
```

> *Timing won’t reflect real hardware latency; for true PREEMPT\_RT tests, boot the device.*

---

#### Attribution

Based on build steps by Tanay Chaturvedi (June 2025).

```
```
