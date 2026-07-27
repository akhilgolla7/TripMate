from pathlib import Path
import os
import traceback
import uvicorn

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend import init_graph, run_travel_agent

from contextlib import asynccontextmanager

# this allows nested event loops to run in the same thread, which is useful for running async code in FastAPI
# import nest_asyncio
# nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting TripMate initialization")

    database_url = os.environ["DATABASE_URL"]

    await init_graph(database_url)

    print("✅ TripMate initialization completed")

    yield

    print("TripMate shutting down")

app = FastAPI(title="TripMate", 
              description="Your Travel Assistant", 
              version="1.0.0",
               lifespan=lifespan)

app.mount("/static", 
          StaticFiles(directory=str(BASE_DIR / "static")), 
          name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

class TravelQuery(BaseModel):
    user_input: str
    thread_id: str | None = None

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("=== 422 validation error ===")
    print("body:", await request.body())
    print("errors:", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request,
                                      name="index.html",
                                      context={})

@app.post("/api/travel")
async def travel_planner(request: Request):
    try:
        raw = await request.body()
        print("=== /api/travel raw body ===", raw)
        print("=== /api/travel content-type ===", request.headers.get("content-type"))
        payload = await request.json()
        print("=== /api/travel parsed json ===", payload)

        user_input = (payload.get("user_input") or "").strip()
        thread_id = payload.get("thread_id")

        if not user_input:
            return JSONResponse(content={"error": "User input is required"}, status_code=400)

        response = await run_travel_agent(
            user_input=user_input,
            thread_id=thread_id
        )
        return JSONResponse(
            content={
                "success": True,
                "thread_id": response.get("thread_id"),
                "answer": response.get("answer"),
                'flight_results': response.get('flight_results', ""),
                "hotel_results": response.get('hotel_results', ""),
                "itinerary": response.get('itinerary', ""),
                "llm_calls": response.get("llm_calls", 0)
            }
        )
    
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/health")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)



if __name__ == "__main__":
    uvicorn.run(app=app,
                host="0.0.0.0", port=8000, reload=True, log_level="info")
