ARG ROCM_PYTORCH_IMAGE=rocm/pytorch:latest
FROM ${ROCM_PYTORCH_IMAGE}

ARG COMFYUI_REF=master

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    COMFYUI_HOME=/opt/ComfyUI

RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${COMFYUI_REF}" https://github.com/comfyanonymous/ComfyUI.git "${COMFYUI_HOME}"

WORKDIR ${COMFYUI_HOME}

RUN grep -Ev '^(torch|torchaudio|torchvision)([<>=]|$)' requirements.txt > requirements-rocm.txt

RUN python -m pip install --no-cache-dir -r requirements-rocm.txt

COPY docker/comfyui-amd/start.sh /usr/local/bin/start-comfyui-amd
RUN chmod +x /usr/local/bin/start-comfyui-amd

EXPOSE 8188

ENTRYPOINT ["/usr/local/bin/start-comfyui-amd"]
