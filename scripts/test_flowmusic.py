#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flow Music (Lyria 3.5) 测试客户端 —— 用于 Universal Web API

用法:
    python scripts/test_flowmusic.py "Generate a 30 second lo-fi hip hop beat at 80 BPM"
可选参数:
    --base   API 地址，默认 http://127.0.0.1:8199/v1 （可用环境变量 UWA_BASE 覆盖）
    --key    API Key，默认 sk-local （可用环境变量 UWA_KEY 覆盖）
    --model  模型名/路由名，默认 flowmusic
    --out    音频保存目录，默认 outputs
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Flow Music test client for Universal Web API")
    parser.add_argument("prompt", nargs="?", default="Generate a 30 second lo-fi hip hop beat at 80 BPM with a mellow piano melody")
    parser.add_argument("--base", default=os.getenv("UWA_BASE", "http://127.0.0.1:8199/v1"))
    parser.add_argument("--key", default=os.getenv("UWA_KEY", "sk-local"))
    parser.add_argument("--model", default="flowmusic")
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": False,
    }
    url = args.base.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.key}"},
    )

    print(f"[*] 发送请求 -> {url} (model={args.model})")
    print(f"[*] 提示词: {args.prompt[:120]}")
    print("[*] 音乐生成通常需要 40~150 秒，请耐心等待（超时上限 600 秒）...")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[!] 请求失败: {exc}")
        return 1
    print(f"[*] 耗时: {time.time() - t0:.1f} 秒")

    if "error" in data:
        print(f"[!] 服务返回错误: {json.dumps(data['error'], ensure_ascii=False)}")
        return 1

    content = ""
    try:
        content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    except Exception:
        pass
    if content:
        print(f"[*] 回复文本: {content[:300]}")

    media = data.get("media") or []
    print(f"[*] 媒体数量: {len(media)}")
    if not media:
        print("[!] 没有返回音频。请检查控制台日志（http://127.0.0.1:8199）中 Flow Music 的请求记录/错误。")
        return 1

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for item in media:
        print(f"[*] 媒体项: {json.dumps(item, ensure_ascii=False)}")
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        if url.startswith("/"):
            parsed = urllib.parse.urlparse(args.base)
            url = f"{parsed.scheme}://{parsed.netloc}{url}"
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".bin"
        fname = outdir / f"flowmusic_{int(time.time())}_{len(saved)}{ext}"
        try:
            urllib.request.urlretrieve(url, fname)
            saved.append(fname)
            print(f"[*] 已保存: {fname}")
        except Exception as exc:
            print(f"[!] 下载失败 {url}: {exc}")

    if not saved:
        print("[!] 媒体项存在但下载失败，请检查日志。")
        return 1
    print(f"[OK] 完成，共保存 {len(saved)} 个文件到 {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
