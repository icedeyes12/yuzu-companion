import asyncio
import os
import sys
import json
import math
from datetime import datetime

# Adjust Python path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import pg_fetchall_async, pg_execute_async
from app.memory.db_memory_facade import FACT_TYPE_STATIC

def cosine_distance(u, v):
    dot = sum(a * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(b * b for b in v))
    if norm_u == 0 or norm_v == 0:
        return 1.0
    return 1.0 - (dot / (norm_u * norm_v))

async def prune_memories():
    print("Fetching active static facts...")
    facts = await pg_fetchall_async(
        "SELECT id, content, embedding, metadata FROM semantic_facts WHERE fact_type=%s AND invalid_at IS NULL",
        (FACT_TYPE_STATIC,)
    )
    
    if not facts:
        print("No static facts found.")
        return

    print(f"Loaded {len(facts)} active static facts.")
    
    # Parse embeddings
    valid_facts = []
    for f in facts:
        emb = f["embedding"]
        if isinstance(emb, str):
            try:
                emb = json.loads(emb)
            except Exception:
                continue
        if not emb:
            continue
        f["vec"] = emb
        valid_facts.append(f)
    
    facts = valid_facts
    
    # Greedy clustering
    clusters = []
    visited = set()
    
    threshold = 0.10  # Distance threshold for duplicates (very strict)
    
    for i, f1 in enumerate(facts):
        if i in visited:
            continue
            
        cluster = [f1]
        visited.add(i)
        
        for j in range(i + 1, len(facts)):
            if j in visited:
                continue
            f2 = facts[j]
            
            dist = cosine_distance(f1["vec"], f2["vec"])
            if dist < threshold:
                cluster.append(f2)
                visited.add(j)
                
        clusters.append(cluster)
        
    dupes = [c for c in clusters if len(c) > 1]
    
    print(f"Found {len(clusters)} unique semantic clusters.")
    print(f"Identified {len(dupes)} clusters with duplicates.")
    
    if not dupes:
        print("No duplicates to prune.")
        return
        
    invalidated_count = 0
    kept_count = 0
    
    print("\nConsolidating duplicates...")
    for cluster in dupes:
        # Sort by length of content descending to keep the most detailed one
        cluster.sort(key=lambda x: len(x["content"]), reverse=True)
        
        kept = cluster[0]
        to_invalidate = cluster[1:]
        kept_count += 1
        
        for old_fact in to_invalidate:
            await pg_execute_async(
                "UPDATE semantic_facts SET invalid_at=%s WHERE id=%s",
                (datetime.now(), old_fact["id"])
            )
            invalidated_count += 1
            
            # Print a short preview of what was kept vs removed
            kept_preview = kept['content'][:40].replace('\n', ' ')
            old_preview = old_fact['content'][:40].replace('\n', ' ')
            print(f"  [Merge] Kept: '{kept_preview}...'")
            print(f"          Drop: '{old_preview}...'")
            
    print(f"\nPruning complete! Invalidated {invalidated_count} duplicate facts.")
    print(f"Retained {kept_count} canonical facts from the duplicate clusters.")

if __name__ == "__main__":
    asyncio.run(prune_memories())
