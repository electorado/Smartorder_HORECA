FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias Python
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copiar paquete del backend
COPY src/ /app/src/

# Configurar ruta de módulos
ENV PYTHONPATH=/app/src
ENV PORT=8000

EXPOSE 8000

# Arranque dinámico compatible con Google Cloud Run y Render
CMD ["sh", "-c", "uvicorn fb_smartorder.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
