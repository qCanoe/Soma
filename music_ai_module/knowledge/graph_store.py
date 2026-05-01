"""Local JSON graph persistence + NetworkX neighborhood queries."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .schemas import GraphEdge, GraphNode, RelationType, stable_node_id


class GraphStore:
    def __init__(self) -> None:
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []

    def upsert_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def neighbors(self, node_id: str, hops: int = 1) -> Set[str]:
        try:
            import networkx as nx
        except ImportError as exc:
            raise RuntimeError("networkx is required — pip install networkx") from exc

        g = nx.DiGraph()
        for e in self.edges:
            g.add_edge(e.source_id, e.target_id, key=e.id, data=e)
        if node_id not in g and node_id not in self.nodes:
            return set()
        if node_id not in g:
            g.add_node(node_id)
        lengths = nx.single_source_shortest_path_length(g, node_id, cutoff=hops)
        return set(lengths.keys())

    def edges_incident(self, node_ids: Set[str]) -> List[GraphEdge]:
        out: List[GraphEdge] = []
        for e in self.edges:
            if e.source_id in node_ids or e.target_id in node_ids:
                out.append(e)
        return out

    def find_nodes_by_label_substr(self, q: str, limit: int = 32) -> List[GraphNode]:
        q_l = q.lower().strip()
        if not q_l:
            return []
        hits: List[GraphNode] = []
        for n in self.nodes.values():
            if q_l in n.label.lower():
                hits.append(n)
            if len(hits) >= limit:
                break
        return hits

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "GraphStore":
        store = cls()
        if not path.is_file():
            return store
        payload = json.loads(path.read_text(encoding="utf-8"))
        for nid, nd in (payload.get("nodes") or {}).items():
            store.nodes[nid] = GraphNode.from_dict(nd)
        for ed in payload.get("edges") or []:
            store.edges.append(GraphEdge.from_dict(ed))
        return store

    def merge_extraction(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        chunk_id: str,
        chunk_text: str,
        model: str,
        extracted_at: str,
    ) -> Tuple[int, int]:
        """Materialize entities/relations into the store. Returns (n_nodes, n_edges) added."""
        from .schemas import EdgeEvidence

        added_n = 0
        added_e = 0
        label_to_id: Dict[str, str] = {}

        for ent in entities:
            etype = str(ent.get("type") or "").strip()
            label = str(ent.get("label") or "").strip()
            if not etype or not label:
                continue
            nid = stable_node_id(etype, label)
            if nid not in self.nodes:
                self.upsert_node(GraphNode(id=nid, type=etype, label=label, properties={}))
                added_n += 1
            label_to_id[label.lower()] = nid

        allowed_pred = {p.value for p in RelationType}
        for rel in relations:
            sub = str(rel.get("subject") or "").strip().lower()
            obj = str(rel.get("object") or "").strip().lower()
            pred = str(rel.get("predicate") or "").strip()
            quote = str(rel.get("quote") or "").strip()
            if not sub or not obj or pred not in allowed_pred:
                continue
            sid = label_to_id.get(sub)
            oid = label_to_id.get(obj)
            if sid is None or oid is None:
                continue
            if quote and chunk_text and quote not in chunk_text:
                continue
            if not quote:
                continue
            ev = EdgeEvidence(
                chunk_id=chunk_id,
                quote=quote[:2000],
                confidence=float(rel.get("confidence") or 0.75),
                extracted_at=extracted_at,
                model=model,
            )
            eid = f"e_{uuid.uuid4().hex[:12]}"
            self.add_edge(
                GraphEdge(
                    id=eid,
                    source_id=sid,
                    target_id=oid,
                    predicate=pred,
                    evidence=ev,
                )
            )
            added_e += 1
        return added_n, added_e


def seed_store_from_hand_entries(payload: Dict[str, Any]) -> GraphStore:
    """Load hand-authored seed dicts: nodes list, edges list with evidence dicts."""
    from .schemas import EdgeEvidence

    store = GraphStore()
    for n in payload.get("nodes", []) or []:
        store.upsert_node(GraphNode.from_dict(n))
    for e in payload.get("edges", []) or []:
        ev_raw = e.get("evidence")
        ev = EdgeEvidence.from_dict(ev_raw) if ev_raw else None
        store.add_edge(
            GraphEdge(
                id=e["id"],
                source_id=e["source_id"],
                target_id=e["target_id"],
                predicate=e["predicate"],
                evidence=ev,
            )
        )
    return store
