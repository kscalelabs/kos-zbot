#!/bin/bash -e
cd /home/kos

# Remove any existing conda installation
rm -rf /home/kos/conda

wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3.sh -b -p "/home/kos/conda"
source "/home/kos/conda/etc/profile.d/conda.sh"

echo 'conda activate kos' >> /home/kos/.bashrc

# Clean up installer
rm -f Miniforge3.sh