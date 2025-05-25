from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp_client import MCPClient
from pydantic import BaseModel
from typing import Dict,Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    server_script_path:str="F:\\Praveen_Repository\\mcp-server\\main.py"

settings=Settings()

@asynccontextmanager
async def lifespan(app:FastAPI):
    client=MCPClient()
    try:
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise HTTPException(
                status_code=500,
                detail="Failed to Connect to MCP Server"
            )
        app.state.client=client
        yield
    except Exception as e:
        print(f"Error during lifespan: {e}")
        raise e
    finally:
        # shutdown
        await client.cleanup()

app=FastAPI(
    title="MCP Client API",
    lifespan=lifespan
)

#Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query:str

class Message(BaseModel):
    role:str
    content:Any

class ToolCall(BaseModel):
    name:str
    args:Dict[str,Any]

@app.post("/query")
async def process_query(request:QueryRequest):
    try:
        messages= await app.state.client.process_query(request.query)
        return {"messages":messages}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)