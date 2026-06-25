FROM python:3.13-slim

WORKDIR /app

# System deps: gcc+libffi para compilação, git para pip install de repos GitHub,
# libreoffice para conversão DOCX→PDF (job_relatorio)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    git \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "worker_main.py"]
