"""发送表情回复动作"""

from __future__ import annotations

from src.core.components.base import BaseAction
from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.api import adapter_api

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


class SendEmojiLikeAction(BaseAction):
    """发送表情回复动作给消息"""

    action_name = "send_emoji_like"
    action_description = (
        "给指定消息发送表情回复（QQ 表情点赞/回应）。"
        "参数说明："
        "- message_id: 要回复的消息ID（必填，字符串格式的数字）。"
        "- emoji_id: 表情ID，必须是正整数字符串，默认 '126'（点赞）。"
        "常用表情ID对照："
        "126=点赞, 127=踩, 129=抱抱, 131=拍手, 132=恭喜, 133=干杯, "
        "138=耶, 140=加油, 146=好的, 148=哇, 166=开心, 176=大笑, "
        "182=眨眼, 183=嗯嗯, 184=无语, 194=谢谢。"
        "请根据语境选择合适的表情，不要随意猜测表情ID。"
    )

    def _get_adapter_sign(self) -> str:
        """获取适配器签名，优先从插件配置读取，回退到默认值。"""
        try:
            plugin_obj = getattr(self, "plugin", None)
            config_obj = getattr(plugin_obj, "config", None)
            plugin_config = getattr(config_obj, "plugin", None)
            sign = getattr(plugin_config, "adapter_sign", None)
            if sign and str(sign).strip():
                return str(sign).strip()
        except Exception:
            pass
        return _DEFAULT_ADAPTER_SIGN

    async def execute(self, message_id: str, emoji_id: str = "126") -> tuple[bool, str]:
        """执行发送表情回复动作

        Args:
            message_id: 要回复的消息ID
            emoji_id: 表情ID，默认是点赞表情(126)。必须为正整数字符串。
        """
        # 校验 message_id
        if not message_id or not str(message_id).strip():
            logger.warning("发送表情回复失败：message_id 为空")
            return False, "发送表情回复失败：message_id 不能为空"

        # 从配置读取默认 emoji_id（优先级：参数 > 配置默认值 > 硬编码 126）
        try:
            plugin_obj = getattr(self, "plugin", None)
            config_obj = getattr(plugin_obj, "config", None)
            plugin_config = getattr(config_obj, "plugin", None)
            config_default = getattr(plugin_config, "default_emoji_id", "126") or "126"
        except Exception:
            config_default = "126"

        # 校验并归一化 emoji_id
        normalized_emoji_id = _normalize_emoji_id(emoji_id)
        if normalized_emoji_id is None:
            # 尝试使用配置中的默认值
            fallback = _normalize_emoji_id(config_default) or "126"
            logger.warning(
                f"收到无效 emoji_id='{emoji_id}'，已回退到配置默认值 '{fallback}'"
                f"（{_COMMON_EMOJI_MAP.get(fallback, 'ID:' + fallback)}）"
            )
            normalized_emoji_id = fallback

        emoji_name = _COMMON_EMOJI_MAP.get(normalized_emoji_id, f"ID:{normalized_emoji_id}")

        # 构建表情回复参数
        command_data = {
            "message_id": str(message_id).strip(),
            "emoji_id": normalized_emoji_id,
        }

        adapter_sign = self._get_adapter_sign()

        try:
            # 发送表情回复命令到 napcat 适配器
            # 发送 set_msg_emoji_like 命令 (OneBot 11 标准)
            result = await adapter_api.send_adapter_command(
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