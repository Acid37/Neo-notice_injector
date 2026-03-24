"""发送戳一戳动作"""

from __future__ import annotations

import asyncio
import random

from src.core.components.base import BaseAction
from src.app.plugin_system.api.log_api import get_logger

logger = get_logger("notice_injector")


class SendPokeAction(BaseAction):
    """发送戳一戳动作给用户"""

    action_name = "send_poke"
    action_description = (
        "向指定用户发送戳一戳动作。"
        "支持通过 poke_count 指定连续戳一戳次数；"
        "支持通过 target_user_id / target_group_id 显式指定目标（可不等于当前回复对象）；"
        "注意：group_id 必须是群号（数字ID），不能传群名。"
        "请结合上下文与提示词决定次数。"
        "插件默认最大次数为3，硬上限为10，超出会自动按上限截断。"
    )

    @staticmethod
    def _normalize_numeric_id(value: object) -> str | None:
        """将输入归一化为仅数字ID字符串。"""
        if value is None:
            return None
        text = str(value).strip()
        if not text or not text.isdigit():
            return None
        return text

    async def _resolve_group_id_from_stream(self, chat_stream: object) -> str | None:
        """从流上下文或流记录中解析群ID（数字）。"""
        # 1) 优先从当前消息 extra 中获取
        context = getattr(chat_stream, "context", None)
        if context:
            current_message = getattr(context, "current_message", None)
            if current_message:
                extra = getattr(current_message, "extra", {})
                group_id = self._normalize_numeric_id(extra.get("group_id"))
                if group_id:
                    return group_id

        # 2) 回退：按 stream_id 查询 chat_streams 表中的 group_id
        stream_id = getattr(chat_stream, "stream_id", "")
        if not stream_id:
            return None

        try:
            from src.core.models.sql_alchemy import ChatStreams
            from src.kernel.db import QueryBuilder

            record = await QueryBuilder(ChatStreams).filter(stream_id=stream_id).first()
            if not record:
                return None
            return self._normalize_numeric_id(getattr(record, "group_id", None))
        except Exception as e:
            logger.debug(f"通过 stream_id 回查 group_id 失败: {e}")
            return None

    async def execute(
        self,
        user_id: str,
        group_id: str | None = None,
        poke_count: int = 1,
        target_user_id: str | None = None,
        target_group_id: str | None = None,
        **kwargs,
    ) -> tuple[bool, str]:
        """执行发送戳一戳动作

        Args:
            user_id: 要戳的用户ID
            group_id: 可选，群ID（如果是在群里戳的话）
            poke_count: 连续戳一戳次数。建议由 LLM 根据上下文决定；
                实际执行时会被限制在 [1, effective_max]，
                其中 effective_max = min(max_poke_count, 10)
            target_user_id: 可选，显式目标用户ID。若提供则优先于 user_id
            target_group_id: 可选，显式目标群ID。若提供则优先于 group_id
            **kwargs: 上下文参数，可能包含 message 等信息
        """
        try:
            # 获取适配器管理器
            from src.core.managers.adapter_manager import get_adapter_manager
            
            adapter_manager = get_adapter_manager()
            chat_stream = getattr(self, "chat_stream", None)

            # 0. 读取配置并计算有效上限（默认3，硬上限10）
            configured_max = 3
            plugin_obj = getattr(self, "plugin", None)
            config_obj = getattr(plugin_obj, "config", None)
            plugin_config = getattr(config_obj, "plugin", None)
            if plugin_config is not None:
                try:
                    configured_max = int(getattr(plugin_config, "max_poke_count", 3) or 3)
                except (TypeError, ValueError):
                    configured_max = 3

            effective_max = min(max(configured_max, 1), 10)

            # LLM 可能给出越界值：统一截断到合法范围
            try:
                requested_count = int(poke_count)
            except (TypeError, ValueError):
                requested_count = 1
            actual_count = min(max(requested_count, 1), effective_max)

            # 0.1 读取连续执行间隔（毫秒）并归一化
            interval_min_ms = 100
            interval_max_ms = 200
            validate_target_before_poke = False
            validate_target_in_group = True
            validate_target_in_private = True
            if plugin_config is not None:
                try:
                    interval_min_ms = int(getattr(plugin_config, "poke_interval_min_ms", 100) or 0)
                except (TypeError, ValueError):
                    interval_min_ms = 100
                try:
                    interval_max_ms = int(getattr(plugin_config, "poke_interval_max_ms", 200) or 0)
                except (TypeError, ValueError):
                    interval_max_ms = 200
                validate_target_before_poke = bool(
                    getattr(plugin_config, "validate_target_before_poke", False)
                )
                validate_target_in_group = bool(
                    getattr(plugin_config, "validate_target_in_group", True)
                )
                validate_target_in_private = bool(
                    getattr(plugin_config, "validate_target_in_private", True)
                )

            interval_min_ms = max(0, interval_min_ms)
            interval_max_ms = max(0, interval_max_ms)
            if interval_min_ms > interval_max_ms:
                interval_min_ms, interval_max_ms = interval_max_ms, interval_min_ms

            # 0.2 LLM 指向性目标：显式目标优先
            effective_user_id = str(target_user_id).strip() if target_user_id else str(user_id).strip()
            if not effective_user_id:
                return False, "目标用户ID为空，操作取消"

            # group_id 只接受数字ID，拒绝群名等非数字输入
            raw_group_id = target_group_id if target_group_id is not None else group_id
            effective_group_id = self._normalize_numeric_id(raw_group_id)
            if raw_group_id is not None and not effective_group_id:
                logger.warning(f"收到无效 group_id（非数字），将尝试从上下文回退解析: {raw_group_id}")
            
            # 1. 尝试从上下文中获取 group_id
            if not effective_group_id and chat_stream:
                effective_group_id = await self._resolve_group_id_from_stream(chat_stream)
                            
            if effective_group_id:
                logger.debug(
                    f"确定目标为群聊 poke, group_id={effective_group_id}, user_id={effective_user_id}"
                )
                command_name = "group_poke"
                command_data = {
                    "group_id": effective_group_id,
                    "user_id": effective_user_id
                }
            else:
                # 没有 group_id，判断是否应该降级为私聊
                # 再次确认当前 Stream 类型，防止群聊误触私聊
                is_group_env = False
                if chat_stream:
                    c_type = getattr(chat_stream, "chat_type", None)
                    c_type_str = str(c_type) if c_type else ""
                    if "group" in c_type_str.lower():
                        is_group_env = True
                
                if is_group_env:
                    logger.warning(
                        f"当前处于群聊环境但缺失 group_id，放弃发送 poke 以防误触私聊。"
                        f"user_id={effective_user_id}"
                    )
                    return False, "群聊环境缺失群号，操作取消"
                
                logger.debug(f"确定目标为私聊/好友 poke, user_id={effective_user_id}")
                command_name = "friend_poke"
                command_data = {
                    "user_id": effective_user_id
                }

            # 2. 可选目标校验（默认关闭）
            if validate_target_before_poke:
                should_validate = (
                    bool(effective_group_id) and validate_target_in_group
                ) or (
                    (not bool(effective_group_id)) and validate_target_in_private
                )

                if should_validate and effective_group_id:
                    verify_result = await adapter_manager.send_adapter_command(
                        adapter_sign="napcat_adapter:adapter:napcat_adapter",
                        command_name="get_group_member_info",
                        command_data={
                            "group_id": effective_group_id,
                            "user_id": effective_user_id,
                            "no_cache": True,
                        },
                        timeout=10.0,
                    )
                elif should_validate:
                    verify_result = await adapter_manager.send_adapter_command(
                        adapter_sign="napcat_adapter:adapter:napcat_adapter",
                        command_name="get_stranger_info",
                        command_data={"user_id": effective_user_id},
                        timeout=10.0,
                    )
                else:
                    verify_result = {"status": "ok"}

                if verify_result.get("status") != "ok":
                    error_msg = verify_result.get("message", "未知错误")
                    logger.warning(
                        f"目标校验失败，取消发送戳一戳: user_id={effective_user_id}, error={error_msg}"
                    )
                    return False, f"目标校验失败，操作取消: {error_msg}"

            # 发送戳一戳命令到 napcat 适配器（支持连续次数）
            for i in range(actual_count):
                result = await adapter_manager.send_adapter_command(
                    adapter_sign="napcat_adapter:adapter:napcat_adapter",
                    command_name=command_name,
                    command_data=command_data,
                    timeout=10.0
                )
                if result.get("status") != "ok":
                    error_msg = result.get("message", "未知错误")
                    logger.error(
                        f"发送戳一戳失败: user_id={effective_user_id}, 第{i + 1}/{actual_count}次, 错误: {error_msg}"
                    )
                    return False, f"发送戳一戳失败（第{i + 1}/{actual_count}次）: {error_msg}"

                # 多次执行时增加间隔，降低风控风险
                if i < actual_count - 1:
                    interval_ms = random.randint(interval_min_ms, interval_max_ms)
                    await asyncio.sleep(interval_ms / 1000.0)

            # 全部成功
            if effective_group_id:
                logger.info(
                    f"已在群 {effective_group_id} 中连续戳了用户 {effective_user_id} {actual_count} 次"
                )
                return (
                    True,
                    f"已在群 {effective_group_id} 中连续戳了用户 {effective_user_id} {actual_count} 次"
                )

            logger.info(f"已连续戳了用户 {effective_user_id} {actual_count} 次")
            return True, f"已连续戳了用户 {effective_user_id} {actual_count} 次"
                
        except Exception as e:
            logger.error(f"发送戳一戳时发生异常: {e}", exc_info=True)
            return False, f"发送戳一戳时发生异常: {str(e)}"