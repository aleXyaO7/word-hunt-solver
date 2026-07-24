from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any

app = FastAPI()


class SolveRequest(BaseModel):
    model_config = {"extra": "allow"}


class SolveResponse(BaseModel):
    result: Any
    status: str = "ok"


@app.post("/solve", response_model=SolveResponse)
async def solve(request: SolveRequest) -> SolveResponse:
    data = request.model_dump()
    return SolveResponse(result=data, status="ok")
