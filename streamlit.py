# streamlit_app.py

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pybaseball import statcast_pitcher
import requests
import io

# 📥 Google Drive에서 CSV 데이터 로드
@st.cache_data
def load_data_from_drive():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")), encoding='utf-8')
    df = df[df['game_type'] == 'R']  # 정규 시즌만
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.set_index('game_date').sort_index()
    return df

# 📥 Batter ID 엑셀 로드
@st.cache_data
def load_batter_id():
    batter_ID = pd.read_excel('Batter_ID2023.xlsx')
    return batter_ID

# 📊 데이터 준비
df = load_data_from_drive()
batter_ID = load_batter_id()

# dtype 통일 후 병합
df['batter'] = df['batter'].astype(int)
batter_ID['batter'] = batter_ID['batter'].astype(int)
df = pd.merge(df, batter_ID, on='batter', how='left')

# km/h로 변환
df['release_speed'] = round(df['release_speed'] * 1.60934, 1)

# 🎛️ Streamlit UI
st.title('⚾️ MLB Pitcher Dashboard')

# 날짜 선택
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input('Start Date', df.index.min().date())
with col2:
    end_date = st.date_input('End Date', df.index.max().date())

# 날짜 필터
filtered_df = df[(df.index.date >= start_date) & (df.index.date <= end_date)]

# 투수 선택
player_options = filtered_df['player_name'].dropna().unique()
selected_player = st.selectbox('Select Pitcher', sorted(player_options))

# 선택 투수 데이터 필터
player_df = filtered_df[filtered_df['player_name'] == selected_player]

if player_df.empty:
    st.warning(f'⚠️ No pitch data found for {selected_player} between {start_date} and {end_date}.')
    st.stop()

pitcher_id = player_df['pitcher'].iloc[0]

# 📊 Statcast 데이터 수집
st.info(f'Fetching Statcast data for {selected_player} ({pitcher_id}) from {start_date} to {end_date} ...')
statcast_df = statcast_pitcher(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), pitcher_id)

# Batter ID merge
statcast_df['batter'] = statcast_df['batter'].astype(int)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

# km/h 변환
statcast_df['release_speed'] = statcast_df['release_speed'] * 1.60934
statcast_df['release_speed'] = round(statcast_df['release_speed'], 1)

# UI - 타자 선택 & 이닝 선택
batter_options = statcast_df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Select Batter', sorted(batter_options))

filtered_df = statcast_df[statcast_df['batter_name'] == selected_batter]
inning_options = filtered_df['inning'].unique()
selected_inning = st.selectbox('Select Inning', sorted(inning_options))

# 이닝 필터
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
    title=f'{selected_player} - Pitch Location vs {selected_batter} (Inning {selected_inning})',
    xaxis=dict(title='', range=[L-2.5, R+2.5], showticklabels=False),
    yaxis=dict(title='', range=[Bot-3, Top+2], showticklabels=False),
    width=700,
    height=600,
    showlegend=True
)

st.plotly_chart(scatter_fig)

# 📋 테이블
st.subheader("Pitch Details")
st.dataframe(filtered_df[['pitch_number', 'pitch_name', 'outs_when_up', 'balls', 'strikes',
                          'release_speed', 'release_spin_rate', 'type', 'description']])


