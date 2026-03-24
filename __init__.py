"""Notice Injector 插件包。

此包实现了 QQ 通知消息的注入和处理，提供：
- 通知处理器：处理戳一戳、表情回复、禁言等 QQ 通知
- 主动交互组件：支持主动发送戳一戳和表情回复

插件入口在 :mod:`plugin` 模块中由 ``@register_plugin`` 装饰的
``NoticeInjectorPlugin`` 类注册，通过插件加载器自动发现。
"""

__all__: list[str] = []
