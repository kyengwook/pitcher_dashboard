import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io
from pybaseball import statcast_pitcher

st.set_page_config(layout="wide")

#데이터 로드
@st.cache_data
def load_data_from_drive():
    url = 'https://drive.google.com/uc?id=1vZB9axWHpzUB5ixNG9Q3JtxTxQsCDMD4'
    output = 'data.csv'
    gdown.download(url, output, quiet=False)
    df = pd.read_csv(output)
    df = df[df['game_type'] == 'R']
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.set_index('game_date').sort_index()
    return df

@st.cache_data
def load_batter_id():
    batter_ID = pd.read_excel('Batter_ID(2025).xlsx')
    return batter_ID

# 데이터 불러오기
df = load_data_from_drive()
batter_ID = load_batter_id()

if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID나 파일 내용을 확인하세요.")
    st.stop()

st.title("⚾ MLB 2025 - Daily Pitch Information")
st.caption("🧑🏻‍💻 App developed by Kyengwook  |  📬 kyengwook8@naver.com  |  [GitHub](https://github.com/kyengwook/kyengwook)  |  [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data source: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 regular season data.")

# Division 선택 (placeholder 포함)
divisions = {
    'NL East': ['PHI', 'NYM', 'MIA', 'WSH', 'ATL'],
    'NL Central': ['CHC', 'MIL', 'STL', 'CIN', 'PIT'],
    'NL West': ['LAD', 'SD', 'SF', 'AZ', 'COL'],
    'AL East': ['NYY', 'BOS', 'TOR', 'TB', 'BAL'],
    'AL Central': ['DET', 'KC', 'CLE', 'MIN', 'CWS'],
    'AL West': ['TEX', 'LAA', 'HOU', 'ATH', 'SEA']
}

division_options = ['— Select Division —'] + list(divisions.keys())
selected_division = st.selectbox('Select Division', division_options)

if selected_division == '— Select Division —':
    st.info('ℹ️ Division을 먼저 선택해주세요.')
    st.stop()

# 선택한 Division의 팀 필터링
selected_teams = divisions[selected_division]
team_options = ['— Select Team —'] + selected_teams
selected_team = st.selectbox('Select Team', team_options)

if selected_team == '— Select Team —':
    st.info('ℹ️ 팀을 먼저 선택해주세요.')
    st.stop()

# 해당 팀 소속 선수 데이터 필터링
filtered_team_df = df.copy()

team_df = filtered_team_df[
    ((filtered_team_df['home_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Top')) |
    ((filtered_team_df['away_team'] == selected_team) & (filtered_team_df['inning_topbot'] == 'Bot'))
]

if team_df.empty:
    st.warning(f"⚠️ {selected_team} 팀의 데이터가 없습니다.")
    st.stop()

# 선수 선택 (placeholder 포함)
player_options = team_df['player_name'].dropna().unique()
player_options = ['— Select Pitcher —'] + sorted(player_options)
selected_player = st.selectbox('Select Pitcher', player_options)

if selected_player == '— Select Pitcher —':
    st.info('ℹ️ 선수를 선택해주세요.')
    st.stop()

filtered_player_df = team_df[team_df['player_name'] == selected_player]

if filtered_player_df.empty:
    st.warning(f"⚠️ {selected_player} 선수의 데이터가 없습니다.")
    st.stop()

# 날짜 선택 (placeholder 포함)
# 상대팀 정보 컬럼 추가
filtered_player_df['opponent_team'] = filtered_player_df.apply(
    lambda row: row['away_team'] if row['home_team'] == selected_team else row['home_team'], axis=1
)

# 날짜 + 상대팀 문자열 생성 (예: 2025-04-21 ATL)
filtered_player_df['date_str'] = filtered_player_df.index.to_series().dt.strftime('%Y-%m-%d') + ' ' + filtered_player_df['opponent_team']

# 중복 제거 및 정렬
date_options = ['— Select Date —'] + sorted(filtered_player_df['date_str'].unique())
selected_date_str = st.selectbox('Select Date', date_options)

if selected_date_str == '— Select Date —':
    st.info('ℹ️ 날짜를 선택해주세요.')
    st.stop()

# 선택한 날짜와 상대팀 추출
selected_date = pd.to_datetime(selected_date_str.split(' ')[0])
opponent_team = selected_date_str.split(' ')[1]


# 선택한 날짜 데이터 필터링
filtered_df = filtered_player_df[filtered_player_df.index.normalize() == pd.Timestamp(selected_date)]

if filtered_df.empty:
    st.warning(f"⚠️ {selected_player}의 {selected_date} 날짜에 데이터가 없습니다.")
    st.stop()

# pitcher_id 추출
pitcher_id = filtered_df['pitcher'].iloc[0]


statcast_df = statcast_pitcher(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), pitcher_id)

#단위 변환 + Batter_ID merge
statcast_df['release_speed'] = statcast_df['release_speed'] * 1.60934
statcast_df['release_speed'] = round(statcast_df['release_speed'], 1)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

#pitcher_name
pitcher_name = statcast_df['player_name'].iloc[0]

#UI 구분선
st.header(f"{pitcher_name} - Pitch Information ({selected_date.strftime('%Y-%m-%d')} vs {opponent_team})")

#구종별 통계
st.subheader("Pitch Summary(Game)")
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
}).round(1)

# 인덱스 이름 변경
summary_df.index.name = 'Pitch Type'

#단위 변환 (인치 -> 센티미터), 소수점 첫째 자리까지 반올림
summary_df['release_speed'] = (summary_df['release_speed'] * 1.60934).round(1)
summary_df['pfx_x'] = (summary_df['pfx_x'] * 30.48 * -1).round(1)
summary_df['pfx_z'] = (summary_df['pfx_z'] * 30.48).round(1)
summary_df['release_pos_z'] = (summary_df['release_pos_z'] * 30.48).round(1)
summary_df['release_pos_x'] = (summary_df['release_pos_x'] * 30.48 * (-1)).round(1)
summary_df['release_extension'] = (summary_df['release_extension'] * 30.48).round(1)

#Pitch Summary에서 컬럼 이름 정리
summary_df.columns = [
    'Pitches', 
    'Release Speed Min(km/h)', 
    'Release Speed AVG(km/h)', 
    'Release Speed Max(km/h)', 
    'Release Spin Rate(rpm)', 
    'Vertical Release Pos(cm)', 
    'Horizontal Release Pos(cm)', 
    'Release Extension(cm)', 
    'Vertical Break(cm)', 
    'Horizontal Break(cm)', 
    'Spin Axis(°)'
]

# 인덱스는 그대로 유지하고 테이블 출력
summary_df = summary_df.sort_values('Pitches', ascending=False)
st.dataframe(summary_df, use_container_width=True)


st.subheader("Matchups")
batter_options = statcast_df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Select Batter', batter_options)

filtered_df = statcast_df[statcast_df['batter_name'] == selected_batter]
inning_options = filtered_df['inning'].unique()
selected_inning = st.selectbox('Select Inning', inning_options)

#최종 필터링
filtered_df = filtered_df[filtered_df['inning'] == selected_inning]
filtered_df = filtered_df.sort_values(by='pitch_number')

#중복 데이터 제거 (pitch_number + inning + batter 기준)
filtered_df = filtered_df.drop_duplicates(subset=['pitch_number', 'inning', 'batter'])



#Plotly 시각화
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
    'Eephus': {'color': 'black'},
    'Other': {'color': 'black'}
}

for pitch_name, style in pitch_styles.items():
    pitch_data = filtered_df[filtered_df['pitch_name'] == pitch_name]
    if pitch_data.empty:
        continue
    pitch_data = pitch_data.copy()
    pitch_data['custom_hover'] = pitch_data.apply(
    lambda row: (
        f"{row['pitch_name']}<br>"
        f"{row['release_speed']} km/h<br>"
        f"{row['description']}<br>"
        f"{row['events']}<br>" f"xBA {row['estimated_ba_using_speedangle']}" if row['description'] == 'hit_into_play' else
        f"{row['pitch_name']}<br>"
        f"{row['release_speed']} km/h<br>{row['description']}"
    ), axis=1
)


    scatter_fig.add_trace(
        go.Scatter(
            x=pitch_data['plate_x'],
            y=pitch_data['plate_z'],
            mode='markers+text',
            marker=dict(size=15, color=style['color']),
            text=pitch_data['pitch_number'],
            textposition='top center',
            hovertemplate="%{customdata}<extra></extra>",
            customdata=pitch_data['custom_hover'],
            name=pitch_name
        )
    )

# 스트라이크존과 타석 추가
scatter_fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='grey', width=1.5))
scatter_fig.add_shape(type='path', 
    path=f'M {R-0.1},{0} L {L+0.1},{0} L {L-0.1},{-0.6} L 0,{-1.0} L {R+0.1},{-0.6} Z',
    line=dict(color='grey', width=1.5))

#width = 500 / 800 height 600 / 700
scatter_fig.update_layout(
    title=f'{pitcher_name} - Pitch Location vs {selected_batter} (Inning {selected_inning})',
    xaxis=dict(title='', range=[L-2.5, R+2.5], showticklabels=False, fixedrange=True),
    yaxis=dict(title='', range=[Bot-3, Top+2], showticklabels=False, fixedrange=True),
    dragmode=False,
    width=600,
    height=700,
    showlegend=True
)

# Plotly 시각화 출력
st.plotly_chart(scatter_fig)

st.subheader("Pitch Details")

# 컬럼 이름 정리
filtered_df = filtered_df.rename(columns={
    'pitch_number': 'Pitch Number',
    'pitch_name': 'Pitch Type',
    'outs_when_up': 'Outs',
    'balls': 'Balls',
    'strikes': 'Strikes',
    'release_speed': 'Release Speed (km/h)',
    'release_spin_rate': 'Release Spin Rate (rpm)',
    'type': 'Pitch Outcome',
    'description': 'Pitch Description'
})

# 테이블 출력
st.dataframe(filtered_df[['Pitch Number', 'Pitch Type', 'Outs', 'Balls', 'Strikes',
                          'Release Speed (km/h)', 'Release Spin Rate (rpm)', 'Pitch Outcome', 'Pitch Description']], hide_index=True, use_container_width=True)




