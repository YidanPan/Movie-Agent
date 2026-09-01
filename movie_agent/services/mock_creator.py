"""Deterministic planning generator used before model integration."""

from __future__ import annotations

from math import ceil

from movie_agent.models import Shot


def build_storyboard(idea: str, duration: int, style: str, project_id: str) -> list[Shot]:
    shot_count = max(6, ceil(duration / 8))
    shot_count = min(10, shot_count)
    base_duration, remainder = divmod(duration, shot_count)
    framings = ["全景", "中近景", "特写", "过肩镜头", "低机位中景", "空镜"]
    modes = ["T2V", "T2V", "I2V", "I2V", "R2V", "T2V", "I2V", "R2V", "T2V", "I2V"]
    shots: list[Shot] = []
    for index in range(shot_count):
        shot_duration = base_duration + (1 if index < remainder else 0)
        phase = "建立孤独的日常" if index < 2 else "让异常逐渐显现" if index < shot_count - 2 else "完成情绪转折与余韵"
        image = f"{style}电影摄影，同一主角与同一核心空间，{phase}。"
        action = f"主角在第 {index + 1} 个叙事节拍中完成一个克制、清晰的动作。"
        sound = "低频环境声、空间混响与克制的音乐渐进，不使用受版权保护的素材。"
        prompt = (
            f"{image} {action} [{0}s-{shot_duration}s] 镜头运动自然稳定。{sound} "
            "不出现现有影视角色、片名、品牌标志、真人肖像或受版权保护的造型。"
        )
        shots.append(
            Shot(
                number=index + 1,
                duration_seconds=shot_duration,
                framing=framings[index % len(framings)],
                image_description=image,
                action=action,
                sound_design=sound,
                generation_mode=modes[index],
                prompt=prompt,
                output_placeholder=f"outputs/{project_id}/shot-{index + 1:02d}.mp4",
            )
        )
    return shots
