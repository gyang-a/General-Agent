from __future__ import annotations

from app.repositories.base import AppRepository
from app.repositories.mongo_repository import MongoRepository


def get_repository() -> AppRepository:
    return MongoRepository()

