import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "luker_launcher"


def module_identity(path: Path) -> tuple[str, str]:
    """返回模块全名和它相对导入时所在的包。"""
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    module = ".".join(parts)
    package = module if is_package else module.rpartition(".")[0]
    return module, package


def module_name(path: Path) -> str:
    return module_identity(path)[0]


def resolve_relative_import(node: ast.ImportFrom, package: str) -> list[str]:
    """把相对导入解析成绝对模块名，供依赖方向检查使用。"""
    if node.level == 0:
        return [node.module] if node.module else []
    parts = package.split(".") if package else []
    keep = len(parts) - (node.level - 1)
    if keep < 0:
        return []
    base = parts[:keep]
    if node.module:
        return [".".join([*base, node.module])] if base else [node.module]
    return [".".join([*base, alias.name]) for alias in node.names] if base else []


def imported_modules(path: Path) -> list[str]:
    _, package = module_identity(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.extend(resolve_relative_import(node, package))
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

    def test_ctk_private_access_is_isolated(self):
        patterns = (
            r"\._textbox\b",
            r"\._get_widget_scaling\b",
            r"\._canvas\b",
            r"\._draw_engine\b",
            r"window_dpi_scaling_dict",
            r"ScalingTracker\.get_window_dpi_scaling",
        )
        for path in sorted((PACKAGE / "ui").rglob("*.py")):
            if path.name == "ctk_adapter.py":
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if re.search(pattern, text):
                    self.fail(f"{path.relative_to(ROOT)} 直接访问 CTk 私有接口：{pattern}")

    def test_infrastructure_does_not_depend_on_application_or_presentation(self):
        for forbidden in (
            "luker_launcher.application",
            "luker_launcher.ui",
            "luker_launcher.tray",
            "tkinter",
            "customtkinter",
        ):
            with self.subTest(forbidden=forbidden):
                self.assert_no_dependency("luker_launcher.infrastructure", forbidden)

    def test_process_does_not_depend_on_application_or_presentation(self):
        for forbidden in (
            "luker_launcher.application",
            "luker_launcher.ui",
            "luker_launcher.tray",
            "tkinter",
            "customtkinter",
        ):
            with self.subTest(forbidden=forbidden):
                self.assert_no_dependency("luker_launcher.process", forbidden)

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

    def test_relative_imports_resolve_to_absolute_modules(self):
        tree = ast.parse(
            "from .buttons import make_button\nfrom ..ui import colors\nfrom . import helper\n"
        )
        nodes = [node for node in tree.body if isinstance(node, ast.ImportFrom)]

        modules = [
            module
            for node in nodes
            for module in resolve_relative_import(node, "luker_launcher.ui")
        ]

        self.assertEqual(
            modules,
            [
                "luker_launcher.ui.buttons",
                "luker_launcher.ui",
                "luker_launcher.ui.helper",
            ],
        )

    def test_relative_import_above_top_level_is_ignored(self):
        node = ast.parse("from ... import helper").body[0]
        self.assertIsInstance(node, ast.ImportFrom)

        self.assertEqual(resolve_relative_import(node, "luker_launcher"), [])

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
