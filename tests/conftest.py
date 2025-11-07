from __future__ import annotations

from typing import Iterator

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import *  # noqa: F401,F403


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
