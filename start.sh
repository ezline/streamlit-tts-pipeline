#!/bin/bash

# 로그 디렉토리 생성
mkdir -p /app/logs

# Streamlit 실행 (로그 파일로 출력)
streamlit run streamlit_tts.py --server.port=8501 --server.address=0.0.0.0 > /app/logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!

# FastAPI 실행 (로그 파일로 출력)
uvicorn utils.api:app --host 0.0.0.0 --port 8000 > /app/logs/fastapi.log 2>&1 &
FASTAPI_PID=$!

# 로그 모니터링 (두 로그 파일을 동시에 tail)
tail -f /app/logs/streamlit.log /app/logs/fastapi.log &
TAIL_PID=$!

# 프로세스 종료 시 정리
cleanup() {
    echo "Shutting down services..."
    kill $STREAMLIT_PID $FASTAPI_PID $TAIL_PID 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# 두 프로세스 모두 완료될 때까지 대기
wait
