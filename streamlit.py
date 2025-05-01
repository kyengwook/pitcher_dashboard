import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_pitcher

# 📂 Google Drive CSV 데이터 로드
@st.cache_data
def load_data_from_drive():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")), encoding='utf-8')
    df = df[df['game_type'] == 'R']
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

# 📊 Team 선택 (팀 선택 추가)
team_options = df['home_team'].dropna().unique()  # 팀은 'home_team'에서 가져옴
selected_team = st.selectbox('Select Team', team_options)

# 해당 팀의 선수 필터링
team_df = df[(df['home_team'] == selected_team) | (df['away_team'] == selected_team)]

# 선택된 팀의 날짜만 추출
available_dates = team_df.index.normalize().unique()

if len(available_dates) == 0:
    st.warning(f"⚠️ {selected_team}의 데이터가 없습니다.")
    st.stop()

# 날짜 선택
available_dates_str = [date.strftime('%Y-%m-%d') for date in available_dates]
selected_date_str = st.selectbox('Select Date', available_dates_str)

# 선택된 날짜를 datetime 객체로 변환
selected_date = pd.to_datetime(selected_date_str)

# 선택된 팀과 날짜로 필터링
filtered_team_df = team_df[team_df.index.normalize() == selected_date]

if filtered_team_df.empty:
    st.warning(f"⚠️ {selected_team}의 {selected_date.date()} 데이터가 없습니다.")
    st.stop()

# 📊 선수 선택
player_options = filtered_team_df['player_name'].dropna().unique()
selected_player = st.selectbox('Select Pitcher', player_options)

# pitcher_id 추출
player_df = filtered_team_df[filtered_team_df['player_name'] == selected_player]
pitcher_id = player_df['pitcher'].iloc[0]

# 🛰️ pybaseball로 해당 날짜 범위 statcast 데이터 불러오기
statcast_df = statcast_pitcher(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), pitcher_id)

# 📏 단위 변환 + Batter_ID merge
statcast_df['release_speed'] = statcast_df['release_speed'] * 1.60934
statcast_df['release_speed'] = round(statcast_df['release_speed'], 1)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

# 📛 pitcher_name
pitcher_name = statcast_df['player_name'].iloc[0]

# 🎛️ Streamlit UI - Batter/Inning 선택
st.title(f"{pitcher_name} - Pitch Visualization ({selected_date.date()})")

batter_options = statcast_df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Select Batter', batter_options)

filtered_df = statcast_df[statcast_df['batter_name'] == selected_batter]

# 팀에 따른 inning_topbot 값 필터링
if selected_team == filtered_df['home_team'].iloc[0]:
    filtered_df = filtered_df[filtered_df['inning_topbot'] == 'Top']
else:
    filtered_df = filtered_df[filtered_df['inning_topbot'] == 'Bot']

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

st.plotly_chart(scatter_fig)

# 📋 테이블
st.subheader("Pitch Details")
st.dataframe(filtered_df[['pitch_number', 'pitch_name', 'outs_when_up', 'balls', 'strikes',
                          'release_speed', 'release_spin_rate', 'type', 'description']])





