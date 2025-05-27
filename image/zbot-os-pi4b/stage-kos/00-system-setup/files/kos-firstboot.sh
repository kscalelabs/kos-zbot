#!/bin/bash

# KOS First Boot Setup Script
# This script runs once on first boot to set up the KOS environment

set -e  # Exit on any error

# Log all output
exec > >(tee -a /var/log/kos-firstboot.log) 2>&1

echo "Starting KOS first boot setup..."

# Source conda environment and activate kos
source /home/kos/conda/etc/profile.d/conda.sh

conda create -n kos python=3.12 -y

conda activate kos

# Set capabilities for Python to allow nice priority adjustments
setcap cap_sys_nice=eip $(readlink -f $(which python))

# Create the kos state directory
mkdir -p /var/lib/kos

# Clone and install kos-zbot
mkdir -p /home/kos/kscale
cd /home/kos/kscale
git clone https://github.com/kscalelabs/kos-zbot
cd kos-zbot
pip install setuptools
pip install -e .

# Mark first boot as completed
touch /var/lib/kos/first-boot-done

echo "KOS first boot setup completed successfully!"