# rag_jaquad

Japanese RAG PoC task scaffold for CORAL using JaQuAD.

## Data setup

```bash
bash examples/rag_jaquad/scripts/download_jaquad.sh
uv run python examples/rag_jaquad/scripts/prepare_jaquad.py \
  --input-root examples/rag_jaquad/data/raw/JaQuAD/data \
  --output-root examples/rag_jaquad/data/processed \
  --validation-sample-size 200 \
  --validation-sample-seed 42
```

Expected outputs:

- `data/processed/train/corpus.jsonl`
- `data/processed/train/queries.jsonl`
- `data/processed/validation/corpus.jsonl`
- `data/processed/validation/queries.jsonl`

## License note

JaQuAD dataset is licensed under CC BY-SA 3.0.
Source: https://github.com/SkelterLabsInc/JaQuAD
