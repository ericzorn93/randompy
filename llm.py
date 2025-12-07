from os import getenv

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.prompts.chat import SystemMessagePromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel
from pydantic.config import ConfigDict

load_dotenv()


class NflResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    team_name: str = Field(
        ...,
        description="The name of the NFL team that WON the Super Bowl in the specified year.",
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


llm = ChatOpenAI(
    api_key=getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-oss-20b:free",
    default_headers={
        "HTTP-Referer": getenv("YOUR_SITE_URL") or "",
        "X-Title": getenv("YOUR_SITE_NAME") or "",
    },
)
nfl_llm = llm.with_structured_output(NflResponse)


math_agent = create_agent(
    model=llm,
    tools=[multiply_numbers],
    system_prompt=SystemMessagePromptTemplate.from_template(
        "You are a helpful math assistant. You can perform only math equation solution when asked."
        "You must use the multiply_numberstool perform any math calculations where there are multiplication."
    ).format(),
    response_format=ProviderStrategy(MathResponse),
)


class LLMResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    nfl_response: NflResponse = Field(
        ..., description="The response from the NFL search via the LLM."
    )
    math_response: MathResponse = Field(
        ..., description="The response from the Math agent via the LLM."
    )


async def make_llm_calls() -> None:
    """
    Make calls to LLMs for NFL and Math responses.

    Returns:
        LLMResponse: Combined responses from NFL and Math LLMs.
    """

    question1 = "What NFL team won the Super Bowl in the year Justin Beiber was born? Make sure to include the winning team name and the year in your response."
    nfl_response = nfl_llm.invoke(question1)

    num_a = 2
    num_b = 5
    question2 = f"What is {num_a} multiplied by {num_b}?"
    math_response = math_agent.invoke({"messages": [HumanMessage(content=question2)]})
    structured_math_response: MathResponse = math_response["structured_response"]

    return LLMResponse(
        nfl_response=nfl_response,
        math_response=structured_math_response,
    )
