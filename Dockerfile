# RM Intelligence Workbench — container image.
# The bank-realistic deploy: one immutable image, key injected at runtime as an
# environment variable / secret (never baked in).
#
#   docker build -t jb-wealth-intelligence .
#   docker run -p 8080:8080 -e ANTHROPIC_API_KEY=sk-ant-... jb-wealth-intelligence
#
# Without a key it still runs — explanations fall back to the deterministic path.
FROM python:3.11-slim

WORKDIR /app

# Install app dependencies first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application and its data.
COPY wealth_intelligence/ ./wealth_intelligence/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY streamlit_app.py .

EXPOSE 8080

# Streamlit, bound for a container: no telemetry, listen on all interfaces.
ENV STREAMLIT_SERVER_PORT=8080 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

HEALTHCHECK --interval=30s --timeout=4s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/_stcore/health')" || exit 1

CMD ["streamlit", "run", "streamlit_app.py"]
