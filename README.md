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