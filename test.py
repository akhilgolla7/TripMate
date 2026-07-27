import asyncio
from mcp_client_test import get_all_tools, run_tavily_mcp_search

if __name__ == "__main__":
    asyncio.run(run_tavily_mcp_search("what are the best hotels in India?"))

















# from tools.tavily_tool import tavily_search
# from backend import run_travel_agent

# # query = " what are the best hotels in India"
# # results = tavily_search(query)
# # print(results)

# user_input = input("Enter your travel query: ")

# response = run_travel_agent(
#     user_input=user_input,
#     thread_id="test_user"
#     )

# print(f"Response: \n\n{response['answer']}")