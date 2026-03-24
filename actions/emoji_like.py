"""发送表情回复动作"""

from __future__ import annotations

from src.core.components.base import BaseAction
from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.api import adapter_api

logger = get_logger("notice_injector")


class SendEmojiLikeAction(BaseAction):
    """发送表情回复动作给消息"""

    action_name = "send_emoji_like"
    action_description = "给指定消息发送表情回复。你可以在需要表达对消息的态度时使用这个功能，比如点赞、开心、惊讶等。"

    async def execute(self, message_id: str, emoji_id: str = "126") -> tuple[bool, str]:
        """执行发送表情回复动作

        Args:
            message_id: 要回复的消息ID
            emoji_id: 表情ID，默认是点赞表情(126)
        """
        # 构建表情回复参数
        command_data = {
            "message_id": message_id,
            "emoji_id": emoji_id
        }
        
        try:
            # 发送表情回复命令到 napcat 适配器
            # 注意：这里使用了硬编码的 adapter_sign，这是目前唯一可用的 QQ 适配器
            # 发送 set_msg_emoji_like 命令 (OneBot 11 标准)
            result = await adapter_api.send_adapter_command(
                adapter_sign="napcat_adapter:adapter:napcat_adapter",
                command_name="set_msg_emoji_like",
                command_data=command_data,
                timeout=10.0
            )

            if result.get("status") == "ok":
                logger.info(f"已对消息 {message_id} 发送表情回复，表情ID: {emoji_id}")
                return True, f"已对消息 {message_id} 发送表情回复，表情ID: {emoji_id}"
            else:
                error_msg = result.get("message", "未知错误")
                logger.error(f"发送表情回复失败: 消息ID {message_id}, 错误: {error_msg}")
                return False, f"发送表情回复失败: {error_msg}"
                
        except Exception as e:
            logger.error(f"发送表情回复时发生异常: {e}", exc_info=True)
            return False, f"发送表情回复时发生异常: {str(e)}"