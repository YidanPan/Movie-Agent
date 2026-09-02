"""Storyboard agent: creates renderable, independently generated shots."""

from movie_agent.models import Shot
from movie_agent.services.mock_creator import build_storyboard
from movie_agent.services.llm import CreativeLLM

_MIN_SHOT_SECONDS = 4
_MAX_SHOT_SECONDS = 8


def _parse_duration(raw: object) -> int:
    try:
        return int(round(float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("分镜 Agent 返回了无法解析的镜头时长。") from error


def _fit_durations(durations: list[int], target_seconds: int) -> list[int] | None:
    """Clamp each shot into 4–8s, then redistribute the remainder to hit the target."""

    fitted = [max(_MIN_SHOT_SECONDS, min(_MAX_SHOT_SECONDS, duration)) for duration in durations]
    difference = target_seconds - sum(fitted)
    index = 0
    while difference > 0:
        if all(duration >= _MAX_SHOT_SECONDS for duration in fitted):
            return None
        if fitted[index % len(fitted)] < _MAX_SHOT_SECONDS:
            fitted[index % len(fitted)] += 1
            difference -= 1
        index += 1
    while difference < 0:
        if all(duration <= _MIN_SHOT_SECONDS for duration in fitted):
            return None
        if fitted[index % len(fitted)] > _MIN_SHOT_SECONDS:
            fitted[index % len(fitted)] -= 1
            difference += 1
        index += 1
    return fitted


class StoryboardAgent:
    def __init__(
        self,
        llm: CreativeLLM | None = None,
        allowed_generation_modes: set[str] | None = None,
    ) -> None:
        self.llm = llm
        self.allowed_generation_modes = allowed_generation_modes or {"T2V", "I2V", "R2V"}

    def create(
        self,
        idea: str,
        duration_seconds: int,
        visual_style: str,
        project_id: str,
        brief: dict[str, str],
        script: dict[str, str],
        visual_bible: dict[str, str],
    ) -> list[Shot]:
        if self.llm:
            result = self.llm.complete_json(
                "你是电影分镜师。将故事拆成独立、可生成的原创科幻镜头。"
                "每镜 4–8 秒，镜头数 6–10，避免复杂多人互动与现有影视 IP。"
                f"当前可用生成方式仅为：{'、'.join(sorted(self.allowed_generation_modes))}。"
                "所有镜头的 duration_seconds 之和必须恰好等于总时长。",
                (
                    f"创意：{idea}\n总时长：{duration_seconds} 秒\n风格：{visual_style}\n"
                    f"导演设定：{brief}\n剧本：{script}\n视觉设定：{visual_bible}\n"
                    "文字要精炼以控制生成时间：image_description 与 action 各不超过 40 个字，"
                    "sound_design 不超过 20 个字，prompt 用不超过 60 词的英文视频提示词。"
                    "返回 JSON：{\"shots\":[{\"duration_seconds\":6,\"framing\":\"中近景\","
                    "\"image_description\":\"...\",\"action\":\"...\",\"sound_design\":\"...\","
                    "\"generation_mode\":\"T2V\",\"prompt\":\"...\"}]}。"
                ),
            )
            raw_shots = result.get("shots")
            if not isinstance(raw_shots, list) or not 6 <= len(raw_shots) <= 10:
                raise ValueError("分镜 Agent 未返回 6–10 个镜头。")
            for raw_shot in raw_shots:
                if not isinstance(raw_shot, dict):
                    raise ValueError("分镜 Agent 返回了无效镜头。")
            raw_durations = [_parse_duration(raw_shot.get("duration_seconds")) for raw_shot in raw_shots]
            fitted_durations = _fit_durations(raw_durations, duration_seconds)
            if fitted_durations is None:
                raise ValueError(
                    f"分镜 Agent 返回的镜头数无法在 4–8 秒区间内凑满 {duration_seconds} 秒，请重新开机。"
                )
            shots: list[Shot] = []
            for number, raw_shot in enumerate(raw_shots, start=1):
                shot_duration = fitted_durations[number - 1]
                mode = str(raw_shot["generation_mode"]).upper()
                if mode not in self.allowed_generation_modes:
                    allowed = "、".join(sorted(self.allowed_generation_modes))
                    raise ValueError(f"分镜 Agent 使用了当前工作流不支持的生成方式：{mode}（仅支持 {allowed}）。")
                shots.append(
                    Shot(
                        number=number,
                        duration_seconds=shot_duration,
                        framing=str(raw_shot["framing"]),
                        image_description=str(raw_shot["image_description"]),
                        action=str(raw_shot["action"]),
                        sound_design=str(raw_shot["sound_design"]),
                        generation_mode=mode,
                        prompt=str(raw_shot["prompt"]),
                        output_placeholder=f"outputs/{project_id}/shot-{number:02d}.mp4",
                    )
                )
            return shots
        shots = build_storyboard(idea, duration_seconds, visual_style, project_id)
        if self.allowed_generation_modes == {"T2V"}:
            for shot in shots:
                shot.generation_mode = "T2V"
        return shots

    def revise(self, shot: Shot, visual_bible: dict[str, str]) -> Shot:
        """Refresh one render prompt while retaining its assigned story beat and duration."""
        consistency = "；".join(
            value for key, value in visual_bible.items() if key in {"角色卡", "场景卡", "风格卡"}
        )
        revised_prompt = f"{shot.prompt}。一致性约束：{consistency}"
        return Shot(
            number=shot.number,
            duration_seconds=shot.duration_seconds,
            framing=shot.framing,
            image_description=shot.image_description,
            action=shot.action,
            sound_design=shot.sound_design,
            generation_mode=shot.generation_mode,
            prompt=revised_prompt,
            output_placeholder=shot.output_placeholder,
            status="replanned",
            attempts=shot.attempts + 1,
        )
