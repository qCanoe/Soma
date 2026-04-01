# MoodTune Web UI MVP PRD v0.1

顶部是一条很轻的 Header（Logo + 右侧一个 “Reset” 小按钮），下面立刻进入“意图输入区”，再是一个很大的“Player Card”，最底部是“Controls Drawer（可折叠控制抽屉）”。你做副业产品，第一屏要像“一个可以立刻用的工具”，不要像“需要学习的产品”。

意图输入区的 UI 关键在于“短输入 + 词卡补全”。视觉上是一行输入框（两行高度上限，避免像聊天框），placeholder 类似 “Describe how you feel… (e.g., anxious, need focus, can’t sleep)”。输入框右侧放一个小的 Apply/Generate 按钮（MVP 更直观），输入框下方放两排 chips：第一排是 Mode（Focus / Calm / Sleep），只能单选；第二排是 Feelings/Intent（Anxious、Overwhelmed、Low energy、Restless、Deep work、Light study…），允许多选但最多 3 个。再加一排 Environment（Rain / White Noise / None），可以和下方 Background 控件联动。交互上你要做得“很像有智能”：点击卡片立刻在输入框下方出现一行 “Interpreting as: Calm · Warm · Slow · Low density” 这样的 tiny label（不是解释技术，是给用户掌控感），同时 Player Card 的标题/图标/动效风格立即变化（比如 Calm 更柔、Focus 更利落）。即使音频还没接，这个“即时反馈”也能让 demo 站得住。

中心 Player Card 是你 UI 的核心资产：它需要在视觉上让人产生“点一下就开始”的冲动。卡片内从上到下：顶部左侧是当前 Preset 名（例如 “Deep Focus” 或 “Soft Calm”），右侧是一个小的 “Regenerate” 图标按钮；中间是一个波形/呼吸动效占位（用 canvas 或纯 CSS 都行），底部是超大的 Play/Pause 圆形按钮，旁边两个小按钮（Restart、Mute/Volume）。再往下是一行进度条 + 计时显示（45:00），以及一个 “Ends with: Fade out” 的小字（给安全感）。MVP 阶段你可以把 Play 行为做成“假播放”：点击后波形动起来、进度条走、按钮状态切换、页面标题显示 “Playing…”，这就足够支撑 UI 验证和可用性测试。

底部 Controls 建议做成抽屉（桌面端固定在右侧面板也行，但 MVP 用抽屉更省空间也更像移动端产品）。抽屉默认收起，只露出一行：“Intensity 3 · 45 min · Rain”，点击展开后是三个控件：Intensity（1-5 离散点）、Duration（15/30/45/60）、Background（None/Rain/Noise）。这三个控件要做到“改一下马上反映到 Player Card”，比如 Intensity 变化会影响波形振幅/动效速度；Duration 变化更新倒计时；Background 更新 chips 高亮。你暂时不接音频也没关系，UI 上必须让用户感到参数确实在驱动体验。
