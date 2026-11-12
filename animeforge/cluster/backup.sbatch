#!/bin/bash
#SBATCH -A plafnet2
#SBATCH -p plafnet2
#SBATCH -J af_backup
#SBATCH --exclude=gnode118
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=animeforge/logs/backup_%j.log
# Copy the model cache from node scratch (purged weekly) to /share6 through the gateway. No GPU.
set -euo pipefail
export ANIMEFORGE_HOME=/scratch/$USER/animeforge
AF=$ANIMEFORGE_HOME
source "$HOME/animeforge/src/animeforge/cluster/models_sync.sh"
af_backup
