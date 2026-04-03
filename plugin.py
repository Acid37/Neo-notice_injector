"""NoticeInjector 插件实现"""

from __future__ import annotations

from typing import Any

# 导入必要的类
from src.app.plugin_system.api.log_api import get_logger
from src.core.components.base import BasePlugin, BaseEventHandler
from src.core.components.loader import register_plugin
from src.core.components.types import EventType
from src.kernel.event import EventDecision

from .config import NoticeInjectorConfig
from .actions.poke import SendPokeAction, SendPokeMultipleAction
from .actions.emoji_like import SendEmojiLikeAction

logger = get_logger("notice_injector")


# ─── Event Handler ──────────────────────────────────────────


class NoticeInjectorEventHandler(BaseEventHandler):
    """Notice 注入事件处理器"""

    handler_name = "notice_injector"
    handler_description = "将 QQ 通知消息（如戳一戳、表情回复等）转换为标准文本消息。"

    # 订阅的事件类型
    init_subscribe = [EventType.ON_RECEIVED_OTHER_MESSAGE]
    
    def __init__(self, plugin: "NoticeInjectorPlugin") -> None:
        """初始化处理器
        
        Args:
            plugin: 所属插件实例
        """
        super().__init__(plugin)
        self.plugin = plugin
        self._bot_id: str | None = None

    async def execute(
        self, event_name: str, params: dict[str, Any]
    ) -> tuple[EventDecision, dict[str, Any]]:
        """处理其他类型消息，将 notice 转换为标准消息"""
        # 获取配置对象
        config: NoticeInjectorConfig = self.plugin.config  # type: ignore
        if not config:
            # 如果配置未加载，保守起见不进行处理
            return EventDecision.SUCCESS, params
            
        # 1. 检查全局开关
        if not config.plugin.enabled:
            return EventDecision.SUCCESS, params

        raw = params.get("raw", {})
        msg_info = raw.get("message_info", {})
        message_type = msg_info.get("message_type", "")
        
        # 2. 只处理 notice 类型的消息
        if message_type != "notice":
            return EventDecision.SUCCESS, params
            
        extra = msg_info.get("extra", {})
        notice_type = extra.get("notice_type", "")
        text_description = extra.get("text_description", "")

        # 对 group_msg_emoji_like 类型尝试提取更丰富的描述
        if notice_type == "group_msg_emoji_like" and not text_description:
            # 尝试从 emoji_list 中构建描述
            emoji_list = extra.get("emoji_list", [])
            if emoji_list:
                emoji_id = str(emoji_list[0].get("emoji_id", "")) if emoji_list else ""
                count = emoji_list[0].get("count", 1) if emoji_list else 1
                from_user = msg_info.get("from_user", {})
                sender_nick = from_user.get("nickname", "") or from_user.get("user_id", "某人")
                msg_id = msg_info.get("message_id", "")
                text_description = (
                    f"{sender_nick} 对消息{(' ' + str(msg_id)) if msg_id else ''}"
                    f" 发送了表情回复（表情ID: {emoji_id}，数量: {count}）"
                )
                extra["text_description"] = text_description
                if config.plugin.enable_debug:
                    logger.debug(f"构建表情回复描述: {text_description}")

        # 如果没有 text_description，无法处理，直接返回
        if not text_description:
            return EventDecision.SUCCESS, params

        # 3. 按类型检查功能开关
        if notice_type == "poke" and not config.plugin.enable_poke:
            if config.plugin.enable_debug:
                logger.debug(f"通过配置忽略戳一戳通知: {text_description}")
            return EventDecision.SUCCESS, params
            
        elif notice_type == "group_msg_emoji_like" and not config.plugin.enable_emoji_like:
            if config.plugin.enable_debug:
                logger.debug(f"通过配置忽略表情回复通知: {text_description}")
            return EventDecision.SUCCESS, params
            
        elif notice_type == "group_ban" and not config.plugin.enable_ban:
            if config.plugin.enable_debug:
                logger.debug(f"通过配置忽略禁言通知: {text_description}")
            return EventDecision.SUCCESS, params
            
        elif notice_type == "group_upload" and not config.plugin.enable_group_upload:
            if config.plugin.enable_debug:
                logger.debug(f"通过配置忽略上传通知: {text_description}")
            return EventDecision.SUCCESS, params

        # 4. 检查是否是机器人自己发送的动作（防止自循环）
        # 优先使用适配器提供的标记，如果没有则回退到简单的逻辑判断
        # 受控于 config.plugin.ignore_self_notice
        if config.plugin.ignore_self_notice:
            is_self = extra.get("self_sent", False)
            if not is_self:
                is_self = await self._is_self_sent_poke(extra, msg_info)
                
            if is_self:
                if config.plugin.enable_debug:
                    logger.debug(f"检测到自己发送的动作，已忽略: {text_description}")
                return EventDecision.SUCCESS, params
            
        # 5. 检查是否启用了聊天触发
        # 如果未启用 trigger_chat，则不注入消息，从而避免消耗 Token 和污染上下文
        if not config.plugin.trigger_chat:
            if config.plugin.enable_debug:
                logger.debug(f"Chat Trigger 未启用，忽略通知: {text_description}")
            return EventDecision.SUCCESS, params

        # 根据 notice 类型处理并记录日志
        if config.plugin.enable_debug:
            logger.info(f"处理通知消息 [{notice_type}]: {text_description}")
        
        # 关键修改：将 notice 消息转换为 processed 文本
        # 这样 _handle_other 方法会创建 Message 并触发 ON_MESSAGE_RECEIVED
        
        # 设置 processed 字段，让 _handle_other 创建标准消息
        params["processed"] = text_description
        
        # 同时保留原始信息到 extra，供后续使用
        # 且标记为 trigger_chat=True，供下游 StreamManager 参考（目前核心层尚未实现瞬态消息支持，未来可扩展 ephemeral）
        current_extra = msg_info.get("extra", {})
        current_extra.update({
            "original_notice_type": notice_type,
            "trigger_chat": True,
            "ephemeral": True  # 建议的核心层协议：标记为瞬态消息，不持久化到数据库
        })
        msg_info["extra"] = current_extra
        
        return EventDecision.SUCCESS, params

    async def _is_self_sent_poke(self, extra: dict, msg_info: dict) -> bool:
        """检查是否是机器人自己发送的动作"""
        # 尝试获取操作者ID
        # 注意：adapter生成的msg_info中，user_id通常位于from_user字段，而不是extra
        operator_id = extra.get("operator_id") or extra.get("user_id")
        
        if not operator_id:
            # 尝试从 from_user 获取
            from_user = msg_info.get("from_user", {})
            operator_id = from_user.get("user_id")
            
        if not operator_id:
            return False
            
        # 懒加载获取 Bot ID
        if not self._bot_id:
            try:
                from src.app.plugin_system.api import adapter_api
                # 尝试获取 QQ 平台的 bot 信息
                bot_info = await adapter_api.get_bot_info_by_platform("qq")
                if bot_info:
                    self._bot_id = str(bot_info.get("user_id", ""))
            except Exception as e:
                logger.warning(f"获取Bot信息失败: {e}")
        
        # 比对操作者ID与Bot ID
        if self._bot_id and str(operator_id) == self._bot_id:
            return True
            
        return False


# ─── Plugin ────────────────────────────────────────────────


@register_plugin
class NoticeInjectorPlugin(BasePlugin):
    """NoticeInjector 插件主类"""

    plugin_name = "notice_injector"
    plugin_version = "1.1.2"
    plugin_author = "NeoFox"
    plugin_description = "将 QQ 通知消息（如戳一戳、表情回复等）转换为标准文本消息。"
    configs = [NoticeInjectorConfig]

    async def on_load(self) -> bool:
        """插件加载时的处理"""
        logger.info("NoticeInjector 插件加载成功")
        return True

    async def on_unload(self) -> bool:
        """插件卸载时的处理"""
        logger.info("NoticeInjector 插件卸载成功")
        return True

    def get_components(self) -> list[type]:
        """获取插件内所有组件类"""
        return [
            SendPokeAction,
            SendPokeMultipleAction,
            SendEmojiLikeAction,
            NoticeInjectorEventHandler,
        ]
