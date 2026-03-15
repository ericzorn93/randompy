import http
import logging
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from cachetools import TTLCache
from cachetools_async import cached as async_cached
from fastapi import FastAPI, HTTPException, Response
from httpx import AsyncClient, HTTPStatusError
from pydantic import BaseModel, Field, computed_field
from pydantic.alias_generators import to_camel
from pydantic.config import ConfigDict
from pythonjsonlogger import jsonlogger

from llm import LLMResponse, make_llm_calls

# 1. Create a logger
logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)

# 2. Define the JSON format
# The fmt parameter defines which fields are included in the JSON object
formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")

# 3. Add the formatter to the handler and the handler to the logger
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

app = FastAPI(
    title="Todo API Proxy",
    version="1.0.0",
    description="An API that proxies todo items with computed artifact IDs.",
)


class TodoItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int = Field(..., description="The unique identifier for the todo item")
    user_id: int = Field(..., description="The ID of the user who owns the todo item")
    title: str = Field(..., description="The title of the todo item")
    completed: bool = Field(..., description="The completion status of the todo item")


class TodoItemWithArtifact(TodoItem):
    """A todo item model that includes a computed artifact ID."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @computed_field
    @property
    def artifact_id(self) -> str:
        """Return the artifact ID computed from the model's id and title.

        This value is not stored on the model and is only included during
        serialization (e.g., `model_dump()` or when FastAPI serializes a
        response).
        """
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.id}-{self.title}"))


class HealthcheckResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: str = Field(
        "ok",
        description="The health status of the API",
        examples=["ok", "degraded", "down"],
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="The current timestamp in UTC",
    )


class RandomResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    random_number: int = Field(..., description="A random integer between 1 and 1000")
    random_uuid: uuid.UUID = Field(..., description="A random UUID string")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="The current timestamp in UTC",
    )


@async_cached(cache=TTLCache(maxsize=10, ttl=30))
async def find_todos() -> List[TodoItemWithArtifact]:
    """
    Find all todos from the endpoint in JSON placeholder

    Returns:
        List[TodoItemWithArtifact]: Parsed list of todo items with artifact IDs
    """

    async with AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/todos")
        response.raise_for_status()
        logger.info(f"Todos status: {response.status_code}")
        data: List[Dict[str, Any]] = response.json()
        todos: List[TodoItemWithArtifact] = [
            TodoItemWithArtifact.model_validate(item) for item in data
        ]

        return todos


@app.get(
    "/healthz",
    response_model=HealthcheckResponse,
    tags=["Health"],
    description="Health check endpoint",
)
async def health_check() -> HealthcheckResponse:
    return HealthcheckResponse(status="ok")


@app.get(
    "/random",
    response_model=RandomResponse,
    tags=["Random"],
    description="Return a random number and a random UUID",
)
async def random_data() -> RandomResponse:
    """Return a random number and a random UUID.

    This endpoint generates a random integer between 1 and 100 and a random UUID,
    then returns them in a JSON response.

    Returns:
        RandomResponse: A response model containing the random number, UUID, and timestamp.
    """
    random_number = random.randint(
        1, 1000
    )  # Generate a random integer between 1 and 100
    random_uuid = uuid.uuid4()  # Generate a random UUID

    return RandomResponse(random_number=random_number, random_uuid=random_uuid)


@app.get(
    "/todos",
    response_model=List[TodoItemWithArtifact],
    tags=["Todos"],
    description="Fetch a list of todo items with computed artifact IDs.",
)
async def get_todos(res: Response) -> List[TodoItemWithArtifact]:
    todos = await find_todos()
    return todos


@app.get(
    "/todos/{todo_id}",
    response_model=TodoItemWithArtifact,
    tags=["Todos"],
    description="Find a specific todo id",
)
async def get_single_todo(todo_id: int, res: Response) -> TodoItemWithArtifact:
    async with AsyncClient() as client:
        response = await client.get(
            f"https://jsonplaceholder.typicode.com/todos/{todo_id}"
        )

        cf_ray = response.headers.get("cf-ray", "unknown")
        res.headers["cf-ray"] = cf_ray

        try:
            response.raise_for_status()
        except HTTPStatusError:
            raise HTTPException(http.HTTPStatus.NOT_FOUND, detail="Todo item not found")

        logger.info(f"Todos status: {response.status_code}")

        data: Dict[str, Any] = response.json()
        todo: TodoItemWithArtifact = TodoItemWithArtifact.model_validate(data)

        return todo


@app.get("/llm", response_model=LLMResponse, tags=["LLM"], description="Make LLM calls")
async def make_ai_call() -> LLMResponse:
    return await make_llm_calls()
