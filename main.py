import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# KOBIS API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 한국 시간대를 사용합니다.
# 배포 서버가 해외 시간대를 사용하더라도 한국 날짜를 정확히 계산합니다.
KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------
# 함수 1: 한국 시간 기준으로 어제 날짜 계산
# ---------------------------------------------------------

def get_yesterday():
    """한국 시간 기준으로 어제 날짜를 yyyymmdd 형태로 반환합니다."""
    now_kst = datetime.now(KST)
    yesterday = now_kst - timedelta(days=1)

    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# 함수 2: KOBIS API에서 박스오피스 가져오기
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_date):
    """
    같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를 사용합니다.

    ttl=3600은 3,600초, 즉 약 1시간입니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 키를 코드에 직접 적지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    # KOBIS API 요청에 사용할 파라미터입니다.
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        # KOBIS API 호출
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON 응답으로 변환합니다.
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 항목을 확인해 주세요.\n"
                "- 인터넷 연결 상태\n"
                "- KOBIS API 주소\n"
                "- KOBIS 서버 상태\n"
                "- 잠시 후 다시 시도했을 때도 같은 문제가 발생하는지\n\n"
                f"상세 오류: {e}"
            ),
            "movies": [],
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다.\n\n"
                "KOBIS 서버 상태나 API 응답 형식을 확인해 주세요."
            ),
            "movies": [],
        }

    # 인증키가 잘못된 경우에도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 반드시 faultInfo가 있는지 확인해야 합니다.
    fault_info = data.get("faultInfo")

    if fault_info:
        error_code = fault_info.get("errorCode", "알 수 없음")
        message = fault_info.get("message", "알 수 없는 API 오류")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                "다음 항목을 확인해 주세요.\n"
                "- Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 있는지\n"
                "- KOBIS 인증키가 정확한지\n"
                "- 인증키에 불필요한 공백이나 따옴표가 들어가지 않았는지\n\n"
                f"오류 코드: {error_code}\n"
                f"오류 메시지: {message}"
            ),
            "movies": [],
        }

    # 정상적인 응답에서 boxOfficeResult를 가져옵니다.
    box_office_result = data.get("boxOfficeResult")

    if not box_office_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 `boxOfficeResult`가 없습니다.\n\n"
                "조회 날짜와 KOBIS API 응답 형식을 확인해 주세요."
            ),
            "movies": [],
        }

    # 영화 목록을 가져옵니다.
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 목록이 비어 있으면 사용자에게 확인할 내용을 알려줍니다.
    if not movie_list:
        return {
            "success": False,
            "message": (
                "해당 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "다음 항목을 확인해 주세요.\n"
                "- 조회 날짜에 박스오피스 데이터가 집계되었는지\n"
                "- KOBIS에서 해당 날짜의 일별 박스오피스를 제공하는지\n"
                "- API 응답이 일시적으로 비어 있는 것은 아닌지\n"
            ),
            "movies": [],
        }

    # KOBIS는 숫자도 문자열로 보내므로 숫자로 변환합니다.
    movies = []

    for movie in movie_list:
        try:
            rank = int(movie.get("rank", 0))
        except (TypeError, ValueError):
            rank = 0

        try:
            audi_cnt = int(movie.get("audiCnt", 0))
        except (TypeError, ValueError):
            audi_cnt = 0

        try:
            audi_acc = int(movie.get("audiAcc", 0))
        except (TypeError, ValueError):
            audi_acc = 0

        try:
            scrn_cnt = int(movie.get("scrnCnt", 0))
        except (TypeError, ValueError):
            scrn_cnt = 0

        movies.append(
            {
                "rank": rank,
                "movieNm": movie.get("movieNm", ""),
                "openDt": movie.get("openDt", ""),
                "audiCnt": audi_cnt,
                "audiAcc": audi_acc,
                "scrnCnt": scrn_cnt,
            }
        )

    # 순위가 낮은 숫자부터 정렬합니다.
    movies.sort(key=lambda x: x["rank"])

    return {
        "success": True,
        "message": "",
        "movies": movies,
    }


# ---------------------------------------------------------
# 화면 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")

# 한국 시간 기준으로 어제를 계산합니다.
target_date = get_yesterday()

# 보기 좋은 날짜도 만들어 줍니다.
display_date = datetime.strptime(target_date, "%Y%m%d").strftime("%Y년 %m월 %d일")

st.caption(f"조회 기준일: {display_date} (한국 시간 기준)")


# ---------------------------------------------------------
# API 호출
# ---------------------------------------------------------

result = get_box_office(target_date)


# ---------------------------------------------------------
# API 오류 처리
# ---------------------------------------------------------

if not result["success"]:
    st.error(result["message"])
    st.stop()


movies = result["movies"]


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader("🏆 1위 영화")

st.markdown(f"## {first_movie['movieNm']}")

# 1위 영화의 주요 숫자를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 다시 정렬합니다.
top_5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True,
)[:5]

# Streamlit의 차트에는 숫자형 데이터를 사용합니다.
chart_data = {
    movie["movieNm"]: movie["audiCnt"]
    for movie in top_5
}

st.bar_chart(chart_data)


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("📋 전체 박스오피스")

# 화면에 보여줄 데이터만 별도로 구성합니다.
table_data = []

for movie in movies:
    table_data.append(
        {
            "순위": movie["rank"],
            "영화명": movie["movieNm"],
            "개봉일": movie["openDt"],
            "관객수": movie["audiCnt"],
            "누적관객": movie["audiAcc"],
            "스크린수": movie["scrnCnt"],
        }
    )

# 표를 보여줍니다.
# 숫자 컬럼은 실제 숫자형이므로 정렬 및 데이터 처리에도 숫자로 사용됩니다.
st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%,d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%,d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%,d개",
        ),
    },
)
