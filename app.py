import os
import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. Page Configuration & Global CSS
# ==========================================
st.set_page_config(page_title="PMC Bridge SHM Explorer", layout="wide")

st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        html, body, [class*="st-"] { font-size: 14px !important; }
        h1 { font-size: 28px !important; padding-bottom: 10px !important;}
        h2 { font-size: 22px !important; }
        h3 { font-size: 18px !important; }
        h5 { font-size: 15px !important; }
        .dataframe { font-size: 12px !important; }
        i.fa-solid { margin-right: 8px; } 
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Data Loading & Processing Pipelines
# ==========================================
PATH_SS = 'SS.csv'
PATH_C = 'C.csv'
PATH_DS = 'DS.csv'
PATH_SC = 'SC.csv'

def assign_color(category, event):
    event_upper = str(event).upper()
    if category == 'Sensor Setup':
        if 'S1' in event_upper: return '#1F77B4' 
        if 'S2' in event_upper: return '#FF7F0E' 
        if 'S3' in event_upper: return '#2CA02C' 
        if 'S4' in event_upper: return '#E377C2' 
        if 'S5' in event_upper: return '#8C564B' 
        if 'S6' in event_upper: return '#17BECF' 
        return '#3498DB'
    
    # 【新增】渐变红：为 Damage Scenario 连续状态层分配越来越红的警示色
    elif category == 'Damage Scenario':
        if 'DS0' in event_upper: return '#FFEBEE' # 极浅粉 (几乎无损)
        if 'DS1' in event_upper: return '#FFCDD2'
        if 'DS2' in event_upper: return '#EF9A9A'
        if 'DS3' in event_upper: return '#E57373'
        if 'DS4' in event_upper: return '#EF5350'
        if 'DS5' in event_upper: return '#F44336'
        if 'DS6' in event_upper: return '#D32F2F'
        if 'DS7' in event_upper: return '#B71C1C' # 极暗红 (最严重)
        return '#C0392B'
        
    elif category == 'Damage Introduction':
        return '#C0392B' # 瞬时破坏动作统一使用标准红
        
    elif category == 'Time Series Data':
        if 'AMB' in event_upper: return '#27AE60' 
        if 'FVR' in event_upper or 'FVA' in event_upper: return '#8E44AD' 
        if 'FVB' in event_upper: return '#F39C12' 
        return '#1ABC9C'
        
    elif category == 'Perturbation':
        return '#34495E' 
        
    return '#000000'

@st.cache_data
def load_and_process_timeline_data():
    def fix_time(t_str):
        t_str = str(t_str).strip()
        if t_str == 'nan': return '00:00:00'
        return t_str + ":00" if len(t_str.split(':')) == 2 else t_str

    # 【智能算法】在空白时间段补上带括号()的顺延状态
    def create_gap_rows(start_dt, end_dt, base_row):
        gap_rows = []
        curr_start = start_dt
        while curr_start < end_dt:
            curr_end_of_day = curr_start.replace(hour=23, minute=59, second=59)
            curr_end = min(end_dt, curr_end_of_day)

            if curr_start >= curr_end: break

            new_row = base_row.to_dict()
            new_row['Start'] = curr_start
            new_row['End'] = curr_end
            new_row['Start_Time'] = curr_start.strftime('%H:%M:%S')
            new_row['End_Time'] = curr_end.strftime('%H:%M:%S')
            new_row['Date'] = curr_start.strftime('%Y-%m-%d')
            
            event_name = str(base_row['Event'])
            new_row['Event'] = f"({event_name})" if not event_name.startswith('(') else event_name
            
            detail_name = str(base_row['Detail'])
            new_row['Detail'] = f"({detail_name})" if not detail_name.startswith('(') else detail_name
            
            gap_rows.append(new_row)
            curr_start = curr_end + pd.Timedelta(seconds=1)
        return gap_rows

    try:
        # 读取原始数据
        df_ss = pd.read_csv(PATH_SS)
        df_ss['Date'] = pd.to_datetime(df_ss['Date'], format='%d.%m.%Y', errors='coerce').dt.strftime('%Y-%m-%d')
        df_ss['Category'] = 'Sensor Setup'
        df_ss['Event'] = 'Setup ' + df_ss['Sensor Setup'].astype(str)
        df_ss['Detail'] = 'Sensor Configuration'
        
        df_c = pd.read_csv(PATH_C)
        df_c['Date'] = pd.to_datetime(df_c['Date'], format='%d.%m.%Y', errors='coerce')
        df_c['Date'] = df_c['Date'].ffill().dt.strftime('%Y-%m-%d')
        df_c['Category'] = df_c['Construction'].apply(lambda x: 'Damage Introduction' if 'Damage' in str(x) else 'Perturbation')
        df_c['Event'] = df_c['Construction']
        df_c['Detail'] = df_c['Detail'].astype(str) + ' | Pos: ' + df_c['Position'].astype(str)

        df_ds = pd.read_csv(PATH_DS)
        df_ds['Date'] = pd.to_datetime(df_ds['Date'], format='%d.%m.%Y', errors='coerce').dt.strftime('%Y-%m-%d')
        df_ds['Category'] = 'Time Series Data'
        df_ds['Event'] = df_ds['Time Serie ID']
        df_ds['Detail'] = df_ds['Damage Scenarios']

        cols_to_keep = ['Date', 'Category', 'Event', 'Detail', 'Start_Time', 'End_Time']
        df_all = pd.concat([df_ss[cols_to_keep], df_c[cols_to_keep], df_ds[cols_to_keep]], ignore_index=True)

        df_all['Start_Time'] = df_all['Start_Time'].apply(fix_time)
        df_all['End_Time'] = df_all['End_Time'].apply(fix_time)
        df_all['Start'] = pd.to_datetime(df_all['Date'] + " " + df_all['Start_Time'])
        df_all['End'] = pd.to_datetime(df_all['Date'] + " " + df_all['End_Time'])

        # =========================================================
        # 【核心算法】提取 Damage Scenario 形成连续状态图层
        # =========================================================
        ds_records = []
        df_c_ds = df_c[df_c['Construction'].astype(str).str.contains('DS', na=False)]
        for _, row in df_c_ds.iterrows():
            match = re.search(r'(DS\d)', str(row['Construction']))
            if match:
                ds_records.append({'DS': match.group(1), 'Start': pd.to_datetime(row['Date'] + ' ' + fix_time(row['Start_Time']))})
                
        for _, row in df_ds.iterrows():
            if 'DS' in str(row['Damage Scenarios']):
                ds_records.append({'DS': str(row['Damage Scenarios']), 'Start': pd.to_datetime(row['Date'] + ' ' + fix_time(row['Start_Time']))})
                
        if ds_records:
            ds_starts = pd.DataFrame(ds_records).groupby('DS')['Start'].min().reset_index().sort_values('Start')
            
            global_max_dt = df_all['End'].max()
            if pd.isna(global_max_dt): global_max_dt = pd.to_datetime('2019-11-29 23:59:59')
            else: global_max_dt = global_max_dt.replace(hour=23, minute=59, second=59)
            
            new_ds_rows = []
            for i in range(len(ds_starts)):
                curr_ds = ds_starts.iloc[i]['DS']
                start_dt = ds_starts.iloc[i]['Start']
                end_dt = ds_starts.iloc[i+1]['Start'] if i < len(ds_starts) - 1 else global_max_dt
                    
                curr_split = start_dt
                while curr_split < end_dt:
                    end_of_day = curr_split.replace(hour=23, minute=59, second=59)
                    segment_end = min(end_dt, end_of_day)
                    if curr_split >= segment_end: break
                        
                    new_ds_rows.append({
                        'Date': curr_split.strftime('%Y-%m-%d'),
                        'Category': 'Damage Scenario',
                        'Event': curr_ds,
                        'Detail': f'Progressive State: {curr_ds}',
                        'Start_Time': curr_split.strftime('%H:%M:%S'),
                        'End_Time': segment_end.strftime('%H:%M:%S'),
                        'Start': curr_split,
                        'End': segment_end
                    })
                    curr_split = end_of_day + pd.Timedelta(seconds=1)
            
            df_all = pd.concat([df_all, pd.DataFrame(new_ds_rows)], ignore_index=True)

        # =========================================================
        # 【核心算法】仅对 Sensor Setup 进行带括号的隐性填充
        # =========================================================
        all_new_rows = []
        for cat in df_all['Category'].unique():
            df_cat = df_all[df_all['Category'] == cat].sort_values('Start').reset_index(drop=True)
            
            if cat == 'Sensor Setup':
                for i in range(len(df_cat)):
                    curr_row = df_cat.iloc[i]
                    all_new_rows.append(curr_row.to_dict())
                    
                    if i < len(df_cat) - 1:
                        next_start = df_cat.iloc[i+1]['Start']
                        curr_end = curr_row['End']
                        if curr_end < next_start:
                            all_new_rows.extend(create_gap_rows(curr_end, next_start, curr_row))
                    else:
                        if curr_row['End'] < global_max_dt:
                            all_new_rows.extend(create_gap_rows(curr_row['End'], global_max_dt, curr_row))
            else:
                all_new_rows.extend(df_cat.to_dict('records'))

        df_final = pd.DataFrame(all_new_rows).sort_values('Start').reset_index(drop=True)
        df_final['Color'] = df_final.apply(lambda row: assign_color(row['Category'], row['Event']), axis=1)
        return df_final.rename(columns={'Date': 'Day'})
        
    except Exception as e:
        st.error(f"🚨 Error processing Timeline CSVs: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def load_sensor_coords():
    try:
        df_sc = pd.read_csv(PATH_SC)
        df_sc['Setup'] = df_sc['Setup'].ffill().astype(int)
        return df_sc
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. Header & Sidebar Controls
# ==========================================
st.markdown("<h1><i class='fa-solid fa-bridge' style='color:#34495E;'></i> Ponte Moesa Campagnola (PMC) Bridge<br><span style='font-size:20px; color:gray;'>SHM Benchmark Dataset Explorer</span></h1>", unsafe_allow_html=True)

df = load_and_process_timeline_data()
df_sc = load_sensor_coords()

if df.empty:
    st.stop()

st.sidebar.markdown("<h3 style='margin-bottom:5px;'><i class='fa-solid fa-calendar-days' style='color:#2980B9;'></i> Timeline Settings</h3>", unsafe_allow_html=True)
selected_day = st.sidebar.selectbox("Select Date:", sorted(df['Day'].unique()), label_visibility="collapsed")

st.sidebar.markdown("---")
st.sidebar.markdown("<h3 style='margin-bottom:5px;'><i class='fa-solid fa-layer-group' style='color:#27AE60;'></i> Visible Layers</h3>", unsafe_allow_html=True)

available_categories = df['Category'].unique()
selected_cats = []
for cat in available_categories:
    if st.sidebar.checkbox(cat, value=True):
        selected_cats.append(cat)

day_df = df[df['Day'] == selected_day]
setup_df_for_hover = day_df[day_df['Category'] == 'Sensor Setup']
ds_df_for_hover = day_df[day_df['Category'] == 'Damage Scenario']


# ==========================================
# 4. Map View (Placed strictly above timeline)
# ==========================================
col_map_title, col_map_control = st.columns([4, 1])
with col_map_title:
    st.markdown("<h5 style='margin-top:10px;'><i class='fa-solid fa-satellite-dish' style='color:#E74C3C;'></i> Sensor Schematic & Damage Regions (Top View)</h5>", unsafe_allow_html=True)
with col_map_control:
    selected_setup = st.selectbox("Select Setup View:", ["S1", "S2", "S3", "S4", "S5", "S6"], label_visibility="collapsed")

if not df_sc.empty:
    s_id = int(selected_setup.replace('S', ''))
    df_sub = df_sc[df_sc['Setup'] == s_id]
    
    fig_map = go.Figure()
    
    fig_map.add_shape(type="rect", x0=0, y0=-5.5, x1=93.5, y1=5.5, line=dict(color="#7F8C8D", width=2), fillcolor="#ECF0F1", opacity=0.7, layer="below")
    fig_map.add_shape(type="line", x0=0, y0=0, x1=93.5, y1=0, line=dict(color="#BDC3C7", width=1.5, dash="dash"), layer="below")
    
    fig_map.add_shape(type="rect", x0=-1, y0=-6.5, x1=0, y1=6.5, fillcolor="#95A5A6", line_width=0, layer="below")
    fig_map.add_shape(type="rect", x0=93.5, y0=-6.5, x1=94.5, y1=6.5, fillcolor="#95A5A6", line_width=0, layer="below")
    fig_map.add_shape(type="line", x0=31, y0=-6, x1=31, y1=6, line=dict(color="#34495E", width=4), layer="below")
    fig_map.add_shape(type="line", x0=62, y0=-6, x1=62, y1=6, line=dict(color="#34495E", width=4), layer="below")

    damage_regions = {
        'I': (62.0, 3.0), 'II': (62.0, -3.0),
        'III': (78.5, -3.0), 'IV': (5.0, -3.0)
    }
    halo_radii = [2.2, 1.2, 0.5]  
    halo_opacities = [0.15, 0.35, 0.7] 

    for name, (x, y) in damage_regions.items():
        for r, opacity in zip(halo_radii, halo_opacities):
            fig_map.add_shape(type="circle", x0=x-r, y0=y-r, x1=x+r, y1=y+r, fillcolor="#E74C3C", line_width=0, opacity=opacity, layer="below")
        fig_map.add_shape(type="circle", x0=x-0.15, y0=y-0.15, x1=x+0.15, y1=y+0.15, fillcolor="#922B21", line_width=0, opacity=1.0, layer="above")
        
        y_offset = y + 3.5 if y > 0 else y - 3.5
        fig_map.add_annotation(x=x, y=y_offset, text=f"<b>Pos {name}</b>", showarrow=False, font=dict(color="#C0392B", size=11, family="Arial"))

    fixed_sensors = df_sub[df_sub['Sensor ID'].isin([1, 2, 3])]
    roving_sensors = df_sub[~df_sub['Sensor ID'].isin([1, 2, 3])]
    
    if not fixed_sensors.empty:
        fig_map.add_trace(go.Scatter(
            x=fixed_sensors['X/m'], y=fixed_sensors['Y/m'], mode='markers+text',
            marker=dict(size=12, color='#2980B9', line=dict(width=1.5, color='#1A5276')), 
            text=fixed_sensors['Sensor ID'].apply(lambda x: f"{int(x)}"), textposition="middle right", textfont=dict(color="#2C3E50", size=10, family="Arial Black"),
            hoverinfo="text", hovertemplate="<b>Fixed Sensor %{text}</b><br>X: %{x} m<br>Y: %{y} m<extra></extra>"
        ))
        
    if not roving_sensors.empty:
        fig_map.add_trace(go.Scatter(
            x=roving_sensors['X/m'], y=roving_sensors['Y/m'], mode='markers+text',
            marker=dict(size=12, color='#F39C12', line=dict(width=1.5, color='#D68910')), 
            text=roving_sensors['Sensor ID'].apply(lambda x: f"{int(x)}"), textposition="middle right", textfont=dict(color="#2C3E50", size=10, family="Arial Black"),
            hoverinfo="text", hovertemplate="<b>Roving Sensor %{text}</b><br>X: %{x} m<br>Y: %{y} m<extra></extra>"
        ))

    fig_map.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',  
        paper_bgcolor='rgba(0,0,0,0)', 
        xaxis=dict(showgrid=False, zeroline=False, range=[-3, 98], visible=False), 
        yaxis=dict(showgrid=False, zeroline=False, range=[9, -9], visible=False),
        height=200, margin=dict(l=0, r=0, t=10, b=10), showlegend=False
    )
    st.plotly_chart(fig_map, width="stretch", config={'displayModeBar': False})


# ==========================================
# 5. Core Plotly 1D Timeline
# ==========================================
fig = go.Figure()

base_start = pd.to_datetime(f"{selected_day} 00:00:00")
base_end = pd.to_datetime(f"{selected_day} 23:59:59")

fig.add_trace(go.Scatter(x=[base_start, base_end], y=[1, 1], mode="lines", line=dict(color="#D5D8DC", width=2), hoverinfo="none", showlegend=False))

# 【优化】金字塔图层渲染：最宽的 Damage Scenario 垫底，最细的数据线放顶层
render_order = ['Damage Scenario', 'Sensor Setup', 'Damage Introduction', 'Perturbation', 'Time Series Data']
style_map = {
    'Damage Scenario':     {'width': 42, 'opacity': 0.45}, 
    'Sensor Setup':        {'width': 26, 'opacity': 0.60}, 
    'Damage Introduction': {'width': 18, 'opacity': 0.85}, 
    'Perturbation':        {'width': 10, 'opacity': 0.95}, 
    'Time Series Data':    {'width': 4,  'opacity': 1.0}  
}

for category in render_order:
    if category not in selected_cats:
        continue
        
    cat_df = day_df[day_df['Category'] == category]
    c_style = style_map.get(category, {'width': 10, 'opacity': 1.0})
    
    for _, row in cat_df.iterrows():
        # 【穿透式悬停卡片】自动查询当前时刻的 Setup 和 Damage State
        if category in ['Sensor Setup', 'Damage Scenario']:
            context_html = ""
        else:
            active_setup = setup_df_for_hover[(setup_df_for_hover['Start'] <= row['Start']) & (setup_df_for_hover['End'] >= row['Start'])]
            s_name = active_setup.iloc[0]['Event'] if not active_setup.empty else "N/A"
            
            active_ds = ds_df_for_hover[(ds_df_for_hover['Start'] <= row['Start']) & (ds_df_for_hover['End'] >= row['Start'])]
            ds_name = active_ds.iloc[0]['Event'] if not active_ds.empty else "N/A"
            
            context_html = f"<b>Setup:</b> <span style='color:#2980B9'>{s_name}</span> | <b>State:</b> <span style='color:#C0392B'>{ds_name}</span><br>"
        
        hover_text = (
            f"<b>[{category}] {row['Event']}</b><br>"
            f"{context_html}"
            f"<b>Detail:</b> {row['Detail']}<br>"
            f"<b>Time:</b> {row['Start'].strftime('%H:%M:%S')} - {row['End'].strftime('%H:%M:%S')}"
        )
        
        if row['Start'] == row['End']:
            x_vals = [row['Start']]
            y_vals = [1]
            sizes = [c_style['width'] * 0.8]
        else:
            x_vals = pd.date_range(row['Start'], row['End'], periods=30).tolist()
            y_vals = [1] * len(x_vals)
            sizes = [c_style['width'] * 0.8] + [0] * 28 + [c_style['width'] * 0.8]

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="lines+markers", 
            marker=dict(size=sizes, color=row['Color']),
            line=dict(color=row['Color'], width=c_style['width']),
            opacity=c_style['opacity'], hovertemplate=hover_text + "<extra></extra>", showlegend=False
        ))

fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)',  
    paper_bgcolor='rgba(0,0,0,0)', 
    xaxis=dict(
        title=dict(text="", font=dict(size=11)), 
        tickformat="%H:%M", range=[base_start, base_end],
        showspikes=True, spikemode="across", spikesnap="cursor",
        showgrid=True, 
        gridcolor="rgba(236, 240, 241, 0.5)", 
        gridwidth=0.5,                        
        dtick=3600000,                        
        tickfont=dict(size=11) 
    ),
    yaxis=dict(visible=False, range=[0.5, 1.5]),
    height=150, hovermode="closest",
    margin=dict(l=20, r=20, t=10, b=20)
)

st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})


# ==========================================
# 6. Data View (Chronological Sorted)
# ==========================================
st.markdown("---")
st.markdown("<h3 style='margin-bottom:15px;'><i class='fa-solid fa-table-list' style='color:#8E44AD;'></i> Data Roster for Selected Layers (Chronological Order)</h3>", unsafe_allow_html=True)

filtered_df = day_df[day_df['Category'].isin(selected_cats)].copy()

if not filtered_df.empty:
    filtered_df = filtered_df.sort_values(by='Start', ascending=True)
    
    filtered_df['Start_Time'] = filtered_df['Start'].dt.strftime('%H:%M:%S')
    filtered_df['End_Time'] = filtered_df['End'].dt.strftime('%H:%M:%S')
    
    def color_dot(color):
        return f'<span style="color:{color}; font-size:16px;">●</span>'
    
    filtered_df['Color Tag'] = filtered_df['Color'].apply(color_dot)
    display_cols = ['Color Tag', 'Start_Time', 'End_Time', 'Category', 'Event', 'Detail']
    
    st.write(filtered_df[display_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No active layers selected. Enable toggles on the left to view data.")