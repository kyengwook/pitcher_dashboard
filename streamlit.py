import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import requests
import io

st.set_page_config(layout="wide")  # 전체화면 사용 권장

# 📊 CSV 데이터 불러오기 (Google Drive)
@st.cache_data
def load_data_from_drive():
    file_id = "1sWJCEA7MUrOCGfj61ES1JQHJGBfYVYN3"  
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(download_url)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.content.decode("utf-8")), encoding='utf-8')
    df = df[df['game_type'] == 'R']  # 정규시즌만
    df['game_date'] = pd.to_datetime(df['game_date'])
    df = df.set_index('game_date').sort_index()
    return df

df = load_data_from_drive()

# 📅 날짜 선택
st.sidebar.header("Filter Options")
start_date = st.sidebar.date_input('Start Date', value=df.index.min().date())
end_date = st.sidebar.date_input('End Date', value=df.index.max().date())

if start_date > end_date:
    st.error('❌ Start date must be before or equal to end date.')
    st.stop()

# 날짜로 필터링
filtered_df = df.loc[start_date:end_date]

if filtered_df.empty:
    st.warning('⚠️ No data available for selected date range.')
    st.stop()

# 🎯 player_name 선택
player_options = filtered_df['player_name'].dropna().unique()
selected_player = st.sidebar.selectbox('Select Pitcher', sorted(player_options))

# player_name → pitcher ID 매핑
pitcher_id = filtered_df[filtered_df['player_name'] == selected_player]['pitcher'].iloc[0]

# pitcher 데이터 필터링
player_df = filtered_df[filtered_df['pitcher'] == pitcher_id]

# 타자 선택
batter_options = player_df['batter_name'].dropna().unique()
selected_batter = st.sidebar.selectbox('Select Batter', sorted(batter_options))

batter_df = player_df[player_df['batter_name'] == selected_batter]

# 이닝 선택
inning_options = batter_df['inning'].unique()
selected_inning = st.sidebar.selectbox('Select Inning', sorted(inning_options))

final_df = batter_df[batter_df['inning'] == selected_inning].sort_values('pitch_number')

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
    pitch_data = final_df[final_df['pitch_name'] == pitch_name]
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

st.title(f"{selected_player} - Pitch Visualization")
st.plotly_chart(scatter_fig)

# 📋 테이블
st.subheader("Pitch Details")
st.dataframe(final_df[['pitch_number', 'pitch_name', 'outs_when_up', 'balls', 'strikes',
                          'release_speed', 'release_spin_rate', 'type', 'description']])

