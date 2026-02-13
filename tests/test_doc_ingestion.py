from __future__ import annotations

import pathlib
import shutil
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from grant_agent.doc_ingestion import ingest_docs


class DocIngestionTests(unittest.TestCase):
    def test_reads_local_doc_and_writes_evidence(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        temp = root / ".doc_ingestion_test"
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True, exist_ok=True)

        records = ingest_docs(["README.md"], repo_path=root, session_path=temp)
        self.assertEqual(records[0].status, "ok")
        self.assertTrue((temp / "docs_evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
