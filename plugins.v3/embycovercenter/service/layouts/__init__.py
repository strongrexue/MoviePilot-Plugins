"""内置封面布局。

每个布局是一个独立模块，导出：

- ``get_schema() -> {"fields": [...]}``：布局专属参数（前端按此动态生成表单）；
- ``render(engine, bg, config, assets, fonts, step=None) -> PIL.Image``：
  `bg` 为已模糊/调亮的背景，`fonts` 为 ``{"main", "sub", "count"}`` 三个 PIL 字体对象，
  `step`` 为动态封面的 0~1 进度（静态渲染时为 None）。

引擎只会加载同时提供 ``render`` 的模块；布局参数缺省值由本文件的 schema 提供。
"""
