"""
Claude API 로 블로그 글 초안을 만들어 posts/ 폴더에 저장합니다.

    python generate.py "주제" [--tone 친근한] [--keywords "키워드1,키워드2"]
"""
import argparse
import datetime
import os
import re

import anthropic

from common import POSTS_DIR, load_env

PROMPT = """너는 네이버 블로그 글을 쓰는 전문 작가다.
아래 주제로 네이버 블로그 글을 한국어로 작성해라.

- 주제: {topic}
- 핵심 키워드: {keywords}
- 말투: {tone}

규칙:
1. 제목은 핵심 키워드를 앞쪽에 넣고 30자 이내.
2. 본문은 1500~2500자, 소제목(## ) 3~5개, 문단은 2~3문장으로 짧게.
3. 직접 경험한 듯한 구체적인 정보와 팁 위주로 쓰고, 과장 광고나 허위 정보는 쓰지 말 것.
4. 마지막에 한 줄 요약과 독자에게 던지는 질문.
5. 태그는 5~10개.

출력 형식(이 형식 그대로, 다른 말 없이):
---
title: 제목
tags: 태그1, 태그2, 태그3
---
본문
"""


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--tone", default="친근하고 정보 위주의 존댓말")
    args = ap.parse_args()

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
    msg = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=4000,
        messages=[{"role": "user", "content": PROMPT.format(
            topic=args.topic, keywords=args.keywords or args.topic, tone=args.tone)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()

    slug = re.sub(r"[^\w가-힣]+", "-", args.topic).strip("-")[:40]
    out = POSTS_DIR / f"{datetime.date.today():%Y%m%d}-{slug}.md"
    out.write_text(text + "\n", encoding="utf-8")
    print("초안 저장:", out)
    print("※ 발행 전에 꼭 직접 읽고 수정하세요.")


if __name__ == "__main__":
    main()
