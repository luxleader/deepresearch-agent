FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv && useradd --create-home --uid 10001 researcher
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev && mkdir runtime && chown -R researcher:researcher /app
USER researcher
ENV DR_MODE=replay
EXPOSE 8765
CMD [".venv/bin/python", "-m", "uvicorn", "deepresearch_app.api:default_app", "--factory", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
