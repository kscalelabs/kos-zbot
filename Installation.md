# KOS Pi Installation & Configuration Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Python Environment Setup](#python-environment-setup)
3. [KOS Python Package Build](#kos-python-package-build)
4. [Raspberry Pi System Configuration](#raspberry-pi-system-configuration)
    - [Realtime Python Capability](#realtime-python-capability)
    - [/boot/firmware/config.txt](#bootfirmwareconfigtxt)
    - [Ethernet Gadget Mode](#ethernet-gadget-mode)
    - [Static IP for USB Gadget](#static-ip-for-usb-gadget)
    - [DHCP for USB Gadget](#dhcp-for-usb-gadget)
    - [Edit /etc/motd](#edit-etc-motd)
    - [WiFi Setup](#wifi-setup)
    - [Speaker & Microphone (I2S)](#speaker--microphone-i2s)
5. [IMU Configuration](#imu-configuration)
6. [Performance & Latency Testing](#performance--latency-testing)
7. [Servo Communication Protocol](#servo-communication-protocol)
8. [Servo Register Maps](#servo-register-maps)

---

## Prerequisites

- Raspberry Pi 4B
- Raspberry Pi OS 64-bit
- Python 3.12+ (recommended: use Miniforge or Miniconda)
- Required hardware: Feetech Servos, BNO055 IMU, I2S audio, etc.
---

## Python Environment Setup

```bash
# Install system dependencies
sudo apt install portaudio19-dev

# (Optional) Create and activate a conda environment
conda create -n kos python=3.12
conda activate kos

# Install Python dependencies
pip install -r requirements.txt
```

---

## KOS Python Package Build

```bash
# Build the KOS package
pip install build
python -m build
```

---

## Raspberry Pi System Configuration

### Realtime Python Capability

Allow Python to set realtime priorities (for low-latency control):

```bash
sudo setcap cap_sys_nice=eip $(readlink -f $(which python))
```

---

### `/boot/firmware/config.txt`

Edit `/boot/firmware/config.txt` and add/verify the following lines:

```ini
# KOS PI4 Configuration

dtparam=i2c_arm=on
dtoverlay=i2c6,pins_22_23
dtparam=audio=on
camera_auto_detect=1
display_auto_detect=1
auto_initramfs=1
dtoverlay=vc4-kms-v3d
max_framebuffers=2
dtoverlay=disable-bt
dtoverlay=uart5,txd5_pin=12,rxd5_pin=13
disable_fw_kms_setup=1
arm_64bit=1
disable_overscan=1
arm_boost=1
dtparam=i2s=on

[all]
dtoverlay=dwc2
dtoverlay=googlevoicehat-soundcard
dtoverlay=max98357a
```

---

### Ethernet Gadget Mode

To enable USB Ethernet gadget mode, edit `/boot/firmware/cmdline.txt` and add `modules-load=dwc2,g_ether` to the kernel command line (all on one line):
console=tty1 root=PARTUUID=xxxx rootfstype=ext4 fsck.repair=yes rootwait modules-load=dwc2,g_ether quiet splash plymouth.ignore-serial-consoles


---

### Static IP for USB Gadget

Create the file `/etc/systemd/network/usb0.network` with the following content:

```ini
[Match]
Name=usb0

[Network]
Address=192.168.42.1/24
```

Enable and start the network service:

```bash
sudo systemctl enable systemd-networkd
sudo systemctl start systemd-networkd
```

---

### DHCP for USB Gadget

Install and configure `dnsmasq` to provide DHCP over USB:

```bash
sudo apt install dnsmasq
sudo nano /etc/dnsmasq.d/usb0.conf
```

Add the following lines to `/etc/dnsmasq.d/usb0.conf`:
interface=usb0
dhcp-range=192.168.42.2,192.168.42.20,255.255.255.0,24h


Restart `dnsmasq` to apply the changes:

```bash
sudo systemctl restart dnsmasq
```

---

### Edit `/etc/motd` (Message of the Day)

Customize your login banner by editing `/etc/motd`:
-----
***********************************************"
*                KSCALE KOS                   *"
***********************************************"

   Welcome Human!

   Add some notes, instructions to use zbot   

***********************************************   
---

WiFi Setup
To connect to WiFi using NetworkManager:

---

### WiFi Setup

To connect to WiFi using NetworkManager:

```bash
nmcli connection show
sudo nmcli device wifi connect "SSID" password "PASSWORD"
```

---

### Speaker & Microphone (I2S)

- Ensure the correct overlays are set in `/boot/firmware/config.txt` (see above).
- Test playback with:
    ```bash
    aplay -D hw:3,0 pokeman.wav
    ```
