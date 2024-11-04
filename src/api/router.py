from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.Chatbot.bot import wisdom
from dotenv import load_dotenv
from typing import List
from src.utils.logger import logger
from src.models.models import CreateChatroomRequest, SuggestedPromptsResponse, ChatroomResponse, ConversationResponse, UserCredentials    
import threading

router = APIRouter()
bot = wisdom()
load_dotenv()

bot.insert_admin_user()

@router.get('')
async def index_page():
    return {"message": "Wisdom API"}



@router.post('/create_chatroom')
async def create_chatroom(request: CreateChatroomRequest):
    try:
        chatroom_id = bot.create_chatroom(request.user_id)
        return {"chatroom_id": chatroom_id}
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/generate_response')
async def generate_query_response(
        user_query: str = Body("Hello"),
        user_id: str = Body(''),
        chatroom_id: str = Body(''),

):
    try:
        response = bot.get_query_response(
            query=user_query,
            user_id=user_id,
            chatroom_id=chatroom_id
        )
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))

    def save_conversation_and_topic(content):
        """Thread function to save the conversation and generate the topic."""
        if content:  # Check if content is not empty
            bot.save_conversation(chatroom_id, "user", user_query)
            bot.save_conversation(chatroom_id, "assistant", content)

            # Generate and save the conversation topic if it's the first question
            if len(bot.get_chatroom_history(chatroom_id)) == 2:
                topic = bot.generate_conversation_topic(str(user_query), str(content))
                bot.update_chatroom_topic(chatroom_id, topic)
        else:
            logger.warning("No content to save for user_id: %s", user_id)

    def generate():
        content = ''  # Initialize content to collect the response
        for chunk in response:
            if chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content

        # Start a thread to save the conversation and topic after streaming
        threading.Thread(target=save_conversation_and_topic, args=(content,)).start()

    headers = {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache',
               'X-Accel-Buffering': 'no'}

    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)

@router.get('/suggested_prompts', response_model=SuggestedPromptsResponse)
async def get_suggested_prompts():
    try:
        prompts = bot.get_suggested_prompts()
        return {"prompts": prompts}
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/chatrooms/{user_id}', response_model=List[ChatroomResponse])
async def get_all_chatrooms(user_id: str, offset: int = Query(0), limit: int = Query(20)):
    try:
        chatrooms = bot.get_all_chatrooms(user_id, offset, limit)
        # Ensure topic is a valid string
        for chatroom in chatrooms:
            if chatroom['topic'] is None:
                chatroom['topic'] = ""
        return chatrooms
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/chatroom/{chatroom_id}/{user_id}', response_model=List[ConversationResponse])
async def get_conversation_by_chatroom_id(chatroom_id: str, user_id: str, offset: int = Query(0), limit: int = Query(20)):
    try:
        conversation = bot.get_conversation_by_chatroom_id(chatroom_id, user_id, offset, limit)
        return conversation
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth")
async def authenticate_user(credentials: UserCredentials):
    conn = None
    try:
        conn = bot.get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT password FROM users WHERE email = %s', (credentials.email,))
            result = cursor.fetchone()
            if result and result[0] == credentials.password:  # Check against plain text password
                return {"message": "Authentication successful"}
            else:
                raise HTTPException(status_code=400, detail="Incorrect email or password")
    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        if conn:
            bot.connection_pool.putconn(conn)
    
@router.get('/latest_chats/{user_id}')
async def get_latest_chats(user_id: str):
    try:
        latest_chats = bot.get_latest_chats_for_user(user_id, limit=3) 
        
        return {"latest_chats": latest_chats}  
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post('/reset_chat')
async def reset_chat(user_id: str, chatroom_id: str):
    try:
        bot.delete_chatroom_conversations(chatroom_id)
        return {"message": "Chat reset successfully."}
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get('/documents', response_model=List[dict])
async def get_documents(query: str, num_docs: int = Query(5)):
    """
    Get documents based on a query.
    
    - **query**: The search query.
    - **num_docs**: The number of documents to return (default is 5).
    """
    try:
        documents = bot.get_documents_by_query(query, num_docs)
        return documents
    except Exception as e:
        logger.info(e)
        raise HTTPException(status_code=500, detail=str(e))
