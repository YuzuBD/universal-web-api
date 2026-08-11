# -*- coding: utf-8 -*-
"""
flowmusic_parser.py - Google Flow Music 专用响应解析器

从 Flow Music 内部接口 __api/clips 的 JSON 响应中提取 audio_url / wav_url，
直接把真实音频文件（storage.googleapis.com 直链）作为媒体项返回，
避免通过页面播放/录音的方式获取音频。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.parsers.base import ResponseParser


class FlowMusicParser(ResponseParser):
    """解析 Flow Music __api/clips 响应，提取音频直链。"""

    # ============ 核心解析 ============

    def parse_chunk(self, raw_response: str) -> Dict[str, Any]:
        delta = self._prepare_incremental_raw_response(raw_response)
        if not delta:
            return {"content": "", "images": [], "done": False, "error": None}

        try:
            data = json.loads(raw_response)
        except Exception:
            return {"content": "", "images": [], "done": False, "error": None}

        media = self._extract_media(data)
        if media:
            return {
                "content": "",
                "images": media,
                "done": True,
                "error": None,
            }
        return {"content": "", "images": [], "done": False, "error": None}

    def reset(self) -> None:
        self._last_raw_response = ""
        self._last_raw_length = 0

    # ============ 媒体提取 ============

    @staticmethod
    def _extract_media(data: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                audio = node.get("audio_url") or node.get("audioUrl")
                wav = node.get("wav_url") or node.get("wavUrl")
                url = audio or wav
                if isinstance(url, str) and url.strip().startswith("http"):
                    url = url.strip()
                    mime = "audio/mp4"
                    if url.lower().endswith(".wav"):
                        mime = "audio/wav"
                    elif url.lower().endswith(".mp3"):
                        mime = "audio/mpeg"
                    elif url.lower().endswith((".ogg", ".oga")):
                        mime = "audio/ogg"
                    items.append(
                        {
                            "media_type": "audio",
                            "kind": "url",
                            "url": url,
                            "mime": mime,
                            "label": "flowmusic_download",
                            "source": "flowmusic_stream",
                        }
                    )
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(data)

        seen = set()
        result: List[Dict[str, Any]] = []
        for item in items:
            ref = str(item.get("url") or "").strip()
            if not ref or ref in seen:
                continue
            seen.add(ref)
            result.append(item)
        return result

    # ============ 元数据 ============

    @classmethod
    def get_id(cls) -> str:
        return "flowmusic"

    @classmethod
    def get_name(cls) -> str:
        return "FlowMusic"

    @classmethod
    def get_description(cls) -> str:
        return "从 Flow Music __api/clips 响应中提取 audio_url / wav_url 直链"

    @classmethod
    def get_supported_patterns(cls) -> List[str]:
        return ["__api/clips"]


__all__ = ["FlowMusicParser"]
