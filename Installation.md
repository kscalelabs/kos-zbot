# KOS Pi Installation & Configuration Guide

## Table of Contents

- [KOS Pi Installation \& Configuration Guide](#kos-pi-installation--configuration-guide)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Python Environment Setup](#python-environment-setup)
  - [Raspberry Pi System Configuration](#raspberry-pi-system-configuration)
    - [Realtime Python Capability](#realtime-python-capability)
    - [Add User Permissions](#add-user-permissions)
    - [`/boot/firmware/config.txt`](#bootfirmwareconfigtxt)
    - [Ethernet Gadget Mode](#ethernet-gadget-mode)
    - [Static IP for USB Gadget](#static-ip-for-usb-gadget)
    - [DHCP for USB Gadget](#dhcp-for-usb-gadget)
    - [Edit `/etc/motd` (Message of the Day)](#edit-etcmotd-message-of-the-day)
  - [Customize your login banner by editing `/etc/motd`:](#customize-your-login-banner-by-editing-etcmotd)
    - [WiFi Setup](#wifi-setup)
    - [Speaker \& Microphone (I2S)](#speaker--microphone-i2s)
    - [Camera](#camera)
    - [Display (SPI)](#display-spi)

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
sudo apt install portaudio19-dev python3-dev

# Install Rust (kinfer)
sudo apt install rustc -y
rustup default stable

# (Optional) Create and activate a conda environment
# Programmatic Miniforge install : https://github.com/conda-forge/miniforge
wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3.sh -b -p "${HOME}/conda"
source "${HOME}/conda/etc/profile.d/conda.sh"
# Add to .bashrc for terminal login:
cat << EOF >> ~/.bashrc
source "${HOME}/conda/etc/profile.d/conda.sh"
EOF

# K-OS Install
conda activate
conda create -n kos python=3.12 -y
conda activate kos
cd ~
git clone https://github.com/kscalelabs/kos-zbot
cd kos-zbot
pip install -e .
pip install -r requirements.txt

```


## Raspberry Pi System Configuration

### Realtime Python Capability

Allow Python to set realtime priorities (for low-latency control):

```bash
#Enable Thread Pinning
sudo setcap cap_sys_nice=eip $(readlink -f $(which python))

#Inspect interrupts and find uart_pl011 (double check that uart_pl011 is on IRQ 36)
watch -n 0.2 cat /proc/interrupts

# pin uart_pl011 irq to cpu1 (we pin our servo control loop also to cpu1)
sudo sh -c 'echo 2 > /proc/irq/36/smp_affinity'

# To set IRQ pinning persistently, add a udev rule 
# nano /etc/udev/rules.d/80-irq-affinity.rules
ACTION=="add", SUBSYSTEM=="irq", KERNEL=="36", ATTR{smp_affinity}="2"

#Reload udev
sudo udevadm control --reload

#Optionally force device event now (or reboot and test)
sudo udevadm trigger --action=add --subsystem-match=irq --attr-match=irq=36

#Verify that udev rule has been applies to IRQ 36
cat /proc/irq/36/smp_affinity

```

---

### Add User Permissions

Add your user to the necessary groups for hardware access:

```bash
sudo usermod -aG dialout $USER
sudo usermod -aG i2c $USER
sudo usermod -aG audio $USER
sudo usermod -aG video $USER
```
Log out and back in for group changes to take effect.

---

### `/boot/firmware/config.txt`

Edit `/boot/firmware/config.txt` and add/verify the following lines:

```ini
[all]
# KOS PI4 Configuration

# Gadget Mode
dtoverlay=dwc2

# SPI Display
dtparam=spi=on

# IMU
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=400000
dtoverlay=i2c6,pins_22_23

# Audio Amplifier. Pin 37 for Amp pull up, Left Channel. G16 for gain, ground = positive.
dtparam=i2s=on
dtparam=audio=on
dtoverlay=max98357a
gpio=26=op,dh
gpio=16=op,dl

# Camera
camera_auto_detect=1
display_auto_detect=1
dtoverlay=imx219

# Microphone, Pin 18 for Mic pull up, Right Channel, Pin 16 for Mic Vin. Requires Y Split for BCLK + LRCLK to follow same I2S as Audio Amp
dtoverlay=googlevoicehat-soundcard
gpio=24=op,dh

# Display, Pin 11 for Backlight pull up
gpio=17=op,dh

# Servo Controller
enable_uart=1
auto_initramfs=1
dtoverlay=vc4-kms-v3d
max_framebuffers=2
dtoverlay=disable-bt
dtoverlay=uart5,txd5_pin=12,rxd5_pin=13
disable_fw_kms_setup=1
arm_64bit=1
disable_overscan=1
arm_boost=1


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
- Playback should now be bound to _"Google voiceHat soundcard"_ __sndrpigooglevoi__  for both input and output. Verify this option is available with `aplay -l`
- Test playback with:
    ```bash
    aplay -D hw:sndrpigooglevoi filename.wav
    ```
- You may define a more intuitive device name using a `asound.conf` file:
    ```bash
    sudo tee /etc/asound.conf > /dev/null << EOF
    # Mic and Speaker, named 'zbot'
    pcm.zbot {
    type plug
        slave {
        pcm "plughw:sndrpigooglevoi,0"
        }
    }

    ctl.zbot {
        type hw
        card sndrpigooglevoi
    }
    EOF
    ```
    - This will now allow for running `aplay` and `arecord` with `-D zbot` argument.
    - _Note that attempting to set it as a `!default` device generally appears to fail (possibly to do with conflicts with pulseaudio?)_



### Camera

Enable Camera via raspi-config

Install Gstreamer
```bash
sudo apt update
sudo apt install -y \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  libgstrtspserver-1.0-dev \
  gstreamer1.0-libcamera

  sudo apt install python3-gi python3-gst-1.0 gir1.2-gst-rtsp-server-1.0

```

### Display (SPI)

- Ensure the correct overlays are set in `/boot/firmware/config.txt` (see above).
    - Alternatively configurable through `raspi-config`
- For current Bookworm operating systems, install `lgpio` to support the SPI / GPIO interfacing:

```
# Reference waveshare documentation: https://www.waveshare.com/wiki/2inch_LCD_Module?amazon#STM32_hardware_connection
sudo su
wget https://github.com/joan2937/lg/archive/master.zip
unzip master.zip
cd lg-master
sudo make install
exit
```
