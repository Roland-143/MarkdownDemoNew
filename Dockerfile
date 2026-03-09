FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install \
    "streamlit>=1.55.0,<2.0.0" \
    "pandas>=2.2,<3" \
    "sqlalchemy>=2.0.48,<3.0.0" \
    "psycopg[binary]>=3.3.3,<4.0.0" \
    "python-dotenv>=1.2.2,<2.0.0"

COPY ops_summary ./ops_summary
COPY app.py ./app.py

RUN useradd --create-home appuser
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
