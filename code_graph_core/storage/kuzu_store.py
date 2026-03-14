from __future__ import annotations

import json
import shutil
from pathlib import Path

import kuzu

from code_graph_core.graph.models import GraphBundle, NodeRecord, RelationshipRecord
from code_graph_core.graph.schema import NODE_TABLE_SCHEMAS, REL_TABLE_SCHEMA


class KuzuStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database: kuzu.Database | None = None
        self.connection: kuzu.Connection | None = None
        if self.database_path.exists():
            self._connect()

    def reinitialize(self) -> None:
        if self.database_path.exists():
            if self.database_path.is_dir():
                shutil.rmtree(self.database_path)
            else:
                self.database_path.unlink()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connect()

    def bootstrap(self) -> None:
        connection = self._require_connection()
        for schema in NODE_TABLE_SCHEMAS.values():
            connection.execute(schema)
        connection.execute(REL_TABLE_SCHEMA)

    def persist(self, graph_bundle: GraphBundle) -> None:
        for node in graph_bundle.nodes:
            self._insert_node(node)
        for relationship in graph_bundle.relationships:
            self._insert_relationship(relationship)

    def table_count(self, table_name: str) -> int:
        result = self._require_connection().execute(f"MATCH (n:{table_name}) RETURN count(n) AS count;")
        return int(result.get_next()[0])

    def _insert_node(self, node: NodeRecord) -> None:
        assignments = ", ".join(
            f"{key}: {self._literal(value)}"
            for key, value in node.properties.items()
        )
        self._require_connection().execute(f"CREATE (:{node.kind} {{{assignments}}});")

    def _insert_relationship(self, relationship: RelationshipRecord) -> None:
        props = {
            "type": relationship.type,
            "confidence": relationship.confidence,
            "reason": relationship.reason,
            "step": relationship.step,
        }
        prop_literal = ", ".join(f"{key}: {self._literal(value)}" for key, value in props.items())
        query = f"""
            MATCH (a:{relationship.from_kind} {{id: {self._literal(relationship.from_id)}}}),
                  (b:{relationship.to_kind} {{id: {self._literal(relationship.to_id)}}})
            CREATE (a)-[:CodeRelation {{{prop_literal}}}]->(b);
        """
        self._require_connection().execute(query)

    def _connect(self) -> None:
        self.database = kuzu.Database(str(self.database_path))
        self.connection = kuzu.Connection(self.database)

    def _require_connection(self) -> kuzu.Connection:
        if self.connection is None:
            self._connect()
        return self.connection

    @staticmethod
    def _literal(value: object) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(value)
