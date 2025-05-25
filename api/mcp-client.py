from typing import Optional
from contextlib import AsyncExitStack
import traceback
from utils.logger import logger
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import StdioClient
from datetime import datetime
from utils import logger
import json
import os

from anthropic import Anthropic
from anthropic.types import Message
from anthropic import ChatMessage, ChatCompletion

class MCPClient:
    def __init__(self):
        #initialize session and client objects
        self.session: Optional[ClientSession] =None
        self.exit_stack=AsyncExitStack()
        self.llm=Anthropic()
        self.tools=[]
        self.messages=[]
        self.logger=logger

    #connect to mcp  server
    async def connect_to_server(self,server_script_path:str):
        try:
            is_python=server_script_path.endswith(".py")
            is_js=server_script_path.endswith(".js")
            if not(is_python or is_js):
                raise ValueError("Server script must be a .py or .js file")

            command="python" if is_python else "node"
            server_params=StdioServerParameters(
                command=command,
                args=[server_script_path],env=None
            )
            
            stdio_transport=await self.exit_stack.enter_async_context(
                StdioClient(server_params)
            )
            self.stdio,self.write=stdio_transport
            self.session=await self.exit_stack.enter_async_context(
                ClientSession(stdio_transport)
            )
            
            await self.session.initialize()

            self.logger.info("Connected to mcp server")

            mcp_tools= await self.get_mcp_tools()
            self.tools=[{
                "name":tool.name,
                "description":tool.description,
                "parameters":tool.parameters
            } 
            for tool in mcp_tools
            ]

            self.logger.info (f"Available tools:{[tool['name'] for tool in self.tools]}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to mcp server:{e}")
            traceback.print_exc()
            raise

    #call the mcp tool from mcp server

    #get mcp tool list
    async def get_mcp_tools(self):
        try:
            response=await self.session.list_tools()
            return response.tools
        except Exception as e:
            self.logger.error(f"Failed to get mcp tools:{e}")
            raise 

    #process query
    async def process_query(self,query:str):
        try:
            self.logger.info(f"Processing query:{query}")
            user_message={"role":"user","content":query}
            self.messages=[user_message]
            
            while True:
                response=await self.call_llm()

                #the response is a text messaage
                if response.content[0].type=="text" and len(response.content)==1:
                    assistant_message={
                        "role":"assistant",
                        "content":response.content[0].text,
                    }
                    self.messages.append(assistant_message)
                    await self.log_conversation()
                    break

                #the response is a tool call
                assistant_message={
                    "role":"assistant",
                    "content":response.to_dict()["content"],
                }
                self.messages.append(assistant_message)
                await self.log_conversation()


                for content in response.content:
                    if content.type=="text":
                        self.messages.append(
                            {
                            "role":"assistant",
                            "content":content.text,
                            }
                            )
                    if content.type=="tool_call":
                        tool_name=content.name
                        tool_args=content.input
                        tool_use_id=content.id
                        self.logger.info(
                            f"Calling tool {tool_name} with args {tool_args}"
                        )
                        try:
                            result=await self.call_tool(tool_name,tool_args)
                            self.logger.info(f"Tool {tool_name} returned {result[:100]}...")
                            self.messages.append(
                                {
                                "role":"user",
                                "content":[
                                    {
                                        "type":"tool_result",
                                        "tool_use_id":tool_use_id,
                                        "content":result.content,
                                    }
                                ]
                                }
                           )
                        await self.log_conversation()
                    except Exception as e:
                        self.logger.error(f"Failed to call tool {tool_name}:{e}")
                        raise
                        
            return self.messages

        except Exception as e:
            self.logger.error(f"Failed to process query:{e}")
            traceback.print_exc()
            raise
    #call llm
    async def call_llm(self):
        try:
            self.logger.info("Calling LLM")
            return await self.llm.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=self.messages,
                tools=self.tools,
            )
        except Exception as e:
            self.logger.error(f"Failed to call llm:{e}")
            raise
    #cleanup
    async def cleanup(self):

    async def log_converrsation(self):
        os.makedirs("conversations",exist_ok=True)

        serializable_conversations=[]

        for message in self.messages:
            try:
                serialize_messsage={
                    "role":message["role"],
                    "content":message["content"],
                }
                serializable_conversations.append(serialize_messsage)
            except Exception as e:
                self.logger.error(f"Failed to serialize message:{e}")
                raise
        
        timestamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        conversation_file_path=f"conversations/conversation_{timestamp}.json"
        try:
            with open(conversation_file_path,"w") as f:
                json.dump(serializable_conversations,f,indent=4)
            self.logger.info(f"Logged conversation to {conversation_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to log conversation:{e}")
            raise
        
        try:
            await self.exit_stack.aclose()
            self.logger.info("Disconnected from MCP Server")
        except Exception as e:
            self.logger.error(f"Failed to cleanup mcp client:{e}")
            traceback.print_exc()
            raise
    #extra

    #log conversation