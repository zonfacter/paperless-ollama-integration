ARG OPEN_WEBUI_IMAGE_TAG=v0.8.12
FROM ghcr.io/open-webui/open-webui:${OPEN_WEBUI_IMAGE_TAG}

COPY docker/open-webui/apply_openwebui_patches.py /opt/paperless-open-webui/apply_openwebui_patches.py
COPY docker/open-webui/bootstrap_openwebui.py /opt/paperless-open-webui/bootstrap_openwebui.py
COPY docker/open-webui/load_json_env.py /opt/paperless-open-webui/load_json_env.py
COPY docker/open-webui/start-with-bootstrap.sh /usr/local/bin/start-with-bootstrap.sh
COPY docker/open-webui/workflows /opt/paperless-open-webui/workflows
COPY scripts/openwebui/install_model_profiles.py /opt/paperless-open-webui/install_model_profiles.py
COPY scripts/openwebui/install_workspace_agent_tools.py /opt/paperless-open-webui/install_workspace_agent_tools.py

RUN chmod 755 /usr/local/bin/start-with-bootstrap.sh

CMD ["bash", "/usr/local/bin/start-with-bootstrap.sh"]
