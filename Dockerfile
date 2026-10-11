# 선택 사항: Docker 가 있는 컴퓨터라면 설치 없이 실행할 수 있습니다.
#   docker build -t landai .
#   docker run --rm -v "$PWD/raw:/app/raw" -v "$PWD/profiles:/app/profiles" \
#     -v "$PWD/staging:/app/staging" --env-file .env landai ingest --all
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
ENTRYPOINT ["python", "-m", "landai"]
CMD ["doctor"]
