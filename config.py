"""Notice Injector 插件配置"""

from __future__ import annotations

from typing import ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class NoticeInjectorConfig(BaseConfig):
    """Notice Injector 插件配置类"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "Notice Injector 配置"

    @config_section("plugin")
    class PluginSection(SectionBase):
        """插件基础配置"""

        enabled: bool = Field(default=True, description="插件总开关。false 时本插件所有能力均停用。")
        enable_poke: bool = Field(default=True, description="是否处理戳一戳相关通知（notice_type=poke）。")
        enable_emoji_like: bool = Field(default=True, description="是否处理表情点赞/表情回复通知。")
        enable_ban: bool = Field(default=True, description="是否处理群禁言/解除禁言通知。")
        enable_group_upload: bool = Field(default=True, description="是否处理群文件上传通知。")
        enable_debug: bool = Field(default=False, description="是否输出调试日志；建议仅在排障时开启。")
        ignore_self_notice: bool = Field(default=True, description="是否忽略机器人自身触发的通知，避免自循环。")
        trigger_chat: bool = Field(default=False, description="是否将通知注入对话流触发聊天。false 可减少 token 与上下文污染。")
        # 表情回复配置
        enable_send_emoji_like: bool = Field(default=True, description="是否启用主动动作 send_emoji_like。关闭后即使 LLM 调用该 action 也会被拒绝执行。")
        default_emoji_id: str = Field(default="126", description="发送表情回复时的默认表情ID（未指定时使用）。126=点赞，具体ID可参考 QQ 表情列表。")
        emoji_like_allowed_ids: list[str] = Field(
            default_factory=lambda: [
                "126", "129", "131", "132", "133", "138", "140", "146", "148", "166", "176", "182", "183", "184", "194"
            ],
            description="send_emoji_like 允许使用的表情ID白名单。开启严格模式后，超出该列表会自动回退默认值。",
        )
        emoji_like_strict_mode: bool = Field(default=True, description="是否启用 send_emoji_like 严格模式。开启后不在白名单内的 emoji_id 会自动回退到默认值。")
        emoji_like_custom_rules: dict[str, list[str]] = Field(
            default_factory=dict,
            description="自定义语义规则映射，格式为 {emoji_id: [关键词, ...]}。用于补充或覆盖内置回复意图匹配词。",
        )
        emoji_like_emotion_tag_map: dict[str, str] = Field(
            default_factory=dict,
            description="情感标签到表情ID的自定义映射，格式为 {标签: emoji_id}。用于在 emotion_tags 存在时优先决策。",
        )
        emoji_like_emotion_tag_priority: list[str] = Field(
            default_factory=lambda: [
                "委屈", "难过", "害怕", "生气", "赞同", "否定", "疑惑", "惊讶", "开心", "兴奋", "尴尬", "无语", "疲惫", "紧张", "厌恶", "冷漠", "嘲讽", "害羞"
            ],
            description="emotion_tags 冲突时的标签优先级（从高到低）。纯本地规则，不增加模型调用消耗。",
        )
        # 单戳连击限制
        max_poke_count: int = Field(default=3, description="单次动作最大连戳次数。建议 1~3；运行时会被强制限制在 [1, 10]。")
        poke_interval_min_ms: int = Field(default=100, description="连戳最小间隔（毫秒）。与 max 组成随机区间，降低风控概率。")
        poke_interval_max_ms: int = Field(default=200, description="连戳最大间隔（毫秒）。若小于 min，运行时会自动交换两者。")
        validate_target_before_poke: bool = Field(default=False, description="发送戳一戳前是否先做目标存在性校验（程序内 API，不消耗 LLM token）。")
        validate_target_in_group: bool = Field(default=True, description="群聊场景是否执行目标校验（建议开启，避免无效成员 ID）。")
        validate_target_in_private: bool = Field(default=False, description="私聊场景是否执行目标校验。默认 false；通常不推荐设为 true（会增加一次额外 API 调用）。")
        # AOE 戳一戳配置
        aoe_poke_max_targets: int = Field(default=5, description="AOE 戳一戳（send_poke_multiple）的最大目标人数上限。运行时会被限制在 [1, 20]。")
        validate_target_before_aoe_poke: bool = Field(default=True, description="AOE 戳一戳前是否校验目标用户存在。")

    plugin: PluginSection = Field(default_factory=PluginSection)