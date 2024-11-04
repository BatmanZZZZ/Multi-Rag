import os
import uuid
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Initialize session state variables
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback" not in st.session_state:
    st.session_state.feedback = []
if "disabled" not in st.session_state:
    st.session_state["disabled"] = False
if "show_input" not in st.session_state:
    st.session_state["show_input"] = False
if "current_feedback_id" not in st.session_state:
    st.session_state["current_feedback_id"] = None
if "current_feedback_question" not in st.session_state:
    st.session_state["current_feedback_question"] = None
if "chatroom_id" not in st.session_state:
    # Create a new chatroom
    response = requests.post(os.getenv("LOCALHOST_API_CREATE_CHATROOM"), json={"user_id": st.session_state["user_id"]})
    if response.status_code == 200:
        st.session_state["chatroom_id"] = response.json()["chatroom_id"]
    else:
        st.error("Failed to create chatroom")
        
st.title("Simpla Multi-Modal Chatbot")




# Display chat messages
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)
        if message["role"] == "assistant":
            col1, col2, col3 = st.columns(3)
            with col3:
                col4, col5 = st.columns(2)
                with col4:
                    if st.button("👍", key=f"like_{i}"):
                        feedback_id = st.session_state.messages[i]["id"]
                        payload = {
                            "id": feedback_id,
                            "feedback": 1,
                            "desired_answer": "NULL"
                        }
                        feedback_endpoint = os.getenv("LOCAL_HOST_UPDATE_FEEDBACK")
                        response = requests.post(feedback_endpoint, json=payload)
                        st.rerun()
                with col5:
                    if st.button("👎", key=f"dislike_{i}"):
                        feedback_id = st.session_state.messages[i]["id"]
                        st.session_state["show_input"] = True
                        st.session_state["current_feedback_id"] = feedback_id
                        st.session_state["current_feedback_question"] = st.session_state.messages[i-1]["content"]
                        payload = {
                            "id": feedback_id,
                            "feedback": -1,
                            "desired_answer": "NULL"
                        }
                        feedback_endpoint = os.getenv("LOCAL_HOST_UPDATE_FEEDBACK")
                        response = requests.post(feedback_endpoint, json=payload)
                        st.rerun()

if st.session_state["show_input"]:
    st.write(f'')
    st.markdown(f'<p style="font-size:20px;">Please provide your desired answer for question: <b> {st.session_state["current_feedback_question"]}</b></p>', unsafe_allow_html=True)
    desired_answer = st.text_input("Your desired answer:")
    if st.button("Send"):
        feedback_id = st.session_state["current_feedback_id"]
        payload = {
            "id": feedback_id,
            "feedback": -1,
            "desired_answer": desired_answer
        }
        feedback_endpoint = os.getenv("LOCAL_HOST_UPDATE_FEEDBACK")
        response = requests.post(feedback_endpoint, json=payload)
        st.session_state["show_input"] = False
        st.session_state["current_feedback_id"] = None
        st.rerun()

if prompt := st.chat_input("Query"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)
    assistant_message_placeholder = st.empty()
    with assistant_message_placeholder.chat_message("assistant"):
        stream_container = st.empty()
        
        with st.spinner("Thinking..."):
            endpoint = os.getenv('LOCALHOST_API_URL')
            payload = {
                "user_query": prompt,
                "user_id": st.session_state["user_id"],
                "chatroom_id": st.session_state["chatroom_id"]
            }
            
            response = requests.post(endpoint, json=payload, stream=True)

            content_response = ""
            if response.status_code == 200:
                for token in response.iter_content(512):
                    if token:
                        token = token.decode('utf-8')
                        content_response += token
                        stream_container.markdown(content_response, unsafe_allow_html=True)
                human_message = {'question':  prompt}
                ai_message = {'output_key': content_response}
                
                feedback_id = str(uuid.uuid4())
                st.session_state.messages.append(
                        {"role": "assistant", "content": content_response, "id": feedback_id})
                feedback_endpoint = os.getenv("LOCAL_HOST_FEEDBACK")
                payload = {
                    "id": feedback_id,
                    "userid": st.session_state["user_id"],
                    "question": prompt,
                    "answer": content_response,
                    "feedback": 0
                }
                # response = requests.post(feedback_endpoint, json=payload)
                st.rerun()
                
            else:
                print(response)