"""发送表情回复动作"""

from __future__ import annotations

from src.core.components.base import BaseAction
from src.app.plugin_system.api.log_api import get_logger
from src.core.managers.adapter_manager import get_adapter_manager

logger = get_logger("notice_injector")

# QQ 常用表情 ID 参考映射（仅用于 action_description 展示和校验提示）
# 完整列表参见: https://bot.q.qq.com/wiki/develop/api/openapi/emoji/emoji_type.html
_COMMON_EMOJI_MAP: dict[str, str] = {
    "4": "调皮",
    "5": "流泪",
    "6": "害羞",
    "8": "睡",
    "9": "大哭",
    "10": "尴尬",
    "12": "调皮",
    "14": "微笑",
    "16": "酷",
    "21": "可爱",
    "22": "傲慢",
    "23": "饥饿",
    "24": "困",
    "25": "惊恐",
    "26": "流汗",
    "27": "憨笑",
    "28": "悠闲",
    "29": "奋斗",
    "30": "咒骂",
    "31": "疑问",
    "32": "嘘",
    "33": "晕",
    "34": "折磨",
    "35": "衰",
    "36": "骷髅",
    "37": "敲打",
    "38": "再见",
    "39": "擦汗",
    "40": "抠鼻",
    "41": "鼓掌",
    "42": "糗大了",
    "43": "坏笑",
    "44": "左哼哼",
    "45": "右哼哼",
    "46": "哈欠",
    "47": "鄙视",
    "48": "委屈",
    "49": "快哭了",
    "50": "阴险",
    "51": "亲亲",
    "53": "吓",
    "54": "可怜",
    "66": "机器人",
    "74": "月亮",
    "75": "太阳",
    "76": "礼物",
    "78": "强",
    "79": "弱",
    "80": "握手",
    "81": "胜利",
    "83": "抱拳",
    "84": "勾引",
    "85": "拳头",
    "86": "差劲",
    "87": "爱你",
    "88": "NO",
    "89": "OK",
    "96": "红鼻子",
    "97": "流泪",
    "98": "睡觉",
    "100": "示爱",
    "101": "害羞",
    "102": "坏笑",
    "103": "左太极",
    "104": "右太极",
    "106": "双喜",
    "107": "鞭炮",
    "108": "灯笼",
    "112": "饭",
    "113": "茶",
    "114": "泪",
    "116": "礼物",
    "117": "鸡",
    "118": "蜡烛",
    "120": "白眼",
    "122": "喷血",
    "123": "捂脸",
    "124": "奸笑",
    "125": "铃铛",
    "126": "点赞",
    "127": "踩",
    "128": "瓢虫",
    "129": "抱抱",
    "130": "拍桌",
    "131": "拍手",
    "132": "恭喜",
    "133": "干杯",
    "134": "嘿哈",
    "135": "捂脸",
    "136": "机智",
    "137": "皱眉",
    "138": "耶",
    "139": "吃瓜",
    "140": "加油",
    "141": "汗",
    "142": "天啊",
    "143": "Emm",
    "144": "社会社会",
    "145": "旺柴",
    "146": "好的",
    "147": "打脸",
    "148": "哇",
    "149": "翻白眼",
    "150": "666",
    "151": "让我看看",
    "152": "叹气",
    "153": "苦涩",
    "154": "裂开",
    "155": "嘿嘿",
    "156": "我酸了",
    "157": "汪汪",
    "158": "汗颜",
    "160": "无眼看",
    "161": "敬礼",
    "162": "狗头",
    "163": "加油",
    "164": "笑脸",
    "166": "开心",
    "167": "摸鱼",
    "168": "比心",
    "169": "糊脸",
    "170": "拍头",
    "171": "扯一扯",
    "172": "舔一舔",
    "173": "蹭一蹭",
    "174": "拽炸天",
    "175": "顶",
    "176": "大笑",
    "177": "不开心",
    "178": "冷漠",
    "179": "呃呃",
    "180": "好主意",
    "181": "急急急",
    "182": "眨眼",
    "183": "嗯嗯",
    "184": "无语",
    "185": "快看",
    "186": "惊喜",
    "187": "原来如此",
    "188": "酱紫",
    "189": "拜托了",
    "190": "对对对",
    "191": "不对不对",
    "192": "行吧",
    "193": "戳一戳",
    "194": "谢谢",
    "195": "吓到了",
}

# 有效 emoji_id 范围（QQ 表情 ID 均为正整数）
_EMOJI_ID_MIN = 1
_EMOJI_ID_MAX = 300  # 保守上限，实际可能更高

# 默认适配器签名（可通过配置覆盖）
_DEFAULT_ADAPTER_SIGN = "napcat_adapter:adapter:napcat_adapter"

# 默认允许的“稳健”表情集合（语义更明确，减少乱贴）
_DEFAULT_ALLOWED_EMOJI_IDS: tuple[str, ...] = (
    "126",  # 点赞
    "129",  # 抱抱
    "131",  # 拍手
    "132",  # 恭喜
    "133",  # 干杯
    "138",  # 耶
    "140",  # 加油
    "146",  # 好的
    "148",  # 哇
    "166",  # 开心
    "176",  # 大笑
    "182",  # 眨眼
    "183",  # 嗯嗯
    "184",  # 无语
    "194",  # 谢谢
)

# 语义关键词到 emoji_id 的回复意图映射（强调“如何回应”，而非复读情绪）
_SEMANTIC_EMOJI_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("194", ("谢谢", "谢啦", "感谢", "辛苦", "麻烦你", "多谢")),
    ("132", ("恭喜", "祝贺", "牛", "厉害", "太强", "真棒", "优秀")),
    ("140", ("加油", "冲", "稳住", "别慌", "顶住", "继续")),
    ("129", ("抱抱", "安慰", "难过", "委屈", "别哭", "心疼", "伤心", "悲伤", "难受", "emo")),
    ("146", ("收到", "好的", "ok", "没问题", "明白", "安排")),
    ("131", ("支持", "同意", "靠谱", "赞同", "说得好")),
    ("176", ("哈哈", "笑死", "乐", "有趣", "好玩", "逗")),
)

# 参考 emoji_sender 的标签化语义输入：用于“意图先验”
_EMOTION_TAG_PRESET: tuple[str, ...] = (
    "开心",
    "难过",
    "生气",
    "惊讶",
    "害羞",
    "尴尬",
    "无语",
    "委屈",
    "嘲讽",
    "疑惑",
    "赞同",
    "否定",
    "兴奋",
    "疲惫",
    "害怕",
    "厌恶",
    "紧张",
    "冷漠",
)

_DEFAULT_EMOTION_TAG_TO_EMOJI: dict[str, str] = {
    "开心": "166",
    "难过": "129",
    "生气": "184",
    "惊讶": "148",
    "害羞": "182",
    "尴尬": "183",
    "无语": "184",
    "委屈": "129",
    "嘲讽": "176",
    "疑惑": "182",
    "赞同": "131",
    "否定": "184",
    "兴奋": "138",
    "疲惫": "183",
    "害怕": "129",
    "厌恶": "184",
    "紧张": "140",
    "冷漠": "184",
}

_DEFAULT_EMOTION_TAG_PRIORITY: tuple[str, ...] = (
    "委屈",
    "难过",
    "害怕",
    "生气",
    "赞同",
    "否定",
    "疑惑",
    "惊讶",
    "开心",
    "兴奋",
    "尴尬",
    "无语",
    "疲惫",
    "紧张",
    "厌恶",
    "冷漠",
    "嘲讽",
    "害羞",
)


def _normalize_emoji_id(emoji_id: object) -> str | None:
    """将输入归一化为合法的表情 ID 字符串。

    Returns:
        合法的表情 ID 字符串，若无效则返回 None。
    """
    if emoji_id is None:
        return None
    text = str(emoji_id).strip()
    if not text.isdigit():
        return None
    val = int(text)
    if val < _EMOJI_ID_MIN or val > _EMOJI_ID_MAX:
        return None
    return text


def _normalize_allowed_emoji_ids(raw_ids: object) -> set[str]:
    """将配置中的允许列表归一化为合法的 emoji_id 集合。"""
    if not isinstance(raw_ids, list):
        return set(_DEFAULT_ALLOWED_EMOJI_IDS)

    normalized = {
        valid_id
        for item in raw_ids
        if (valid_id := _normalize_emoji_id(item)) is not None
    }
    if not normalized:
        return set(_DEFAULT_ALLOWED_EMOJI_IDS)
    return normalized


def _pick_emoji_by_semantic_hint(
    semantic_hint: str,
    semantic_rules: tuple[tuple[str, tuple[str, ...]], ...],
    default_emoji_id: str,
) -> str:
    """基于语义提示选择表情；未命中时回退默认值。"""
    text = semantic_hint.strip().lower()
    if not text:
        return default_emoji_id

    for emoji_id, keywords in semantic_rules:
        if any(keyword in text for keyword in keywords):
            return emoji_id

    return default_emoji_id


def _normalize_custom_semantic_rules(
    raw_rules: object,
) -> dict[str, tuple[str, ...]]:
    """归一化自定义语义规则。"""
    if not isinstance(raw_rules, dict):
        return {}

    normalized: dict[str, tuple[str, ...]] = {}
    for emoji_id_raw, keywords_raw in raw_rules.items():
        emoji_id = _normalize_emoji_id(emoji_id_raw)
        if emoji_id is None:
            continue
        if not isinstance(keywords_raw, list):
            continue

        keywords = tuple(
            keyword.strip().lower()
            for keyword in keywords_raw
            if isinstance(keyword, str) and keyword.strip()
        )
        if keywords:
            normalized[emoji_id] = keywords

    return normalized


def _build_semantic_rules(
    allowed_emoji_ids: set[str],
    custom_rules: object,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """构建最终语义规则：自定义优先，内置补齐。"""
    merged: dict[str, tuple[str, ...]] = {}

    normalized_custom = _normalize_custom_semantic_rules(custom_rules)
    for emoji_id, keywords in normalized_custom.items():
        if emoji_id in allowed_emoji_ids:
            merged[emoji_id] = keywords

    for emoji_id, builtin_keywords in _SEMANTIC_EMOJI_RULES:
        if emoji_id not in allowed_emoji_ids:
            continue
        if emoji_id in merged:
            merged[emoji_id] = tuple(dict.fromkeys((*merged[emoji_id], *builtin_keywords)))
        else:
            merged[emoji_id] = builtin_keywords

    return tuple((emoji_id, keywords) for emoji_id, keywords in merged.items())


def _normalize_emotion_tags(raw_tags: object) -> list[str]:
    """归一化 emotion_tags，仅保留预设标签。"""
    if not isinstance(raw_tags, list):
        return []
    normalized: list[str] = []
    for raw in raw_tags:
        if not isinstance(raw, str):
            continue
        tag = raw.strip()
        if tag in _EMOTION_TAG_PRESET and tag not in normalized:
            normalized.append(tag)
    return normalized


def _normalize_emotion_tag_to_emoji_map(raw_map: object) -> dict[str, str]:
    """归一化 emotion_tag -> emoji_id 映射。"""
    if not isinstance(raw_map, dict):
        return {}

    result: dict[str, str] = {}
    for tag_raw, emoji_id_raw in raw_map.items():
        if not isinstance(tag_raw, str):
            continue
        tag = tag_raw.strip()
        if tag not in _EMOTION_TAG_PRESET:
            continue
        emoji_id = _normalize_emoji_id(emoji_id_raw)
        if emoji_id is None:
            continue
        result[tag] = emoji_id
    return result


def _normalize_emotion_tag_priority(raw_priority: object) -> list[str]:
    """归一化 emotion tag 优先级列表。"""
    if not isinstance(raw_priority, list):
        return []

    normalized: list[str] = []
    for item in raw_priority:
        if not isinstance(item, str):
            continue
        tag = item.strip()
        if tag and tag in _EMOTION_TAG_PRESET and tag not in normalized:
            normalized.append(tag)
    return normalized


def _sort_emotion_tags_by_priority(
    emotion_tags: list[str],
    priority_tags: list[str],
) -> list[str]:
    """根据优先级对标签排序，未声明优先级的保持原始相对顺序。"""
    priority_index = {tag: idx for idx, tag in enumerate(priority_tags)}
    fallback_base = len(priority_index)

    return sorted(
        emotion_tags,
        key=lambda item: (priority_index.get(item, fallback_base), emotion_tags.index(item)),
    )


def _pick_emoji_by_emotion_tags(
    emotion_tags: list[str],
    allowed_emoji_ids: set[str],
    emotion_tag_to_emoji_map: dict[str, str],
    emotion_tag_priority: list[str],
) -> str | None:
    """按 emotion_tags 先验选择 emoji_id。"""
    ordered_tags = _sort_emotion_tags_by_priority(emotion_tags, emotion_tag_priority)

    for tag in ordered_tags:
        mapped = emotion_tag_to_emoji_map.get(tag)
        if mapped and mapped in allowed_emoji_ids:
            return mapped
    return None


class SendEmojiLikeAction(BaseAction):
    """发送表情回复动作给消息"""

    action_name = "send_emoji_like"
    action_description = (
        "给指定消息发送表情回复（QQ 表情点赞/回应）。"
        "参数说明："
        "- message_id: 要回复的消息ID（必填，字符串格式的数字）。"
        "- emoji_id: 表情ID，可选；该参数仅为兼容保留，执行时会忽略。"
        "  可传 'auto' 触发语义自动选择。"
        "- semantic_hint: 语义提示文本（必填）；用于匹配“回复意图”。"
        "- emotion_tags: 情感标签列表（可选）。若提供，会先按标签做意图先验选择。"
        "常用表情ID对照："
        "126=点赞, 127=踩, 129=抱抱, 131=拍手, 132=恭喜, 133=干杯, "
        "138=耶, 140=加油, 146=好的, 148=哇, 166=开心, 176=大笑, "
        "182=眨眼, 183=嗯嗯, 184=无语, 194=谢谢。"
        "请根据语境选择“回应型”表情，不要把对方情绪原样复读。"
    )

    async def execute(
        self,
        message_id: str,
        emoji_id: str = "126",
        semantic_hint: str = "",
        emotion_tags: list[str] | None = None,
    ) -> tuple[bool, str]:
        """执行发送表情回复动作

        Args:
            message_id: 要回复的消息ID
            emoji_id: 表情ID（兼容参数，执行时会忽略）。
            semantic_hint: 语义提示文本（必填），用于自动匹配回复意图。
            emotion_tags: 情感标签列表（可选，参考 emoji_sender 标签集合）。
        """
        # 检查是否为群聊环境
        chat_type = getattr(self.chat_stream, "chat_type", "")
        if "group" not in str(chat_type).lower():
            logger.warning(f"表情回复仅支持群聊，当前环境: {chat_type}")
            return False, "表情回复仅支持群聊环境"

        # 校验 message_id
        if not message_id or not str(message_id).strip():
            logger.warning("发送表情回复失败：message_id 为空")
            return False, "发送表情回复失败：message_id 不能为空"

        # 强制语义模式：必须提供 semantic_hint
        semantic_text = str(semantic_hint or "").strip()
        if not semantic_text:
            logger.warning("发送表情回复失败：semantic_hint 为空（语义结合为必选）")
            return False, "发送表情回复失败：semantic_hint 不能为空（语义结合为必选）"

        # 从配置读取功能开关与默认策略
        try:
            plugin_obj = getattr(self, "plugin", None)
            config_obj = getattr(plugin_obj, "config", None)
            plugin_config = getattr(config_obj, "plugin", None)
            
            if plugin_config is None:
                raise AttributeError("配置对象未加载")
                
            config_default = getattr(plugin_config, "default_emoji_id", "126") or "126"
            enable_send_emoji_like = bool(
                getattr(plugin_config, "enable_send_emoji_like", True)
            )
            strict_mode = bool(getattr(plugin_config, "emoji_like_strict_mode", True))
            allowed_emoji_ids = _normalize_allowed_emoji_ids(
                getattr(plugin_config, "emoji_like_allowed_ids", list(_DEFAULT_ALLOWED_EMOJI_IDS))
            )
            custom_semantic_rules = getattr(plugin_config, "emoji_like_custom_rules", {})
            custom_emotion_tag_map = getattr(plugin_config, "emoji_like_emotion_tag_map", {})
            custom_emotion_tag_priority = getattr(
                plugin_config,
                "emoji_like_emotion_tag_priority",
                list(_DEFAULT_EMOTION_TAG_PRIORITY),
            )
        except (AttributeError, TypeError) as e:
            logger.warning(f"读取配置失败，使用默认值: {e}")
            config_default = "126"
            enable_send_emoji_like = True
            strict_mode = True
            allowed_emoji_ids = set(_DEFAULT_ALLOWED_EMOJI_IDS)
            custom_semantic_rules = {}
            custom_emotion_tag_map = {}
            custom_emotion_tag_priority = list(_DEFAULT_EMOTION_TAG_PRIORITY)

        if not enable_send_emoji_like:
            logger.info("已通过配置关闭 send_emoji_like 动作，跳过执行")
            return False, "send_emoji_like 已关闭（enable_send_emoji_like=false）"

        normalized_default = _normalize_emoji_id(config_default) or "126"

        # 若默认值不在白名单，兜底到白名单中的点赞（126）或排序后的第一个可用值
        if normalized_default not in allowed_emoji_ids:
            normalized_default = "126" if "126" in allowed_emoji_ids else sorted(allowed_emoji_ids)[0]

        semantic_rules = _build_semantic_rules(
            allowed_emoji_ids=allowed_emoji_ids,
            custom_rules=custom_semantic_rules,
        )
        normalized_emotion_tags = _normalize_emotion_tags(emotion_tags)
        emotion_tag_map = {
            **_DEFAULT_EMOTION_TAG_TO_EMOJI,
            **_normalize_emotion_tag_to_emoji_map(custom_emotion_tag_map),
        }
        emotion_tag_priority = _normalize_emotion_tag_priority(custom_emotion_tag_priority)
        if not emotion_tag_priority:
            emotion_tag_priority = list(_DEFAULT_EMOTION_TAG_PRIORITY)

        # 强制语义选取：忽略显式 emoji_id，统一按 semantic_hint 决策
        if str(emoji_id or "").strip():
            logger.debug("send_emoji_like 收到显式 emoji_id，但当前为强制语义模式，将忽略该参数")

        normalized_emoji_id = _pick_emoji_by_emotion_tags(
            emotion_tags=normalized_emotion_tags,
            allowed_emoji_ids=allowed_emoji_ids,
            emotion_tag_to_emoji_map=emotion_tag_map,
            emotion_tag_priority=emotion_tag_priority,
        )
        if normalized_emoji_id is None:
            normalized_emoji_id = _pick_emoji_by_semantic_hint(
                semantic_hint=semantic_text,
                semantic_rules=semantic_rules,
                default_emoji_id=normalized_default,
            )

        if strict_mode and normalized_emoji_id not in allowed_emoji_ids:
            logger.warning(
                f"emoji_id={normalized_emoji_id} 不在允许列表中，已回退到默认值 {normalized_default}"
            )
            normalized_emoji_id = normalized_default

        emoji_name = _COMMON_EMOJI_MAP.get(normalized_emoji_id, f"ID:{normalized_emoji_id}")

        # 构建表情回复参数
        command_data = {
            "message_id": str(message_id).strip(),
            "emoji_id": normalized_emoji_id,
        }

        adapter_sign = _DEFAULT_ADAPTER_SIGN

        try:
            # 获取适配器管理器
            adapter_manager = get_adapter_manager()
            
            # 发送表情回复命令到 napcat 适配器
            # 发送 set_msg_emoji_like 命令 (OneBot 11 标准)
            result = await adapter_manager.send_adapter_command(
                adapter_sign=adapter_sign,
                command_name="set_msg_emoji_like",
                command_data=command_data,
                timeout=10.0
            )

            if result.get("status") == "ok":
                logger.info(
                    f"已对消息 {message_id} 发送表情回复 [{emoji_name}]（ID: {normalized_emoji_id}）"
                )
                return (
                    True,
                    f"已对消息 {message_id} 发送表情回复 [{emoji_name}]（ID: {normalized_emoji_id}）",
                )
            else:
                error_msg = result.get("message", "未知错误")
                logger.error(
                    f"发送表情回复失败: 消息ID={message_id}, "
                    f"表情=[{emoji_name}](ID:{normalized_emoji_id}), 错误: {error_msg}"
                )
                return False, f"发送表情回复失败: {error_msg}"

        except Exception as e:
            logger.error(
                f"发送表情回复时发生异常: 消息ID={message_id}, "
                f"表情=[{emoji_name}](ID:{normalized_emoji_id}), 异常: {e}",
                exc_info=True,
            )
            return False, f"发送表情回复时发生异常: {str(e)}"