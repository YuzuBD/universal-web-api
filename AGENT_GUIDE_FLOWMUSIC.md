# Agent 调用指南：通过 Universal Web API 生成 Flow Music 音乐（Lyria 3.5）

> 适用对象：需要让 agent 自动生成音乐的开发者/模型。
> 本文件教一个 AI agent 如何调用本地已运行的 **Universal Web API** 桥接服务，
> 在 Google Flow Music（Lyria 3.5）上生成歌曲并取回完整音频文件。

---

## 1. 这是什么

本地跑了一个 OpenAI 兼容的 API 服务（Universal Web API），它驱动一个**已登录 Flow Music 的受控浏览器**：

- 输入：一段自然语言音乐描述（风格 / BPM / 时长 / 乐器 / 人声等）
- 输出：OpenAI 格式的响应，`media` 数组里是**真实音频文件**（m4a，含 wav 备用链接）
- 每次调用会新建会话，Producer 通常返回 **2 首候选（A/B 变体）**，全部返回

| 项目 | 值 |
|---|---|
| Base URL | `http://192.168.1.114:8199/v1`（可配置） |
| 端点 | `POST /chat/completions` |
| 模型名 | `flowmusic` |
| 认证 | 默认关闭，Header 填 `Authorization: Bearer sk-local` 即可 |
| 超时 | 生成 40~150 秒，**客户端超时建议 ≥ 600 秒** |
| 并发 | 只有一个 Flow Music 标签页，**请串行调用** |

---

## 2. 调用前检查环境（可选但推荐）

```bash
# 服务健康
curl http://192.168.1.114:8199/health
# -> {"service":"healthy","browser":{"connected":true,"port":9222},...}

# 模型是否可用（能看到 flowmusic 说明路由正常）
curl http://192.168.1.114:8199/v1/models -H "Authorization: Bearer sk-local"
```

如果 `browser.connected=false` 或 `/v1/models` 里没有 `flowmusic`：
说明受控浏览器没开 / 没登录 Flow Music，需要人工在受控浏览器里登录一次。

---

## 3. 生成一首歌（最简单）

### curl

```bash
curl http://192.168.1.114:8199/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "flowmusic",
    "messages": [
      {"role": "user", "content": "Generate a 30 second lo-fi hip hop beat at 80 BPM with a mellow piano melody"}
    ],
    "stream": false
  }'
```

### Python（requests）

```python
import requests

resp = requests.post(
    "http://192.168.1.114:8199/v1/chat/completions",
    headers={"Authorization": "Bearer sk-local"},
    json={
        "model": "flowmusic",
        "messages": [{"role": "user", "content": "Generate a dreamy synthwave track at 100 BPM"}],
        "stream": False,
    },
    timeout=600,
)
data = resp.json()
print(data["media"])   # 音频列表
```

### Node.js

```js
const resp = await fetch("http://192.168.1.114:8199/v1/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json", "Authorization": "Bearer sk-local" },
  body: JSON.stringify({
    model: "flowmusic",
    messages: [{ role: "user", content: "Generate an upbeat electronic dance track at 124 BPM" }],
    stream: false,
  }),
  signal: AbortSignal.timeout(600_000),
});
const data = await resp.json();
console.log(data.media);
```

> 仓库里也自带一个测试客户端：`python scripts/test_flowmusic.py "你的描述"`
> （会自动下载所有音频到 `--out` 目录）。

---

## 4. 响应格式

非流式响应（OpenAI chat.completion 形状），音频在 **顶层 `media`** 和 **`choices[0].message.media`**：

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "",
        "media": [
          {
            "media_type": "audio",
            "kind": "url",
            "url": "https://storage.googleapis.com/producer-app-public/clips/<clip-uuid>.m4a",
            "mime": "audio/mp4",
            "label": "Analog Drift",
            "title": "Analog Drift",
            "wav_url": "https://storage.googleapis.com/producer-app-public/clips/<clip-uuid>.wav",
            "source": "flowmusic_direct"
          }
        ]
      },
      "finish_reason": "stop"
    }
  ],
  "media": [ "...同上，音频数组..." ]
}
```

要点：

- `media` 里**每首一首歌**；Producer 通常一次给 2 首（A/B 变体），用 `title` 区分
- `url` 是 m4a（AAC，48kHz 立体声，最长约 3 分钟），`wav_url` 是 wav 备用
- URL 是公开可下载的（无需 cookie），直接 GET 即可
- 流式请求（`stream: true`）同样在 SSE chunk 的 `media` 字段里返回音频，但**建议用非流式**更简单

---

## 5. 下载音频

```python
import requests

for i, item in enumerate(data["media"]):
    url = item["url"]                      # 或 item["wav_url"] 拿 wav
    ext = url.rsplit(".", 1)[-1]           # m4a / wav
    r = requests.get(url, timeout=120)
    open(f"song_{i}.{ext}", "wb").write(r.content)
    print("saved", item.get("title", i), item["url"])
```

---

## 6. 给 agent 用的函数定义（function calling schema）

如果你的 agent 支持注册工具，可以直接用这个 schema：

```json
{
  "type": "function",
  "function": {
    "name": "generate_music",
    "description": "Generate music via Google Flow Music (Lyria 3.5). Returns 1-2 complete audio files (m4a) with titles. Call takes 40-150 seconds.",
    "parameters": {
      "type": "object",
      "properties": {
        "prompt": {
          "type": "string",
          "description": "Music description. Include genre, mood, tempo/BPM, duration, instruments, and whether vocals/instrumental. Example: 'Generate a 30 second lo-fi hip hop beat at 80 BPM with a mellow piano melody'"
        },
        "out_dir": {
          "type": "string",
          "description": "Directory to save downloaded audio files (optional)."
        }
      },
      "required": ["prompt"]
    }
  }
}
```

工具内部逻辑（参考实现）：

1. `POST {base}/v1/chat/completions`，`model=flowmusic`，`stream=false`，超时 600s
2. 从 `data["media"]` 取所有条目
3. 逐个下载 `url`（m4a）到 `out_dir`，文件名用 `title`（若存在）
4. 返回给上层：歌曲标题 + 本地文件路径 + 时长/格式说明

---

## 7. 提示词怎么写（实测有效）

- **风格 + 情绪 + 乐器 + BPM + 时长**，一次说全，例如：
  - `Generate a 30 second lo-fi hip hop beat at 80 BPM with a mellow piano melody`
  - `Generate a dreamy synthwave track with retro analog synth leads at 100 BPM`
  - `Generate an upbeat electronic dance track with driving bass at 124 BPM`
- 要人声/歌词：明确写 `with female vocals` / `with lyrics about ...`；要纯音乐：写 `instrumental`
- 时长：写 `30 seconds` / `1 minute`（Lyria 3.5 支持时长控制，实际会按模型判断，最长约 3 分钟）
- Producer 有时会**自己改词/给两个变体**，属正常现象，选一首即可

---

## 8. 常见问题排查

| 现象 | 原因 | 处理 |
|---|---|---|
| HTTP 500 / 请求秒回 | 服务刚改配置没重启 / 受控浏览器没就绪 | 重启服务；看 `http://192.168.1.114:8199` 控制台日志 |
| 返回 0 个 media | 未登录 / 额度用完 / 内容审核拒绝 / 生成失败 | 检查受控浏览器登录态、Flow Music 积分、换提示词 |
| 拿到的是旧歌 | 上次遗留（正常不会发生） | 每次调用会自动新建会话；如仍异常看服务日志 |
| 调用很慢 | 生成本身 40~150s | 属正常，把客户端超时设到 600s |
| 并发调用报错/排队 | 只有一个受控标签页 | 串行调用，或给服务配置多个 Flow Music 标签页 |

---

## 9. 限制与注意事项

- **仅限个人研究/调试**，遵守 Flow Music 服务条款（项目原免责声明同样适用）
- 每次生成消耗 Flow Music 积分（免费档每天有额度）
- 生成的歌曲会保存在你的 Flow Music 账号里
- 底层使用 Flow Music 内部接口 `__api/clips` 获取音频直链；如果 Flow Music 改版导致失效，需要重新适配（可退回“下载菜单”方案）
- 页面结构变化可能导致选择器失效——更新 `config/sites.json` 里的站点配置即可，无需改代码

---

## 10. 相关文件

- `scripts/test_flowmusic.py`：测试/示例客户端
- `FLOWMUSIC.md`：人类可读的完整适配说明（安装、启动、登录）
- `config/sites.json`：Flow Music 站点配置（选择器、工作流）
- `app/core/workflow/executor.py`：`FLOWMUSIC_FETCH_CLIP` 动作实现
