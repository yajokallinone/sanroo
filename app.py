import time
import requests
import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Chatbot", layout="centered")

# โหลดค่า .env
webhook_url = os.getenv("WEBHOOK_URL")
username = os.getenv("USERNAME", "user-test")
send_history = os.getenv("SEND_HISTORY", "true").lower() == "true"

# ถ้าไม่พบ WEBHOOK_URL → หยุดโปรแกรมตรงนี้ เอาขึ้นบน UI ให้รู้
if not webhook_url:
    st.error("⛔ ไม่พบตัวแปร WEBHOOK_URL ในไฟล์ .env กรุณาตั้งค่าก่อนใช้งาน")
    st.stop()

st.title("Chatbot งานบริการการศึกษาฯ (ทดสอบ)")

# st.write("ตัวอย่าง UI แชตที่ยิง API ไปยัง n8n webhook")

# -------------------------------
# Initialize session state
# -------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_error" not in st.session_state:
    st.session_state.last_error = None

# -------------------------------
# ฟังก์ชันเรียก n8n webhook
# -------------------------------
def call_n8n(message: str, conversation=None, username: str = None):
    payload = {
        "message": message,
        "timestamp": int(time.time()),
    }
    if username:
        payload["username"] = username
    if conversation is not None:
        payload["conversation"] = conversation

    try:
        r = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()

        # รองรับทั้ง JSON และ text
        reply_text = ""
        raw = None
        ct = r.headers.get("content-type", "")
        if "application/json" in ct.lower():
            data = r.json()
            raw = data
            # รองรับรูปแบบ {"reply": "..."} หรือโครงสร้างอื่น
            if isinstance(data, dict):
                reply_text = (
                    data.get("reply")
                    or data.get("answer")
                    or data.get("text")
                    or data.get("message")
                    or str(data)
                )

            # กรณี 2: เป็น list ของ dicts → เอา 'answer' ของตัวสุดท้าย/ตัวแรกที่เจอ
            elif isinstance(data, list) and data:
                # หาอันสุดท้ายที่มีคีย์ answer
                ans = None
                for item in reversed(data):
                    if isinstance(item, dict) and "answer" in item:
                        ans = item["answer"]
                        break
                # ถ้าไม่เจอ answer ลอง reply/text/message
                if ans is None:
                    for item in reversed(data):
                        if isinstance(item, dict):
                            ans = item.get("reply") or item.get("text") or item.get("message")
                            if ans:
                                break
                reply_text = ans or str(data)

        return reply_text.strip(), raw, None

    except requests.exceptions.RequestException as e:
        return "", None, f"Webhook error: {e}"

# -------------------------------
# แสดงประวัติการคุย
# -------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------
# ช่องพิมพ์ข้อความผู้ใช้
# -------------------------------
user_input = st.chat_input("พิมพ์คำถามแล้วกด Enter...")
if user_input:
    # เพิ่มข้อความของ user
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # เตรียม conversation (เฉพาะ role/content)
    conversation = None
    if send_history:
        conversation = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

    # เรียก n8n
    with st.chat_message("assistant"):
        with st.spinner("..."):
            reply, raw, err = call_n8n(
                message=user_input,
                conversation=conversation,
                username=username.strip() or None,
            )
        if err:
            st.error(err)
            st.session_state.last_error = err
        else:
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

# -------------------------------
# ส่วนเสริมเล็กน้อย: ปุ่มล้างแชต
# -------------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("🧹 ล้างประวัติแชต"):
        st.session_state.messages = []
        st.session_state.last_error = None
        st.rerun()
with col2:
    if st.session_state.last_error:
        st.info("พบข้อผิดพลาดล่าสุด: " + st.session_state.last_error)
