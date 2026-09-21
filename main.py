import streamlit as st
import pandas as pd
import json
import requests
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 고령화 지도")
st.write("65세 이상 인구 비율(고령화율)을 시군구 단위 단계구분도로 보여줍니다.")

# 2. 데이터 로드 (캐싱을 적용하여 속도 최적화)
@st.cache_data
def load_data():
    # (1) 인구 데이터 불러오기
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # 코드는 5자리 잘라 쓰기 위해 문자열(dtype=str)로 읽기
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 코드가 5자리 미만인 경우 대비하여 10자리(행정동 코드) 기준 0 채우기 후 앞 5자리 추출
    df['코드'] = df['코드'].astype(str).str.zfill(10)
    df['시군구코드'] = df['코드'].str[:5]
    
    # (2) GeoJSON 지도 경계 데이터 불러오기
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    geojson_data = response.json()
    
    return df, geojson_data

with st.spinner("데이터를 불러오는 중입니다..."):
    df_raw, geojson_data = load_data()

# 3. 데이터 전처리 (가장 최신 연도 자동 선택 및 고령화율 계산)
# 최신 연도 추출
latest_year = df_raw['연도'].max()
df_latest = df_raw[df_raw['연도'] == latest_year].copy()

# 65세 이상 인구 열 찾기 ('계_65세' ~ '계_100세 이상')
# '계_'로 시작하는 열 중 전체 인구합 및 65세 이상 컬럼을 분류
all_total_cols = [c for c in df_latest.columns if c.startswith('계_')]

# 나이 숫자를 추출하여 65세 이상 열 식별
aging_cols = []
for col in all_total_cols:
    age_str = col.replace('계_', '').replace('세 이상', '').replace('세', '')
    if age_str.isdigit() and int(age_str) >= 65:
        aging_cols.append(col)

# 시군구 단위로 인구 합산 (시도, 시군구 이름 유지)
# 시군구코드를 기준으로 그룹화
df_latest['총인구'] = df_latest[all_total_cols].sum(axis=1)
df_latest['65세이상인구'] = df_latest[aging_cols].sum(axis=1)

# 시군구별 그룹화
df_sigungu = df_latest.groupby(['시군구코드', '시도', '시군구'], as_index=False)[['총인구', '65세이상인구']].sum()

# 고령화율(%) 계산 및 소수점 정돈
df_sigungu['고령화율'] = (df_sigungu['65세이상인구'] / df_sigungu['총인구']) * 100
df_sigungu['고령화율'] = df_sigungu['고령화율'].round(1)

# 4. 5단계 색상 구간 설정 (19%, 23%, 28%, 38% 경계 기준)
# 구간 나누기 (0~19, 19~23, 23~28, 28~38, 38~100)
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_sigungu['고령화_구간'] = pd.cut(
    df_sigungu['고령화율'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 서브타이틀 안내
st.subheader(f"📌 {latest_year}년 기준 전국 시군구 고령화율")

# 5. Plotly 단계구분도(Choropleth) 지도 생성
# 사용자 정의 색상 팔레트 (연한 색 -> 진한 색)
color_discrete_map = {
    '19% 미만': '#edf8fb',
    '19% 이상 ~ 23% 미만': '#b2e2e2',
    '23% 이상 ~ 28% 미만': '#66c2a4',
    '28% 이상 ~ 38% 미만': '#2ca25f',
    '38% 이상': '#006d2c'
}

fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='시군구코드',          # 데이터의 시군구코드
    featureidkey='properties.코드',  # GeoJSON 내부 속성의 5자리 코드
    color='고령화_구간',             # 색상으로 구분할 구간 열
    color_discrete_map=color_discrete_map,
    category_orders={'고령화_구간': labels}, # 범례 순서 고정
    hover_name='시군구',
    hover_data={
        '시도': True,
        '시군구코드': False,
        '고령화율': ':.1f',
        '고령화_구간': False
    },
    mapbox_style="white-bg",         # 배경 지도 타일 없이 경계선만 표시
    center={"lat": 35.8, "lon": 127.8}, # 대한민국 중심 좌표
    zoom=6.2,
    opacity=0.85
)

# 지도 레이아웃 세부 설정
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    legend_title_text="고령화율 구간",
    legend=dict(
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

# Streamlit 화면에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.write("---")

# 6. 고령화율 상위 / 하위 Top 10 표 출력
st.subheader("📊 고령화율 상위 및 하위 지역 Top 10")

col1, col2 = st.columns(2)

# 표에 보여줄 컬럼 정리
display_cols = ['시도', '시군구', '고령화율', '총인구', '65세이상인구']

with col1:
    st.markdown("### 🔴 고령화율 가장 높은 곳 Top 10")
    top_10 = df_sigungu.sort_values(by='고령화율', ascending=False).head(10)[display_cols]
    top_10 = top_10.reset_index(drop=True)
    top_10.index += 1
    st.dataframe(top_10, use_container_width=True)

with col2:
    st.markdown("### 🔵 고령화율 가장 낮은 곳 Top 10")
    bottom_10 = df_sigungu.sort_values(by='고령화율', ascending=True).head(10)[display_cols]
    bottom_10 = bottom_10.reset_index(drop=True)
    bottom_10.index += 1
    st.dataframe(bottom_10, use_container_width=True)
