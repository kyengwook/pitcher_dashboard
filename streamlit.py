import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_pitcher

st.set_page_config(layout="wide")

# 📂 Google Drive CSV 데이터 로드
@st.cache_data
def load_data_from_drive():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"  # 본인의 파일 ID
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")), encoding='utf-8')
    df = df[df['game_type'] == 'R']  # 정규시즌만
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.set_index('game_date').sort_index()
    return df

# 📋 Batter ID 파일 불러오기
@st.cache_data
def load_batter_id():
    batter_ID = pd.read_excel('Batter_ID2023.xlsx')
    return batter_ID

# 데이터 불러오기
df = load_data_from_drive()
batter_ID = load_batter_id()

# 📢 데이터셋 비었으면 경고 후 종료
if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID나 파일 내용을 확인하세요.")
    st.stop()

st.title("⚾ MLB 2025 - Daily Pitch Information")
st.caption("🧑🏻‍💻 App developed by Kyengwook  |  📬 kyengwook8@naver.com  |  [GitHub](https://github.com/kyengwook/kyengwook)  |  [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data source: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 regular season data.")

# ⚾️ 1️⃣ 팀 선택 (placeholder 포함)
teams = sorted(set(df['home_team'].unique()).union(df['away_team'].unique()))
team_options = ['— Select Team —'] + teams
selected_team = st.selectbox('Select Team', team_options)

if selected_team == 'Select Team':
    st.info('ℹ️ 팀을 먼저 선택해주세요.')
    st.stop()

# 📋 해당 팀 소속 선수 데이터 필터링
filtered_team_df = df.copy()

team_df = filtered_team_df[
    ((filtered_team_df['home_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Top')) |
    ((filtered_team_df['away_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Bot'))
]

if team_df.empty:
    st.warning(f"⚠️ {selected_team} 팀의 데이터가 없습니다.")
    st.stop()

# ⚾️ 2️⃣ 선수 선택 (placeholder 포함)
player_options = team_df['player_name'].dropna().unique()
player_options = ['— Select Pitcher —'] + sorted(player_options)
selected_player = st.selectbox('Select Pitcher', player_options)

if selected_player == 'Select Pitcher':
    st.info('ℹ️ 선수를 선택해주세요.')
    st.stop()

# 선택된 선수에 대한 데이터가 존재하는지 확인
filtered_player_df = team_df[team_df['player_name'] == selected_player]

if filtered_player_df.empty:
    st.warning(f"⚠️ {selected_player} 선수의 데이터가 없습니다.")
    st.stop()

# 📅 3️⃣ 날짜 선택 (placeholder 포함)
available_dates = filtered_player_df.index.normalize().unique()
available_dates = sorted([d.date() for d in available_dates])
date_options = ['— Select Date —'] + available_dates
selected_date = st.selectbox('Select Date', date_options)

if selected_date == 'Select Date':
    st.info('ℹ️ 날짜를 선택해주세요.')
    st.stop()

# 📋 선택한 날짜 데이터 필터링
filtered_df = filtered_player_df[filtered_player_df.index.normalize() == pd.Timestamp(selected_date)]

if filtered_df.empty:
    st.warning(f"⚠️ {selected_player}의 {selected_date} 날짜에 데이터가 없습니다.")
    st.stop()

# pitcher_id 추출
pitcher_id = filtered_df['pitcher'].iloc[0]

# 🛰️ pybaseball로 statcast 데이터 불러오기 (선택한 날짜 하루만)
statcast_df = statcast_pitcher(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), pitcher_id)

# 📏 단위 변환 + Batter_ID merge
statcast_df['release_speed'] = statcast_df['release_speed'] * 1.60934
statcast_df['release_speed'] = round(statcast_df['release_speed'], 1)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

# 📛 pitcher_name
pitcher_name = statcast_df['player_name'].iloc[0]

# 🎛️ Streamlit UI - Batter/Inning 선택
st.header(f"{pitcher_name} - Pitch Information ({selected_date})")

# 📊 구종별 통계
st.subheader("Pitch Type Summary")
summary_df = filtered_df.groupby('pitch_name').agg({
    'pitch_name': 'count',
    'release_speed': ['min', 'mean', 'max'],
    'release_spin_rate': ['mean'],
    'release_pos_z': ['mean'],
    'release_pos_x': ['mean'],
    'release_extension': ['mean'],
    'pfx_z': ['mean'],
    'pfx_x': ['mean'],
    'spin_axis': ['mean']
}).rename(columns={'pitch_name': 'pitches'}).round(1)

# 📏 pfx_x, pfx_z 단위 변환 (인치 -> 센티미터)
summary_df['pfx_x'] = summary_df['pfx_x'] * 30.48 * -1
summary_df['pfx_z'] = summary_df['pfx_z'] * 30.48

# column 이름 정리
summary_df.columns = ['_'.join(col).strip() for col in summary_df.columns.values]
summary_df = summary_df.reset_index()

st.dataframe(summary_df)

batter_options = statcast_df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Select Batter', batter_options)

filtered_df = statcast_df[statcast_df['batter_name'] == selected_batter]
inning_options = filtered_df['inning'].unique()
selected_inning = st.selectbox('Select Inning', inning_options)

# 📊 최종 필터링
filtered_df = filtered_df[filtered_df['inning'] == selected_inning]
filtered_df = filtered_df.sort_values(by='pitch_number')

# 📈 Plotly 시각화
L, R = -0.708333, 0.708333
Bot, Top = 1.5, 3.5

scatter_fig = go.Figure()

pitch_styles = {
    '4-Seam Fastball': {'color': '#D22D49'},
    'Sinker': {'color': '#FE9D00'},
    'Cutter': {'color': '#933F2C'},
    'Knuckle Curve': {'color': 'mediumpurple'},
    'Sweeper': {'color': 'olive'},
    'Split-Finger': {'color': '#888888'},
    'Changeup': {'color': '#1DBE3A'},
    'Screwball': {'color': '#1DBE3A'},
    'Forkball': {'color': '#888888'},
    'Slurve': {'color': 'teal'},
    'Knuckleball': {'color': 'lightsteelblue'},
    'Slider': {'color': 'darkkhaki'},
    'Curveball': {'color': 'teal'},
}

for pitch_name, style in pitch_styles.items():
    pitch_data = filtered_df[filtered_df['pitch_name'] == pitch_name]
    if pitch_data.empty:
        continue
    pitch_data = pitch_data.copy()
    pitch_data['custom_hover'] = pitch_data.apply(
        lambda row: (
            f"{row['release_speed']} km/h<br>"
            f"{row['description']}<br>"
            f"{row['events']}" if row['description'] == 'hit_into_play' else
            f"{row['release_speed']} km/h<br>{row['description']}"
        ), axis=1
    )

    scatter_fig.add_trace(
        go.Scatter(
            x=pitch_data['plate_x'],
            y=pitch_data['plate_z'],
            mode='markers+text',
            marker=dict(size=10, color=style['color']),
            text=pitch_data['pitch_number'],
            textposition='top center',
            hovertemplate="%{customdata}<extra></extra>",
            customdata=pitch_data['custom_hover'],
            name=pitch_name
        )
    )

# 스트라이크존과 타석 추가
scatter_fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='black', width=2))
scatter_fig.add_shape(type='path', 
    path=f'M {R-0.1},{0} L {L+0.1},{0} L {L-0.1},{-0.6} L 0,{-1.0} L {R+0.1},{-0.6} Z',
    line=dict(color='grey', width=1))

scatter_fig.update_layout(
    title=f'{pitcher_name} - Pitch Location vs {selected_batter} (Inning {selected_inning})',
    xaxis=dict(title='', range=[L-2.5, R+2.5], showticklabels=False),
    yaxis=dict(title='', range=[Bot-3, Top+2], showticklabels=False),
    width=700,
    height=600,
    showlegend=True
)

# Plotly 시각화 출력
col1, col2 = st.columns([2, 1])  # 왼쪽은 plot, 오른쪽은 구종별 통계
with col1:
    st.plotly_chart(scatter_fig)

with col2:
    # 📋 테이블
    st.subheader("Pitch Details")

    # 컬럼 이름 정리
    filtered_df = filtered_df.rename(columns={
        'pitch_number': 'Pitch Number',
        'pitch_name': 'Pitch Type',
        'outs_when_up': 'Outs When Up',
        'balls': 'Balls',
        'strikes': 'Strikes',
        'release_speed': 'Release Speed (km/h)',
        'release_spin_rate': 'Release Spin Rate (rpm)',
        'type': 'Pitch Outcome',
        'description': 'Pitch Description'
    })

    st.dataframe(filtered_df[['Pitch Number', 'Pitch Type', 'Outs When Up', 'Balls', 'Strikes',
                              'Release Speed (km/h)', 'Release Spin Rate (rpm)', 'Pitch Outcome', 'Pitch Description']])


