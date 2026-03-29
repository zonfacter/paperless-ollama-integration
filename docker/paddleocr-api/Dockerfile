FROM ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddle:3.0.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    PADDLEOCR_LANG=german \
    PADDLEOCR_CPU_THREADS=4 \
    PADDLEOCR_ENABLE_MKLDNN=true \
    PADDLEOCR_DEVICE=cpu

WORKDIR /app

RUN python -m pip install --upgrade pip setuptools wheel
COPY requirements.txt /app/requirements.txt
RUN python -m pip install -r /app/requirements.txt

COPY app.py /app/app.py

EXPOSE 8091

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091"]
