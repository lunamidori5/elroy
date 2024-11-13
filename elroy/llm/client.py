import json
import re
from dataclasses import asdict
from functools import partial
from typing import Any, Dict, Iterator, List, Union

from litellm import completion, embedding
from litellm.exceptions import BadRequestError
from toolz import pipe
from toolz.curried import keyfilter, map

from ..config.config import ChatModel, EmbeddingModel
from ..config.constants import MissingToolCallMessageError
from ..repository.data_models import SYSTEM, USER, ContextMessage
from ..utils.utils import logged_exec_time


@logged_exec_time
def generate_chat_completion_message(chat_model: ChatModel, context_messages: List[ContextMessage]) -> Iterator[Dict]:
    context_messages = pipe(
        context_messages,
        map(asdict),
        map(keyfilter(lambda k: k not in ("id", "created_at", "memory_metadata", "chat_model"))),
        list,
    )

    if chat_model.ensure_alternating_roles:
        USER_HIDDEN_PREFIX = "[This is a system message, representing internal thought process of the assistant]"
        for idx, message in enumerate(context_messages):
            assert isinstance(message, Dict)

            if idx == 0:
                assert message["role"] == SYSTEM, f"First message must be a system message, but found: " + message["role"]

            if idx != 0 and message["role"] == SYSTEM:
                message["role"] = USER
                message["content"] = f"{USER_HIDDEN_PREFIX} {message['content']}"

    try:
        completion_kwargs = _build_completion_kwargs(
            chat_model=chat_model, messages=context_messages, stream=True, use_tools=True  # type: ignore
        )
        return completion(**completion_kwargs)  # type: ignore
    except BadRequestError as e:
        if "An assistant message with 'tool_calls' must be followed by tool messages" in str(e):
            raise MissingToolCallMessageError
        else:
            raise e


def query_llm(model: ChatModel, prompt: str, system: str) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return _query_llm(model=model, prompt=prompt, system=system)


def query_llm_json(model: ChatModel, prompt: str, system: str) -> Union[dict, list]:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return pipe(
        _query_llm(model=model, prompt=prompt, system=system),
        partial(_parse_json, model),
    )  # type: ignore


def query_llm_with_word_limit(model: ChatModel, prompt: str, system: str, word_limit: int) -> str:
    if not prompt:
        raise ValueError("Prompt cannot be empty")
    return query_llm(
        prompt="\n".join(
            [
                prompt,
                f"Your word limit is {word_limit}. DO NOT EXCEED IT.",
            ]
        ),
        model=model,
        system=system,
    )


def get_embedding(model: EmbeddingModel, text: str) -> List[float]:
    """
    Generate an embedding for the given text using the specified model.

    Args:
        text (str): The input text to generate an embedding for.
        model (str): The name of the embedding model to use.

    Returns:
        List[float]: The generated embedding as a list of floats.
    """
    if not text:
        raise ValueError("Text cannot be empty")
    embedding_kwargs = {
        "model": model.model,
        "input": [text],
        "caching": True,
        "api_key": model.api_key,
    }

    if model.api_base:
        embedding_kwargs["api_base"] = model.api_base
    if model.organization:
        embedding_kwargs["organization"] = model.organization

    response = embedding(**embedding_kwargs)
    return response.data[0]["embedding"]


def _build_completion_kwargs(
    chat_model: ChatModel,
    messages: List[Dict[str, str]],
    stream: bool = False,
    use_tools: bool = False,
) -> Dict[str, Any]:
    """Centralized configuration for LLM requests"""
    kwargs = {
        "messages": messages,
        "model": chat_model.model,
        "api_key": chat_model.api_key,
    }

    if chat_model.api_base:
        kwargs["api_base"] = chat_model.api_base
    if chat_model.organization:
        kwargs["organization"] = chat_model.organization

    if use_tools:
        from ..tools.function_caller import get_function_schemas

        kwargs.update(
            {
                "tool_choice": "auto",
                "tools": get_function_schemas(),
            }
        )

    if stream:
        kwargs["stream"] = True

    return kwargs


def _query_llm(model: ChatModel, prompt: str, system: str) -> str:
    messages = [{"role": SYSTEM, "content": system}, {"role": USER, "content": prompt}]
    completion_kwargs = _build_completion_kwargs(chat_model=model, messages=messages, stream=False, use_tools=False)
    return completion(**completion_kwargs).choices[0].message.content  # type: ignore


def _parse_json(chat_model: ChatModel, json_str: str, attempt: int = 0) -> Union[Dict, List]:
    cleaned_str = pipe(
        json_str,
        str.strip,
        partial(re.sub, r"^```json", ""),
        str.strip,
        partial(re.sub, r"```$", ""),
        str.strip,
    )

    try:
        return json.loads(cleaned_str.strip())
    except json.JSONDecodeError as e:
        if attempt > 3:
            raise e
        else:
            return pipe(
                query_llm(
                    chat_model,
                    system=f"You will be given a text that is malformed JSON. An attempt to parse it has failed with error: {str(e)}."
                    "Repair the json and return it. Respond with nothing but the repaired JSON."
                    "If at all possible maintain the original structure of the JSON, in your repairs bias towards the smallest edit you can make to form valid JSON",
                    prompt=cleaned_str,
                ),
                lambda x: _parse_json(chat_model, x, attempt + 1),
            )  # type: ignore
