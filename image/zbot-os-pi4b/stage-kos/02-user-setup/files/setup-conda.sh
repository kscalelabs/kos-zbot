#!/bin/bash -e
cd /home/kos
wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3.sh -b -p "/home/kos/conda"
source "/home/kos/conda/etc/profile.d/conda.sh"
echo 'source "${HOME}/conda/etc/profile.d/conda.sh"' >> /home/kos/.bashrc

# Create KOS environment
conda create -n kos python=3.12 -y

echo 'source "${HOME}/conda/etc/profile.d/conda.sh"' >> /home/kos/.bashrc
echo 'conda activate kos' >> /home/kos/.bashrc