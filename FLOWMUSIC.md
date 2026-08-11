# Flow Music（Lyria 3.5）适配说明

本分支在 Universal Web API 上新增了 **Google Flow Music（Lyria 3.5）** 站点适配：
把已登录的 Flow Music 网页包装成 OpenAI 兼容 API，agent 通过 `/v1/chat/completions`
生成音乐，并直接拿到**完整真实音频文件**（m4a，storage.googleapis.com 直链）。

> 音频获取方式：不走页面录音，也不点下载菜单。生成完成后在页面上下文直接调用
> Flow Music 内部接口 `POST /__api/clips`（body: `{"clip_ids": ["..."]}`），
> 从返回的 `audio_url` / `wav_url` 字段拿到真实直链，再由服务下载到本地。
> **Producer 通常一次返回 2 首歌（A/B 变体），本适配会一次性返回全部歌曲的音频**，
> 每首以独立 media 项给出（含 `title`，方便区分）。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `app/models/schemas.py` | 动作白名单新增 `WAIT_FOR_SELECTOR`、`FLOWMUSIC_FETCH_CLIP` |
| `app/api/config_workflow_support.py` | 新增动作中文标签 |
| `app/core/workflow/executor.py` | 实现 `WAIT_FOR_SELECTOR`（等待元素出现/消失）与 `FLOWMUSIC_FETCH_CLIP`（页面内调 `__api/clips` 取音频直链） |
| `app/core/browser/workflow.py` | 把新动作并入“流式步骤”，并允许无选择器动作 |
| `app/core/parsers/flowmusic_parser.py` | 新增：解析 `__api/clips` 响应提取 audio_url（备用/调试用） |
| `config/parsers.json` | 注册 `flowmusic` 解析器 |
| `config/sites.json` | 新增 `www.flowmusic.app` / `flowmusic.app` 两个站点条目（预设 `lyria35`） |
| `scripts/test_flowmusic.py` | 测试客户端（新增） |

## 运行步骤

1. **安装依赖**（Python 3.10+，已装 Chrome/Edge）
   ```
   pip install -r requirements.txt
   ```

2. **启动服务**
   - Windows: 双击 `start.bat`，或 `python start.py`
   - 服务地址: `http://127.0.0.1:8199`，控制台也在该地址

3. **在受控浏览器里登录 Flow Music**
   - 服务启动后会弹出一个受控浏览器窗口
   - 在该窗口打开 `https://www.flowmusic.app/`，用你的 Google 账号登录
   - **保持该标签页打开**（建议只留这一个网站标签）

4. **生成一首歌**
   ```
   python scripts/test_flowmusic.py "Generate a 30 second lo-fi hip hop beat at 80 BPM with a mellow piano melody"
   ```
   或直接调 API:
   ```
   curl http://127.0.0.1:8199/v1/chat/completions ^
     -H "Content-Type: application/json" ^
     -H "Authorization: Bearer sk-local" ^
     -d "{\"model\":\"flowmusic\",\"messages\":[{\"role\":\"user\",\"content\":\"Generate a 30 second lo-fi hip hop beat at 80 BPM\"}],\"stream\":false}"
   ```

5. **响应里的音频**
   - 非流式响应：`data.media[0].url` 是本地音频地址（形如 `/media/xxx.m4a`），
     拼接 `http://127.0.0.1:8199` 即可下载；响应内容里也有 `[audio_0](...)` 链接
   - 流式响应：同样在 SSE 的 `data.media` 字段

## 工作机制（简要）

- Flow Music 交互是“聊天框 + 生成卡片”：
  - 输入框 `textarea[aria-label="Chat message"]`
  - 发送按钮 `button[aria-label="Send message"]`
  - 侧边栏 `New session` 按钮（每次调用先开新会话，保证拿的是本轮新歌）
- 工作流：
  1. 点 `New session` → 2. 填提示词 → 3. 点发送
  4. 等 `Stop generating` 出现（生成开始）→ 5. 等它消失（**生成结束**）
  6. 等会话内出现歌曲卡片（`.chat-history-part.producer-part .render-group-clip`）
  7. 收集本轮 producer 回复里的全部歌曲 id → 页面内调 `POST /__api/clips` 拿每首歌的 `audio_url`（m4a 直链）→ 服务下载到本地，全部作为 media 返回
- 每次调用都会新建会话，互不干扰；生成的歌会留在你的 Flow Music 账号里

## 常见问题

- **没有返回 media**：打开控制台 `http://127.0.0.1:8199` → 请求监控看日志。常见原因：
  1. 受控浏览器未登录 / 标签页不是 Flow Music
  2. 生成被内容审核拒绝（换一个提示词）
  3. 免费额度用完
- **返回的音频是旧歌**：Flow Music 侧边栏有“最近歌曲”列表，早期版本会误抓。
  当前已限定只从 `producer-part`（本轮回复）里取最新歌曲链接；如果仍异常，
  在控制台检查 `FLOWMUSIC_FETCH_CLIP` 步骤日志。
- **生成较慢**：Lyria 3.5 生成一首完整歌曲通常 40~150 秒，属正常；
  等待上限可在 `WAIT_FOR_SELECTOR` 的 `timeout` 里调整。
- **想控制时长**：在提示词里写明（如 “30 seconds”），Lyria 3.5 支持节奏/时长控制。

## 风险提示

- 仅限个人研究/调试，遵守 Flow Music 服务条款；账号风险自负（项目原免责声明同样适用）
- 页面结构变化可能导致选择器失效，届时在控制台更新站点配置即可，无需改代码
- `__api/clips` 是 Flow Music 内部接口，未来可能变动；届时可退回“下载菜单”方案
