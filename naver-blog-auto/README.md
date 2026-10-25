# 네이버 블로그 자동 포스팅

AI로 글 초안을 만들고(선택), 브라우저 자동화(Playwright)로 내 네이버 블로그에 **임시저장 또는 발행**까지 하는 도구입니다.

> 네이버의 공식 "블로그 글쓰기 API"는 종료되어서, 사람이 글을 쓰는 것처럼 브라우저를 대신 조작하는 방식을 씁니다.
> **반드시 내 PC에서 실행하세요.** 클라우드 서버에서 로그인하면 네이버 보안에 막힙니다.

## 1. 설치 (최초 1회)

Python 3.10 이상이 필요합니다.

```bash
cd naver-blog-auto
pip install -r requirements.txt
python -m playwright install chromium
```

`.env.example` 파일을 복사해서 `.env` 파일을 만들고 내용을 채웁니다.

```
NAVER_BLOG_ID=내블로그아이디        # blog.naver.com/여기부분
ANTHROPIC_API_KEY=sk-ant-...      # AI 글 생성할 때만 필요
```

## 2. 로그인 (최초 1회)

```bash
python login.py
```

브라우저 창이 뜨면 **직접** 로그인하고(로그인 상태 유지 체크), 터미널에서 Enter를 누릅니다.
아이디·비밀번호는 어디에도 저장되지 않고, 로그인 세션만 `.naver-profile/` 폴더에 남습니다.
로그인이 풀리면 이 단계만 다시 하면 됩니다.

## 3. 글 준비

`posts/` 폴더에 `.md` 파일을 넣습니다. (예시: `posts/20261025-sample.md`)

```markdown
---
title: 글 제목
tags: 태그1, 태그2, 태그3
---
## 소제목
본문 문단입니다. 빈 줄은 한 줄 띄우기가 됩니다.

![](images/사진.jpg)
```

- `## 소제목`, `**굵게**` 같은 기호는 지워지고 글자만 들어갑니다.
- `![](images/사진.jpg)` 위치에 사진이 업로드됩니다. 사진은 `images/` 폴더에 넣으세요.

**AI로 초안 만들기 (선택)**

```bash
python generate.py "제주도 3박4일 가족여행 코스" --keywords "제주도 가족여행, 제주 3박4일"
```

`posts/`에 초안이 저장됩니다. **올리기 전에 꼭 직접 읽고 고치세요.** 사진과 내 경험을 덧붙이면 훨씬 좋습니다.

## 4. 올리기

```bash
# 임시저장 (기본값, 추천) → 블로그에서 확인 후 직접 발행
python post.py posts/20261025-sample.md

# 바로 발행
python post.py posts/20261025-sample.md --publish

# posts/ 에서 파일 이름순으로 가장 앞의 글 1개를 발행하고 posts/done/ 으로 옮기기
python post.py --next --publish
```

실패하면 `error.png`에 그때 화면이 저장됩니다.

## 5. 매일 자동으로 올리기

`posts/`에 글을 여러 개 쌓아두면 하루에 1개씩 발행합니다. `--jitter 30` 옵션을 주면 매번 0~30분 사이 랜덤한 시간에 올라갑니다.

**Windows (작업 스케줄러)**
1. `작업 스케줄러` → `기본 작업 만들기`
2. 트리거: 매일, 원하는 시간
3. 동작: 프로그램 시작 → `naver-blog-auto\run_daily.bat` 선택
4. 결과는 `post.log`에 남습니다.

**Mac / Linux (cron)** — `crontab -e`에 추가:
```
0 9 * * * cd /경로/naver-blog-auto && python3 post.py --next --publish --jitter 30 >> post.log 2>&1
```

PC가 켜져 있고 로그인된 상태여야 동작합니다.

## 꼭 지켜야 할 점

- **하루 1~2개까지만** 올리세요. 짧은 시간에 많이 올리거나 AI 글을 그대로 복붙하면 저품질·누락 판정을 받을 수 있습니다.
- 처음에는 **임시저장 모드로 몇 번 확인**한 뒤 `--publish`로 바꾸세요.
- 남의 글 복사나 과장 광고는 쓰지 마세요. 네이버 운영정책 위반이 될 수 있습니다.
- 네이버가 에디터 화면을 바꾸면 버튼 위치를 못 찾을 수 있습니다. 그럴 때는 `post.py`의 선택자(`.se-...`, `publish_btn` 등)를 고쳐야 합니다. `error.png`를 같이 보내주시면 수정해 드릴게요.
