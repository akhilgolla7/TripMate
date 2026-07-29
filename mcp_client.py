from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq
import os
from typing import cast

load_dotenv()

AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# MCP Severs
client = MultiServerMCPClient(
    cast(dict, {
            "tavily":{
                "transport":"streamable_http",
                "url":f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
            },
            
            "Aviationstack MCP": {
                "transport": "stdio",
                "command": "python",
                "args": [
                    "-m",
                    "aviationstack_mcp",
                ],
                "env": {
                    "AVIATION_STACK_API_KEY": AVIATIONSTACK_API_KEY,
                },
            }
        })
)


async def get_all_tools():
    tools = await client.get_tools()
    print("Available tools:")
    for tool in tools:
        print(f" - {tool.name}")


search_tool = None
aviation_tools = {}

async def initialize_mcp():
    
    global search_tool
    global aviation_tools
    
    if search_tool is not None and aviation_tools:
        return
    
    tools = await client.get_tools()
    
    search_tool = next((tool for tool in tools if tool.name == "tavily_search"), None)
    
    aviation_tools = {tool.name : tool for tool in tools if tool.name != "tavily_search"}
    


async def run_tavily_mcp_search(query: str):
    await initialize_mcp()
    if search_tool is None:
        raise ValueError("tavily_search tool not found")
    
    result = await search_tool.ainvoke({"query": query})
    #print(f"Result: {result}")
    return result

async def aviation_mcp_call(tool_name : str, tool_args: str | None):
    tools = await client.get_tools()
    tool = next(t for t in tools if t.name == tool_name)
    result = await tool.ainvoke(tool_args or {})
    return result
        
    