import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import gdown
from pybaseball import statcast_pitcher

st.set_page_config(layout="wide")

# ------------------------------
# 📦 데이터 로드 함수
# ------------------------------

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

# ------------------------------
# 🔄 데이터 불러오기
# ------------------------------

df = load_data_from_drive()
batter_ID = load_batter_id()

if df.empty:
    st.error("❌ 데이터셋이 비어있습니다. Google Drive 파일 ID나 파일 내용을 확인하세요.")
    st.stop()

# ------------------------------
# UI 구성
# ------------------------------

st.title("⚾ MLB 2025 - Daily Pitch Info")
st.caption("🧑🏻‍💻 Kyengwook | 📬 kyengwook8@naver.com | [GitHub](https://github.com/kyengwook/kyengwook) | [Instagram](https://instagram.com/kyengwook)")
st.caption("📊 Data: [Baseball Savant](https://baseballsavant.mlb.com/) – MLB 2025 Regular Season")

divisions = {
    'NL East': ['PHI', 'NYM', 'MIA', 'WSH', 'ATL'],
    'NL Central': ['CHC', 'MIL', 'STL', 'CIN', 'PIT'],
    'NL West': ['LAD', 'SD', 'SF', 'AZ', 'COL'],
    'AL East': ['NYY', 'BOS', 'TOR', 'TB', 'BAL'],
    'AL Central': ['DET', 'KC', 'CLE', 'MIN', 'CWS'],
    'AL West': ['TEX', 'LAA', 'HOU', 'ATH', 'SEA']
}

div_options = ['— Select Division —'] + list(divisions.keys())
selected_division = st.selectbox('Division', div_options, label_visibility='collapsed')

if selected_division == '— Select Division —':
    st.info('ℹ️ Division을 먼저 선택해주세요.')
    st.stop()

selected_teams = divisions[selected_division]
team_options = ['— Select Team —'] + selected_teams
selected_team = st.selectbox('Team', team_options, label_visibility='collapsed')

if selected_team == '— Select Team —':
    st.info('ℹ️ 팀을 먼저 선택해주세요.')
    st.stop()

team_df = df[
    ((df['home_team'] == selected_team) & (df['inning_topbot'] == 'Top')) |
    ((df['away_team'] == selected_team) & (df['inning_topbot'] == 'Bot'))
]

if team_df.empty:
    st.warning(f"⚠️ {selected_team} 팀 데이터가 없습니다.")
    st.stop()

player_options = team_df['player_name'].dropna().unique()
player_options = ['— Select Pitcher —'] + sorted(player_options)
selected_player = st.selectbox('Pitcher', player_options, label_visibility='collapsed')

if selected_player == '— Select Pitcher —':
    st.info('ℹ️ 선수를 선택해주세요.')
    st.stop()

filtered_player_df = team_df[team_df['player_name'] == selected_player]

if filtered_player_df.empty:
    st.warning(f"⚠️ {selected_player} 선수 데이터가 없습니다.")
    st.stop()

filtered_player_df = filtered_player_df.copy()
filtered_player_df['opponent_team'] = filtered_player_df.apply(
    lambda row: row['away_team'] if row['home_team'] == selected_team else row['home_team'], axis=1
)
filtered_player_df['date_str'] = filtered_player_df.index.to_series().dt.strftime('%Y-%m-%d') + ' ' + filtered_player_df['opponent_team']

date_options = ['— Select Date —'] + sorted(filtered_player_df['date_str'].unique())
selected_date_str = st.selectbox('Date', date_options, label_visibility='collapsed')

if selected_date_str == '— Select Date —':
    st.info('ℹ️ 날짜를 선택해주세요.')
    st.stop()

selected_date = pd.to_datetime(selected_date_str.split(' ')[0])
filtered_df = filtered_player_df[filtered_player_df.index.normalize() == selected_date]

if filtered_df.empty:
    st.warning(f"⚠️ {selected_player}의 {selected_date} 날짜 데이터가 없습니다.")
    st.stop()

pitcher_id = filtered_df['pitcher'].iloc[0]
statcast_df = statcast_pitcher(selected_date.strftime('%Y-%m-%d'), selected_date.strftime('%Y-%m-%d'), pitcher_id)

statcast_df['release_speed'] = round(statcast_df['release_speed'] * 1.60934, 1)
statcast_df = pd.merge(statcast_df, batter_ID, on='batter', how='left')

pitcher_name = statcast_df['player_name'].iloc[0]
opponent_team = selected_date_str.split(' ')[1]
st.header(f"{pitcher_name} - {selected_date.strftime('%Y-%m-%d')} vs {opponent_team}")

# ------------------------------
# 📊 Pitch Summary
# ------------------------------

st.subheader("Pitch Summary")

summary_df = filtered_df.groupby('pitch_name').agg({
    'pitch_name': 'count',
    'release_speed': ['min', 'mean', 'max'],
    'release_spin_rate': 'mean',
    'pfx_z': 'mean',
    'pfx_x': 'mean',
    'spin_axis': 'mean',
    'release_pos_z': 'mean',
    'release_pos_x': 'mean',
    'release_extension': 'mean',
}).round(1)

summary_df['release_speed'] = (summary_df['release_speed'] * 1.60934).round(1)
summary_df['pfx_x'] = (summary_df['pfx_x'] * 30.48 * -1).round(1)
summary_df['pfx_z'] = (summary_df['pfx_z'] * 30.48).round(1)
summary_df['release_pos_z'] = (summary_df['release_pos_z'] * 30.48).round(1)
summary_df['release_pos_x'] = (summary_df['release_pos_x'] * 30.48 * (-1)).round(1)
summary_df['release_extension'] = (summary_df['release_extension'] * 30.48).round(1)

summary_df.index.name = 'Pitch Type'
summary_df.columns = [
    'Pitches', 'Velo Min(km/h)', 'Velo Avg(km/h)', 'Velo Max(km/h)', 'Spin(rpm)',
     'IVB(cm)', 'HB(cm)', 'Axis(°)', 'RelZ(cm)', 'RelX(cm)', 'Ext(cm)'
]

summary_df = summary_df.sort_values('Pitches', ascending=False)
st.dataframe(summary_df)

# ------------------------------
# 🎯 Matchups 시각화
# ------------------------------

st.subheader("Matchups")

batter_options = statcast_df['batter_name'].dropna().unique()
selected_batter = st.selectbox('Batter', batter_options, label_visibility='collapsed')

filtered_df = statcast_df[statcast_df['batter_name'] == selected_batter]
inning_options = filtered_df['inning'].unique()
selected_inning = st.selectbox('Inning', inning_options, label_visibility='collapsed')

filtered_df = filtered_df[(filtered_df['inning'] == selected_inning)].sort_values('pitch_number')
filtered_df = filtered_df.drop_duplicates(subset=['pitch_number', 'inning', 'batter'])
filtered_df = filtered_df.dropna(subset=['plate_x', 'plate_z'])

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
        lambda row: f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}<br>{row['events']}<br>xBA {row['estimated_ba_using_speedangle']}" 
        if row['description'] == 'hit_into_play' 
        else f"{row['pitch_name']}<br>{row['release_speed']} km/h<br>{row['description']}",
        axis=1
    )
    scatter_fig.add_trace(
        go.Scatter(
            x=pitch_data['plate_x'], y=pitch_data['plate_z'],
            mode='markers+text', marker=dict(size=13, color=style['color']),
            text=pitch_data['pitch_number'], textposition='top center',
            hoverinfo='text',
            hovertext=pitch_data['custom_hover'],
            name=pitch_name
        )
    )

scatter_fig.add_shape(type='rect', x0=L, x1=R, y0=Bot, y1=Top, line=dict(color='grey', width=1.5))
scatter_fig.add_shape(type='path', 
    path=f'M {R-0.1},{0} L {L+0.1},{0} L {L-0.1},{-0.6} L 0,{-1.0} L {R+0.1},{-0.6} Z',
    line=dict(color='grey', width=1.5))

scatter_fig.update_layout(
    title=f'{pitcher_name} vs {selected_batter} (Inning {selected_inning})',
    xaxis=dict(range=[L-2.5, R+2.5], showticklabels=False, fixedrange=True),
    yaxis=dict(range=[Bot-3, Top+2], showticklabels=False, fixedrange=True),
    width=550, height=600, showlegend=True,
    margin=dict(l=5, r=5, t=80, b=5),
    autosize=True,
    legend=dict(
        x=0.02, y=0.98,
        bgcolor='rgba(255,255,255,0.7)',
        bordercolor='black', borderwidth=1
    ),
    dragmode=False
)

st.plotly_chart(scatter_fig, use_container_width=True)

# ------------------------------
# 📝 Pitch Details
# ------------------------------

st.subheader("Pitch Details")

filtered_df = filtered_df.rename(columns={
    'pitch_number': 'No', 'pitch_name': 'Type', 'outs_when_up': 'Out',
    'balls': 'B', 'strikes': 'S', 'release_speed': 'Velo(km/h)',
    'release_spin_rate': 'Spin(rpm)', 'type': 'Result', 'description': 'Desc'
})

st.dataframe(filtered_df[['No', 'Type', 'Out', 'B', 'S', 'Velo(km/h)', 'Spin(rpm)', 'Result', 'Desc']], hide_index=True)
