import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from src.Chatbot import prompt_templates
import openai
from datetime import datetime, timezone
import uuid
import tiktoken 
from src.utils.logger import logger
from src.utils.utils import get_rds_connection

load_dotenv()

class wisdom():

    def __init__(self, path=None):
        if path:
            self.root_dir = path
        else:
            self.root_dir = str(Path.cwd())
            
        os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
        self.embedding = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        self.MODEL_NAME = os.getenv("MODEL_NAME")
        
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.llm_api = openai.OpenAI(api_key=openai.api_key)
        self.llm = ChatOpenAI(temperature=0.0, model_name=self.MODEL_NAME)
        self.topic_llm = ChatOpenAI(temperature=0.0, model_name=self.MODEL_NAME, max_tokens=10)

        chromadb_path = f'{self.root_dir}/databases'
        self.wisdom_db = Chroma(collection_name="mm_rag_cj_blog", persist_directory=chromadb_path,
                                 embedding_function=self.embedding)

        self.refined_query_chain = self.__get_refine_query_chain()
        self.connection_pool = get_rds_connection()
        self.create_tables()  # Create tables on initialization
        self.insert_suggested_prompts()  # Insert suggested prompts on initialization

    def create_tables(self):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''CREATE TABLE IF NOT EXISTS chatrooms (
                        chatroom_id UUID PRIMARY KEY,
                        user_id TEXT,
                        topic TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )''')
                    cursor.execute('''CREATE TABLE IF NOT EXISTS conversations (
                        id SERIAL PRIMARY KEY,
                        chatroom_id UUID,
                        role TEXT,
                        content TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
                    cursor.execute('''CREATE TABLE IF NOT EXISTS suggested_prompts (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL
                    )''')
                    
                    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id SERIAL PRIMARY KEY, 
                    email TEXT, 
                    password TEXT)''')
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def get_db_connection(self):
        """Get a connection from the connection pool."""
        try:
            conn = self.connection_pool.getconn()
            if conn.closed:  # Check if the connection is closed
                logger.warning("Received a closed connection, reinitializing connection.")
                self.connection_pool = get_rds_connection()  # Reinitialize connection pool
                conn = self.connection_pool.getconn()
            return conn
        except Exception as e:
            logger.error(f"Error getting database connection: {e}")
            self.connection_pool = get_rds_connection()  # Reinitialize connection pool
            return self.connection_pool.getconn()

    def create_chatroom(self, user_id):
        chatroom_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)  # Ensure this is UTC
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO chatrooms (chatroom_id, user_id, created_at, updated_at)
                                  VALUES (%s, %s, %s, %s)''', (chatroom_id, user_id, now_utc, now_utc))
                conn.commit()
        except Exception as e:
            logger.error(f"Error creating chatroom: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool
        return chatroom_id

    def save_conversation(self, chatroom_id, role, content):
        now_utc = datetime.now(timezone.utc)  # Ensure this is UTC
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO conversations (chatroom_id, role, content)
                                  VALUES (%s, %s, %s)''', (chatroom_id, role, content))
                cursor.execute('''UPDATE chatrooms SET updated_at = %s WHERE chatroom_id = %s''',
                               (now_utc, chatroom_id))  # Save UTC timestamp
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_chatroom_history(self, chatroom_id, limit=10):
        rows = []
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''SELECT role, content, timestamp FROM conversations
                                  WHERE chatroom_id = %s ORDER BY timestamp DESC LIMIT %s''',
                               (chatroom_id, limit))
                rows = cursor.fetchall()
            return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in rows]
        except Exception as e:
            logger.error(f"Error getting chatroom history: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool
                
    def get_documents_by_query(self, query: str, num_docs: int):
        """Retrieve documents based on a query and the number of documents to return."""
        try:
            # Perform a similarity search in the wisdom_db
            results = self.wisdom_db.similarity_search(query, k=num_docs)
            
            # Convert results to a list of dictionaries if necessary
            documents = [{"document": result.page_content , "metadata": result.metadata} for result in results]  # Adjust based on your actual result structure
            return documents
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            raise e

    def insert_admin_user(self):
        admin_email = "test@test.com"  # Hardcoded admin email
        admin_password = "admin"  # Hardcoded admin password
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                # Check if the admin user already exists
                cursor.execute('SELECT COUNT(*) FROM users WHERE email = %s', (admin_email,))
                count = cursor.fetchone()[0]
                if count == 0:
                    cursor.execute('INSERT INTO users (email, password) VALUES (%s, %s)', (admin_email, admin_password))
                    conn.commit()
                    logger.info("Admin user created.")
                else:
                    logger.info("Admin user already exists.")
        except Exception as e:
            logger.error(f"Error inserting admin user: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool
    
    def insert_suggested_prompts(self):
        prompts = [
            "What impact could my personal wellbeing have on how I lead?",
            "How can I effectively deal with the stresses I face?",
            "What steps can I take to build a thriving team?",
            "How to support daily thriving?",
        ]
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM suggested_prompts')  # Delete existing values from the table
                cursor.executemany('INSERT INTO suggested_prompts (question) VALUES (%s)', [(prompt,) for prompt in prompts])
                conn.commit()
        except Exception as e:
            logger.error(f"Error inserting suggested prompts: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_suggested_prompts(self):
        rows = []
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT question FROM suggested_prompts')
                rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting suggested prompts: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def __get_refine_query_chain(self):
        prompt = PromptTemplate.from_template(template=prompt_templates.refine_query_prompt)
        chain = prompt | self.llm
        return chain
    
    def get_latest_chats_for_user(self, user_id, limit=3):
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            # Updated SQL query to select only chatroom_id and topic
            cursor.execute('''SELECT chatroom_id, topic FROM chatrooms WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s''', (user_id, limit))
            chatroom_ids = cursor.fetchall()
            if not chatroom_ids:
                logger.info(f"No chatrooms found for user_id: {user_id}")
                return []  # Return empty if no chatrooms exist

            logger.info(f"Latest Chatroom IDs: {chatroom_ids}")
            latest_chats = []

            for chatroom in chatroom_ids:
                chatroom_id, topic = chatroom  # Extract chatroom_id and topic from the tuple
                latest_chats.append({"chatroom_id": chatroom_id, "question": topic})  # Include only chatroom_id and topic
            return latest_chats
        except Exception as e:
            logger.error(f"Error getting latest chats for user: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_conversation_by_chatroom_id(self, chatroom_id, user_id, offset=0, limit=20):
        conn = None
        chatroom_history = []
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''SELECT role, content, timestamp FROM conversations
                                  WHERE chatroom_id = %s AND chatroom_id IN (
                                      SELECT chatroom_id FROM chatrooms WHERE user_id = %s
                                  ) ORDER BY timestamp DESC LIMIT %s OFFSET %s''',
                               (chatroom_id, user_id, limit, offset))
                rows = cursor.fetchall()
                for row in rows:
                    role, content, timestamp = row
                    formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp else None
                    chatroom_history.append({"role": role, "content": content, "timestamp": formatted_timestamp})
            return chatroom_history
        except Exception as e:
            logger.error(f"Error fetching conversation by chatroom ID: {e}")
            raise e
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_all_chatrooms(self, user_id, offset=0, limit=20):
        rows = []
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''SELECT chatroom_id, topic, created_at, updated_at FROM chatrooms
                                  WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s''',
                               (user_id, limit, offset))
                rows = cursor.fetchall()
            return [
                {
                    "chatroom_id": str(row[0]),  # Ensure UUID is a string
                    "topic": row[1],
                    "created_at": row[2].strftime("%Y-%m-%d %H:%M:%S.%f") + row[2].strftime("%z")[:3] + ":" + row[2].strftime("%z")[3:],  # Custom format with colon
                    "updated_at": row[3].strftime("%Y-%m-%d %H:%M:%S.%f") + row[3].strftime("%z")[:3] + ":" + row[3].strftime("%z")[3:]  # Custom format with colon
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting all chatrooms: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def delete_chatroom_conversations(self, chatroom_id):
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM conversations WHERE chatroom_id = %s', (chatroom_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error deleting chatroom conversations: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_num_tokens(self, text: str):
        return len(self.encoding.encode(text))

    def get_system_prompt(self, general_context, history):
        print("Getting custom system prompt")
        template_inputs = f""" **Context**: ```{general_context}```

        -----------------------------------------------------------------------------

        **Chat history**: ``{history}```

        """
        system_prompt = f"""{prompt_templates.SYSTEM_PROMPT}\n{template_inputs}"""
        
        return system_prompt

        
    def generate_conversation_topic(self, user_query, assistant_response):
        prompt = f"""
        Generate a short, concise, and relevant topic for the following conversation. 
        Only provide the topic without any extra words or phrases like here is the topic or the topic is or give heading of topic:
        
        User: {user_query}
        Assistant: {assistant_response}
        """
        
        response = self.topic_llm.invoke(prompt)
        print(response)
        
        return response.content.strip()

    def update_chatroom_topic(self, chatroom_id, topic):
        conn = None
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('''UPDATE chatrooms SET topic = %s WHERE chatroom_id = %s''', (topic, chatroom_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating chatroom topic: {e}")
        finally:
            if conn:
                self.connection_pool.putconn(conn)  # Ensure the connection is returned to the pool

    def get_query_response(self, query, user_id: str = '', chatroom_id: str = ''):
        try:
            history = self.get_chatroom_history(chatroom_id)
            history = history[::-1]  # Reverse the history
            logger.info(f"Chatroom History: {history}")

            refined_query = self.refined_query_chain.invoke(
                {"conversation_history": str(history),
                 "userPrompt": query})

            refined_query = refined_query.content

            general_context = self.wisdom_db.similarity_search_with_score(refined_query, k=8)
      
            messages = [
                {
                    "role": "system",
                    "content": self.get_system_prompt(
                        general_context=general_context,
                        history=history,
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
            response = self.llm_api.chat.completions.create(
                model=self.MODEL_NAME,
                messages=messages,
                stream=True,
            )

            logger.info(f"\n\n ----------------------")
            logger.info(f"User Query: {query} ")
            logger.info(f"Refined Query: {refined_query} ")
            logger.info(f"General Context: {str(general_context)}")

            return response

        except Exception as e:
            logger.error(f"Error getting query response: {e}")
            raise e
        

if __name__ == '__main__':
    pass