import re
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="전국 고령화 및 학생 인구 지도", layout="wide")
st.title("🗺️ 전국 시군구별 고령화 및 학생 인구 지도")
st.caption("시군구별 65세 이상 고령 인구 및 학생(6~18세) 성별 인구 비율 분석")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    # '코드' 열은 앞자리 0이 사라지지 않게 글자로 읽습니다
    return pd.read_csv(POP_URL, dtype={"코드": str})

@st.cache_data(show_spinner="지도 경계를 불러오는 중입니다...")
def load_geojson():
    return requests.get(GEO_URL, timeout=30).json()

df = load_population()
geojson = load_geojson()

# 1. 가장 최신 연도만 사용
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

# 2. 열 분류 ('계_', '남_', '여_' 구별)
total_cols = [c for c in df.columns if c.startswith("계_")]
male_cols = [c for c in df.columns if c.startswith("남_")]
female_cols = [c for c in df.columns if c.startswith("여_")]

def get_age(col_name):
    m = re.search(r"(\d+)세", col_name)
    return int(m.group(1)) if m else None

# 3. 고령 인구(65세 이상) 및 학생 인구(초/중/고 연령대: 6세~18세) 열 추출
elderly_cols = [c for c in total_cols if get_age(c) is not None and get_age(c) >= 65]

student_total_cols = [c for c in total_cols if get_age(c) is not None and 6 <= get_age(c) <= 18]
student_male_cols = [c for c in male_cols if get_age(c) is not None and 6 <= get_age(c) <= 18]
student_female_cols = [c for c in female_cols if get_age(c) is not None and 6 <= get_age(c) <= 18]

# 4. 동 단위 집계
df["전체인구"] = df[total_cols].sum(axis=1)
df["고령인구"] = df[elderly_cols].sum(axis=1)

df["학생인구"] = df[student_total_cols].sum(axis=1)
df["남학생인구"] = df[student_male_cols].sum(axis=1)
df["여학생인구"] = df[student_female_cols].sum(axis=1)

# 5. '코드' 앞 5자리 = 시군구 코드 기준 집계 및 비율 계산
df["시군구코드"] = df["코드"].str[:5]
grouped = df.groupby("시군구코드")[
    ["전체인구", "고령인구", "학생인구", "남학생인구", "여학생인구"]
].sum().reset_index()

# 고령화율 및 학생 관련 비율 계산
grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"] * 100).round(2)
grouped["학생비율"] = (grouped["학생인구"] / grouped["전체인구"] * 100).round(2)

# 학생 내 남녀 비율 계산 (0 나누기 방지)
grouped["남학생비율"] = (grouped["남학생인구"] / grouped["학생인구"].replace(0, 1) * 100).round(1)
grouped["여학생비율"] = (grouped["여학생인구"] / grouped["학생인구"].replace(0, 1) * 100).round(1)

# GeoJSON 정보 연동 (시도, 시군구 이름)
names = pd.DataFrame([
    {
        "시군구코드": str(f["properties"]["코드"]),
        "시군구": f["properties"]["시군구"],
        "시도": f["properties"]["시도"],
    }
    for f in geojson["features"]
])
merged = grouped.merge(names, on="시군구코드", how="left")

# 6. 5단계 색 구간 설정 (파란색 계열)
BINS = [0, 19, 23, 28, 38, 100]
LABELS = ["19% 미만", "19~23%", "23~28%", "28~38%", "38% 이상"]

# 지도의 배경 및 구분을 파란색(Blue) 팔레트로 설정
BLUE_COLORS = {
    "19% 미만": "#eff3ff",
    "19~23%": "#bdd7e7",
    "23~28%": "#6baed6",
    "28~38%": "#3182bd",
    "38% 이상": "#08519c",
}

merged["단계"] = pd.cut(merged["고령화율"], bins=BINS, labels=LABELS, right=False)

# 7. 파란색 톤 지도 생성 및 마우스 오버(Hover) 상세 정보 설정
fig = px.choropleth(
    merged,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="단계",
    category_orders={"단계": LABELS},
    color_discrete_map=BLUE_COLORS,
    hover_name="시군구",
    hover_data={
        "시도": True,
        "고령화율": ":.2f",
        "학생비율": ":.2f",
        "남학생비율": ":.1f",
        "여학생비율": ":.1f",
        "학생인구": ":,d",
        "시군구코드": False,
        "단계": False,
    },
    labels={
        "고령화율": "고령화율(%)",
        "학생비율": "전체 대비 학생 비율(%)",
        "남학생비율": "남학생 비율(%)",
        "여학생비율": "여학생 비율(%)",
        "학생인구": "총 학생 수(명)",
    },
)

# 지도 스타일 및 파란색 계열 배경 설정
fig.update_geos(
    fitbounds="locations",
    visible=False,
    bgcolor="#e6f2ff"  # 연한 파란색 바다/배경 색상
)

fig.update_layout(
    margin=dict(l=0, r=0, t=10, b=0),
    height=700,
    paper_bgcolor="#f4f8fb",  # 캔버스 겉면 배경 파란 톤
    legend_title_text=f"고령화율 단계 ({latest_year}년)",
)

st.plotly_chart(fig, use_container_width=True)

# 8. 하단 현황 데이터 표
st.subheader("📋 지역별 학생 인구 및 성별 비율 현황")

# 표시할 컬럼 지정
cols_display = [
    "시도", "시군구", "전체인구", "고령화율", 
    "학생인구", "학생비율", "남학생인구", "남학생비율", "여학생인구", "여학생비율"
]

tab1, tab2 = st.columns(2)
with tab1:
    st.markdown("### 🔵 학생 비율이 높은 지역 Top 10")
    st.dataframe(
        merged.nlargest(10, "학생비율")[cols_display].reset_index(drop=True),
        use_container_width=True
    )

with tab2:
    st.markdown("### 🔴 고령화율이 높은 지역 Top 10")
    st.dataframe(
        merged.nlargest(10, "고령화율")[cols_display].reset_index(drop=True),
        use_container_width=True
    )
