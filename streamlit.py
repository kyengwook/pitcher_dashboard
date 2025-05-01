import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pybaseball import statcast_pitcher
from datetime import datetime

# 📊 Batter ID 파일 불러오기 (초기에 한번만)
batter_ID = pd.read_excel('Batter_ID2023.xlsx')

# 🎛️ Streamlit UI - 날짜 선택
st.title("MLB Pitch Visualization")

# 📅 날짜 선택 (start / end)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input('Select Start Date', datetime(2025, 4, 21))
with col2:
    end_date = st.date_input('Select End Date', datetime(2025, 4, 21))

# 📊 데이터 불러오기
@st.cache_data
def load_data(start_date, end_date):
    df = statcast_pitcher(str(start_date), str(end_date))
    df['release_speed'] = df['release_speed'] * 1.60934
    df['release_speed'] = round(df['release_speed'], 1)
    df = pd.merge(df, batter_ID, on='batter', how='left')
    return df

df = load_data(start_date, end_date)

if df.empty:
    st.warning('⚠️ No data available for the selected date range.')
    st.stop()

# 🔥 player_name <-> pitcher_id 매핑 자동 생성
pitcher_mapping_df = df[['player_name', 'pitcher']].drop_duplicates()
pitcher_mapping = dict(zip(pitcher_mapping_df['player_name'], pitcher_mapping_df['pitcher']))

# 🎛️ 선수 선택
player_name_options = list(pitcher_mapping.keys())
selected_player_name = st.selectbox('Select Pitcher', player_name_options)

# ⏩ pitcher_id 할당 (자동 매핑)
pitcher_id = pitcher_mapping[selected_player_name]

# ➡️ 선택된 투수만 필터링
df = df[df['pitcher'] == pitcher_id]
pitcher_name = df['player_name'].iloc[0]

# 🎛️ Streamlit UI (Batter/Inning)
st.header(f"{pitcher_name} - Pitch Visualization ({start_date} to {end_date})")

batter_options = df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Select Batter', batter_options)

filtered_df = df[df['batter_name'] == selected_batter]
inning_options = filtered_df['inning'].unique()
selected_inning = st.selectbox('Select Inning', inning_options)

# 필터링
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
    title=f'{pitcher_name} - Pitch Location vs {selected_batter} (Inning {selected_inning})',
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
