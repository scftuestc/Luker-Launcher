import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "luker_launcher"


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return modules


def package_modules() -> dict[str, list[str]]:
    modules: dict[str, list[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        modules[module_name(path)] = imported_modules(path)
    return modules


def imports_under(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = package_modules()

    def assert_no_dependency(self, source_prefix: str, forbidden_prefix: str) -> None:
        for source, imports in self.modules.items():
            if not imports_under(source, source_prefix):
                continue
            for target in imports:
                if imports_under(target, forbidden_prefix):
                    self.fail(f"{source} 不应导入 {target}")

    def test_services_do_not_depend_on_ui_tray_or_application(self):
        for forbidden in (
            "luker_launcher.ui",
            "luker_launcher.tray",
            "luker_launcher.application",
            "tkinter",
            "customtkinter",
        ):
            with self.subTest(forbidden=forbidden):
                self.assert_no_dependency("luker_launcher.services", forbidden)

    def test_log_domain_does_not_depend_on_presentation(self):
        for forbidden in (
            "luker_launcher.ui",
            "luker_launcher.tray",
            "luker_launcher.application",
            "tkinter",
            "customtkinter",
        ):
            with self.subTest(forbidden=forbidden):
                self.assert_no_dependency("luker_launcher.log", forbidden)

    def test_config_does_not_depend_on_presentation(self):
        for forbidden in (
            "luker_launcher.ui",
            "luker_launcher.tray",
            "luker_launcher.application",
        ):
            with self.subTest(forbidden=forbidden):
                self.assert_no_dependency("luker_launcher.config", forbidden)

    def test_ui_does_not_depend_on_application(self):
        self.assert_no_dependency("luker_launcher.ui", "luker_launcher.application")

    def test_theme_and_paths_only_use_stdlib(self):
        for module in ("luker_launcher.theme", "luker_launcher.paths"):
            for imported in self.modules[module]:
                if imported == "luker_launcher" or imported.startswith("luker_launcher."):
                    self.fail(f"{module} 不应导入项目模块 {imported}")

    def test_only_entrypoints_import_bootstrap(self):
        allowed = {"luker_launcher.__main__"}
        for source, imports in self.modules.items():
            if source in allowed:
                continue
            for target in imports:
                if imports_under(target, "luker_launcher.bootstrap"):
                    self.fail(f"{source} 不应导入启动入口 {target}")

    def test_production_code_lives_in_package(self):
        root_modules = sorted(path.name for path in ROOT.glob("*.py"))
        self.assertEqual(root_modules, ["main.py"])

    def test_main_is_a_thin_entrypoint(self):
        text = (ROOT / "main.py").read_text(encoding="utf-8")
        imports = imported_modules(ROOT / "main.py")

        self.assertEqual(imports, ["luker_launcher.bootstrap.entrypoint"])
        self.assertNotIn("tkinter", text)
        self.assertNotIn("customtkinter", text)

    def test_no_import_cycles(self):
        graph = {
            source: [target for target in imports if target.startswith("luker_launcher.")]
            for source, imports in self.modules.items()
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str, path: list[str]) -> None:
            if node in visited:
                return
            if node in visiting:
                cycle = " -> ".join([*path, node])
                self.fail(f"检测到导入环: {cycle}")
            visiting.add(node)
            for target in graph.get(node, []):
                if target in graph:
                    visit(target, [*path, node])
            visiting.remove(node)
            visited.add(node)

        for module in graph:
            visit(module, [])


if __name__ == "__main__":
    unittest.main()
