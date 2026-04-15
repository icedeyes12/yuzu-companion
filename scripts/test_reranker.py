#!/usr/bin/env python3
"""
Test reranker with data from yuzuki database.

Requirement:
  - SSH tunnel to PostgreSQL running
  - Ollama with model dengcao/Qwen3-Reranker-0.6B:Q8_0 installed
  - Environment variables set (see AGENTS.md for values)

Usage:
  python3 test_reranker.py "your search query"
"""

import os
import sys
import json
import requests
from typing import Optional

# Read from environment (set these before running)
# PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
OLLAMA_URL = "http://localhost:11434/api/generate"
RERANKER_MODEL = "dengcao/Qwen3-Reranker-0.6B:Q8_0"


def get_db_connection():
    """Get psycopg connection from env vars."""
    import psycopg
    return psycopg.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "yuzuki"),
        user=os.getenv("PGUSER", "yuzu_agent"),
        password=os.getenv("PGPASSWORD"),
    )


def query_facts(limit: int = 20, fact_type: Optional[str] = None) -> list[dict]:
    """Fetch facts from database."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if fact_type:
        cur.execute(
            """
            SELECT id, content, metadata
            FROM semantic_facts
            WHERE invalid_at IS NULL AND fact_type = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (fact_type, limit),
        )
    else:
        cur.execute(
            """
            SELECT id, content, metadata
            FROM semantic_facts
            WHERE invalid_at IS NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
    
    rows = cur.fetchall()
    conn.close()
    
    return [
        {"id": r[0], "content": r[1], "metadata": r[2]}
        for r in rows
    ]


def rerank_with_ollama(query: str, documents: list[dict]) -> list[dict]:
    """
    Rerank documents using Ollama reranker model.
    
    Returns list of {id, content, score}
    """
    # Build prompt for reranker
    doc_texts = [d["content"] for d in documents]
    
    prompt = f"""Given the query: "{query}"

Rank the following documents by relevance (most relevant first).
Output JSON array with scores 0-1 where 1 is most relevant.

Documents:
{json.dumps(doc_texts, indent=2)}

Output format: [{{"index": 0, "score": 0.95}}, ...]
Only output the JSON array, nothing else."""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": RERANKER_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )
    
    if response.status_code != 200:
        print(f"Ollama error: {response.status_code}")
        return []
    
    result = response.json()
    output = result.get("response", "")
    
    # Parse JSON from response
    try:
        rankings = json.loads(output)
    except json.JSONDecodeError:
        # Try to extract JSON
        import re
        match = re.search(r'\[.*\]', output, re.DOTALL)
        if match:
            rankings = json.loads(match.group(0))
        else:
            print(f"Could not parse reranker output: {output[:200]}")
            return []
    
    # Merge rankings with documents
    results = []
    for r in rankings:
        idx = r.get("index", 0)
        score = r.get("score", 0.5)
        if 0 <= idx < len(documents):
            doc = documents[idx]
            results.append({
                "id": doc["id"],
                "content": doc["content"],
                "score": score,
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_reranker.py 'your query'")
        print("\nSet env vars first: PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD")
        sys.exit(1)
    
    query = sys.argv[1]
    
    print(f"Query: {query}\n")
    
    # Fetch candidate facts
    print("Fetching facts from database...")
    facts = query_facts(limit=20, fact_type="static")
    print(f"Found {len(facts)} facts\n")
    
    if not facts:
        print("No facts found in database")
        return
    
    # Rerank
    print("Reranking with Ollama...")
    ranked = rerank_with_ollama(query, facts)
    
    print("\n=== Top Results ===")
    for i, r in enumerate(ranked[:5], 1):
        print(f"\n{i}. Score: {r['score']:.3f}")
        print(f"   ID: {r['id']}")
        print(f"   Content: {r['content'][:100]}...")


if __name__ == "__main__":
    main()
