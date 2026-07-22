from tools.tavily_tool import tavily_search


query = " what are the best hotels in India"
results = tavily_search(query)
print(results)