import asyncio
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.prompts.chat import SystemMessagePromptTemplate

# from langchain_openrouter import ChatOpenRouter
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel
from pydantic.config import ConfigDict

load_dotenv()


class NflResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    team_name: str = Field(
        ...,
        description="The name of the NFL team that WON the Super Bowl in the specified year. Example: New York Giants",
    )
    year: int = Field(..., description="The year in which the Super Bowl was won.")


class MathResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    result: float = Field(..., description="The result of the math operation.")


@tool("multiply_numbers")
def multiply_numbers(a: float, b: float) -> float:
    """
    Multiplies two numbers and returns the result.

    Args:
        a (float): The first number.
        b (float): The second number.
    Returns:
        float: The product of the two numbers.
    """
    print("Multiplying numbers via tool call...")
    return a * b


# llm = ChatOpenRouter(
#     model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
#     temperature=0.0,
# )

llm = ChatOpenAI(
    base_url="https://gateway.ai.cloudflare.com/v1/e93b61784a3f070859a6640663a3317e/challah-social/compat",
    model="workers-ai/@cf/google/gemma-4-26b-a4b-it",
    api_key=os.getenv("CLOUDFLARE_API_GATEWAY_API_KEY"),
    default_headers={"cf-aig-gateway-id": "challah-social"},
)
nfl_llm = llm.with_structured_output(NflResponse, method="json_schema", strict=True)


math_agent = create_agent(
    model=llm,
    tools=[multiply_numbers],
    # pyrefly: ignore [bad-argument-type]
    system_prompt=SystemMessagePromptTemplate.from_template(
        "You are a helpful math assistant. You can perform only math equation solution when asked."
        "You must use the multiply_numbers tool perform any math calculations where there are multiplication."
    ).format(),
    response_format=ProviderStrategy(MathResponse, strict=True),
)


class LLMResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    nfl_response: NflResponse = Field(
        ..., description="The response from the NFL search via the LLM."
    )
    math_response: MathResponse = Field(
        ..., description="The response from the Math agent via the LLM."
    )


async def make_llm_calls() -> LLMResponse:
    """
    Make calls to LLMs for NFL and Math responses.

    Returns:
        LLMResponse: Combined responses from NFL and Math LLMs.
    """

    question1 = "What NFL team won the Super Bowl in the year Justin Beiber was born? Make sure to include the winning team name and the year in your response. Always validate what you are thinking before responding."

    num_a = 2
    num_b = 5
    question2 = f"What is {num_a} multiplied by {num_b}?"

    tasks = [
        asyncio.create_task(nfl_llm.ainvoke(question1)),
        asyncio.create_task(
            math_agent.ainvoke({"messages": [HumanMessage(content=question2)]})
        ),
    ]

    nfl_response, math_response = await asyncio.gather(*tasks)
    structured_nfl_response: NflResponse = nfl_response  # type: ignore
    structured_math_response: MathResponse = math_response["structured_response"]

    return LLMResponse(
        nfl_response=structured_nfl_response,
        math_response=structured_math_response,
    )
