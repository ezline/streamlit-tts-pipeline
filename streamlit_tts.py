# streamlit_app.py
import re
import os
import wave
import base64
import requests
from datetime import datetime

import streamlit as st
from openai import OpenAI
from google.cloud import texttospeech

import utils.database as db
from utils.prompt import prompt
from utils.update_db import update_db
from utils.valid_text import is_valid_text
from utils.create_script import create_script
from utils.synthesize_text import synthesize_text

# ---------- 기본 설정 ----------
st.set_page_config(page_title="TTS page", page_icon="")

# secrets에서 불러오기
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
API_BASE = "http://127.0.0.1:8000" 
MODEL_NAME = "gpt-4.1-mini"

def enqueue_tts_batch(batch_id: str, record_dicts: list[dict]) -> dict:
    """FastAPI /ingest 로 배치 전송"""
    payload = {"batch_id": batch_id, "records": record_dicts}
    r = requests.post(f"{API_BASE}/ingest", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

@st.cache_resource
def get_client():
    from openai import OpenAI
    from google.cloud import texttospeech
    return OpenAI(api_key=OPENAI_API_KEY), texttospeech.TextToSpeechClient()

openai_client, gtts_client = get_client()

# ---------- 세션 시작 ----------
st.header("Text to Speech", divider="blue")

# --- 기본값 세팅 ---
WORKERS = [""]
UPLOAD_TYPES = [""]
# MODEL_NAMES = ["gpt-4.1-mini", "gpt-5-mini", "gpt-4o-mini"]
st.session_state.setdefault("worker", WORKERS[0])
st.session_state.setdefault("upload_type", UPLOAD_TYPES[0])
st.session_state.setdefault("model_name", MODEL_NAME)
st.session_state.setdefault("target_word", "")
st.session_state.setdefault("tts_name", {})
st.session_state.setdefault("tts_audio", {})
st.session_state.setdefault("inserted", {})
st.session_state.setdefault("inserted_ids", {})

# 조건: upload_type 선택이 끝나면 expander 자동으로 접힘
expander_open = st.session_state.upload_type == ""

with st.expander(f"{st.session_state.worker}/{st.session_state.upload_type}", expanded=expander_open):
    l1, r1 = st.columns([1, 1])
    # STEP 1: 작업자 선택
    l1.selectbox("작업자 선택:",
        WORKERS,
        key="worker",
    )
    # STEP 2: 업로드 타입 선택 (작업자 선택 후 노출)
    r1.selectbox("업로드 타입 선택:",
        UPLOAD_TYPES,
        key="upload_type",
    )
    if not st.session_state.worker:
        st.error("작업자를 선택해주세요.")
    elif not st.session_state.upload_type:
        st.error("업로드 타입을 선택해주세요.")
    else:
        pass
# STEP 3: 타겟 단어 입력 (이때는 이전 선택들은 박스 상단에만 표시)
if (st.session_state.worker != '' and st.session_state.upload_type != ''):
    with st.form("word_form"):
        l2, r2 = st.columns([8, 1])
        with l2:
            st.text_input("단어 입력:",
                    key="target_word",
                    placeholder="문장을 생성할 단어를 입력하세요.",
                )
        with r2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        submitted = r2.form_submit_button("제출")
    # STEP 4: 타겟 단어에 대한 문장 생성
    if submitted:
        if not st.session_state.target_word.strip():
            st.error("단어를 입력해 주세요.")
        else:
            with st.spinner('문장을 생성 중입니다...'):
                try:
                    if st.session_state.upload_type == 'ENG':
                        sentences = create_script(openai_client, prompt, st.session_state.target_word, st.session_state.model_name, label='ENG')
                    else:
                        sentences = create_script(openai_client, prompt, st.session_state.target_word, st.session_state.model_name)
                    st.session_state['sentences'] = sentences
                except Exception as e:
                    st.error(f"생성 중 오류가 발생했습니다: {e}")
    
# STEP 4: 생성된 문장별 수정/삽입 시행
sentences = st.session_state.get("sentences", [])
# 스타일: 위아래 마진 최소화
st.markdown("""
    <style>
    .sent-row { margin: 2px 0 !important; padding: 0 !important; }
    .sent-cell p { margin: 0 !important; }  /* st.write가 만드는 <p> 마진 제거 */
    .sent-hr { margin: 6px 0 !important; opacity: 0.3; }
    .stButton>button { padding: 0.25rem 0.5rem; }  /* 버튼 여백 축소 */
    </style>
""", unsafe_allow_html=True)

if sentences:
    # 헤더 행
    c1, c2, c3 = st.columns([1, 8.05, 0.95])
    with c1: st.markdown('<div class="sent-row sent-cell"><strong>번호</strong></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="sent-row sent-cell"><strong>문장</strong></div>', unsafe_allow_html=True)
    with c3: st.markdown('<div class="sent-row sent-cell"><strong>선택</strong></div>', unsafe_allow_html=True)
    st.markdown('<hr class="sent-hr">', unsafe_allow_html=True)

    # 각 문장 행
    for idx, sent in enumerate(sentences, start=1):
        c1, c2, c3 = st.columns([1, 8, 1])
        is_inserted = st.session_state.get(f"inserted_{idx}", False)
        with c1:
            st.markdown(f'<div class="sent-row sent-cell">{idx}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="sent-row sent-cell">{sent}</div>', unsafe_allow_html=True)
        with c3:
            if st.button("선택", key=f"gen_{idx}", disabled=is_inserted):
                if not is_inserted:
                    st.session_state[f"show_edit_{idx}"] = True
        st.markdown('<hr class="sent-hr">', unsafe_allow_html=True)

        # 👉 생성 버튼 누르면 해당 문장 아래에 편집란 표시
        if st.session_state.get(f"show_edit_{idx}", False):
            script_val = st.text_area("script(DB)", value=sent, key=f"script_{idx}", height=64)
            tts_val = st.text_area("tts", value=sent, key=f"tts_{idx}", height=64)
            if not is_valid_text(script_val):
                st.warning("script가 전사규칙에 맞지 않습니다.")
            else:
                pass
            if st.button("TTS 생성", key=f"ttsgen_{idx}"):
                with st.spinner("TTS 생성 중..."):    
                    try:
                        if st.session_state.upload_type == 'ENG':                        
                            response, name = synthesize_text(gtts_client, tts_val, "en-US")
                        else:
                            response, name = synthesize_text(gtts_client, tts_val, "ko-KR")
                        audio = response.audio_content
                        st.session_state[f'tts_name_{idx}'] = name
                        st.session_state[f'tts_audio_{idx}'] = audio
                        st.session_state[f'wav_base64'] = base64.b64encode(audio).decode('utf-8')
                        st.session_state[f'autoplay_tts_{idx}'] = True
                    except Exception as e:
                        st.error(f"TTS 생성 오류: {e}")

            if st.session_state.get(f"tts_audio_{idx}"):
                #처음 생성시에만 자동재생, 이후부터 재생 안 되도록
                if st.session_state.get(f"autoplay_tts_{idx}", False):
                    audio_tag = '<audio autoplay="true" src="data:audio/wav;base64,'+ st.session_state['wav_base64'] + '">'
                    st.markdown(audio_tag, unsafe_allow_html=True)
                    st.session_state[f"autoplay_tts_{idx}"] = False
                st.audio(st.session_state[f"tts_audio_{idx}"], format="audio/wav")
                disabled = st.session_state.get(f"inserted_{idx}", False)

                # 삽입 버튼을 눌렀을 때 기본 3개씩 생성되어지도록
                if st.button("Upload data X3", key=f"insert_{idx}", disabled=disabled):
                    #DB 삽입 로직 연결
                    try:
                        records = []
                        records.append({
                                        "worker": st.session_state.worker,
                                        "upload_type": st.session_state.upload_type,           # "ENR" | "KOR" | "ENG" | "ENR+KOR"
                                        "script": script_val,                                  # 전사 텍스트
                                        "tts_text": tts_val,                                   # 실제 TTS로 읽힌 텍스트
                                        "audio_name": st.session_state.get(f"tts_name_{idx}") or f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
                                        "audio_b64": st.session_state['wav_base64'],           # 이미 base64 인코딩되어 있음
                        })

                        with st.spinner("추가 TTS 생성 및 업로드 중..."):
                            for _ in range(2):
                                if st.session_state.upload_type == 'ENG':
                                    response, name = synthesize_text(gtts_client, tts_val, "en-US")
                                else:
                                    response, name = synthesize_text(gtts_client, tts_val, "ko-KR")
                                wav_b64 = base64.b64encode(response.audio_content).decode("utf-8")
                                records.append({
                                    "worker": st.session_state.worker,
                                    "upload_type": st.session_state.upload_type,
                                    "script": script_val,
                                    "tts_text": tts_val,
                                    "audio_name": name,
                                    "audio_b64": wav_b64,
                                })
                        # FastAPI에 배치 큐 요청
                        batch_id = f"tts-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                        res = enqueue_tts_batch(batch_id, records)
                        job_id = res["job_id"]
                        r = requests.get(f"{API_BASE}/jobs/{job_id}")
                        status_payload = r.json()
                                                
                        if status_payload["status"] == "done":
                            st.session_state[f'inserted_ids_{idx}'] = status_payload["inserted_ids"]
                        # DB 삽입 후 화면에 수정된 문장이 표시되도록
                        display_after = script_val.strip()
                        st.session_state["sentences"][idx-1] = display_after
                        st.session_state[f"inserted_{idx}"] = True
                        st.session_state.pop(f"show_edit_{idx}", None)
                        st.session_state.pop(f"tts_name_{idx}", None)
                        st.session_state.pop(f"tts_audio_{idx}", None)
                        st.session_state.pop(f"wav_base64", None)
                        st.rerun()
                    
                    except requests.HTTPError as he:
                        try:
                            detail = he.response.json()
                        except Exception:
                            detail = he.response.text
                        st.error(f"API 오류: {detail}")
                    except Exception as e:
                        st.error(f"Que 적재/요청 중 오류: {e}")

        if is_inserted:
            st.success(f"id: {sorted(st.session_state[f'inserted_ids_{idx}'])}, DB 삽입 완료 ✅")

# ----- 작업 완료 후 단어 입력부터 -----
    if st.button("처음으로", use_container_width=True):
        for k in list(st.session_state.keys()):
            if not k.startswith(("upload_", "worker", "model_", "target_")):
                st.session_state.pop(k, None)
        st.rerun()
