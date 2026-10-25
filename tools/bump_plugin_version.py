"""把某个插件目录下的版本号统一改到目标版本。

用法：
    <python> tools/bump_plugin_version.py tgmediacenter 1.13.26
    <python> tools/bump_plugin_version.py subscribecenter 1.14.8

会改到这些位置（存在哪个改哪个）：

- ``<plugin>/core/constants.py`` 的 ``PLUGIN_VERSION = "x.y.z"``（订阅中心有，别的插件可能没有）
- ``<plugin>/__init__.py`` 的类级 ``plugin_version = "x.y.z"``
- ``<plugin>/src/components/version.js`` 的 ``export const FRONTEND_VERSION = 'x.y.z'``
- ``<plugin>/package.json`` 的 ``"version": "x.y.z"``

只替换版本字面量，保留声明前缀；一律以 UTF-8 无 BOM + LF 写回（PowerShell
的 ``Set-Content`` 会写成 BOM+CRLF，让 git diff 变成整文件重写）。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rewrite(path: Path, pattern: re.Pattern, template: str) -> bool:
    """按正则替换一次，返回是否命中。"""
    text = io.open(path, encoding="utf-8").read()
    new_text, count = pattern.subn(template, text, count=1)
    if not count:
        return False
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    print(f"OK  {path.relative_to(ROOT)} -> {template[-24:]}")
    return True


def main() -> int:
    """按命令行参数替换版本号。"""
    if len(sys.argv) < 3:
        print("用法: bump_plugin_version.py <插件目录名> <x.y.z>")
        return 2
    plugin_name, version = sys.argv[1], sys.argv[2]
    if version.count(".") < 1:
        print("!! 版本号至少要有一段小数点，例如 1.13.26")
        return 2

    plugin = ROOT / "plugins.v3" / plugin_name
    if not plugin.is_dir():
        print(f"!! 找不到插件目录 {plugin}")
        return 1

    expected = 0
    changed = 0
    for path, pattern, template in (
        (
            plugin / "core" / "constants.py",
            re.compile(r'^(PLUGIN_VERSION\s*=\s*)"[^"]*"', re.MULTILINE),
            rf'\g<1>"{version}"',
        ),
        (
            plugin / "__init__.py",
            re.compile(r'^(\s*plugin_version\s*=\s*)"[^"]*"', re.MULTILINE),
            rf'\g<1>"{version}"',
        ),
        (
            plugin / "src" / "components" / "version.js",
            re.compile(r"^(export\s+const\s+FRONTEND_VERSION\s*=\s*)'[^']*'", re.MULTILINE),
            rf"\g<1>'{version}'",
        ),
        (
            plugin / "package.json",
            re.compile(r'("version"\s*:\s*)"[^"]*"'),
            rf'\g<1>"{version}"',
        ),
    ):
        if not path.exists():
            continue
        expected += 1
        if not _rewrite(path, pattern, template):
            print(f"!! {path.relative_to(ROOT)} 未匹配到版本声明")
            return 1
        changed += 1

    if not changed:
        print(f"!! {plugin_name} 里没有可改的版本声明")
        return 1
    print(f"done: {plugin_name} -> {version} ({changed}/{expected} 处)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
