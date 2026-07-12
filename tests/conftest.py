import sqlite3

import pytest

from predictions_log import init_db


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()
