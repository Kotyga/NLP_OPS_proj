FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        cmake \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

COPY worker/requirements.txt ./requirements.txt

RUN python -m pip install \
    --no-cache-dir \
    --upgrade pip setuptools wheel

RUN python -m pip install \
    --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.2.1

RUN python -m pip install \
    --no-cache-dir \
    -r requirements.txt

RUN python -m pip install \
    --no-cache-dir \
    "Cython==0.29.36" \
    && python -m pip install \
        --no-cache-dir \
        --no-build-isolation \
        "youtokentome==1.0.6"


FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/app/.cache/huggingface

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY common ./common
COPY worker ./worker

RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /app/.cache/huggingface \
    && chown -R worker:worker /app

USER worker

CMD ["python", "-u", "-m", "worker.main"]
