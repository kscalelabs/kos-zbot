#!/bin/bash
# Activate conda
source "/home/kos/conda/etc/profile.d/conda.sh"
conda activate kos

# Clone and install kos-zbot
mkdir -p /home/kos/kscale
cd /home/kos/kscale
git clone https://github.com/kscalelabs/kos-zbot
cd kos-zbot
pip install setuptools
pip install -e .