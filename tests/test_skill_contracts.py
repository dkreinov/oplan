from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


VALIDATOR = Path(__file__).resolve().parents[1] / "oplan" / "scripts" / "validate_skill_contracts.py"


class SkillContractsTests(unittest.TestCase):
    def test_validate_skill_contracts_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"validate_skill_contracts.py failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
