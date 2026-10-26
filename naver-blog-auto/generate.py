"""
Claude API 로 블로그 글 초안을 만들어 posts/ 폴더에 저장합니다.

    # 맛집: 내가 다녀온 가게 폴더(메모 + 사진)로 글 쓰기
    python generate.py food visits/가게이름

    # 축제/행사
    python generate.py festival visits/축제이름

    # 자유 주제 (사진·메모 없이)
    python generate.py topic "주제" --keywords "키워드1,키워드2"

    --dry-run 을 붙이면 API 호출 없이 어떤 사진·메모가 들어가는지만 보여줍니다.

방문 폴더 구성:
    visits/가게이름/
        memo.txt        ← 필수. 내가 직접 보고 느낀 것 (templates/ 의 양식 참고)
        *.jpg / *.png   ← 내가 찍은 사진 (파일 이름 순서대로 전달)
        reference.txt   ← 선택. 참고하고 싶은 다른 블로그 글 본문 (구성·말투만 참고, 유사도 검사에 사용)

references/food_style_guide.md (festival_style_guide.md) 가 있으면 글 스타일 가이드로 함께 전달됩니다.
"""
import argparse
import base64
import datetime
import io
import os
import re
import sys
from pathlib import Path

from check_similarity import report as similarity_report
from common import BASE_DIR, POSTS_DIR, load_env

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTOS = 20

COMMON_RULES = """
[절대 규칙]
- 사실 정보(가게 이름, 위치, 가격, 영업시간, 주차, 날짜, 입장료 등)는 반드시 [내 메모]와 사진에 있는 것만 쓴다.
  메모에 없는 정보는 지어내지 말고 그 항목을 빼라. ("정보 없음"이라고 쓰지도 말 것)
- 맛·분위기·느낌은 메모에 적힌 내 감상을 바탕으로 살을 붙이되, 메모와 반대되는 평가는 하지 않는다.
- [참고 글]이 있다면 글의 '구성 방식과 말투'만 참고한다. 참고 글의 문장, 표현, 비유, 소제목 문구를 그대로 쓰거나
  단어만 바꿔 쓰지 마라. 참고 글에 나온 사실을 내 경험처럼 쓰지 마라.
- 사진은 아래에 제공된 파일 이름만 사용하고, 각 사진은 한 번씩 내용에 맞는 위치에 `![](경로)` 형식으로 넣는다.
  사진 내용과 본문이 어긋나지 않게 배치한다. 사진이 없으면 사진 줄은 넣지 않는다.
- 문단은 1~3문장으로 짧게, 문단 사이 빈 줄. 말투는 친근한 '~요'체, 문장 끝을 다양하게.
- 이모지는 쓰지 않거나 아주 가끔만.

[서식] (아래 표시만 사용)
- 소제목: `## 소제목`
- 강조: `**굵게**` (핵심 정보), `__밑줄__` (위치·주차 등 꼭 알아야 할 정보) — 문단당 1개 이하
- 구분선: `---`

[출력 형식] 아래 형식 그대로, 앞뒤에 다른 말 없이:
---
title: 제목
tags: 태그1, 태그2, ...
---
본문
"""

FOOD_PROMPT = """너는 내 네이버 블로그 맛집 후기를 대신 써주는 작가다. 내가 직접 다녀온 가게의 메모와 사진으로 후기를 써라.

[글 구성] (이 순서를 기본으로, 메모에 내용이 없는 섹션은 생략)
1. 제목: '지역 + 메뉴/가게 특징 + 맛집' 키워드를 앞쪽에, 30자 이내. 예) "OO 맛집 OO, 직접 끓이는 OO정식 후기"
2. 도입 (2~3문단): 이 가게를 가게 된 계기와 첫인상. 대표 사진 1장.
3. `## 한눈에 보기`: 가게 이름 / 주소 / 영업시간 / 주차 / 대표 메뉴와 가격을 '항목: 내용' 한 줄씩. (메모에 있는 것만)
4. `## 찾아가는 길과 주차`: 위치, 주변 랜드마크, 주차 팁. 외관 사진.
5. `## 매장 분위기`: 내부, 좌석, 손님 분위기, 방문 시간 팁. 내부 사진.
6. `## 메뉴와 가격`: 메뉴판 사진이 있으면 함께. 우리가 고른 메뉴와 이유.
7. `## 직접 먹어본 후기`: 메뉴마다 맛·식감·양·곁들임을 구체적으로. 메뉴별로 사진 → 설명 순서.
8. `## 솔직한 총평`: 좋았던 점과 아쉬웠던 점(메모에 있을 때)을 함께. 그리고 '이런 분께 추천해요' 2~3줄.
9. 마무리 한두 문장.
10. 태그 12~15개: 지역+맛집, 지역+메뉴, 가게 이름, 인근 관광지+맛집 등. 공백 없이.
""" + COMMON_RULES

FESTIVAL_PROMPT = """너는 내 네이버 블로그 축제·행사 후기를 대신 써주는 작가다. 내가 직접 다녀온 축제의 메모와 사진으로 후기를 써라.

[글 구성] (이 순서를 기본으로, 메모에 내용이 없는 섹션은 생략)
1. 제목: '연도 + 축제 이름 + 핵심 정보(기간/주차/볼거리 등)' 30자 이내. 예) "2026 OO축제 기간, 주차, 볼거리 총정리"
2. 도입 (2~3문단): 축제를 가게 된 계기, 다녀온 날 분위기. 대표 사진 1장.
3. `## 축제 기본 정보`: 기간 / 장소 / 운영 시간 / 입장료 / 주최 등 '항목: 내용' 한 줄씩. (메모에 있는 것만)
4. `## 가는 길과 주차·셔틀`: 대중교통, 주차장 위치와 혼잡도, 셔틀 정보.
5. `## 볼거리와 프로그램`: 주요 행사, 공연, 체험, 포토존. 사진과 함께.
6. `## 먹거리와 특산물`: 먹어본 것, 가격, 맛.
7. `## 방문 꿀팁`: 붐비는 시간, 준비물, 아이/반려동물 동반 팁 등.
8. `## 다녀온 총평`: 좋았던 점과 아쉬운 점, 추천 대상.
9. 마무리 한두 문장.
10. 태그 12~15개: 축제 이름, 지역+축제, 지역+가볼만한곳, 월+축제(예: 10월축제) 등. 공백 없이.
""" + COMMON_RULES

TOPIC_PROMPT = """너는 네이버 블로그 글을 쓰는 작가다. 아래 주제로 정보성 글을 한국어로 작성해라.

- 주제: {topic}
- 핵심 키워드: {keywords}

규칙:
1. 제목은 핵심 키워드를 앞쪽에 넣고 30자 이내.
2. 본문은 1500~2500자, 소제목(## ) 3~5개, 문단은 2~3문장으로 짧게.
3. 확실하지 않은 사실은 쓰지 말고, 과장 광고나 허위 정보는 쓰지 말 것.
4. 마지막에 한 줄 요약과 독자에게 던지는 질문.
5. 태그는 5~10개.

출력 형식(이 형식 그대로, 다른 말 없이):
---
title: 제목
tags: 태그1, 태그2, 태그3
---
본문
"""


def encode_photo(path: Path):
    """Claude 에 보낼 수 있도록 긴 변 1024px JPEG 로 줄여 base64 인코딩."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("사진 처리를 위해 `pip install pillow` 를 실행하세요.")
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode()


def build_visit_content(kind: str, folder: Path):
    memo_path = folder / "memo.txt"
    if not memo_path.exists():
        sys.exit(f"{memo_path} 가 없습니다. templates/ 폴더의 양식을 복사해서 직접 다녀온 내용을 적어주세요.")
    memo = memo_path.read_text(encoding="utf-8").strip()

    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in PHOTO_EXTS)
    heic = [p.name for p in folder.iterdir() if p.suffix.lower() == ".heic"]
    if heic:
        print(f"[경고] HEIC 사진은 지원하지 않아 제외합니다(JPG로 변환 필요): {', '.join(heic)}")
    if len(photos) > MAX_PHOTOS:
        print(f"[경고] 사진이 {len(photos)}장이라 앞의 {MAX_PHOTOS}장만 사용합니다.")
        photos = photos[:MAX_PHOTOS]

    reference_path = folder / "reference.txt"
    reference = reference_path.read_text(encoding="utf-8").strip() if reference_path.exists() else ""

    prompt = FOOD_PROMPT if kind == "food" else FESTIVAL_PROMPT
    content = [{"type": "text", "text": prompt}]
    guide_path = BASE_DIR / "references" / f"{kind}_style_guide.md"
    if guide_path.exists():
        content.append({"type": "text", "text":
                        "[스타일 가이드] 사진 배치·문단 길이·강조·태그는 이 가이드를 따르라. "
                        "가이드의 예시 가게는 가상의 예시일 뿐이니 내용에 쓰지 마라.\n"
                        + guide_path.read_text(encoding="utf-8")})
    if reference:
        content.append({"type": "text", "text":
                        "[참고 글] (구성과 말투만 참고. 문장·표현·사실을 가져오지 말 것)\n" + reference})
    content.append({"type": "text", "text": "[내 메모]\n" + memo})
    content.append({"type": "text", "text": f"[내 사진] {len(photos)}장. 각 사진 위의 경로를 그대로 사용하라."})
    for p in photos:
        rel = p.resolve().relative_to(BASE_DIR).as_posix()
        content.append({"type": "text", "text": f"사진 경로: {rel}"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": encode_photo(p)}})
    return content, photos, reference


def call_claude(content):
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
    msg = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=8000,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    # 코드블록으로 감싸 오는 경우 제거
    return re.sub(r"^```\w*\n|\n```$", "", text).strip()


def main():
    load_env()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="kind", required=True)
    for kind in ("food", "festival"):
        sp = sub.add_parser(kind)
        sp.add_argument("folder", type=Path, help="visits/ 아래 방문 폴더")
        sp.add_argument("--dry-run", action="store_true")
    sp = sub.add_parser("topic")
    sp.add_argument("topic")
    sp.add_argument("--keywords", default="")
    sp.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    reference = ""
    if args.kind == "topic":
        name = args.topic
        content = [{"type": "text", "text": TOPIC_PROMPT.format(
            topic=args.topic, keywords=args.keywords or args.topic)}]
    else:
        folder = args.folder if args.folder.is_absolute() else (Path.cwd() / args.folder)
        if not folder.is_dir():
            sys.exit(f"폴더가 없습니다: {folder}")
        name = folder.name
        content, photos, reference = build_visit_content(args.kind, folder)
        print(f"메모 + 사진 {len(photos)}장" + (" + 참고 글" if reference else "") + " 으로 작성합니다.")

    if args.dry_run:
        for c in content:
            print("[이미지]" if c["type"] == "image" else c["text"][:300])
        return

    text = call_claude(content)
    slug = re.sub(r"[^\w가-힣]+", "-", name).strip("-")[:40]
    out = POSTS_DIR / f"{datetime.date.today():%Y%m%d}-{slug}.md"
    out.write_text(text + "\n", encoding="utf-8")
    print("초안 저장:", out)

    if reference:
        similarity_report(text, reference)
    print("※ 발행 전에 꼭 직접 읽고, 사실과 다른 부분이나 내 말투와 다른 부분을 고치세요.")


if __name__ == "__main__":
    main()
