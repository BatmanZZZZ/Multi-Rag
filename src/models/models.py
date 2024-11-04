from typing import List
from pydantic import BaseModel



class Message(BaseModel):
    content: str

class ChatHistoryRequest(BaseModel):
    user_id: str

    
class UserCredentials(BaseModel):
    email: str
    password: str


class CreateChatroomRequest(BaseModel):
    user_id: str

class ChatroomResponse(BaseModel):
    chatroom_id: str
    topic: str
    created_at: str
    updated_at: str

class ConversationResponse(BaseModel):
    role: str
    content: str
    timestamp: str
    
class SuggestedPromptsResponse(BaseModel):
    prompts: List[str]
