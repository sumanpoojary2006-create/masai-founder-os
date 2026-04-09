FROM python:3.11-slim

WORKDIR /app

COPY ai_company/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ai_company/ /app/

ENV PYTHONUNBUFFERED=1
ENV AI_COMPANY_HOST=0.0.0.0
ENV AI_COMPANY_PORT=8000

EXPOSE 8000

CMD ["python", "webapp.py"]
