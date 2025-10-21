import streamlit as st
import requests
import uuid
import json
import os
import re
from datetime import datetime

API_URL = "http://127.0.0.1:5050"
DATA_DIR = "data/conversations"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Helper functions ---
def list_conversations():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    return sorted(files, reverse=True)

def load_conversation(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_conversation(filename, messages):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)

# --- Streamlit setup ---
st.set_page_config(page_title="Fintech Agent with Memory", layout="wide")
st.markdown("<h2 style='text-align:center;'>Fintech Conversational Agent</h2>", unsafe_allow_html=True)
st.caption("Persistent Memory + FastAPI + FAISS + OpenAI + Streamlit")

# --- Sidebar: Conversation Tabs ---
st.sidebar.header("Conversations")

if "current_conv" not in st.session_state:
    st.session_state.current_conv = None

convs = list_conversations()

selected = st.sidebar.selectbox("Select a conversation:", ["New Chat"] + convs)

if selected == "New Chat":
    conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{conv_id}.json"
    st.session_state.current_conv = filename
    st.session_state.messages = []
else:
    st.session_state.current_conv = selected
    st.session_state.messages = load_conversation(selected)

st.sidebar.markdown("---")

# --- Sidebar: Upload text ---
st.sidebar.header("Upload Fintech Text")
content = st.sidebar.text_area("Paste your Fintech document content:")
if st.sidebar.button("Upload"):
    if content.strip():
        r = requests.post(f"{API_URL}/ingest", json={"content": content, "metadata": {"title": "User Upload"}})
        if r.status_code == 200:
            st.sidebar.success(" Ingested successfully!")
        else:
            st.sidebar.error(f"Failed: {r.text}")
    else:
        st.sidebar.warning("Please paste content first.")

# --- Display chat history ---
for role, msg in st.session_state.messages:
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(msg)

# --- Chat input ---
if query := st.chat_input("Ask your Fintech question here..."):
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.messages.append(("user", query))

    # --- Handle "previous messages" memory query ---
    if re.search(r"\b(previous|past)\s+(messages|questions|conversation|chats?)\b", query, re.IGNORECASE):
        if len(st.session_state.messages) > 1:
            history_md = "\n\n".join([
                f"**You:** {u}\n\n**Agent:** {a}"
                for (u, a) in zip(
                    [m[1] for m in st.session_state.messages if m[0] == "user"],
                    [m[1] for m in st.session_state.messages if m[0] == "assistant"],
                )
            ])
            answer = f"Here’s your conversation so far:\n\n{history_md}"
        else:
            answer = "You haven’t had any previous messages yet!"
    else:
        try:
            r = requests.post(f"{API_URL}/ask",
                              json={"query": query, "session_id": st.session_state.current_conv},
                              timeout=30)
            if r.status_code == 200:
                data = r.json()
                answer = data.get("answer", "(no answer)")
            else:
                answer = f"API Error: {r.text}"
        except requests.exceptions.RequestException as e:
            answer = f"API Connection Error: {e}"

    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.messages.append(("assistant", answer))

    # Save after every interaction
    save_conversation(st.session_state.current_conv, st.session_state.messages)
