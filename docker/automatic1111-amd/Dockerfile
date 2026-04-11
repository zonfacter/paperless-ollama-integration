FROM rocm/pytorch:latest

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    WEBUI_HOME=/opt/stable-diffusion-webui \
    A1111_VENV=/opt/a1111-venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3.10 python3.10-dev python3.10-venv build-essential libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/AUTOMATIC1111/stable-diffusion-webui.git "${WEBUI_HOME}"

WORKDIR ${WEBUI_HOME}

RUN python3.10 -m venv "${A1111_VENV}" \
    && "${A1111_VENV}/bin/python" -m pip install --upgrade "pip<25.1" "setuptools<81" wheel

RUN useradd --create-home --shell /bin/bash webui \
    && chown -R webui:webui "${WEBUI_HOME}" "${A1111_VENV}"

COPY docker/automatic1111-amd/start.sh /usr/local/bin/start-automatic1111-amd
RUN chmod +x /usr/local/bin/start-automatic1111-amd

EXPOSE 7860

USER webui

ENTRYPOINT ["/usr/local/bin/start-automatic1111-amd"]
