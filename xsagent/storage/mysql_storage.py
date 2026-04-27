"""
MySQL 存储适配器 — 将小说项目持久化到 MySQL 数据库
支持多用户、多项目、按表查询
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import pymysql
    from pymysql.cursors import DictCursor
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from xsagent.core.models import NovelProject, Chapter, Character, Foreshadowing, StyleReference
from .json_storage import JSONStorage


class MySQLStorage(JSONStorage):
    """
    MySQL 存储引擎
    继承 JSONStorage 的导出功能，替换核心的 save/load 为数据库操作
    """

    def __init__(self, config: Dict[str, Any]):
        if not HAS_PYMYSQL:
            raise ImportError("请安装 pymysql: pip install pymysql")

        self.db_config = {
            "host": config.get("host", "localhost"),
            "port": config.get("port", 3306),
            "user": config.get("user", "root"),
            "password": config.get("password", ""),
            "database": config.get("database", "xsagent"),
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
        }
        self._ensure_tables()
        # JSONStorage 的 base_dir 用于导出缓存
        super().__init__(base_dir=config.get("export_dir", "projects"))

    def _get_conn(self):
        return pymysql.connect(**self.db_config)

    def _ensure_tables(self):
        """自动创建所需数据表"""
        sql = """
        CREATE TABLE IF NOT EXISTS novels (
            id VARCHAR(16) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            author VARCHAR(100) DEFAULT '',
            description TEXT,
            world_json LONGTEXT,
            outline_json LONGTEXT,
            style_json LONGTEXT,
            skill_bindings_json TEXT,
            foreshadowings_json LONGTEXT,
            style_refs_json LONGTEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            version VARCHAR(20) DEFAULT '1.0.0'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS chapters (
            id VARCHAR(16) PRIMARY KEY,
            novel_id VARCHAR(16) NOT NULL,
            title VARCHAR(255) DEFAULT '',
            sequence_number INT DEFAULT 0,
            outline_summary TEXT,
            content LONGTEXT,
            status VARCHAR(20) DEFAULT 'planned',
            characters_present_json TEXT,
            locations_json TEXT,
            word_count INT DEFAULT 0,
            foreshadowing_seeded_json TEXT,
            foreshadowing_resolved_json TEXT,
            generation_history_json LONGTEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            notes TEXT,
            INDEX idx_novel_seq (novel_id, sequence_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS characters (
            id VARCHAR(16) PRIMARY KEY,
            novel_id VARCHAR(16) NOT NULL,
            name VARCHAR(100) DEFAULT '',
            role VARCHAR(20) DEFAULT 'supporting',
            data_json LONGTEXT,
            INDEX idx_novel (novel_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS foreshadowings (
            id VARCHAR(16) PRIMARY KEY,
            novel_id VARCHAR(16) NOT NULL,
            name VARCHAR(255) DEFAULT '',
            description TEXT,
            status VARCHAR(20) DEFAULT 'planned',
            importance VARCHAR(20) DEFAULT 'medium',
            seed_chapter_id VARCHAR(16) DEFAULT NULL,
            resolve_chapter_id VARCHAR(16) DEFAULT NULL,
            data_json LONGTEXT,
            INDEX idx_novel (novel_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

        CREATE TABLE IF NOT EXISTS style_refs (
            id VARCHAR(16) PRIMARY KEY,
            novel_id VARCHAR(16) NOT NULL,
            name VARCHAR(255) DEFAULT '',
            reference_author VARCHAR(100) DEFAULT '',
            is_active BOOLEAN DEFAULT TRUE,
            data_json LONGTEXT,
            INDEX idx_novel (novel_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()

    def save(self, project: NovelProject, pretty: bool = True) -> str:
        """保存项目到 MySQL"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # novels 主表
                cur.execute(
                    """
                    INSERT INTO novels (id, title, author, description, world_json, outline_json,
                        style_json, skill_bindings_json, foreshadowings_json, style_refs_json, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title=VALUES(title), author=VALUES(author), description=VALUES(description),
                        world_json=VALUES(world_json), outline_json=VALUES(outline_json),
                        style_json=VALUES(style_json), skill_bindings_json=VALUES(skill_bindings_json),
                        foreshadowings_json=VALUES(foreshadowings_json), style_refs_json=VALUES(style_refs_json),
                        version=VALUES(version)
                    """,
                    (
                        project.id, project.title, project.author, project.description,
                        json.dumps(project.world.to_dict() if project.world else None, ensure_ascii=False),
                        json.dumps(project.outline.to_dict() if project.outline else None, ensure_ascii=False),
                        json.dumps(project.style.to_dict(), ensure_ascii=False),
                        json.dumps(project.skill_bindings, ensure_ascii=False),
                        json.dumps({k: v.to_dict() for k, v in project.foreshadowings.items()}, ensure_ascii=False),
                        json.dumps({k: v.to_dict() for k, v in project.style_references.items()}, ensure_ascii=False),
                        project.version,
                    )
                )

                # chapters 表 — 先删除再插入（简单同步策略）
                cur.execute("DELETE FROM chapters WHERE novel_id = %s", (project.id,))
                for ch in project.chapters.values():
                    cur.execute(
                        """
                        INSERT INTO chapters (id, novel_id, title, sequence_number, outline_summary,
                            content, status, characters_present_json, locations_json, word_count,
                            foreshadowing_seeded_json, foreshadowing_resolved_json,
                            generation_history_json, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            ch.id, project.id, ch.title, ch.sequence_number, ch.outline_summary,
                            ch.content, ch.status.value,
                            json.dumps(ch.characters_present, ensure_ascii=False),
                            json.dumps(ch.locations, ensure_ascii=False),
                            ch.word_count,
                            json.dumps(ch.foreshadowing_seeded, ensure_ascii=False),
                            json.dumps(ch.foreshadowing_resolved, ensure_ascii=False),
                            json.dumps(ch.generation_history, ensure_ascii=False),
                            ch.notes,
                        )
                    )

                # characters 表
                cur.execute("DELETE FROM characters WHERE novel_id = %s", (project.id,))
                for char in project.characters.values():
                    cur.execute(
                        "INSERT INTO characters (id, novel_id, name, role, data_json) VALUES (%s, %s, %s, %s, %s)",
                        (char.id, project.id, char.name, char.role.value, json.dumps(char.to_dict(), ensure_ascii=False))
                    )

                # foreshadowings 表
                cur.execute("DELETE FROM foreshadowings WHERE novel_id = %s", (project.id,))
                for fs in project.foreshadowings.values():
                    cur.execute(
                        """
                        INSERT INTO foreshadowings (id, novel_id, name, description, status, importance,
                            seed_chapter_id, resolve_chapter_id, data_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (fs.id, project.id, fs.name, fs.description, fs.status.value, fs.importance,
                         fs.seed_chapter_id, fs.resolve_chapter_id, json.dumps(fs.to_dict(), ensure_ascii=False))
                    )

                # style_refs 表
                cur.execute("DELETE FROM style_refs WHERE novel_id = %s", (project.id,))
                for ref in project.style_references.values():
                    cur.execute(
                        "INSERT INTO style_refs (id, novel_id, name, reference_author, is_active, data_json) VALUES (%s, %s, %s, %s, %s, %s)",
                        (ref.id, project.id, ref.name, ref.reference_author, ref.is_active, json.dumps(ref.to_dict(), ensure_ascii=False))
                    )

            conn.commit()
        finally:
            conn.close()

        # 同时保存一份 JSON 导出（便于备份和迁移）
        json_path = super().save(project, pretty=pretty)
        return json_path

    def load(self, project_id: str) -> Optional[NovelProject]:
        """从 MySQL 加载项目"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM novels WHERE id = %s", (project_id,))
                row = cur.fetchone()
                if not row:
                    return None

                # 组装 NovelProject
                data = {
                    "id": row["id"],
                    "title": row["title"],
                    "author": row["author"],
                    "description": row["description"],
                    "world": json.loads(row["world_json"]) if row["world_json"] else None,
                    "outline": json.loads(row["outline_json"]) if row["outline_json"] else None,
                    "style": json.loads(row["style_json"]) if row["style_json"] else {},
                    "skill_bindings": json.loads(row["skill_bindings_json"]) if row["skill_bindings_json"] else {},
                    "foreshadowings": json.loads(row["foreshadowings_json"]) if row["foreshadowings_json"] else {},
                    "style_references": json.loads(row["style_refs_json"]) if row["style_refs_json"] else {},
                    "version": row["version"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else "",
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else "",
                }

                # 加载 chapters
                cur.execute("SELECT * FROM chapters WHERE novel_id = %s ORDER BY sequence_number", (project_id,))
                chapters_data = {}
                for ch_row in cur.fetchall():
                    ch_data = {
                        "id": ch_row["id"],
                        "title": ch_row["title"],
                        "sequence_number": ch_row["sequence_number"],
                        "outline_summary": ch_row["outline_summary"],
                        "content": ch_row["content"],
                        "status": ch_row["status"],
                        "characters_present": json.loads(ch_row["characters_present_json"]) if ch_row["characters_present_json"] else [],
                        "locations": json.loads(ch_row["locations_json"]) if ch_row["locations_json"] else [],
                        "word_count": ch_row["word_count"],
                        "foreshadowing_seeded": json.loads(ch_row["foreshadowing_seeded_json"]) if ch_row["foreshadowing_seeded_json"] else [],
                        "foreshadowing_resolved": json.loads(ch_row["foreshadowing_resolved_json"]) if ch_row["foreshadowing_resolved_json"] else [],
                        "generation_history": json.loads(ch_row["generation_history_json"]) if ch_row["generation_history_json"] else [],
                        "notes": ch_row["notes"],
                    }
                    chapters_data[ch_row["id"]] = ch_data
                data["chapters"] = chapters_data

                # 加载 characters
                cur.execute("SELECT data_json FROM characters WHERE novel_id = %s", (project_id,))
                characters_data = {}
                for char_row in cur.fetchall():
                    char_data = json.loads(char_row["data_json"])
                    characters_data[char_data["id"]] = char_data
                data["characters"] = characters_data

                return NovelProject.from_dict(data)
        finally:
            conn.close()

    def delete(self, project_id: str) -> bool:
        """删除项目（级联删除）"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                for table in ["chapters", "characters", "foreshadowings", "style_refs", "novels"]:
                    cur.execute(f"DELETE FROM {table} WHERE novel_id = %s OR id = %s", (project_id, project_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def list_projects(self) -> list:
        """列出所有项目ID"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM novels ORDER BY updated_at DESC")
                return [r["id"] for r in cur.fetchall()]
        finally:
            conn.close()
