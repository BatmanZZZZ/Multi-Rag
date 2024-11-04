from .router import router


def create_app():
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="Simpla API",
        description="Generate response from The RAG chatbot based on user query",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.max_request_size = 200 * 1024 * 1024

    # Set up CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["null", "*"],  
        allow_credentials=True,
        allow_methods=["*"], 
        allow_headers=["*"],
    )

    app.include_router(router, tags=["Simpla Bot"], prefix="/api")

    return app
