# Notice Injector 通知处理器

> *把QQ的"小动作"，变成机器人的"懂你"。*

**QQ通知消息处理与主动交互插件** — Neo-MoFox 插件

---

## ✨ 不止是通知，更是连接

普通的通知系统是一道墙：机器人收到了，但不知道怎么回应。

Notice Injector 不一样。它会：

- 把"戳一戳"变成机器人能看懂的消息："用户A戳了戳你"
- 把"表情回复"变成对话的一部分："用户B给你的消息点了赞"
- 还能让机器人主动去戳一戳、点个赞，像真人一样互动

这不是简单的消息转发，这是**通知语义化**驱动的交互桥梁。

### 它能做什么

#### 接收通知，转化理解
- **戳一戳通知** — 有人戳机器人时，转化为文本消息注入对话
- **表情回复通知** — 有人给机器人消息点赞时，同步到对话流
- **禁言通知** — 有人被禁言/解除禁言时，记录到对话历史
- **文件上传通知** — 群里有人上传文件时，通知机器人处理

#### 主动交互，拉近距离
- **发送戳一戳** — 机器人可以主动戳一戳用户引起注意
- **AOE 戳一戳** — 机器人可以同时戳多个活跃用户（每人一次）
- **发送表情回复** — 机器人可以给用户消息点赞、表达情绪（仅群聊）
- **全场景支持** — 所有功能同时支持私聊和群聊

---

## 🏗 架构

### 原生 Action 支持

Notice Injector 通过框架的原生 Action 系统提供交互能力：

| 动作               | 用途                     | 参数                                   |
|--------------------|--------------------------|----------------------------------------|
| `send_poke`        | 单用户连戳多次           | `user_id`(必选), `group_id`(可选), `poke_count`(可选), `target_user_id`(可选), `target_group_id`(可选) |
| `send_poke_multiple` | 多用户各戳一次（AOE）  | `user_ids`(必选), `group_id`(必选), `max_targets`(可选，默认5), `validate_targets`(可选，默认true) |
| `send_emoji_like`  | 发送表情回复（仅群聊）   | `message_id` (必选), `semantic_hint` (必选), `emotion_tags` (可选), `emoji_id` (兼容参数，执行时忽略) |

### 通知处理流程

```mermaid
graph TD
    A[QQ通知事件] --> B[NoticeHandler]
    B --> C{类型判断}
    C -->|戳一戳| D[转换为文本消息]
    C -->|表情回复| E[提取表情信息]
    C -->|禁言| F[记录禁言状态]
    C -->|文件上传| G[记录文件信息]
    D --> H[注入对话流]
    E --> H
    F --> H
    G --> H
    H --> I[机器人处理对话]
```

---

## 📁 文件结构

```
notice_injector/
├── manifest.json            # 插件元数据
├── plugin.py                # 插件入口，注册组件与事件
├── config.py                # 配置定义
├── LICENSE                  # MIT 许可证
├── README.md                # 插件文档
└── actions/
    ├── poke.py              # send_poke 动作实现
    └── emoji_like.py        # send_emoji_like 动作实现
```

---

## ⚙️ 配置

配置文件首次运行自动生成，路径：`config/plugins/notice_injector/config.toml`

### 配置节：`[plugin]`

> 当前插件所有配置均位于 `[plugin]` 下（无 `[features]` 节）。

| 配置项 | 默认值 | 说明 |
|---|---:|---|
| `enabled` | `true` | 插件总开关 |
| `enable_poke` | `true` | 是否处理戳一戳通知 |
| `enable_emoji_like` | `true` | 是否处理表情回复通知 |
| `enable_ban` | `true` | 是否处理禁言通知 |
| `enable_group_upload` | `true` | 是否处理文件上传通知 |
| `enable_debug` | `false` | 是否输出调试日志 |
| `ignore_self_notice` | `true` | 是否忽略机器人自己触发的通知 |

---

## 🛠️ TODO / 路线图

根据插件现状，以下功能计划按优先级开发：

### 🔴 高优先级：提升 AI 感知与反馈质量
- [ ] **结构化 Prompt 注入**：修改 `NoticeInjectorEventHandler.execute`，将拼接的 `text_description` 包装在标记块中（如 `<social_interaction>...</social_interaction>`），并在 `src/core/prompt` 中定义相应的处理逻辑，使 LLM 识别其为系统事件而非用户发言。
- [ ] **上下文关联 Emoji 回复**：在插件内维护一个简易的 `MessageHistoryCache`（记录 `group_id` / `user_id` 对应的最后 3 条 `message_id`），当 AI 调用 `send_emoji_like` 但未提供 ID 时，自动回填最新的消息 ID。
- [ ] **社交频率限制 (Rate Limiter)**：在 `actions/poke.py` 中引入 `src/kernel/storage` 存储戳人记录，针对同一 `user_id` 在 60s 内仅允许执行一次 `poke` 动作，防止 AI 幻觉导致的无限循环戳人。

### 🟡 中优先级：扩展社交场景
- [ ] **“运气王”语义化**：解析 `notice_type: lucky_king`，从 `extra` 中提取红包金额和运气王昵称，转化为 `[系统通知：用户A成为了运气王，抢到了XX元]` 注入对话。
- [ ] **成员变更实时感知**：监听 `EventType` 中的群成员增加/减少事件，提取入群方式或退群原因，转化为语义描述注入，触发 LLM 生动的欢迎语或告别语。
- [ ] **Action 级联封装**：扩展 `Action` 的 `execute` 方法，支持返回一个包含 `send_message` 指令的 Task，实现“戳一下并附带一句话”的原子操作。

### 🔵 低优先级：工程化优化
- [ ] **语义情绪映射表**：在 `config.py` 中定义 `EMOTION_MAP: dict[str, int]`，将 LLM 常用的情绪词（如 "like", "cry", "fire"）实时映射为标准的 QQ 表情 ID，简化 AI 的交互逻辑。
- [ ] **互动热度统计 Service**：利用 `src/kernel/db` 记录各用户的互动频率（被戳/被赞次数），通过 `src/core/components/base/service.py` 暴露接口，供好感度或活跃度插件查询。

| `trigger_chat` | `false` | 是否将通知注入对话流触发聊天（关闭可省 token） |
| `enable_send_emoji_like` | `true` | 是否启用主动动作 `send_emoji_like` |
| `emoji_like_allowed_ids` | `[...]` | `send_emoji_like` 白名单表情 ID（用于约束乱贴） |
| `emoji_like_strict_mode` | `true` | 开启后不在白名单内的表情会回退默认值 |
| `emoji_like_custom_rules` | `{}` | 自定义语义规则，格式 `{emoji_id: [关键词...]}`，用于补充/覆盖内置规则 |
| `emoji_like_emotion_tag_map` | `{}` | 自定义标签映射，格式 `{标签: emoji_id}`，用于 `emotion_tags` 先验决策 |
| `emoji_like_emotion_tag_priority` | `[...]` | 多标签冲突时的优先级（纯本地规则，零额外消耗） |
| `max_poke_count` | `3` | 单次允许最大连戳次数（内部硬上限 10） |
| `poke_interval_min_ms` | `100` | 连戳最小间隔（毫秒） |
| `poke_interval_max_ms` | `200` | 连戳最大间隔（毫秒） |
| `validate_target_before_poke` | `false` | 发送戳一戳前是否先校验目标 |
| `validate_target_in_group` | `true` | 群聊场景是否执行目标校验 |
| `validate_target_in_private` | `false` | 私聊场景是否执行目标校验（通常不推荐设为 `true`） |
| `aoe_poke_max_targets` | `5` | AOE 戳一戳最大目标人数上限（内部硬上限 20） |
| `validate_target_before_aoe_poke` | `true` | AOE 戳一戳前是否校验目标用户存在 |

### `send_poke` 行为说明

- 次数裁剪：
    - 实际连戳次数会被限制到 `[1, min(max_poke_count, 10)]`
    - 即使模型传入更大值也不会超过硬上限 10
- 目标优先级：
    - 用户：`target_user_id` > `user_id`
    - 群：`target_group_id` > `group_id` > 当前上下文推断
- 群/私聊安全：
    - 群环境缺失 `group_id` 时不会降级为私聊，直接取消执行
- 校验策略：
    - 仅当 `validate_target_before_poke=true` 时才会进入校验流程
    - 群聊校验：`validate_target_in_group=true` 时使用 `get_group_member_info`
    - 私聊校验：`validate_target_in_private=true` 时使用 `get_stranger_info`
    - 私聊默认 `validate_target_in_private=false`，且通常不推荐改为 `true`（会增加额外 API 调用）

### `send_poke_multiple` 行为说明

- 与 `send_poke` 为互斥关系，二选一使用：
    - `send_poke`：单用户连戳多次
    - `send_poke_multiple`：多用户各戳一次
- 每人只戳一次，不支持连戳
- 人数上限由 `max_targets` 控制（默认 5）
- LLM 应从上下文判断"活跃用户"是谁，建议从最近消息中提取
- 目标校验默认开启，会过滤无效用户
- AOE 戳一戳仅支持群聊

### `send_emoji_like` 行为说明

- 回复意图优先（强制）：
    - action 会忽略显式 `emoji_id`，仅根据 `semantic_hint` 做语义选取
    - 这样可避免“对方说难过 -> 机器人也发哭泣”这类情绪复读
- 标签先验（参考 emoji_sender）：
    - 若传入 `emotion_tags`，会先按标签映射选择表情，再回退到 `semantic_hint` 规则
    - 默认支持标签：开心/难过/生气/惊讶/害羞/尴尬/无语/委屈/嘲讽/疑惑/赞同/否定/兴奋/疲惫/害怕/厌恶/紧张/冷漠
- 冲突决策（零额外消耗）：
    - 当同时出现多个标签时，按 `emoji_like_emotion_tag_priority` 选择最高优先级标签
    - 该步骤仅本地排序，不触发任何额外模型调用
- `semantic_hint` 为必填：
    - 未提供时将拒绝执行，避免脱离语义上下文乱贴
- 语义未命中时：
    - 回退到 `default_emoji_id`（默认 `126` 点赞）
- 继续加入语义规则：
    - 在 `emoji_like_custom_rules` 中按 `{emoji_id: [关键词...]}` 添加
    - 自定义规则优先于内置规则，且会与内置关键词自动合并
- 推荐调用方式：
    - 只需填写 `semantic_hint`（例如：感谢/恭喜/安慰/加油/确认）

### 推荐配置（低延迟+稳健）

```toml
[plugin]
# 插件总开关：false 时本插件完全停用
enabled = true

# 通知处理类型开关
enable_poke = true
enable_emoji_like = true
enable_ban = true
enable_group_upload = true

# 调试日志（排障时开启）
enable_debug = false

# 是否忽略机器人自己产生的通知（避免自循环）
ignore_self_notice = true

# 是否把通知注入对话触发聊天（false 可显著节省 token）
trigger_chat = false

# 连戳次数上限（运行时硬上限=10）
max_poke_count = 3

# 连戳随机间隔区间（毫秒）
poke_interval_min_ms = 100
poke_interval_max_ms = 200

# 发送前目标校验总开关（程序内 API 校验，不消耗 LLM token）
validate_target_before_poke = true

# 分场景校验开关：推荐群聊开、私聊关
validate_target_in_group = true
validate_target_in_private = false
```

---

## 🔧 安装

将 `notice_injector/` 目录放入 Neo-MoFox 的 `plugins/` 文件夹，首次启动自动生成配置。

**要求**：Neo-MoFox >= 2.0.0 · Python >= 3.11

---

## 📜 许可证

MIT License
