"""
네이버 블로그(스마트에디터 ONE)에 글을 올립니다.

    python post.py posts/글.md                # 임시저장(기본, 가장 안전)
    python post.py posts/글.md --publish      # 바로 발행
    python post.py --next --publish           # posts/ 에서 가장 오래된 글 1개 발행 후 done/ 으로 이동
    python post.py --next --publish --jitter 30   # 0~30분 랜덤 대기 후 실행 (스케줄러용)

먼저 login.py 로 로그인 세션을 만들어 두어야 합니다.
"""
import argparse
import os
import random
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from common import BASE_DIR, DONE_DIR, POSTS_DIR, PROFILE_DIR, load_env, parse_post


def pause(a=0.4, b=1.2):
    time.sleep(random.uniform(a, b))


def click_if_visible(scope, selector, timeout=2000):
    try:
        scope.locator(selector).first.click(timeout=timeout)
        return True
    except (PWTimeout, PWError):
        return False


def open_editor(page, blog_id):
    page.goto(f"https://blog.naver.com/{blog_id}?Redirect=Write", wait_until="domcontentloaded")
    if "nid.naver.com" in page.url:
        sys.exit("로그인 세션이 없습니다. 먼저 `python login.py` 를 실행하세요.")

    # 에디터는 보통 iframe#mainFrame 안에 뜬다
    editor = page
    try:
        page.wait_for_selector("iframe#mainFrame", timeout=10000)
        editor = page.frame_locator("iframe#mainFrame")
    except PWTimeout:
        pass
    editor.locator(".se-content, .se-documentTitle").first.wait_for(timeout=30000)
    pause(1.5, 2.5)

    # "작성 중인 글이 있습니다" → 취소(새 글), 도움말 패널 닫기
    click_if_visible(editor, ".se-popup-button-cancel")
    click_if_visible(editor, ".se-help-panel-close-button")
    return editor


def type_text(page, text):
    """한 줄씩 입력. 빈 줄은 문단 띄우기."""
    if text:
        page.keyboard.insert_text(text)
    page.keyboard.press("Enter")
    pause(0.05, 0.25)


def insert_image(page, editor, img_path: Path):
    if not img_path.exists():
        print(f"  [경고] 이미지 없음, 건너뜀: {img_path}")
        return
    with page.expect_file_chooser(timeout=10000) as fc:
        editor.locator("button.se-image-toolbar-button, button[data-name='image']").first.click()
    fc.value.set_files(str(img_path))
    # 업로드가 끝나 이미지 컴포넌트가 생길 때까지 대기
    editor.locator(".se-component.se-image").last.wait_for(timeout=60000)
    pause(1.5, 2.5)
    # 이미지 아래에 이어서 쓸 수 있도록 커서를 다음 문단으로
    last = editor.locator(".se-component").last
    if "se-text" not in (last.get_attribute("class") or ""):
        last.click()
        page.keyboard.press("Enter")
    else:
        last.locator(".se-text-paragraph").last.click()
    pause()


def fill_post(page, editor, post):
    # 제목
    editor.locator(".se-documentTitle .se-text-paragraph, .se-title-text").first.click()
    pause()
    page.keyboard.insert_text(post.title)
    pause()

    # 본문 첫 문단
    editor.locator(".se-component.se-text .se-text-paragraph, .se-section-text").first.click()
    pause()

    for kind, value in post.blocks:
        if kind == "image":
            insert_image(page, editor, value)
        else:
            type_text(page, value)


def save_draft(editor):
    editor.locator("button[class*='save_btn'], button:has-text('저장')").first.click()
    pause(2, 3)
    print("임시저장 완료 → 블로그 '글쓰기 > 임시저장 글'에서 확인 후 발행하세요.")


def publish(page, editor, tags):
    editor.locator("button[class*='publish_btn']").first.click()
    pause(1, 2)

    # 발행 설정 레이어에서 태그 입력
    if tags:
        tag_input = editor.locator("#tag-input, input[placeholder*='태그']").first
        try:
            tag_input.click(timeout=5000)
            for t in tags[:30]:
                page.keyboard.insert_text(t)
                page.keyboard.press("Enter")
                pause(0.2, 0.5)
        except PWTimeout:
            print("  [경고] 태그 입력란을 찾지 못해 태그 없이 발행합니다.")

    editor.locator(
        "button[data-testid='seOnePublishBtn'], button[class*='confirm_btn']"
    ).first.click()
    page.wait_for_url("**/PostView**", timeout=30000)
    print("발행 완료:", page.url)


def pick_next():
    files = sorted(POSTS_DIR.glob("*.md"))
    if not files:
        sys.exit("posts/ 폴더에 올릴 글(.md)이 없습니다.")
    return files[0]


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="올릴 글 파일(.md)")
    ap.add_argument("--next", action="store_true", help="posts/ 에서 가장 오래된 글 선택")
    ap.add_argument("--publish", action="store_true", help="임시저장 대신 바로 발행")
    ap.add_argument("--headless", action="store_true", help="브라우저 창 숨기기")
    ap.add_argument("--jitter", type=int, default=0, help="실행 전 0~N분 랜덤 대기")
    args = ap.parse_args()

    blog_id = os.environ.get("NAVER_BLOG_ID")
    if not blog_id:
        sys.exit(".env 에 NAVER_BLOG_ID 를 설정하세요. (blog.naver.com/아이디 의 '아이디')")

    path = pick_next() if args.next else Path(args.file or "")
    if not path.is_file():
        sys.exit("글 파일을 지정하거나 --next 를 사용하세요.")
    post = parse_post(path)

    if args.jitter:
        wait = random.randint(0, args.jitter * 60)
        print(f"{wait // 60}분 {wait % 60}초 대기 후 실행합니다...")
        time.sleep(wait)

    print(f"'{post.title}' ({'발행' if args.publish else '임시저장'})")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=args.headless, locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            editor = open_editor(page, blog_id)
            fill_post(page, editor, post)
            if args.publish:
                publish(page, editor, post.tags)
            else:
                save_draft(editor)
        except Exception:
            shot = BASE_DIR / "error.png"
            page.screenshot(path=str(shot), full_page=True)
            print("실패! 화면 캡처:", shot)
            raise
        finally:
            ctx.close()

    if args.publish and path.parent == POSTS_DIR:
        DONE_DIR.mkdir(exist_ok=True)
        shutil.move(str(path), DONE_DIR / path.name)
        print("글 파일을 posts/done/ 으로 옮겼습니다.")


if __name__ == "__main__":
    main()
