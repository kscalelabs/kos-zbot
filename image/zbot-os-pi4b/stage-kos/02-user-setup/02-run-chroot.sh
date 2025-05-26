#!/bin/bash

usermod -aG dialout kos
usermod -aG i2c kos
usermod -aG audio kos
usermod -aG video kos

# Run setup scripts as the kos user
su - kos -c '/home/kos/setup-conda.sh'
su - kos -c '/home/kos/setup-kos.sh'

