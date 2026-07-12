import sqlite3
from datetime import datetime


def get_connection(db_path: str = "predictions.db") -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            predicted_class TEXT NOT NULL,
            confidence REAL NOT NULL,
            thumbnail BLOB,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def log_prediction(conn: sqlite3.Connection, predicted_class: str, confidence: float, thumbnail: bytes) -> None:
    conn.execute(
        "INSERT INTO predictions (predicted_class, confidence, thumbnail, created_at) VALUES (?, ?, ?, ?)",
        (predicted_class, float(confidence), thumbnail, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_total_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute("SELECT COUNT(*) FROM predictions")
    return cursor.fetchone()[0]


def get_class_distribution(conn: sqlite3.Connection) -> dict:
    cursor = conn.execute("SELECT predicted_class, COUNT(*) FROM predictions GROUP BY predicted_class")
    return dict(cursor.fetchall())


def get_recent(conn: sqlite3.Connection, limit: int = 20) -> list:
    cursor = conn.execute(
        "SELECT id, predicted_class, confidence, thumbnail, created_at "
        "FROM predictions ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    columns = ["id", "predicted_class", "confidence", "thumbnail", "created_at"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_average_confidence(conn: sqlite3.Connection) -> float:
    cursor = conn.execute("SELECT AVG(confidence) FROM predictions")
    result = cursor.fetchone()[0]
    return float(result) if result is not None else 0.0


def get_confidence_series(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT created_at, confidence FROM predictions ORDER BY id ASC")
    return [{"created_at": row[0], "confidence": row[1]} for row in cursor.fetchall()]
