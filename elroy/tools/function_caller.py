import inspect
import logging
from dataclasses import dataclass
from types import FunctionType, ModuleType
from typing import Dict, List, Optional, Type, Union, get_args, get_origin

from docstring_parser import parse
from sqlmodel import Session
from toolz import concat, concatv, merge, pipe
from toolz.curried import filter, map, remove

from elroy.ui.loading_message import cli_loading

PY_TO_JSON_TYPE = {
    int: "integer",
    str: "string",
    bool: "boolean",
    float: "number",
    Optional[str]: "string",
}


def get_json_type(py_type: Type) -> str:
    """
    Returns a string representing the JSON type, and bool indicating if it is required.
    """
    if py_type in PY_TO_JSON_TYPE:
        return PY_TO_JSON_TYPE[py_type]
    if get_origin(py_type) is Union:
        args = get_args(py_type)
        if type(None) in args:  # This is an Optional type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return PY_TO_JSON_TYPE[non_none_args[0]]
    raise ValueError(f"Unsupported type: {py_type}")


def get_modules():

    return []


@dataclass
class FunctionCall:
    id: str
    function_name: str
    user_id: int
    arguments: Dict


ERROR_PREFIX = "**Tool call resulted in error: **"


@cli_loading("Executing function call")
def exec_function_call(session: Session, user_id: int, function_call: FunctionCall) -> str:
    try:
        function_to_call = get_functions()[function_call.function_name]

        return pipe(
            {"user_id": user_id} if "user_id" in function_to_call.__code__.co_varnames else {},
            lambda d: merge(d, {"session": session}) if "session" in function_to_call.__code__.co_varnames else d,
            lambda d: merge(function_call.arguments, d),
            lambda args: function_to_call.__call__(**args),
            lambda result: str(result) if result is not None else "Success",
            str,
        )  # type: ignore

    except Exception as e:
        logging.error("Function call resulted in error: %s", e)
        return f"{ERROR_PREFIX}{e}"


def get_module_functions(module: ModuleType) -> List[FunctionType]:
    return pipe(
        dir(module),
        map(lambda name: getattr(module, name)),
        filter(lambda _: inspect.isfunction(_) and _.__module__ == module.__name__),
        list,
    )  # type: ignore


def get_function_schema(function: FunctionType) -> Dict:
    @dataclass
    class Parameter:
        name: str
        type: Type
        docstring: Optional[str]
        optional: bool

    def validate_parameter(parameter: Parameter) -> Parameter:
        if not parameter.optional:
            assert (
                parameter.type != inspect.Parameter.empty
            ), f"Required parameter {parameter.name} for function {function.__name__} has no type annotation"
        assert parameter.name in docstring_dict, f"Parameter {parameter.name} for function {function.__name__} has no docstring"
        if parameter.type != inspect.Parameter.empty:
            assert (
                get_json_type(parameter.type) is not None
            ), f"Parameter {parameter.name} for function {function.__name__} has no corresponding JSON schema type"

        return parameter

    assert function.__doc__ is not None, f"Function {function.__name__} has no docstring"
    docstring_dict = {p.arg_name: p.description for p in parse(function.__doc__).params}

    signature = inspect.signature(function)

    return pipe(
        signature.parameters.items(),
        list,
        remove(lambda _: _[0] == "user_id"),
        remove(lambda _: _[0] == "session"),
        map(
            lambda _: Parameter(
                name=_[0],
                type=_[1].annotation,
                docstring=docstring_dict.get(_[0]),
                optional=_[1].default != inspect.Parameter.empty or get_origin(_[1].annotation) is Union,
            )
        ),
        map(validate_parameter),
        map(
            lambda _: [
                _.name,
                {"type": get_json_type(_.type) if _.type != inspect.Parameter.empty else "string", "description": _.docstring},
            ]
        ),
        dict,
        lambda properties: {
            "name": function.__name__,
            "parameters": {"type": "object", "properties": properties},
            "required": [
                name
                for name, param in signature.parameters.items()
                if param.default == inspect.Parameter.empty
                and get_origin(param.annotation) is not Union
                and name not in ["user_id", "session"]
            ],
        },
    )  # type: ignore


def get_function_schemas():
    return pipe(
        get_functions().values(),
        map(get_function_schema),
        map(lambda _: {"type": "function", "function": _}),
        list,
    )  # type: ignore


def get_functions() -> Dict[str, FunctionType]:
    from elroy.store.goals import (create_goal, get_active_goals_summary,
                                   mark_goal_completed, update_goal_status)
    from elroy.tools.functions.user_preferences import (
        get_display_internal_monologue, get_user_preferred_name,
        get_user_time_zone, set_display_internal_monologue,
        set_user_preferred_name, set_user_time_zone)
    from elroy.tools.system_commands import (print_system_instruction,
                                             refresh_system_instructions)

    return pipe(
        get_modules(),
        map(get_module_functions),
        concat,
        list,
        lambda _: concatv(
            _,
            [
                # system commands
                refresh_system_instructions,
                print_system_instruction,
                # goal operations
                get_active_goals_summary,
                update_goal_status,
                create_goal,
                mark_goal_completed,
                # user preferences
                get_user_preferred_name,
                set_user_preferred_name,
                get_user_time_zone,
                set_user_time_zone,
                get_display_internal_monologue,
                set_display_internal_monologue,
            ],
        ),
        map(lambda _: [_.__name__, _]),
        dict,
    )


def validate_openai_tool_schema():
    """
    Validates the schema for OpenAI function tools' parameters.

    :param function_schemas: List of function schema dictionaries.
    :returns: Tuple (is_valid, errors). is_valid is a boolean indicating if all schemas are valid.
                Errors is a list of error messages if any issues are detected.
    """
    errors = []

    function_schemas = get_function_schemas()

    if not isinstance(function_schemas, list):
        errors.append("Function schemas should be a list.")
        return False, errors

    for idx, func_schema in enumerate(function_schemas):
        if not isinstance(func_schema, dict):
            errors.append(f"Schema at index {idx} is not a dictionary.")
            continue

        if "type" not in func_schema or func_schema["type"] != "function":
            errors.append(f"Schema at index {idx} is missing 'type' or 'type' is not 'function'.")
        if "function" not in func_schema:
            errors.append(f"Schema at index {idx} is missing 'function' key.")
            continue

        function = func_schema["function"]
        if not isinstance(function, dict):
            errors.append(f"Function schema at index {idx} is not a dictionary.")
            continue

        if "name" not in function:
            errors.append(f"Function schema at index {idx} is missing 'name' key.")

        if "parameters" not in function:
            errors.append(f"Function schema at index {idx} is missing 'parameters' key.")
            continue

        parameters = function["parameters"]
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            errors.append(f"Parameters for function '{function.get('name')}' must be an object.")

        if "properties" not in parameters or not isinstance(parameters["properties"], dict):
            errors.append(f"'properties' for function '{function.get('name')}' must be a valid dictionary.")

        required_fields = parameters.get("required")
        if required_fields is not None and not isinstance(required_fields, list):
            errors.append(f"'required' for function '{function.get('name')}' must be a list if present.")

    if len(errors) > 0:
        raise ValueError(errors)


validate_openai_tool_schema()
