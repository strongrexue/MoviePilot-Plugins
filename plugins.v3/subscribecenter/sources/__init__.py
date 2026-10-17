"""数据源适配器包。

每个适配器只负责「取数 + 归一为 :class:`~..core.model.DiscoveredItem`」，
不参与去重、过滤与写入（开发文档 §7.1）。
"""
