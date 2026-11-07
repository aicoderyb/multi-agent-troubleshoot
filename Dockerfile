FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home appuser
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

USER appuser
ENV MULAT_HOST=0.0.0.0 MULAT_PORT=8000
EXPOSE 8000

CMD ["uvicorn", "mulat.main:app", "--host", "0.0.0.0", "--port", "8000"]
