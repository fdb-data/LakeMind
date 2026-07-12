FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.29" "httpx>=0.27" "mcp>=1.28" "imageio-ffmpeg>=0.5" && \
    python -c "import imageio_ffmpeg, os; src=imageio_ffmpeg.get_ffmpeg_exe(); os.symlink(src, '/usr/local/bin/ffmpeg')" && \
    ffmpeg -version | head -1

COPY agent.py lakemind_client.py ./
COPY static/ static/
COPY skills/ skills/
COPY scripts/ scripts/

ENV PORT=9100
EXPOSE 9100

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
