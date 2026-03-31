FROM debian:trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git python3 curl ca-certificates \
    libvulkan-dev vulkan-tools mesa-vulkan-drivers glslang-tools glslc && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone https://github.com/ggml-org/llama.cpp.git . && \
    cmake -B build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build -j$(nproc) --target llama-server llama-cli

EXPOSE 8080

CMD ["/src/build/bin/llama-server", \
     "-m", "/models/Qwen3.5-4B-Q4_K_M.gguf", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--n-gpu-layers", "99", \
     "--ctx-size", "4096", \
     "--threads", "4", \
     "--log-prefix"]
