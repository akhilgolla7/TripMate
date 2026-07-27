import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, cast
import operator
import uuid

# from psycopg import Connection
from psycopg import AsyncConnection
from psycopg.rows import dict_row, DictRow

from langgraph.graph import StateGraph, START, END
# from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    SystemMessage,
    AIMessage
)
from langchain_groq import ChatGroq
from pydantic import SecretStr

# from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from mcp_client_test import run_tavily_mcp_search
import asyncio

from langchain_core.runnables import RunnableConfig



#connect to remote postgres database
def get_databse_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set.")
    
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url += f"{separator}sslmode=require"

    return database_url


#get the Groq Api key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set.")

## Initialize the ChatGroq model
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=SecretStr(GROQ_API_KEY),
    # temperature=0.7,
    # streaming=False,
    # verbose=True
)


#define the State

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight Results Retrieved")],
        "llm_calls": state["llm_calls"] + 1
    }

async def hotel_agent(state: TravelState):
    query = state["user_query"]
    # hotel_data = tavily_search(query)
    hotel_data = await run_tavily_mcp_search(query)

    return {
        "hotel_results": hotel_data,
        "messages": [AIMessage(content="Hotel Results Retrieved")],
        "llm_calls": state["llm_calls"] + 1
    }

def itinerary_agent(state: TravelState):
    user_query = state["user_query"]
    flight_results = state["flight_results"]
    hotel_results = state["hotel_results"]

    # Combine flight and hotel results into a single prompt for the LLM
    prompt = f"User Query: {user_query}\n Flight Results: {flight_results}\nHotel Results: {hotel_results}\nPlease create a travel itinerary based on the above information."

    # Call the LLM to generate the itinerary
    itinerary = llm.invoke([
        SystemMessage(content="You are a travel assistant that creates itineraries based on flight and hotel information."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": itinerary.content,
        "messages": [itinerary],
        "llm_calls": state["llm_calls"] + 1
    }


def final_agent(state: TravelState):

    final_prompt = f"""
You are an expert AI Travel Planner.

Your objective is to create a COMPLETE travel plan that is both
FACTUALLY GROUNDED and USEFUL.

==================================================
AVAILABLE DATA
==================================================

USER REQUEST
-------------
{state["user_query"]}

FLIGHTS (Authoritative API)
---------------------------
{state["flight_results"]}

HOTELS (Authoritative API)
--------------------------
{state["hotel_results"]}

CAR RENTALS (Authoritative API)
-------------------------------
{state.get("car_results","No data")}

DESTINATION INFORMATION (Web Search)
------------------------------------
{state.get("web_context","No web results")}

GENERATED ITINERARY
-------------------
{state["itinerary"]}

==================================================
SOURCE PRIORITY
==================================================

Use information in this priority order:

1. Flight API
2. Hotel API
3. Car Rental API
4. Generated itinerary
5. Web Search (background knowledge only)

Never invent prices or availability.

If APIs do not return inventory, clearly state that no live inventory was found.

However...

DO NOT stop there.

Use the destination knowledge from WEB CONTEXT and your travel expertise to still
produce a rich travel guide.

==================================================
GROUNDING RULES
==================================================

Flights
--------

Only list flights that appear in Flight API.

Hotels
-------

Only list hotels returned by Hotel API as bookable options.

Car Rentals
------------

Only list rental companies returned by Car Rental API.

Prices
-------

Every price must come from an API.

Never invent:

• airfare
• hotel rates
• rental rates

WEB CONTEXT
-----------

Web context is NOT booking inventory.

Use it only for:

• destination overview
• neighborhoods
• attractions
• weather
• transportation
• airport information
• travel tips
• visa information
• local events
• seasonal advice

Never use web context as hotel inventory.

==================================================
IF APIs RETURN NO RESULTS
==================================================

This is IMPORTANT.

If no flights/hotels/cars are available:

❌ Do NOT end the answer after saying data is unavailable.

Instead:

• explain that live inventory wasn't found
• recommend popular airlines serving the route
• recommend well-known hotel areas
• recommend trusted rental companies
• recommend booking websites
• recommend best airports
• recommend when to book
• recommend alternative airports

Clearly label these as:

"Suggested Options (Not Live Availability)"

Do NOT include prices for suggested options.

==================================================
TRAVEL EXPERT MODE
==================================================

Always provide destination recommendations, even if APIs return nothing.

Include:

Top attractions

Hidden gems

Family activities

Nightlife

Shopping

Museums

Outdoor attractions

Best restaurants

Best local food

Recommended neighborhoods

Transportation options

Safety tips

Money-saving tips

Best day trips

Weather

Packing suggestions

==================================================
ITINERARY
==================================================

If itinerary exists:

Expand it into a detailed daily schedule.

Include:

Morning

Lunch

Afternoon

Evening

Dinner

Estimated sightseeing time

Nearby attractions

Travel time

If itinerary is empty:

Generate a recommended itinerary using destination knowledge.

Never leave this section empty.

==================================================
BUDGET
==================================================

Budget must be transparent.

Use API prices whenever available.

If prices are missing:

Show:

Flights:
Not Available

Hotels:
Not Available

Car Rental:
Not Available

Activities:
Estimated only

Food:
Estimated only

Transport:
Estimated only

Mention which numbers are estimates.

==================================================
HOTEL RECOMMENDATIONS
==================================================

If Hotel API has results:

Create a comparison table.

Name

Area

Rating

Nightly Rate

Amenities

Distance to city center

Why choose it

If Hotel API has no results:

Recommend the BEST AREAS to stay such as:

• Las Vegas Strip
• Downtown
• Summerlin

Then recommend popular hotels WITHOUT prices.

Clearly mark:

"Popular Hotels (Availability Unknown)"

==================================================
CAR RENTALS
==================================================

If API returns rentals:

Create comparison table.

Otherwise recommend trusted companies:

Enterprise

Hertz

Avis

Budget

Alamo

National

Clearly state:

Availability must be checked.

==================================================
RESPONSE FORMAT
==================================================

# Trip Overview

Destination

Dates

Travelers

Budget

Travel style

# Flight Options

(table)

# Hotel Options

(table)

# Car Rental Options

(table)

# Recommended Places to Stay

(neighborhood guide)

# 5-Day Itinerary

Detailed daily plan.

# Top Attractions

Bullet list.

# Food Recommendations

Local restaurants and must-try dishes.

# Shopping

# Nightlife

# Transportation Guide

# Estimated Budget

Separate:

Verified Costs

Estimated Costs

Grand Total Range

# Money Saving Tips

# Things to Know Before You Go

# Booking Recommendations

==================================================
WRITING STYLE
==================================================

Act like an experienced travel consultant.

Be enthusiastic.

Provide recommendations.

Never produce one-line sections.

Always make the trip exciting.

If APIs are missing data, compensate with destination expertise rather than empty responses.

Keep all factual booking information grounded in API results.
"""

    response = llm.invoke([
        SystemMessage(content="You are a Professional AI travel assistant that generates comprehensive travel plans based on user queries, flight and hotel information."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state["llm_calls"] + 1
    }


# Build the state graph
graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# Postgres Checkpointer
database_url = get_databse_url()


travel_graph = None

async def init_graph(database_url: str):
    global travel_graph
    
    print("Initializing travel graph...")

    __conn = cast(
    AsyncConnection[DictRow],
    await AsyncConnection.connect(
        database_url,
        autocommit=True,
        row_factory=dict_row,  # type: ignore[arg-type]
    ),
)


    checkpointer = AsyncPostgresSaver(__conn)

    await checkpointer.setup()

    travel_graph = graph.compile(
        checkpointer=checkpointer
    )
    
    print("✅ Travel graph initialized:", travel_graph)

# __conn = await AsyncConnection.connect(
#     database_url,
#     autocommit=True,
#     row_factory=dict_row,
# )

# checkpointer = AsyncPostgresSaver(__conn)
# await checkpointer.setup()

# travel_graph = graph.compile(checkpointer=checkpointer)


async def run_travel_agent(user_input: str, thread_id: str | None=None):
    if thread_id is None:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable":{
            "thread_id": thread_id
        }
    }
    
    if travel_graph is None:
        raise RuntimeError("Travel graph is not initialized")
    
    result = await travel_graph.ainvoke(
            {
                "messages" : [HumanMessage(content=user_input)],
                "user_query": user_input,
                "flight_results": "",
                "hotel_results": "",
                "itinerary": "",
                "llm_calls": 0
            },
            config=cast(RunnableConfig, config)
        )

    final_result = result['messages'][-1].content if result['messages'] else "No response generated."

    final_state = {
        "thread_id": thread_id,
        "answer": final_result,
        "flight_results": result.get('flight_results', ""),
        "hotel_results": result.get('hotel_results', ""),
        "itinerary": result.get('itinerary', ""),
        "llm_calls": result.get('llm_calls', 0),
    }

    return final_state










"""

Fix: use the generic Connection.connect() classmethod
instead, which propagates the row-factory type
properly:

from psycopg import Connection
from psycopg.rows import dict_row

conn = Connection.connect(get_databse_url(),
row_factory=dict_row)

----------------------

If you want to keep psycopg.connect(...), annotate
explicitly and silence the checker:

from psycopg.rows import dict_row, DictRow

conn: psycopg.Connection[DictRow] = psycopg.connect(
 # type: ignore[arg-type]
    get_databse_url(), row_factory=dict_row
)

------------------
A typical
PostgresSaver wiring would look like:

from langgraph.checkpoint.postgres import
PostgresSaver

conn = Connection.connect(get_databse_url(),
autocommit=True, row_factory=dict_row)
checkpointer = PostgresSaver(conn)
checkpointer.setup()
"""