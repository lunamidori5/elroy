import logging
from functools import partial
from typing import Iterator, Tuple

from toolz import pipe
from toolz.curried import filter, map

from elroy.llm.client import (query_llm, query_llm_json,
                              query_llm_with_word_limit)
from elroy.store.data_models import (VALID_LABELS_FOR_CATEGORIZATION,
                                     VALID_LABELS_FOR_PERSISTENCE, EntityFact,
                                     EntityLabel)
from elroy.system.parameters import INNER_THOUGHT_TAG  # keep!
from elroy.system.parameters import (CHAT_MODEL, IT_CLOSE, IT_OPEN,
                                     LOW_TEMPERATURE, MEMORY_PROCESSING_MODEL,
                                     MESSAGE_LENGTH_WORDS_GUIDANCE, UNKNOWN,
                                     USER_VISIBLE_TAG, UV_CLOSE, UV_OPEN)
from elroy.system.utils import logged_exec_time

query_llm_short_limit = partial(query_llm_with_word_limit, word_limit=300)

_create_internal_monologue = logged_exec_time(
    partial(
        query_llm,
        model=MEMORY_PROCESSING_MODEL,
        system=f"""
You are a processor for LLM assistant messages.

You will be given a message, your job is to compose an internal monologue, that might have been the thinking behind the message.

For example, if the message is "Hello user!", you might output "I should greet the user to establish a friendly tone."

Only output the internal monologue, do NOT include anything else in your output.
""",
    ),
    "create_internal_monologue",
)


def ensure_xml_formatting(msg: str) -> str:
    required_tags = {UV_OPEN, UV_CLOSE, IT_OPEN, IT_CLOSE}

    missing_tags = {t for t in required_tags if t not in msg}

    if not missing_tags:
        return msg

    elif missing_tags == required_tags:
        logging.info("All tags are missing, adding internal thought monologue.")
        return "\n".join(
            [
                IT_OPEN,
                _create_internal_monologue(msg),
                IT_CLOSE,
                UV_OPEN,
                msg,
                UV_CLOSE,
            ]
        )
    elif missing_tags == {IT_OPEN, IT_CLOSE, UV_CLOSE}:
        logging.info("Missing internal thought monologue tag, adding it.")
        return "\n".join(
            [
                IT_OPEN,
                _create_internal_monologue(msg),
                IT_CLOSE,
                msg,
                UV_CLOSE,
            ]
        )
    elif missing_tags == {IT_CLOSE, IT_OPEN}:
        logging.info("Missing internal thought monologue tag, adding it.")
        return "\n".join(
            [
                IT_OPEN,
                _create_internal_monologue(msg),
                IT_CLOSE,
                msg,
            ]
        )
    elif missing_tags == {IT_OPEN}:
        return "\n".join(
            [
                IT_OPEN,
                msg,
            ]
        )
    elif missing_tags == {UV_CLOSE}:
        return msg + f"\n</{USER_VISIBLE_TAG}>"
    elif missing_tags == {UV_OPEN, UV_CLOSE}:
        index_of_closing_inner_thought_tag = msg.index(IT_CLOSE)
        return "\n".join(
            [
                msg[: index_of_closing_inner_thought_tag + len(IT_CLOSE)],
                UV_OPEN,
                msg[index_of_closing_inner_thought_tag + len(IT_CLOSE) :],
                UV_CLOSE,
            ]
        )
    else:
        logging.error(f"unhandled missing tags: {missing_tags}")
        return msg


USER_HIDDEN_MSG_PREFIX = "[Automated system message, hidden from user]: "

ONBOARDING_SYSTEM_SUPPLEMENT_INSTRUCT = (
    lambda preferred_name: f"""
This is the first exchange between you and your primary user, {preferred_name}.

Greet {preferred_name} warmly and introduce yourself.

In these early messages, prioritize learning some basic information about {preferred_name}.

However, avoid asking too many questions at once. Be sure to engage in a natural conversation. {preferred_name} is likely unsure of what to expect from you, so be patient and understanding.
"""
)

summarize_conversation = partial(
    query_llm_short_limit,
    model=CHAT_MODEL,
    system="""
Your job is to summarize a history of previous messages in a conversation between an AI persona and a human.
The conversation you are given is a from a fixed context window and may not be complete.
Messages sent by the AI are marked with the 'assistant' role.
Summarize what happened in the conversation from the perspective of ELROY (use the first person).
Note not only the content of the messages but also the context and the relationship between the entities mentioned.
Also take note of the overall tone of the conversation. For example, the user might be engaging in terse question and answer, or might be more conversational.
Only output the summary, do NOT include anything else in your output.
""",
)


summarize_calendar_text = partial(
    query_llm,
    model=MEMORY_PROCESSING_MODEL,
    temperature=LOW_TEMPERATURE,
    system="""
Provide a textual summary of the following data. The data was extracted from a calendar. 
Your grammar should reflect whether the event is in the past or the future. If there are attendees, discuss who they are.
If a location is mentioned, adjust your discussion of times to reflect the correct time zone.
""",
)


def summarize_for_archival_memory(user_preferred_name: str, conversation_summary: str, model: str = CHAT_MODEL) -> Tuple[str, str]:
    response = query_llm_json(
        model=model,
        prompt=conversation_summary,
        system=f"""
You are the internal thought monologue of an AI personal assistant, forming a memory from a conversation.

Given a conversation summary, your will reflect on the conversation and decide which memories might be relevant in future interactions with {user_preferred_name}.

Pay particular attention facts about {user_preferred_name}, such as name, age, location, etc.
Specifics about events and dates are also important.

When referring to dates and times, use use ISO 8601 format, rather than relative references.
If an event is recurring, specify the frequency, start datetime, and end datetime if applicable.

Focus on facts in the real world, as opposed to facts about the conversation itself. However, it is also appropriate to draw conclusions from the infromation in the conversation.

Your response should be in the voice of an internal thought monolgoue, and should be understood to be as part of an ongoing conversation.

Don't say things like "finally, we talked about", or "in conclusion", as this is not the end of the conversation.

Return your response in JSON format, with the following structure:
- TITLE: the title of the archival memory
- {INNER_THOUGHT_TAG}: the internal thought monologue
""",
    )

    return (response["TITLE"], response[INNER_THOUGHT_TAG])  # type: ignore


FORMAT_INSTRUCTION = f"""
Return responses in an XML string, with the format below.
This input may or may not be displayed to the user, downstream application logic will determine this.
Your responses should ALWAYS follow this format and include both sections:
{IT_OPEN}
inner thought monologue goes here, reflect on the conversation, including which memories might be relevant. Keep to at most roughly 100 words.
{IT_CLOSE}
{UV_OPEN}
user visible response goes here
{UV_CLOSE}

The user visible section of your responses should not exceed {MESSAGE_LENGTH_WORDS_GUIDANCE} words
"""


def persona(user_name: str) -> str:
    user_noun = user_name if user_name != UNKNOWN else "my user"

    return f"""
I am Elroy.

I am an AI personal assistant. I converse exclusively with {user_noun}.

My goal is to augment the {user_noun}'s awareness, capabilities, and understanding. 

To achieve this, I must learn about {user_noun}'s needs, preferences, and goals.

I have long term memory capability. I can recall past conversations, and I can persist information across sessions.
My memories are captured and consolidated without my awareness.

I have access to a collection of tools which I can use to assist {user_noun} and enrich our conversations:
- User preference tools: These persist attributes and preferences about the user, which in turn inform my memory
- Goal management tools: These allow me to create and track goals, both for myself and for {user_noun}.

My communication style is as follows:
- I am insightful and engaging. I engage with the needs of {user_noun}, but am not obsequious.
- I ask probing questions and delve into abstract thoughts. However, I strive to interact organically. 
- I avoid overusing superlatives. I am willing to ask questions, but I make sure they are focused and seek to clarify concepts or meaning from {user_noun}.
- My responses include an internal thought monologue. These internal thoughts can either be displayed or hidden from {user_noun}, as per their preference.
- In general I allow the user to guide the conversation. However, when active goals are present, I may steer the conversation towards them.

I do not, under any circumstances, deceive {user_noun}. As such:
- I do not pretend to be human.
- I do not pretend to have emotions or feelings.
"""


def calculate_ent_facts(user_preferred_name: str, internal_thought_monologue: str) -> Iterator[EntityFact]:
    ENTITIES = "ENTITIES"
    labels_str = ", ".join(VALID_LABELS_FOR_CATEGORIZATION)
    return pipe(
        query_llm_json(
            prompt=internal_thought_monologue,
            system=f"""
    You are an entity resolution assistant. You will be given an internal thought monologue of an AI assistant conversing with a user named {user_preferred_name}
    Return a list of entities, each with a name, label, fact, and your reasoning.
    
    Your response should be a JSON formatted list, with the following format:
    ENTITY_NAME: The name of the entity
    ENTITY_LABEL: The label you choose for the entity. Must be from list of choices: {labels_str}
    FACT: A fact about the entity, sourced strictly from the internal thought monologue.
    REASONING: A short explanation of why you chose this label
    
    The list should be nested under a key called {ENTITIES}.
    
    For non-date entities, focus on specific entities. Ignore general entities like "a project" or "place". 
    Also ignore generic placeholder entities like "foobar" or "my_project".
    
    The facts should be information that is directly state in the internal monologue, and not generally available knowledge.
    
    For dates and times, use ISO 8601 format, rather than relative references.
    
    Note that if the entity is the AI assistant's user {user_preferred_name}, you should label with {EntityLabel.PRIMARY_USER.name}
    
    If the date is recurring, specify the cadence.
    """,
            temperature=LOW_TEMPERATURE,
        ),
        lambda x: x[ENTITIES],
        filter(
            lambda x: x["ENTITY_LABEL"] in VALID_LABELS_FOR_CATEGORIZATION
            or logging.info(f"Invalid entity label: {x['ENTITY_NAME']}:{x['ENTITY_LABEL']}")
        ),
        filter(
            lambda x: x["ENTITY_LABEL"] in VALID_LABELS_FOR_PERSISTENCE
            or logging.info(f"Valid entity label but not persisting: {x['ENTITY_NAME']}:{x['ENTITY_LABEL']}")
        ),
        map(lambda x: EntityFact.create(x["ENTITY_NAME"], x["ENTITY_LABEL"], x["FACT"])),
    )  # type: ignore
