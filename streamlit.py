import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_pitcher

# 📂 Google Drive CSV 데이터 로드
@st.cache_data
def load_data_from_drive():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"  # 여기에 본인의 파일 ID 유지
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

# 1. 팀 선택
team_options = df['home_team'].unique().tolist() + df['away_team'].unique().tolist()
team_options = list(set(team_options))  # 중복된 팀 제거
selected_team = st.selectbox('Select Team', team_options)

# 해당 팀의 데이터 필터링
filtered_team_df = df[(df['home_team'] == selected_team) | (df['away_team'] == selected_team)]

# 팀 선택 후 홈팀 또는 원정팀에 맞춰 inning_topbot 필터링
if selected_team in filtered_team_df['home_team'].values:
    # 홈팀일 경우: inning_topbot = 'Top'
    team_df = filtered_team_df[(filtered_team_df['home_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Top')]
else:
    # 원정팀일 경우: inning_topbot = 'Bot'
    team_df = filtered_team_df[(filtered_team_df['away_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Bot')]

# 2. 선수 선택
player_options = team_df['player_name'].dropna().unique()
selected_player = st.selectbox('Select Pitcher', player_options)

# 선수가 선택되었을 경우 필터링
filtered_player_df = team_df[team_df['player_name'] == selected_player]

# 📢 해당 선수의 데이터가 없으면 경고 후 종료
if filtered_player_df.empty:
    st.warning(f"⚠️ {selected_player}의 데이터가 없습니다.")
    st.stop()

# 3. 날짜 선택 - 해당 선수가 참여한 날짜만 필터링
start_date = filtered_player_df.index.min().date()
end_date = filtered_player_df.index.max().date()

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input('Start Date', start_date, min_value=start_date, max_value=end_date)
with col2:
    end_date = st.date_input('End Date', end_date, min_value=start_date, max_value=end_date)

# 날짜 필터링
filtered_df = filtered_player_df.loc[start_date:end_date]

# 📢 날짜 범위 내 데이터가 없으면 경고 후 종료
if filtered_df.empty:
    st.warning(f"⚠️ {selected_player}의 {start_date} ~ {end_date} 기간에 데이터가 없습니다.")
    st.stop()

# pitcher_id 추출
pitcher_id = filtered_df['pitcher'].iloc[0]

# 🛰️ pybaseball로 해당 날짜 범위 statcast 데이터 불러오기
statcast_df = statcast_pitcher(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), pitcher_id)

# 📏 단위 변환 + Batter_ID merge
statcast_df['release_speed'] = statcast_df['release_speed'] * 1.60934
statcast_df['release_speed'] = round(statcast_df['release_speed'], 1)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

# 📛 pitcher_name
pitcher_name = statcast_df['player_name'].iloc[0]

# 🎛️ Streamlit UI - Batter/Inning 선택
st.title(f"{pitcher_name} - Pitch Visualization ({start_date} ~ {end_date})")

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
    pitch_data = pitch_data.copy()  # SettingWithCopyWarning 방지
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

