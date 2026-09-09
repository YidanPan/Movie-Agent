FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-py312-torch2.10.0-1.37.1

WORKDIR /home/studio/PROJECT

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["sh", "-c", "python scripts/stage5a_runtime_check.py && uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]
