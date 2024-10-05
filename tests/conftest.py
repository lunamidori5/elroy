import os
import random
import string

import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from alembic.command import upgrade
from alembic.config import Config
from elroy.config import ElroyConfig, get_config, session_manager
from elroy.store.goals import create_goal
from tests.fixtures import (BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
                            create_test_user)


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("ankane/pgvector:v0.5.1") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:6-alpine") as redis:
        yield redis


@pytest.fixture(scope="session")
def config(postgres_container, redis_container) -> ElroyConfig:
    # Get the Redis host and port
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)
    os.environ["ELROY_REDIS_URL"] = f"redis://{redis_host}:{redis_port}"

    # Get the PostgreSQL host and port
    postgres_host = postgres_container.get_container_host_ip()
    postgres_port = postgres_container.get_exposed_port(5432)
    os.environ["ELROY_DATABASE_URL"] = f"postgresql://test:test@{postgres_host}:{postgres_port}/test"
    return get_config()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(config, postgres_container):
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", config.database_url)
    postgres_container.exec(["psql", "-U", "test", "-d", "test", "-c", "CREATE EXTENSION IF NOT EXISTS vector;"])
    upgrade(alembic_cfg, "head")


from sqlmodel import delete

from elroy.store.data_models import CalendarEventDB, Goal, Signup, User
from elroy.store.message import (ContextMessage, Message, get_context_messages,
                                 replace_context_messages)
from elroy.store.store import ArchivalMemory, MemoryEntity
from elroy.store.user import UserPreference


@pytest.fixture(scope="session")
def session(postgres_container, apply_migrations, config):
    # Reset both engine and session_maker to ensure we're using the test database

    with session_manager() as session:
        # Delete all rows from the tables
        session.exec(delete(Message))  # type: ignore
        session.exec(delete(Goal))  # type: ignore
        session.exec(delete(UserPreference))  # type: ignore
        session.exec(delete(CalendarEventDB))  # type: ignore
        session.exec(delete(ArchivalMemory))  # type: ignore
        session.exec(delete(MemoryEntity))  # type: ignore
        session.exec(delete(Signup))  # type: ignore
        session.exec(delete(User))  # type: ignore
        session.commit()

        yield session


@pytest.fixture(scope="function")
def user_id(session, phone_number) -> int:
    return create_test_user(session, phone_number)


@pytest.fixture(scope="function")
def onboarded_user_id(session, phone_number) -> int:
    return create_test_user(
        session,
        phone_number,
        initial_messages=["Hello! My name is George. I work as a air traffic controller."],
    )


@pytest.fixture(scope="function")
def george_user_id(session, user_id) -> int:
    messages = [
        ContextMessage(
            role="user", content="Hello! My name is George. I'm curious about the history of Minnesota. Can you tell me about it?"
        ),
        ContextMessage(
            role="assistant",
            content="Hello George! It's nice to meet you. I'd be happy to share some information about the history of Minnesota with you. What aspect of Minnesota's history are you most interested in?",
        ),
        ContextMessage(
            role="user",
            content="I'm particularly interested in when Minnesota became a state and any significant events leading up to that.",
        ),
        ContextMessage(
            role="assistant",
            content="Certainly, George! Minnesota became the 32nd state of the United States on May 11, 1858. Here are some key events leading up to statehood:\n\n1. In 1803, the eastern part of Minnesota was acquired by the U.S. as part of the Louisiana Purchase.\n2. The western part was acquired in 1818 through a convention with Britain.\n3. In 1820, Fort Snelling was established at the confluence of the Mississippi and Minnesota rivers.\n4. The Minnesota Territory was created in 1849, which set the stage for eventual statehood.\n5. The population grew rapidly in the 1850s, leading to the push for statehood.\n\nWould you like to know more about any specific aspect of this period?",
        ),
        ContextMessage(
            role="user",
            content="That's interesting! What were some of the main industries or economic activities in Minnesota during its early statehood?",
        ),
        ContextMessage(
            role="assistant",
            content="Great question, George! In its early years of statehood, Minnesota's economy was primarily based on natural resources and agriculture. Here are some key industries:\n\n1. Lumber: The vast forests in northern Minnesota made lumber a major industry.\n2. Agriculture: Wheat farming was particularly important, with Minneapolis becoming a major flour milling center.\n3. Iron ore mining: The discovery of iron ore in the Mesabi Range in the 1860s led to significant mining operations.\n4. Fur trading: While declining by the time of statehood, it had been a crucial early industry.\n5. Transportation: The Mississippi River and later railroads were vital for moving goods and people.\n\nThese industries shaped Minnesota's early development and laid the foundation for its future growth. Is there a particular industry you'd like to know more about?",
        ),
        ContextMessage(
            role="user",
            content="The iron ore mining sounds fascinating. Can you tell me more about the Mesabi Range and its impact on Minnesota?",
        ),
        ContextMessage(
            role="assistant",
            content="Absolutely, George! The Mesabi Range and its iron ore mining had a profound impact on Minnesota. Here are some key points:\n\n1. Discovery: Iron ore was discovered in the Mesabi Range in 1866, but large-scale mining didn't begin until the 1890s.\n\n2. Location: The Mesabi Range is located in northeast Minnesota and is about 110 miles long and 1-3 miles wide.\n\n3. Economic impact: It became one of the world's largest iron ore mining districts, significantly boosting Minnesota's economy.\n\n4. Steel industry: The high-quality iron ore from the Mesabi Range was crucial for the U.S. steel industry, particularly during World Wars I and II.\n\n5. Technology: The development of open-pit mining and new transportation methods revolutionized the industry.\n\n6. Communities: Mining led to the growth of many towns in northern Minnesota, like Hibbing and Virginia.\n\n7. Environmental impact: While economically beneficial, mining also had significant environmental effects that are still being addressed today.\n\n8. Legacy: Although production has decreased since its peak, mining remains an important part of Minnesota's economy and identity.\n\nIs there a specific aspect of the Mesabi Range or iron mining you'd like to explore further?",
        ),
        ContextMessage(
            role="user", content="Thanks for all this information! It's really helped me understand Minnesota's history better."
        ),
        ContextMessage(
            role="assistant",
            content="You're welcome, George! I'm glad I could help you learn more about Minnesota's history, particularly about its statehood and the significant impact of iron ore mining in the Mesabi Range. Minnesota has a rich and diverse history that has shaped its culture and economy to this day. If you have any more questions about Minnesota or any other topic, feel free to ask. It's always a pleasure to explore history and share knowledge!",
        ),
    ]

    replace_context_messages(session, user_id, get_context_messages(session, user_id) + messages)

    create_goal(
        session,
        user_id,
        BASKETBALL_FOLLOW_THROUGH_REMINDER_NAME,
        "Remind Goerge to follow through if he mentions basketball.",
        "George is working to improve his basketball game, in particular his shooting form.",
        "George acknowledges my reminder that he needs to follow through on basketball shots.",
        "7 DAYS",
        0,
    )

    create_goal(
        session,
        user_id,
        "Pay off car loan by end of year",
        "Remind George to pay off his loan by the end of the year.",
        "George has a loan that he needs to pay off by the end of the year.",
        "George confirms that he has paid off his loan.",
        "1 YEAR",
        0,
    )

    return user_id


@pytest.fixture(scope="function")
def phone_number():
    country_code = random.randint(1, 999)
    subscriber_number = "".join(random.choices(string.digits, k=random.randint(6, 12)))
    return f"+{country_code}{subscriber_number}"


@pytest.fixture(scope="function")
def context_refresh_token_target(config):
    return config.context_refresh_token_target
