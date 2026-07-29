# TripMate
TripMate - multi agent travel partner

## How to run
###### Create the virtual env

- conda create -n travel python=3.14 -y

###### Acivate the Environment

- conda activate travel

##### install requirements

- pip install -r requirements.txt

4. >> uv pip compile pyproject.toml -o requirements.txt
   >> uv run fastapi dev main.py 

#### Render
 - uv run uvicorn main:app --host 0.0.0.0 --port $PORT



# ** Converting TripMate from Synchronous to Asynchronous Architecture **

## Overview

Initially, the application was using a synchronous execution flow where LangGraph operations, database checkpoints, and tool executions were handled using blocking calls. To support FastAPI's asynchronous architecture and use `await graph.ainvoke()`, we migrated the application to a fully asynchronous workflow.

The main goal of this migration was to prevent blocking operations, improve scalability, and correctly integrate LangGraph's async execution model with FastAPI.

---

## 1. Replaced Synchronous LangGraph Execution with Async Execution

### Before

The application was using synchronous graph execution:

```python
result = travel_graph.invoke(
    input_data,
    config=config
)
```

The synchronous `invoke()` method blocks the current thread until the graph execution completes.

### After

Changed to asynchronous execution:

```python
result = await travel_graph.ainvoke(
    input_data,
    config=config
)
```

The async version allows other requests to continue processing while waiting for external operations such as API calls, database operations, and LLM responses.

---

## 2. Converted Synchronous Postgres Checkpointer to Async Postgres Checkpointer

### Before

The application used:

```python
from langgraph.checkpoint.postgres import PostgresSaver
```

with:

```python
checkpointer = PostgresSaver(connection)
```

`PostgresSaver` only supports synchronous graph execution using:

```python
graph.invoke()
```

It does not implement async checkpoint methods required by:

```python
graph.ainvoke()
```

which caused:

```
NotImplementedError: aget_tuple
```

---

### After

Replaced it with:

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
```

and initialized:

```python
checkpointer = AsyncPostgresSaver(connection)
```

The async checkpointer provides:

* `aget_tuple()`
* async checkpoint reads
* async checkpoint writes

which are required by LangGraph async execution.

---

## 3. Converted PostgreSQL Connection from Sync to Async

### Before

The application used:

```python
from psycopg import Connection

connection = Connection.connect(...)
```

This creates a blocking database connection.

---

### After

Changed to:

```python
from psycopg import AsyncConnection

connection = await AsyncConnection.connect(...)
```

The database operations can now run asynchronously without blocking FastAPI worker threads.

---

## 4. Added Async Database Initialization

Previously, database initialization happened immediately during module import.

Example:

```python
connection = Connection.connect(...)
checkpointer.setup()
```

This approach does not work with async operations because Python does not allow:

```python
await
```

outside an async function.

---

The initialization was moved into an async startup function:

```python
async def init_graph(database_url: str):

    connection = await AsyncConnection.connect(...)

    checkpointer = AsyncPostgresSaver(connection)

    await checkpointer.setup()

    travel_graph = graph.compile(
        checkpointer=checkpointer
    )
```

This ensures the database and graph are ready before handling API requests.

---

## 5. Added FastAPI Lifespan Startup Handling

Since the graph requires asynchronous initialization, FastAPI's lifespan mechanism was added.

Before:

```python
app = FastAPI()
```

After:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):

    await init_graph(DATABASE_URL)

    yield


app = FastAPI(
    lifespan=lifespan
)
```

The application startup flow is now:

```
FastAPI Starts
        |
        ↓
Lifespan Executes
        |
        ↓
Initialize Async PostgreSQL Connection
        |
        ↓
Setup Async Checkpointer
        |
        ↓
Compile LangGraph
        |
        ↓
Accept API Requests
```

---

## 6. Removed nest_asyncio Usage

Previously:

```python
import nest_asyncio
nest_asyncio.apply()
```

was used to allow nested event loops.

This was removed because FastAPI with Uvicorn already manages the asyncio event loop.

Additionally, `nest_asyncio` is incompatible with `uvloop`, which caused:

```
ValueError: Can't patch loop of type <class 'uvloop.Loop'>
```

The application now relies on FastAPI/Uvicorn's native async event loop.

---

## 7. Converted Agent Functions to Async

Agent functions that perform async operations were changed.

### Before:

```python
def hotel_agent(state):
    result = asyncio.run(search())
```

This caused:

```
asyncio.run() cannot be called from a running event loop
```

because FastAPI already runs inside an event loop.

---

### After:

```python
async def hotel_agent(state):

    result = await search()

    return result
```

The function now directly participates in the existing async event loop.

---

## 8. Removed Blocking asyncio.run()

Before:

```python
hotel_data = asyncio.run(
    run_tavily_search(query)
)
```

Problem:

```
RuntimeError:
asyncio.run() cannot be called from a running event loop
```

After:

```python
hotel_data = await run_tavily_search(query)
```

The existing event loop handles execution.

---

## Final Async Architecture

The final execution flow is:

```
Client Request
       |
       ↓
FastAPI Async Endpoint
       |
       ↓
await run_travel_agent()
       |
       ↓
await travel_graph.ainvoke()
       |
       ↓
Async LangGraph Nodes
       |
       ↓
Async Tools (Tavily, LLM APIs)
       |
       ↓
Async PostgreSQL Checkpointer
       |
       ↓
Response Returned
```

---

## Benefits of Migration

* Non-blocking API execution
* Better handling of multiple simultaneous users
* Compatible with FastAPI async endpoints
* Supports LangGraph async execution
* Enables async database checkpoint persistence
* Removes event loop conflicts
* Improves scalability for external API calls and LLM workflows

The application is now following a fully asynchronous architecture from API layer → LangGraph → tools → database layer.

## *****************************************************************