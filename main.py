import http
import logging
import uuid
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Response
from httpx import AsyncClient, HTTPStatusError
from pydantic import BaseModel, Field, computed_field
from pydantic.alias_generators import to_camel
from pydantic.config import ConfigDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("todoApiLogger")

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


@app.get(
    "/todos",
    response_model=List[TodoItemWithArtifact],
    tags=["Todos"],
    description="Fetch a list of todo items with computed artifact IDs.",
)
async def get_todos(res: Response) -> List[TodoItemWithArtifact]:
    async with AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/todos")
        response.raise_for_status()
        logger.info("Todos status:", extra={"status_code": response.status_code})

        cf_ray = response.headers.get("cf-ray", "unknown")
        res.headers["cf-ray"] = cf_ray

        data: List[Dict[str, Any]] = response.json()
        todos: List[TodoItemWithArtifact] = [
            TodoItemWithArtifact.model_validate(item) for item in data
        ]

        return todos


@app.get(
    "/todos/{todo_id}",
    response_model=TodoItemWithArtifact,
    tags=["Todos"],
    description="Find a specific todo id",
)
async def get_todos(todo_id: int, res: Response) -> TodoItemWithArtifact:
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
