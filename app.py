import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from html import escape
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="컴퓨터전자공학과 통합 학사 다중 게시판")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "board.db")

# ---------------------------------------------------------------------------
# 1. 게시판 카테고리 및 가상 테스트 계정 정의
# ---------------------------------------------------------------------------
BOARDS = {
    "notice": {
        "code": "notice",
        "name": "공지사항",
        "desc": "컴퓨터전자공학과 공식 학사 일정 및 주요 안내사항을 전달합니다.",
        "badge": "bg-rose-100 text-rose-800 border-rose-200",
        "accent": "indigo",
    },
    "free": {
        "code": "free",
        "name": "자유게시판",
        "desc": "학과 구성원들이 자유롭게 일상과 소식을 나누는 소통 공간입니다.",
        "badge": "bg-emerald-100 text-emerald-800 border-emerald-200",
        "accent": "emerald",
    },
    "qna": {
        "code": "qna",
        "name": "Q&A게시판",
        "desc": "전공 수업, 실험·실습, 졸업요건 및 학사 관련 질의응답 공간입니다.",
        "badge": "bg-amber-100 text-amber-800 border-amber-200",
        "accent": "amber",
    },
}

USERS = {
    "ce_admin": {
        "id": "ce_admin",
        "name": "학과사무실 관리자",
        "role": "ADMIN",
        "role_label": "ADMIN (관리자)",
        "badge_class": "bg-rose-600 text-white",
    },
    "ce_202601": {
        "id": "ce_202601",
        "name": "김전자",
        "role": "USER",
        "role_label": "USER (일반학생 A)",
        "badge_class": "bg-sky-600 text-white",
    },
    "ce_202602": {
        "id": "ce_202602",
        "name": "이컴공",
        "role": "USER",
        "role_label": "USER (일반학생 B)",
        "badge_class": "bg-teal-600 text-white",
    },
}

DEFAULT_USER_ID = "ce_202601"


# ---------------------------------------------------------------------------
# 2. 데이터베이스 초기화 및 시드 데이터 자동 삽입
# ---------------------------------------------------------------------------
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_role TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute("SELECT COUNT(*) AS cnt FROM posts")
        count = cursor.fetchone()["cnt"]

        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            seed_posts = [
                (
                    "notice",
                    "[필독] 2026학년도 2학기 컴퓨터전자공학과 졸업작품 캡스톤디자인 심사 안내",
                    "안녕하세요, 컴퓨터전자공학과 사무실입니다.\n\n"
                    "2026학년도 2학기 캡스톤디자인 최종 발표 및 시연 심사 일정을 안내드립니다.\n"
                    "- 일시: 2026년 11월 25일(수) 13:00 ~ 17:30\n"
                    "- 장소: 제2공학관 402호 임베디드시스템 실습실\n"
                    "- 제출물: 최종 보고서 PDF 및 시연 영상 링크\n\n"
                    "기한 내 미제출 시 졸업 요건 심사에서 제외될 수 있으니 반드시 일정을 준수해 주시기 바랍니다.",
                    "ce_admin",
                    USERS["ce_admin"]["name"],
                    USERS["ce_admin"]["role"],
                    42,
                    now,
                    now,
                ),
                (
                    "free",
                    "이번 학기 마이크로프로세서 응용 실험 키트 같이 대여하실 분 계신가요?",
                    "STM32 보드 실습 과제를 주말 동안 진행하려고 하는데,\n"
                    "실습실 대여 신청 같이 하실 학우분 계시면 편하게 연락 주세요!\n"
                    "현재 2명 모였고 1~2분 더 모이면 같이 스터디룸 예약하려고 합니다.",
                    "ce_202601",
                    USERS["ce_202601"]["name"],
                    USERS["ce_202601"]["role"],
                    18,
                    now,
                    now,
                ),
                (
                    "free",
                    "제2공학관 3층 라운지 자판기 옆에 공학용 계산기 두고 가신 분!",
                    "오늘 오후 2시쯤 회로이론 수업 끝나고 라운지 테이블에 카시오 공학용 계산기가 놓여 있어서\n"
                    "분실 방지를 위해 학과사무실에 맡겨 두었습니다.\n"
                    "찾으시는 분은 학과사무실(301호)로 방문해 보세요!",
                    "ce_202602",
                    USERS["ce_202602"]["name"],
                    USERS["ce_202602"]["role"],
                    27,
                    now,
                    now,
                ),
                (
                    "qna",
                    "논리회로설계 과목 Verilog 시뮬레이션 환경 구축 관련 질문드립니다.",
                    "교수님께서 강의자료에 올려주신 테스트벤치 파일을 실행할 때\n"
                    "파형 출력(Waveform) 창에서 클럭 주기가 초기값 X로 유지되는 현상이 발생합니다.\n"
                    "초기 reset 신호 인가 타이밍을 어떻게 설정해야 정상 동작하는지 선배님들의 조언 부탁드립니다!",
                    "ce_202601",
                    USERS["ce_202601"]["name"],
                    USERS["ce_202601"]["role"],
                    15,
                    now,
                    now,
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO posts (
                    board, title, content, author_id, author_name, author_role, views, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                seed_posts,
            )
            conn.commit()


init_db()


# ---------------------------------------------------------------------------
# 3. 역할 기반 권한 매트릭스 (RBAC) 헬퍼 함수
# ---------------------------------------------------------------------------
def get_current_user(request: Request) -> dict:
    user_id = request.cookies.get("ce_user_id", DEFAULT_USER_ID)
    if user_id not in USERS:
        user_id = DEFAULT_USER_ID
    return USERS[user_id]


def can_write_board(user: dict, board_code: str) -> bool:
    """공지사항(notice)은 관리자(ADMIN)만 작성 가능, 자유/Q&A는 모든 계정 작성 가능."""
    if board_code == "notice":
        return user["role"] == "ADMIN"
    return board_code in ("free", "qna")


def can_modify_post(user: dict, post: sqlite3.Row) -> bool:
    """
    - 관리자(ADMIN): 모든 게시판의 본인/타인 글 수정 및 삭제 가능
    - 일반학생(USER): 공지사항 수정/삭제 불가, 자유/Q&A 게시판의 본인 작성 글만 수정/삭제 가능
    """
    if user["role"] == "ADMIN":
        return True
    if post["board"] == "notice":
        return False
    return post["author_id"] == user["id"]


# ---------------------------------------------------------------------------
# 4. 공통 UI 레이아웃 및 403 Forbidden 전용 렌더링
# ---------------------------------------------------------------------------
def render_layout(
    title: str,
    user: dict,
    active_board: str,
    body_html: str,
    current_path: str = "/",
) -> str:
    # 상단 원클릭 계정 스위칭 버튼
    switcher_buttons = []
    for uid, uinfo in USERS.items():
        is_current = uid == user["id"]
        btn_style = (
            "bg-slate-900 text-white ring-2 ring-indigo-400 font-semibold shadow-sm"
            if is_current
            else "bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium"
        )
        role_dot = (
            "bg-rose-400" if uinfo["role"] == "ADMIN" else "bg-sky-400"
        )
        switcher_buttons.append(
            f"""
            <a href="/switch-user/{uid}?next={escape(current_path, quote=True)}"
               class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition {btn_style}">
                <span class="w-2 h-2 rounded-full {role_dot}"></span>
                <span>{escape(uinfo['name'])}</span>
                <span class="opacity-75">({escape(uinfo['id'])})</span>
            </a>
            """
        )

    # 카테고리 탭 네비게이션
    nav_tabs = []
    for bcode, binfo in BOARDS.items():
        is_active = bcode == active_board
        tab_cls = (
            "border-indigo-600 text-indigo-600 font-bold bg-indigo-50/60"
            if is_active
            else "border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300 font-medium"
        )
        lock_badge = (
            '<span class="ml-1.5 text-[11px] px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 font-semibold">ADMIN 전용작성</span>'
            if bcode == "notice"
            else ""
        )
        nav_tabs.append(
            f"""
            <a href="/?board={bcode}"
               class="inline-flex items-center py-3.5 px-5 border-b-2 text-sm transition {tab_cls}">
                {escape(binfo['name'])}
                {lock_badge}
            </a>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape(title)} - 컴퓨터전자공학과 통합 학사 다중 게시판</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 text-slate-800 flex flex-col">
    <!-- 상단 헤더 & 원클릭 계정 스위칭 바 -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-xs">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div class="flex items-center gap-3">
                <a href="/?board={escape(active_board)}" class="flex items-center gap-2.5 group">
                    <div class="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-extrabold text-sm shadow-xs group-hover:bg-indigo-700 transition">
                        CE
                    </div>
                    <div>
                        <h1 class="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                            컴퓨터전자공학과 통합 학사 다중 게시판
                        </h1>
                        <p class="text-xs text-slate-500">
                            Department of Computer &amp; Electronic Engineering Multi-Board System
                        </p>
                    </div>
                </a>
            </div>

            <!-- 현재 로그인 계정 표시 및 원클릭 계정 전환 -->
            <div class="flex flex-wrap items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl p-2">
                <div class="flex items-center gap-1.5 pr-2 border-r border-slate-200">
                    <span class="text-xs text-slate-500">현재 계정:</span>
                    <span class="px-2 py-0.5 rounded text-xs font-bold {user['badge_class']}">
                        {escape(user['name'])} ({escape(user['role'])})
                    </span>
                </div>
                <div class="flex flex-wrap items-center gap-1">
                    <span class="text-[11px] text-slate-400 mr-1">원클릭 전환:</span>
                    {''.join(switcher_buttons)}
                </div>
            </div>
        </div>

        <!-- 게시판 카테고리 탭 (3종) -->
        <div class="max-w-6xl mx-auto px-4 sm:px-6 border-t border-slate-100 flex items-center justify-between">
            <nav class="flex -mb-px space-x-1 overflow-x-auto">
                {''.join(nav_tabs)}
            </nav>
            <div class="hidden sm:flex items-center gap-2 text-xs text-slate-500">
                <span>권한 테스트 URL:</span>
                <a href="/write?board=notice" class="text-rose-600 hover:underline font-medium">
                    /write?board=notice 직접 진입 테스트
                </a>
            </div>
        </div>
    </header>

    <!-- 메인 컨텐츠 영역 -->
    <main class="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
        {body_html}
    </main>

    <!-- 하단 푸터 -->
    <footer class="bg-white border-t border-slate-200 py-5 mt-12">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
            <div>© 2026 컴퓨터전자공학과 학사 시스템 (Multi-Board RBAC Engine)</div>
            <div>계정 권한: 관리자(ce_admin: 전 게시판 제어) | 학생(ce_202601, ce_202602: 공지 조회 전용 / 자유·Q&amp;A 본인글 제어)</div>
        </div>
    </footer>
</body>
</html>"""


def render_403_response(
    request: Request,
    user: dict,
    board_code: str = "notice",
    detail_reason: str = "",
) -> HTMLResponse:
    if board_code not in BOARDS:
        board_code = "notice"
    extra_html = (
        f'<p class="mt-2 text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 inline-block">{escape(detail_reason)}</p>'
        if detail_reason
        else ""
    )
    body = f"""
    <div class="max-w-xl mx-auto mt-8 bg-white border-2 border-rose-200 rounded-2xl shadow-sm p-8 text-center">
        <div class="w-16 h-16 mx-auto mb-5 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-9 h-9" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
        </div>
        <span class="inline-block px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-700 mb-3">
            HTTP 403 FORBIDDEN · RBAC ACCESS DENIED
        </span>
        <h2 class="text-xl sm:text-2xl font-extrabold text-slate-900 mb-3">
            접속할 수 있는 권한이 없습니다. (403 Forbidden)
        </h2>
        <p class="text-sm sm:text-base text-slate-600 leading-relaxed">
            해당 게시판의 쓰기/수정 권한이 없거나, 접근이 제한된 구역입니다.
        </p>
        {extra_html}
        <div class="mt-6 pt-5 border-t border-slate-100 text-xs text-slate-500 space-y-1">
            <div>현재 접속 계정: <strong class="text-slate-800">{escape(user['name'])} ({escape(user['id'])} / 역할: {escape(user['role'])})</strong></div>
            <div>대상 게시판: <strong class="text-slate-800">{escape(BOARDS[board_code]['name'])} ({escape(board_code)})</strong></div>
        </div>
        <div class="mt-7 flex items-center justify-center gap-3">
            <a href="/?board={escape(board_code)}"
               class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold transition shadow-xs">
                ← 이전 목록으로 돌아가기
            </a>
        </div>
    </div>
    """
    current_url = str(request.url.path)
    if request.url.query:
        current_url += f"?{request.url.query}"
    html = render_layout(
        title="403 Forbidden - 권한 없음",
        user=user,
        active_board=board_code,
        body_html=body,
        current_path=current_url,
    )
    return HTMLResponse(content=html, status_code=403)


# ---------------------------------------------------------------------------
# 5. 라우터 엔드포인트 구현
# ---------------------------------------------------------------------------
@app.get("/switch-user/{user_id}")
def switch_user(user_id: str, next: str = Query(default="/")):
    if user_id not in USERS:
        raise HTTPException(status_code=400, detail="존재하지 않는 테스트 계정입니다.")
    if not next.startswith("/"):
        next = "/"
    response = RedirectResponse(url=next, status_code=303)
    response.set_cookie(key="ce_user_id", value=user_id, path="/", max_age=60 * 60 * 24 * 7)
    return response


@app.get("/", response_class=HTMLResponse)
def list_posts(request: Request, board: str = Query(default="notice")):
    if board not in BOARDS:
        board = "notice"
    user = get_current_user(request)
    board_meta = BOARDS[board]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM posts WHERE board = ? ORDER BY id DESC",
            (board,),
        )
        posts = cursor.fetchall()

        # 카테고리별 게시글 수 집계
        cursor.execute("SELECT board, COUNT(*) AS cnt FROM posts GROUP BY board")
        counts = {row["board"]: row["cnt"] for row in cursor.fetchall()}

    # UI 글쓰기 버튼 노출 여부 (공지사항에서 일반학생에게는 숨김)
    write_button_html = ""
    if can_write_board(user, board):
        write_button_html = f"""
        <a href="/write?board={escape(board)}"
           class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold shadow-xs transition">
            <span>+ 새 게시글 작성</span>
        </a>
        """
    else:
        write_button_html = """
        <div class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 text-slate-500 text-xs font-medium border border-slate-200">
            <span>🔒 공지사항은 관리자(ADMIN)만 작성할 수 있습니다 (조회 전용)</span>
        </div>
        """

    rows_html = []
    if not posts:
        rows_html.append(
            """
            <tr>
                <td colspan="5" class="px-6 py-12 text-center text-sm text-slate-400">
                    등록된 게시글이 없습니다. 첫 번째 게시글을 작성해 보세요!
                </td>
            </tr>
            """
        )
    else:
        for post in posts:
            is_owner = post["author_id"] == user["id"]
            can_mod = can_modify_post(user, post)
            role_pill = (
                '<span class="ml-1.5 px-1.5 py-0.5 text-[10px] font-bold rounded bg-rose-100 text-rose-700">ADMIN</span>'
                if post["author_role"] == "ADMIN"
                else '<span class="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-100 text-slate-600">학부생</span>'
            )
            perm_hint = ""
            if can_mod:
                if is_owner:
                    perm_hint = '<span class="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">내 작성글 (수정/삭제 가능)</span>'
                elif user["role"] == "ADMIN":
                    perm_hint = '<span class="ml-2 text-[11px] px-2 py-0.5 rounded-full bg-rose-50 text-rose-600 font-medium">관리자 권한 제어 가능</span>'

            rows_html.append(
                f"""
                <tr class="hover:bg-slate-50/90 transition">
                    <td class="px-5 py-4 text-xs font-mono text-slate-500 whitespace-nowrap">#{post['id']}</td>
                    <td class="px-5 py-4">
                        <a href="/post/{post['id']}" class="text-sm font-semibold text-slate-900 hover:text-indigo-600 transition">
                            {escape(post['title'])}
                        </a>
                        {perm_hint}
                    </td>
                    <td class="px-5 py-4 text-xs text-slate-700 whitespace-nowrap">
                        <span class="font-medium">{escape(post['author_name'])}</span>
                        <span class="text-slate-400">({escape(post['author_id'])})</span>
                        {role_pill}
                    </td>
                    <td class="px-5 py-4 text-xs text-slate-500 whitespace-nowrap">{escape(post['created_at'])}</td>
                    <td class="px-5 py-4 text-xs text-slate-500 text-right whitespace-nowrap">{post['views']}</td>
                </tr>
                """
            )

    # 상단 요약 카드 (3종 게시판 현황)
    summary_cards = []
    for bcode, binfo in BOARDS.items():
        cnt = counts.get(bcode, 0)
        active_ring = (
            "ring-2 ring-indigo-600 bg-white"
            if bcode == board
            else "bg-white/80 hover:bg-white"
        )
        summary_cards.append(
            f"""
            <a href="/?board={bcode}" class="block p-4 rounded-xl border border-slate-200 transition shadow-2xs {active_ring}">
                <div class="flex items-center justify-between mb-1">
                    <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border {binfo['badge']}">
                        {escape(binfo['name'])}
                    </span>
                    <span class="text-xs font-semibold text-slate-500">총 {cnt}건</span>
                </div>
                <p class="text-xs text-slate-600 mt-1.5 line-clamp-1">{escape(binfo['desc'])}</p>
            </a>
            """
        )

    body = f"""
    <!-- 카테고리 요약 그리드 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {''.join(summary_cards)}
    </div>

    <!-- 게시판 헤더 -->
    <div class="bg-white border border-slate-200 rounded-2xl p-6 mb-6 shadow-2xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
            <div class="flex items-center gap-2 mb-1">
                <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border {board_meta['badge']}">
                    {escape(board_meta['name'])}
                </span>
                <span class="text-xs text-slate-400 font-mono">board={escape(board)}</span>
            </div>
            <h2 class="text-xl font-bold text-slate-900">{escape(board_meta['name'])}</h2>
            <p class="text-sm text-slate-600 mt-0.5">{escape(board_meta['desc'])}</p>
        </div>
        <div class="shrink-0">
            {write_button_html}
        </div>
    </div>

    <!-- 게시글 목록 테이블 -->
    <div class="bg-white border border-slate-200 rounded-2xl shadow-2xs overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase">
                        <th class="px-5 py-3.5 w-20">번호</th>
                        <th class="px-5 py-3.5">제목</th>
                        <th class="px-5 py-3.5 w-52">작성자</th>
                        <th class="px-5 py-3.5 w-36">작성일시</th>
                        <th class="px-5 py-3.5 w-20 text-right">조회수</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
    </div>
    """

    html = render_layout(
        title=board_meta["name"],
        user=user,
        active_board=board,
        body_html=body,
        current_path=f"/?board={board}",
    )
    return HTMLResponse(content=html)


@app.get("/post/{post_id}", response_class=HTMLResponse)
def view_post(request: Request, post_id: int):
    user = get_current_user(request)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        cursor.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
        conn.commit()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()

    board_code = post["board"]
    board_meta = BOARDS.get(board_code, BOARDS["free"])
    can_mod = can_modify_post(user, post)

    # 수정/삭제 버튼 영역 (권한 보유 시 활성화 + 비인가 강제 테스트 버튼도 함께 안내 가능)
    if can_mod:
        admin_notice = (
            '<span class="text-xs text-rose-600 font-semibold mr-2">★ 관리자 권한으로 제어 가능</span>'
            if (user["role"] == "ADMIN" and post["author_id"] != user["id"])
            else ""
        )
        action_buttons = f"""
        <div class="flex flex-wrap items-center gap-2">
            {admin_notice}
            <a href="/edit/{post['id']}"
               class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition">
                수정하기
            </a>
            <form method="post" action="/delete/{post['id']}" onsubmit="return confirm('이 게시글을 삭제하시겠습니까?');" class="inline">
                <button type="submit"
                        class="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition cursor-pointer">
                    삭제하기
                </button>
            </form>
        </div>
        """
    else:
        action_buttons = f"""
        <div class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-slate-400 mr-1">권한 없음 (비인가 403 차단 테스트):</span>
            <a href="/edit/{post['id']}"
               class="px-3 py-1.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 text-xs font-medium transition">
                강제 수정 URL 진입 (403 테스트)
            </a>
            <form method="post" action="/delete/{post['id']}" class="inline">
                <button type="submit"
                        class="px-3 py-1.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 text-xs font-medium transition cursor-pointer">
                    강제 삭제 API 호출 (403 테스트)
                </button>
            </form>
        </div>
        """

    formatted_content = escape(post["content"]).replace("\n", "<br/>")

    body = f"""
    <div class="bg-white border border-slate-200 rounded-2xl shadow-2xs overflow-hidden">
        <!-- 상단 메타 영역 -->
        <div class="p-6 sm:p-8 border-b border-slate-100">
            <div class="flex items-center gap-2 mb-3">
                <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border {board_meta['badge']}">
                    {escape(board_meta['name'])}
                </span>
                <span class="text-xs text-slate-400 font-mono">글번호 #{post['id']}</span>
            </div>
            <h2 class="text-xl sm:text-2xl font-bold text-slate-900 mb-4">
                {escape(post['title'])}
            </h2>
            <div class="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 pt-3 border-t border-slate-100">
                <div class="flex items-center gap-3">
                    <span>작성자: <strong class="text-slate-800">{escape(post['author_name'])} ({escape(post['author_id'])})</strong></span>
                    <span>·</span>
                    <span>역할: <strong class="text-slate-700">{escape(post['author_role'])}</strong></span>
                </div>
                <div class="flex items-center gap-3">
                    <span>작성일: {escape(post['created_at'])}</span>
                    <span>·</span>
                    <span>수정일: {escape(post['updated_at'])}</span>
                    <span>·</span>
                    <span>조회 {post['views']}</span>
                </div>
            </div>
        </div>

        <!-- 본문 영역 -->
        <div class="p-6 sm:p-8 min-h-[220px] text-sm sm:text-base text-slate-800 leading-relaxed">
            {formatted_content}
        </div>

        <!-- 하단 버튼 바 -->
        <div class="px-6 sm:px-8 py-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <a href="/?board={escape(board_code)}"
               class="px-4 py-2 rounded-xl bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition">
                ← 목록으로 돌아가기
            </a>
            {action_buttons}
        </div>
    </div>
    """

    html = render_layout(
        title=post["title"],
        user=user,
        active_board=board_code,
        body_html=body,
        current_path=f"/post/{post_id}",
    )
    return HTMLResponse(content=html)


@app.get("/write", response_class=HTMLResponse)
def write_form(request: Request, board: str = Query(default="free")):
    if board not in BOARDS:
        board = "free"
    user = get_current_user(request)

    # RBAC 검증: 학생이 /write?board=notice 직접 진입 시 403 차단
    if not can_write_board(user, board):
        return render_403_response(
            request=request,
            user=user,
            board_code=board,
            detail_reason=f"일반학생({user['id']}) 계정으로는 공지사항(notice) 작성 페이지에 접근할 수 없습니다.",
        )

    board_meta = BOARDS[board]

    # 게시판 선택 옵션 (학생일 경우 공지사항은 비활성화 안내)
    options_html = []
    for bcode, binfo in BOARDS.items():
        selected = "selected" if bcode == board else ""
        disabled = "disabled" if not can_write_board(user, bcode) else ""
        suffix = " (관리자 전용)" if bcode == "notice" and user["role"] != "ADMIN" else ""
        options_html.append(
            f'<option value="{bcode}" {selected} {disabled}>{escape(binfo["name"])}{suffix}</option>'
        )

    body = f"""
    <div class="max-w-3xl mx-auto bg-white border border-slate-200 rounded-2xl shadow-2xs p-6 sm:p-8">
        <div class="mb-6 pb-4 border-b border-slate-100">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border {board_meta['badge']}">
                {escape(board_meta['name'])}
            </span>
            <h2 class="text-xl font-bold text-slate-900 mt-2">새 게시글 작성</h2>
            <p class="text-xs text-slate-500 mt-1">
                작성자: <strong>{escape(user['name'])} ({escape(user['id'])} / {escape(user['role'])})</strong>
            </p>
        </div>

        <form method="post" action="/write" class="space-y-5">
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">게시판 카테고리</label>
                <select name="board" class="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    {''.join(options_html)}
                </select>
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">제목</label>
                <input type="text" name="title" required maxlength="150"
                       placeholder="제목을 입력하세요"
                       class="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">본문 내용</label>
                <textarea name="content" rows="9" required
                          placeholder="내용을 입력하세요"
                          class="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"></textarea>
            </div>
            <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <a href="/?board={escape(board)}"
                   class="px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 text-xs font-semibold transition">
                    취소
                </a>
                <button type="submit"
                        class="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition cursor-pointer">
                    게시글 등록
                </button>
            </div>
        </form>
    </div>
    """

    html = render_layout(
        title=f"{board_meta['name']} 글쓰기",
        user=user,
        active_board=board,
        body_html=body,
        current_path=f"/write?board={board}",
    )
    return HTMLResponse(content=html)


@app.post("/write", response_class=HTMLResponse)
def create_post(
    request: Request,
    board: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    if board not in BOARDS:
        raise HTTPException(status_code=400, detail="유효하지 않은 게시판 카테고리입니다.")
    user = get_current_user(request)

    # RBAC 검증: 학생이 공지사항에 POST 강제 요청 시 403 차단
    if not can_write_board(user, board):
        return render_403_response(
            request=request,
            user=user,
            board_code=board,
            detail_reason=f"일반학생({user['id']}) 계정으로는 공지사항에 글을 등록할 수 없습니다.",
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts (
                board, title, content, author_id, author_name, author_role, views, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                board,
                title.strip(),
                content.strip(),
                user["id"],
                user["name"],
                user["role"],
                now,
                now,
            ),
        )
        new_id = cursor.lastrowid
        conn.commit()

    return RedirectResponse(url=f"/post/{new_id}", status_code=303)


@app.get("/edit/{post_id}", response_class=HTMLResponse)
def edit_form(request: Request, post_id: int):
    user = get_current_user(request)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()

    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    board_code = post["board"]
    if not can_modify_post(user, post):
        return render_403_response(
            request=request,
            user=user,
            board_code=board_code,
            detail_reason=f"작성자({post['author_name']} / {post['author_id']}) 본인 또는 관리자(ADMIN)만 수정할 수 있습니다.",
        )

    board_meta = BOARDS.get(board_code, BOARDS["free"])
    body = f"""
    <div class="max-w-3xl mx-auto bg-white border border-slate-200 rounded-2xl shadow-2xs p-6 sm:p-8">
        <div class="mb-6 pb-4 border-b border-slate-100">
            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border {board_meta['badge']}">
                {escape(board_meta['name'])}
            </span>
            <h2 class="text-xl font-bold text-slate-900 mt-2">게시글 수정 (#{post['id']})</h2>
            <p class="text-xs text-slate-500 mt-1">
                원 작성자: <strong>{escape(post['author_name'])} ({escape(post['author_id'])})</strong> ·
                현재 수정 수행 계정: <strong>{escape(user['name'])} ({escape(user['role'])})</strong>
            </p>
        </div>

        <form method="post" action="/edit/{post['id']}" class="space-y-5">
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">제목</label>
                <input type="text" name="title" required maxlength="150"
                       value="{escape(post['title'], quote=True)}"
                       class="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1.5">본문 내용</label>
                <textarea name="content" rows="9" required
                          class="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">{escape(post['content'])}</textarea>
            </div>
            <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <a href="/post/{post['id']}"
                   class="px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 text-xs font-semibold transition">
                    취소
                </a>
                <button type="submit"
                        class="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition cursor-pointer">
                    수정 완료
                </button>
            </div>
        </form>
    </div>
    """

    html = render_layout(
        title=f"게시글 수정 - {post['title']}",
        user=user,
        active_board=board_code,
        body_html=body,
        current_path=f"/edit/{post_id}",
    )
    return HTMLResponse(content=html)


@app.post("/edit/{post_id}", response_class=HTMLResponse)
def update_post(
    request: Request,
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
):
    user = get_current_user(request)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        if not can_modify_post(user, post):
            return render_403_response(
                request=request,
                user=user,
                board_code=post["board"],
                detail_reason=f"타인({post['author_name']})이 작성한 게시글을 수정할 권한이 없습니다.",
            )

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "UPDATE posts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title.strip(), content.strip(), now, post_id),
        )
        conn.commit()

    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


@app.post("/delete/{post_id}", response_class=HTMLResponse)
def delete_post(request: Request, post_id: int):
    user = get_current_user(request)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()

        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        board_code = post["board"]
        if not can_modify_post(user, post):
            return render_403_response(
                request=request,
                user=user,
                board_code=board_code,
                detail_reason=f"타인({post['author_name']})이 작성한 게시글을 삭제할 권한이 없습니다.",
            )

        cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()

    return RedirectResponse(url=f"/?board={board_code}", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
