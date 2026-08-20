import subprocess
import sys
import unittest


class LazyToolImportTest(unittest.TestCase):
    def test_optional_tools_are_lazy_loaded(self):
        code = """
import sys
import tools
print('weather' in sys.modules)
print('email' in sys.modules)
print('delegate' in sys.modules)
print('memory' in sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line.strip() for line in result.stdout.strip().splitlines()]
        self.assertEqual(lines, ["False", "False", "False", "True"], lines)


if __name__ == "__main__":
    unittest.main()
