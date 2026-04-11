#!/usr/bin/env bash
set -eu

cd /opt/stable-diffusion-webui

mkdir -p /opt/stable-diffusion-webui/models /opt/stable-diffusion-webui/outputs

export python_cmd=/opt/a1111-venv/bin/python
export venv_dir=-
export STABLE_DIFFUSION_REPO="${STABLE_DIFFUSION_REPO:-https://github.com/w-e-w/stablediffusion.git}"
export COMMANDLINE_ARGS="${COMMANDLINE_ARGS:-} --skip-python-version-check"

exec ./webui.sh
