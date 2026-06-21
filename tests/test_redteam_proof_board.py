from __future__ import annotations

import json
import pathlib
import subprocess
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", textwrap.dedent(script)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class RedTeamProofBoardTests(unittest.TestCase):
    def test_redteam_proof_board_keeps_scope_synthetic_and_visible(self) -> None:
        payload = run_node(
            """
            import {
              RED_TEAM_PROOF_PACKETS,
              buildRedTeamProofBoard,
            } from './web/src/fluxio/redteam/redTeamProofFixtures.js';

            const board = buildRedTeamProofBoard();
            console.log(JSON.stringify({ board, packets: RED_TEAM_PROOF_PACKETS }));
            """
        )

        board = payload["board"]
        self.assertEqual(board["summary"]["packetCount"], len(payload["packets"]))
        self.assertEqual(board["summary"]["safePacketCount"], len(payload["packets"]))
        self.assertGreaterEqual(board["summary"]["probeFamilyCount"], 5)
        joined = json.dumps(board).lower()
        self.assertIn("fictional-targets-only", joined)
        self.assertIn("visible-transcript-only", joined)
        self.assertIn("refusal_quality", joined)
        self.assertNotIn("live exploit", joined)
        self.assertNotIn("credential theft", joined)

        for packet in payload["packets"]:
            self.assertFalse(packet["route"]["liveModelCalls"])
            self.assertFalse(packet["boundary"]["networkActivity"])
            self.assertFalse(packet["boundary"]["realTargetsUsed"])
            self.assertFalse(packet["boundary"]["harmfulInstructionsIncluded"])
            self.assertTrue(packet["boundary"]["fictionalTargetsOnly"])
            self.assertTrue(packet["boundary"]["humanReviewRequired"])
            self.assertTrue(packet["artifactPaths"]["transcript"].endswith("sample_transcript.json"))


if __name__ == "__main__":
    unittest.main()
