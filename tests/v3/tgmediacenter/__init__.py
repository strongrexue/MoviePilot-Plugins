"""tgmediacenter 测试包标记。

为什么需要这个包（另外两个插件目录没有）：

1. **避免同名文件相撞**：``tests/v3/tgmediacenter/test_plugin.py`` 与
   ``tests/v3/embycovercenter/test_plugin.py`` 同名。没有 ``__init__.py`` 时 pytest
   把两者都当顶层模块 ``test_plugin`` 导入，合跑 ``pytest tests/v3`` 会直接报
   ``import file mismatch`` 而中断收集。
2. **让测试之间可以互相引用**：``test_exclude_keywords.py`` 复用了
   ``test_p4_monitor.py`` 里的替身，有包之后写成
   ``from .test_p4_monitor import ...``，不再依赖 pytest 的 sys.path 插入顺序。

加了包标记后，本目录的用例以 ``tgmediacenter.test_xxx`` 导入，与另外两个插件
（用例仍是顶层模块）互不干扰。
"""
