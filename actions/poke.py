"""发送戳一戳动作"""

from __future__ import annotations

import asyncio
import random

from src.core.components.base import BaseAction
from src.app.plugin_system.api.log_api import get_logger

logger = get_logger("notice_injector")

_DEFAULT_ADAPTER_SIGN = "napcat_adapter:adapter:napcat_adapter"


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

            # 0.1 读取连续执行间隔（毫秒）与目标校验开关并归一化
            interval_min_ms = 100
            interval_max_ms = 200
            validate_target_before_poke = False
            validate_target_in_group = True
            validate_target_in_private = False
            adapter_sign = _DEFAULT_ADAPTER_SIGN
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
                    getattr(plugin_config, "validate_target_in_private", False)
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
                        adapter_sign=adapter_sign,
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
                        adapter_sign=adapter_sign,
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
                    adapter_sign=adapter_sign,
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


class SendPokeMultipleAction(BaseAction):
    """AOE 戳一戳动作给多个用户"""

    action_name = "send_poke_multiple"
    action_description = (
        "戳多个参与互动的用户（仅群聊）。"
        "与 send_poke 为互斥关系，请根据场景选择："
        "- send_poke：单用户连戳多次"
        "- send_poke_multiple：多用户各戳一次"
        "参数说明："
        "- user_ids: 目标用户ID列表（必填）。建议从上下文最近有互动的用户中选择。"
        "- group_id: 群号（必填），必须是数字ID，不能传群名。"
        "- max_targets: 最大目标人数上限，默认5，最大10。"
        "- validate_targets: 是否校验目标用户存在，默认true。"
        "注意：每人只戳一次，不支持连戳。"
    )

    async def execute(
        self,
        user_ids: list[str],
        group_id: str | None = None,
        max_targets: int | None = None,
        validate_targets: bool | None = None,
    ) -> tuple[bool, str]:
        """执行 AOE 戳一戳动作

        Args:
            user_ids: 目标用户ID列表
            group_id: 群号（可选，如果 LLM 未提供会从上下文回退解析）
            max_targets: 最大目标人数上限（默认从配置读取）
            validate_targets: 是否校验目标用户存在（默认从配置读取）
        """
        try:
            # 从配置读取默认值
            plugin_obj = getattr(self, "plugin", None)
            config_obj = getattr(plugin_obj, "config", None)
            plugin_config = getattr(config_obj, "plugin", None)

            # max_targets 默认值
            if max_targets is None:
                config_max = 5
                if plugin_config is not None:
                    try:
                        config_max = int(getattr(plugin_config, "aoe_poke_max_targets", 5) or 5)
                    except (TypeError, ValueError):
                        config_max = 5
                max_targets = min(max(config_max, 1), 10)  # 硬上限 10

            # validate_targets 默认值
            if validate_targets is None:
                if plugin_config is not None:
                    validate_targets = bool(getattr(plugin_config, "validate_target_before_aoe_poke", True))
                else:
                    validate_targets = True

            # 参数预处理
            if not user_ids:
                return False, "目标用户列表为空"

            # 限制人数
            effective_max = min(max(max_targets, 1), 10)
            if len(user_ids) > effective_max:
                logger.warning(f"AOE戳一戳目标人数 {len(user_ids)} 超过上限 {effective_max}，已截断")
                user_ids = user_ids[:effective_max]

            # 归一化 group_id（优先使用传入值）
            normalized_group_id = SendPokeAction._normalize_numeric_id(group_id)
            if not normalized_group_id and group_id is not None:
                logger.warning(f"收到无效 group_id（非数字），将尝试从上下文回退解析: {group_id}")

            # 从上下文中回退解析 group_id（内联逻辑，避免跨类静态方法调用）
            if not normalized_group_id:
                chat_stream = getattr(self, "chat_stream", None)
                if chat_stream:
                    # 1) 优先从当前消息 extra 中获取
                    context = getattr(chat_stream, "context", None)
                    if context:
                        current_message = getattr(context, "current_message", None)
                        if current_message:
                            extra = getattr(current_message, "extra", {})
                            normalized_group_id = SendPokeAction._normalize_numeric_id(extra.get("group_id"))
                            if normalized_group_id:
                                logger.debug(f"从消息上下文获取到 group_id: {normalized_group_id}")

                    # 2) 回退：按 stream_id 查询 chat_streams 表中的 group_id
                    if not normalized_group_id:
                        stream_id = getattr(chat_stream, "stream_id", "")
                        if stream_id:
                            try:
                                from src.core.models.sql_alchemy import ChatStreams
                                from src.kernel.db import QueryBuilder

                                record = await QueryBuilder(ChatStreams).filter(stream_id=stream_id).first()
                                if record:
                                    normalized_group_id = SendPokeAction._normalize_numeric_id(getattr(record, "group_id", None))
                                    if normalized_group_id:
                                        logger.debug(f"从数据库查询到 group_id: {normalized_group_id}")
                            except Exception as e:
                                logger.debug(f"通过 stream_id 回查 group_id 失败: {e}")

            if not normalized_group_id:
                return False, "无法获取群号，group_id 为空且无法从上下文解析"

            # 读取动作参数配置
            adapter_sign = _DEFAULT_ADAPTER_SIGN
            interval_min_ms = 100
            interval_max_ms = 200
            if plugin_config is not None:
                try:
                    interval_min_ms = int(getattr(plugin_config, "poke_interval_min_ms", 100) or 0)
                    interval_max_ms = int(getattr(plugin_config, "poke_interval_max_ms", 200) or 0)
                except (TypeError, ValueError):
                    pass

            interval_min_ms = max(0, interval_min_ms)
            interval_max_ms = max(0, interval_max_ms)
            if interval_min_ms > interval_max_ms:
                interval_min_ms, interval_max_ms = interval_max_ms, interval_min_ms

            from src.core.managers.adapter_manager import get_adapter_manager
            adapter_manager = get_adapter_manager()

            # 校验目标用户（可选）
            valid_user_ids: list[str] = []
            invalid_users: list[tuple[str, str]] = []

            if validate_targets:
                for uid in user_ids:
                    normalized_uid = SendPokeAction._normalize_numeric_id(uid)
                    if not normalized_uid:
                        invalid_users.append((uid, "无效ID格式"))
                        continue

                    result = await adapter_manager.send_adapter_command(
                        adapter_sign=adapter_sign,
                        command_name="get_group_member_info",
                        command_data={
                            "group_id": normalized_group_id,
                            "user_id": normalized_uid,
                            "no_cache": True,
                        },
                        timeout=10.0,
                    )

                    if result.get("status") == "ok":
                        valid_user_ids.append(normalized_uid)
                    else:
                        error = result.get("message", "未知错误")
                        invalid_users.append((uid, error))

                if not valid_user_ids:
                    error_detail = "; ".join([f"{uid}({err})" for uid, err in invalid_users])
                    return False, f"所有目标用户校验失败: {error_detail}"
            else:
                valid_user_ids = [
                    uid for uid in user_ids
                    if SendPokeAction._normalize_numeric_id(uid)
                ]
                if not valid_user_ids:
                    return False, "目标用户列表中无有效ID"

            # 执行 AOE 戳一戳
            success_users: list[str] = []
            failed_users: list[tuple[str, str]] = []

            for i, uid in enumerate(valid_user_ids):
                result = await adapter_manager.send_adapter_command(
                    adapter_sign=adapter_sign,
                    command_name="group_poke",
                    command_data={
                        "group_id": normalized_group_id,
                        "user_id": uid,
                    },
                    timeout=10.0,
                )

                if result.get("status") == "ok":
                    success_users.append(uid)
                else:
                    error = result.get("message", "未知错误")
                    failed_users.append((uid, error))

                # 间隔延迟，降低风控
                if i < len(valid_user_ids) - 1:
                    interval_ms = random.randint(interval_min_ms, interval_max_ms)
                    await asyncio.sleep(interval_ms / 1000.0)

            # 汇总结果
            if success_users:
                success_msg = f"成功戳了 {len(success_users)} 人: {', '.join(success_users)}"
                if failed_users:
                    fail_msg = f"，失败 {len(failed_users)} 人: {', '.join([f'{u}({e})' for u, e in failed_users])}"
                    logger.info(f"AOE戳一戳结果: {success_msg}{fail_msg}")
                    return True, success_msg + fail_msg
                else:
                    if invalid_users:
                        success_msg += f"（另有 {len(invalid_users)} 人因校验失败跳过）"
                    logger.info(f"AOE戳一戳完成: {success_msg}")
                    return True, success_msg
            else:
                return False, f"AOE戳一戳全部失败: {', '.join([f'{u}({e})' for u, e in failed_users])}"

        except Exception as e:
            logger.error(f"AOE戳一戳时发生异常: {e}", exc_info=True)
            return False, f"AOE戳一戳时发生异常: {str(e)}"