"""공통 설정과 글 파일(.md) 파서."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / ".naver-profile"   # 로그인 세션(쿠키)이 저장되는 폴더
POSTS_DIR = BASE_DIR / "posts"
DONE_DIR = POSTS_DIR / "done"


def load_env():
    """.env 파일을 읽어 환경변수로 등록 (python-dotenv 없이 동작)."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Post:
    path: Path
    title: str
    tags: list = field(default_factory=list)
    # 본문 블록: ("text", 문단) / ("heading", 소제목) / ("divider", "") / ("image", Path)
    blocks: list = field(default_factory=list)


IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


def _clean_inline(line: str) -> str:
    """**굵게**, __밑줄__ 표시는 post.py 가 서식으로 바꾸므로 남기고 나머지만 정리."""
    line = re.sub(r"(?<![*_])\*(?![*\s])(.+?)(?<![*\s])\*(?!\*)", r"\1", line)  # *기울임*
    line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", line)  # [링크](url)
    return line


def parse_post(path: Path) -> Post:
    """
    글 파일 형식:
        ---
        title: 글 제목
        tags: 태그1, 태그2
        ---
        본문
    본문에서 지원하는 표시:
        ## 소제목        → 굵은 소제목 (▍소제목)
        **굵게**, __밑줄__ → 굵게 / 밑줄
        ---             → 구분선(빈 줄 두 개)
        ![](사진.jpg)    → 사진 업로드
    """
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body = m.group(2)

    title = meta.get("title") or path.stem
    tags = [t.strip().lstrip("#") for t in meta.get("tags", "").split(",") if t.strip()]

    blocks = []
    for raw in body.strip().splitlines():
        img = IMAGE_RE.match(raw.strip())
        if img:
            # 글 파일 기준 상대경로 → 없으면 프로젝트 폴더 기준
            img_path = (path.parent / img.group(1)).resolve()
            fallback = (BASE_DIR / img.group(1)).resolve()
            if not img_path.exists() and fallback.exists():
                img_path = fallback
            blocks.append(("image", img_path))
            continue
        stripped = raw.strip()
        heading = HEADING_RE.match(stripped)
        if heading:
            blocks.append(("heading", heading.group(1).replace("**", "")))
        elif re.fullmatch(r"-{3,}|\*{3,}", stripped):
            blocks.append(("divider", ""))
        else:
            blocks.append(("text", _clean_inline(raw.rstrip())))
    return Post(path=path, title=title, tags=tags, blocks=blocks)
