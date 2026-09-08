import unittest


class LazyToolImportTest(unittest.TestCase):
    def test_optional_tools_are_lazy_loaded(self):
        import sys

        import tools

        self.assertNotIn("tools.weather", sys.modules)
        self.assertNotIn("tools.email", sys.modules)
        self.assertNotIn("tools.delegate", sys.modules)
        self.assertNotIn("tools.memory", sys.modules)
        self.assertNotIn("tools.weather", sys.modules)
        self.assertNotIn("tools.email", sys.modules)
        self.assertNotIn("tools.delegate", sys.modules)


if __name__ == "__main__":
    unittest.main()
