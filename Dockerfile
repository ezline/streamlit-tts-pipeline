# app/Dockerfile

FROM python:3.11-slim

WORKDIR /app
ENV LETSENCRYPT_HOST=''
ENV VIRTUAL_HOST=''
ENV VIRTUAL_PORT=8501
ENV HTPASSWD=''
ENV TZ=Asia/Seoul

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    vim \
    procps \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 빌드 시점에 requirements.txt 복사 및 설치
COPY requirements.txt /app
RUN pip3 install -r requirements.txt

# streamlit_tts.py는 볼륨 마운트로 덮어씌워짐
COPY streamlit_tts.py /app

# 실행 스크립트 복사
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8501 8000

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["/app/start.sh"]
