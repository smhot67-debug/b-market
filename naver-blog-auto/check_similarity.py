"""
내 글이 참고한 글(레퍼런스)과 얼마나 겹치는지 검사합니다.
네이버는 다른 글과 문장이 많이 겹치면 '유사문서'로 판단해 검색에서 누락시킬 수 있습니다.

    python check_similarity.py posts/내글.md visits/가게/reference.txt
"""
import re
import sys
from pathlib import Path

N = 6                 # 글자 6개 단위로 비교 (띄어쓰기·문장부호 무시)
WARN_TOTAL = 0.15     # 전체 겹침 15% 이상이면 경고
WARN_SENTENCE = 0.5   # 한 문장의 절반 이상이 겹치면 그 문장 표시


def _norm(text: str) -> str:
    return re.sub(r"[^\w가-힣]", "", text)


def _grams(text: str) -> set:
    t = _norm(text)
    return {t[i:i + N] for i in range(len(t) - N + 1)}


def _body_lines(md: str) -> list:
    md = re.sub(r"^---\s*\n.*?\n---\s*\n", "", md, flags=re.S)  # front matter 제거
    lines = []
    for line in md.splitlines():
        line = line.strip()
        if not line or line.startswith("![") or re.fullmatch(r"-{3,}", line):
            continue
        lines.append(re.sub(r"^#+\s*|\*\*|__", "", line))
    return lines


def _sentences(lines):
    for line in lines:
        for s in re.split(r"(?<=[.!?~])\s+", line):
            if len(_norm(s)) >= 15:
                yield s


def check(draft_text: str, reference_text: str):
    """(전체 겹침 비율, [(겹침 비율, 문장), ...]) 반환."""
    lines = _body_lines(draft_text)
    ref = _grams(reference_text)
    mine = _grams(" ".join(lines))
    total = len(mine & ref) / len(mine) if mine else 0.0
    flagged = []
    for s in _sentences(lines):
        g = _grams(s)
        ratio = len(g & ref) / len(g)
        if ratio >= WARN_SENTENCE:
            flagged.append((ratio, s))
    return total, flagged


def report(draft_text: str, reference_text: str) -> bool:
    """결과를 출력하고 통과 여부를 반환."""
    total, flagged = check(draft_text, reference_text)
    print(f"\n[유사도 검사] 레퍼런스와 겹치는 비율: {total:.0%} (기준 {WARN_TOTAL:.0%} 미만)")
    for ratio, s in flagged:
        print(f"  - {ratio:.0%} 겹침: {s}")
    ok = total < WARN_TOTAL and not flagged
    print("  → 통과" if ok else "  → 위 문장들을 직접 고쳐 쓰세요.")
    return ok


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ok = report(Path(sys.argv[1]).read_text(encoding="utf-8"),
                Path(sys.argv[2]).read_text(encoding="utf-8"))
    sys.exit(0 if ok else 1)
