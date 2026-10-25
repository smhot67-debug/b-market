"""
최초 1회 실행: 브라우저 창이 뜨면 직접 네이버에 로그인하세요.
로그인 상태는 .naver-profile 폴더에 저장되어 이후 post.py 가 그대로 사용합니다.
(아이디/비밀번호를 코드에 저장하지 않으므로 캡차·보안 차단을 피할 수 있습니다)
"""
from playwright.sync_api import sync_playwright

from common import PROFILE_DIR


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        print("브라우저에서 네이버 로그인을 완료하세요. ('로그인 상태 유지' 체크 권장)")
        input("로그인이 끝났으면 여기서 Enter 를 누르세요... ")
        page.goto("https://blog.naver.com/")
        print("로그인 세션 저장 완료:", PROFILE_DIR)
        ctx.close()


if __name__ == "__main__":
    main()
