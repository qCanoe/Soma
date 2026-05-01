# Medical Music Knowledge Seeds

This directory contains the local seed corpus for the MindWave/Soma medical music knowledge graph.

The seed data is intentionally compact: it stores short, traceable excerpts and hand-authored graph edges so the GraphRAG pipeline can run offline before a full ingestion pass.

## Files

| File | Purpose |
| --- | --- |
| `sources.yaml` | Registry of trusted or openly accessible sources that can be fetched by `python -m music_ai_module.knowledge ingest`. |
| `chunks.jsonl` | Short text chunks with `chunk_id`, `source_id`, URL, title, and approximate character offsets. |
| `graph.json` | Local graph nodes and edges. Every edge has evidence with `chunk_id` and a verbatim `quote` from `chunks.jsonl`. |
| `embeddings.jsonl` | Optional generated embedding cache. This file is ignored by git and can be regenerated. |
| `raw/` | Optional downloaded HTML snapshots. This folder is ignored by git and can be regenerated. |

## Seed Source Coverage

The current seed registry covers:

- NCCIH music and health overview and evidence digest.
- NCCIH anxiety and complementary health approaches.
- NIH/NCCIH Music-Based Intervention Toolkit definitions for music therapy vs music medicine.
- WHO ICD-11 license page for classification and licensing boundaries.
- Sleep music parameter review covering tempo, structure, dosing, volume, and disruptive features.
- ADHD music therapy systematic review and meta-analysis.
- Hyperacusis sound therapy scoping review.
- PTSD / posttraumatic stress music therapy theoretical review.

## Graph Scope

The seed graph focuses on wellness music planning, not diagnosis or treatment. It currently links:

- Conditions: anxiety, sleep problems, insomnia, stress, ADHD, hyperacusis, PTSD, trauma exposure.
- Symptoms: inattention, hyperactivity/impulsivity, sound intolerance, sleep-onset latency, hyperarousal.
- Interventions: music-based interventions, music therapy, music medicine, listening to recorded music, sound therapy, sleep-promoting music.
- Acoustic parameters: slow tempo 60-80 BPM, soft/smooth/instrumental/simple structure, 30-45 minute bedtime dosing, low comfortable volume, avoided sleep-disruptive features.
- Safety constraints: high-volume hearing risk, distressing memory triggers, sharp onsets/percussion, sound sensitivity.

## Validation Rule

Do not add an edge to `graph.json` unless its `evidence.quote` appears verbatim in the referenced chunk text. The test suite checks this rule:

```bash
python -m pytest tests/test_knowledge_seed_data.py -q
```

## Updating Seeds

1. Add a source to `sources.yaml` with license notes and topics.
2. Add a short excerpt to `chunks.jsonl`.
3. Add nodes and evidence-backed edges to `graph.json`.
4. Run:

```bash
python -m pytest tests/test_knowledge_seed_data.py -q
python -m pytest tests/ -q
```

Use `ingest --extract` only when you want the OpenAI-compatible LLM extractor to generate candidate graph edges from fetched chunks. Hand-authored seeds should stay conservative and cite short passages only.
