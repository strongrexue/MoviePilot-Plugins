"""一次性脚本：把订阅中心插件的四处版本号统一改到目标版本。

用法：
    <python> tools/bump_subscribecenter_version.py 0.2.1
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v3" / "subscribecenter"


def main() -> int:
    """按命令行参数替换四处版本号。"""
    version = sys.argv[1] if len(sys.argv) > 1 else ""
    if not version or version.count(".") < 1:
        print("用法: bump_subscribecenter_version.py <x.y.z>")
        return 2

    import re

    #: (文件, 匹配整行的正则, 替换模板) —— 只替换值，保留声明前缀
    patterns = [
        (
            PLUGIN / "core" / "constants.py",
            re.compile(r'^(PLUGIN_VERSION\s*=\s*)"[^"]*"'),
            rf'\g<1>"{version}"',
        ),
        (
            PLUGIN / "__init__.py",
            re.compile(r'^(\s*plugin_version\s*=\s*)"[^"]*"'),
            rf'\g<1>"{version}"',
        ),
        (
            PLUGIN / "src" / "components" / "version.js",
            re.compile(r"^(export\s+const\s+FRONTEND_VERSION\s*=\s*)'[^']*'"),
            rf"\g<1>'{version}'",
        ),
    ]

    for path, pattern, template in patterns:
        text = io.open(path, encoding="utf-8").read()
        new_text, count = pattern.subn(template, text, count=1)
        if not count:
            print(f"!! {path} 未匹配到版本声明")
            return 1
        io.open(path, "w", encoding="utf-8", newline="\n").write(new_text)
        print(f"OK  {path.relative_to(ROOT)} -> {version}")

    # package.json 的 version 字段
    pkg = PLUGIN / "package.json"
    text = io.open(pkg, encoding="utf-8").read()
    new_text, count = re.subn(r'("version"\s*:\s*)"[^"]*"', rf'\1"{version}"', text, count=1)
    if not count:
        print("!! package.json 未找到 version 字段")
        return 1
    io.open(pkg, "w", encoding="utf-8", newline="\n").write(new_text)
    print(f"OK  {pkg.relative_to(ROOT)} -> {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
