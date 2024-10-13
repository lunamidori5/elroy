import hashlib
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, Generic, Iterable, List, Optional, Type, TypeVar

from sqlmodel import Session, select
from toolz import pipe
from toolz.curried import filter, map

from elroy.store.data_models import ArchivalMemory, EmbeddableSqlModel, Goal
from elroy.system.parameters import (L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD,
                                     L2_RANDOM_WORD_DISTANCE,
                                     RESULT_SET_LIMIT_COUNT)


def l2_percent_closer_than_random(l2_distance: float) -> float:
    """The similarity score to use with cutoffs. Measures what % closer the query is than a random sentence."""
    return round(100 * (L2_RANDOM_WORD_DISTANCE - l2_distance) / L2_RANDOM_WORD_DISTANCE, 1)


T = TypeVar("T", bound=EmbeddableSqlModel)


@dataclass
class VectorResultMatch(Generic[T]):
    result: T
    score: float
    percent_closer_than_random: float


def query_vector(
    session: Session, user_id: int, query: List[float], table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Iterable[VectorResultMatch]:
    """
    Perform a vector search on the specified table using the given query.

    Args:
        query (str): The search query.
        table (EmbeddableSqlModel): The SQLModel table to search.

    Returns:
        List[Tuple[Fact, float]]: A list of tuples containing the matching Fact and its similarity score.
    """

    return pipe(
        session.exec(
            select(table, table.embedding.l2_distance(query).label("distance"))  # type: ignore
            .where(
                table.user_id == user_id,
                filter_clause,
                table.embedding != None,
            )
            .order_by("distance")
            .limit(RESULT_SET_LIMIT_COUNT)
        ).all(),
        map(
            lambda row: VectorResultMatch(
                row[0],
                round(row[1], 2),
                l2_percent_closer_than_random(row[1]),
            )
        ),
    )


def get_vector_matches_over_threshold(
    session: Session, user_id: int, query: List[float], table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Iterable[VectorResultMatch]:
    return pipe(
        query_vector(session, user_id, query, table, filter_clause),
        filter(lambda row: row.percent_closer_than_random > L2_PERCENT_CLOSER_THAN_RANDOM_THRESHOLD),
    )


def get_closest_vector_match(
    session: Session, user_id: int, query: List[float], table: Type[EmbeddableSqlModel], filter_clause: Any = lambda: True
) -> Optional[EmbeddableSqlModel]:
    return pipe(
        get_vector_matches_over_threshold(session, user_id, query, table, filter_clause),
        lambda x: next(x, None),
        lambda x: x.result if x else None,
    )  # type: ignore


get_most_relevant_goal = partial(get_closest_vector_match, table=Goal, filter_clause=Goal.is_active == True)
get_most_relevant_archival_memory = partial(get_closest_vector_match, table=ArchivalMemory)

get_relevant_goals = partial(get_vector_matches_over_threshold, table=Goal, filter_clause=Goal.is_active == True)
get_relevant_archival_memories = partial(get_vector_matches_over_threshold, table=ArchivalMemory)


def upsert_embedding(session: Session, row: EmbeddableSqlModel) -> None:
    from elroy.llm.client import get_embedding

    source_fact = row.to_fact()
    new_text = source_fact.text
    new_md5 = hashlib.md5(new_text.encode()).hexdigest()

    if row.embedding_text_md5 == new_md5:
        logging.info("Old and new text matches md5, skipping")
        return
    else:
        embedding = get_embedding(new_text)

        row.embedding = embedding
        row.embedding_text_md5 = new_md5

        session.add(row)
        session.commit()
