from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coral.grader import TaskGrader
from coral.types import ScoreBundle


class Grader(TaskGrader):
    def evaluate(self) -> float | ScoreBundle:
        program_file = self.args.get("program_file", "solution.py")
        queries_file = Path(self.codebase_path) / "data" / "processed" / "validation" / "queries.jsonl"
        fallback_queries = Path(self.private_dir) / "eval" / "fixtures" / "validation_queries.jsonl"

        if not queries_file.exists():
            if fallback_queries.exists():
                queries_file = fallback_queries
            else:
                return self.fail(
                    "Missing processed dataset. Run scripts/download_jaquad.sh and scripts/prepare_jaquad.py first."
                )

        with tempfile.TemporaryDirectory() as td:
            output_file = Path(td) / "predictions.json"
            result = self.run_program(program_file, "--queries", str(queries_file), "--output", str(output_file))
            if result.returncode != 0:
                return self.fail(f"Program failed: {result.stderr[-1000:]}")
            if not output_file.exists():
                return self.fail("Program did not write predictions output.")

            preds = json.loads(output_file.read_text(encoding="utf-8"))
            if not isinstance(preds, list):
                return self.fail("Predictions must be a list.")

            score = 1.0 if preds else 0.0
            return self.score(score, f"Schema check passed. predictions={len(preds)}")
