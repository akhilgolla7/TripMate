# TripMate
TripMate - multi agent travel partner

## How to run
1. Create the virtual env

    >> conda create -n travel python=3.14 -y

2. Acivate the Environment

    >> conda activate travel

3. install requirements

    >> pip install -r requirements.txt

4. >> uv pip compile pyproject.toml -o requirements.txt
   >> uv run fastapi dev main.py 
