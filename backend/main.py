import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="校园失物招领")
DB = Path(__file__).with_name("lost_found.db")
INDEX = Path(__file__).resolve().parent.parent / "index.html"


class PostIn(BaseModel):
    type: Literal["寻物", "招领"]
    title: str = Field(min_length=1, max_length=50)
    place: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)


class ApplicationIn(BaseModel):
    proof: str = Field(min_length=1, max_length=300)


# 首次运行时自动建表
connection = sqlite3.connect(DB)
connection.executescript("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    place TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    proof TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);
""")
connection.close()


def get_db():
    db = sqlite3.connect(DB, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        db.close()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(INDEX)


@app.get("/api/posts")
def list_posts(
    keyword: str = "",
    type: str = "全部",
    db: sqlite3.Connection = Depends(get_db),
):
    if type not in ("全部", "寻物", "招领"):
        raise HTTPException(status_code=422, detail="类型不正确")

    word = f"%{keyword}%"
    rows = db.execute(
        """SELECT * FROM posts
           WHERE (? = '全部' OR type = ?)
             AND (title LIKE ? OR place LIKE ?)
           ORDER BY id DESC""",
        (type, type, word, word),
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/posts", status_code=201)
def create_post(
    post: PostIn,
    db: sqlite3.Connection = Depends(get_db),
):
    cursor = db.execute(
        """INSERT INTO posts (type, title, place, description)
           VALUES (?, ?, ?, ?)""",
        (post.type, post.title, post.place, post.description),
    )
    db.commit()
    return {"id": cursor.lastrowid, **post.model_dump()}


@app.post("/api/posts/{post_id}/applications", status_code=201)
def create_application(
    post_id: int,
    application: ApplicationIn,
    db: sqlite3.Connection = Depends(get_db),
):
    post = db.execute(
        "SELECT id FROM posts WHERE id = ?", (post_id,)
    ).fetchone()
    if post is None:
        raise HTTPException(status_code=404, detail="信息不存在")

    cursor = db.execute(
        "INSERT INTO applications (post_id, proof) VALUES (?, ?)",
        (post_id, application.proof),
    )
    db.commit()
    return {"id": cursor.lastrowid, "message": "申请已提交"}