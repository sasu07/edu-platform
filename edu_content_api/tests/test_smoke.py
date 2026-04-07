import re
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
MAIN_PATH = BACKEND_DIR / "main.py"
ROUTERS_DIR = BACKEND_DIR / "routers"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ApiSmokeTests(unittest.TestCase):
    def test_main_includes_split_routers(self):
        source = _read(MAIN_PATH)

        expected_includes = [
            "app.include_router(auth_router)",
            "app.include_router(exercises_router)",
            "app.include_router(help_router)",
            "app.include_router(parent_router)",
            "app.include_router(study_router)",
            "app.include_router(system_router)",
            "app.include_router(variants_router)",
        ]

        for include in expected_includes:
            self.assertIn(include, source)

    def test_critical_routes_exist_across_backend(self):
        files = [MAIN_PATH, *sorted(ROUTERS_DIR.glob("*_router.py"))]
        route_text = "\n".join(_read(path) for path in files)

        expected_paths = [
            "/health",
            "/exercises/",
            "/exercise-sets/",
            "/variants/generate",
            "/parent/link-student",
            "/admin/parent-student",
            "/study-sessions/start",
        ]

        for path in expected_paths:
            self.assertIn(path, route_text)

    def test_no_duplicate_route_decorators(self):
        route_pattern = re.compile(r'@(?:app|router)\.(get|post|put|delete|patch)\("([^"]+)"')
        files = [MAIN_PATH, *sorted(ROUTERS_DIR.glob("*_router.py"))]
        seen = set()
        duplicates = []

        for path in files:
            for method, route in route_pattern.findall(_read(path)):
                key = (method.upper(), route)
                if key in seen:
                    duplicates.append(key)
                seen.add(key)

        self.assertEqual(duplicates, [])


if __name__ == "__main__":
    unittest.main()
