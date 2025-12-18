import streamlit as st
import requests
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import subprocess
import time

# バックエンドの自動起動（デプロイ環境用）
if "backend_started" not in st.session_state:
    subprocess.Popen(["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
    st.session_state.backend_started = True
    time.sleep(3)

# FastAPIサーバーのエンドポイントURL
FASTAPI_URL = "http://127.0.0.1:8000/api/diagnose_layout"

st.set_page_config(page_title="レイアウト診断", layout="wide")

st.title("ルームレイアウト診断アドバイザー")
st.markdown("現在の家具配置を入力すると、動線・ゾーニング・美観の観点からスコアとアドバイスを提供します。")

# --- 1. 部屋のサイズ入力 ---
st.header("1. 部屋の基本情報 (m)")
col_w, col_d = st.columns(2)
room_width = col_w.slider("部屋の横幅 (Width)", 3.0, 8.0, 4.0, 0.1)
room_depth = col_d.slider("部屋の奥行 (Depth)", 3.0, 8.0, 5.0, 0.1)

st.markdown("🔧 **建具の位置設定** (壁沿いに配置してください)")
num_doors = st.sidebar.number_input("ドアの数", 1, 3, 1)
num_windows = st.sidebar.number_input("窓の数", 1, 3, 1)

door_positions = []
for i in range(num_doors):
    with st.sidebar.expander(f"ドア {i+1} の位置"):
        dx = st.slider(f"X座標", 0.0, room_width, room_width/2, 0.1, key=f"dx{i}")
        dy = st.slider(f"Y座標", 0.0, room_depth, 0.0, 0.1, key=f"dy{i}")
        door_positions.append([dx, dy])

window_positions = []
for i in range(num_windows):
    with st.sidebar.expander(f"窓 {i+1} の位置"):
        wx = st.slider(f"X座標", 0.0, room_width, room_width/2, 0.1, key=f"wx{i}")
        wy = st.slider(f"Y座標", 0.0, room_depth, room_depth, 0.1, key=f"wy{i}")
        window_positions.append([wx, wy])

# --- 2. 家具情報の入力 ---
st.header("2. 家具の配置とサイズ (m) & レイアウト確認")

# 【修正点1】col_input として定義
col_input, col_preview = st.columns([7, 3])

if 'furniture_list' not in st.session_state:
    st.session_state.furniture_list = [
        {"name": "ダブルベッド", "category": "Bed", "width": 1.6, "depth": 2.0, "x": 2.0, "y": 1.5, "rotation": 0.0},
        {"name": "デスク", "category": "Desk", "width": 1.2, "depth": 0.7, "x": 2.0, "y": 3.0, "rotation": 90.0},
        {"name": "本棚", "category": "Shelf", "width": 0.8, "depth": 0.3, "x": 0.5, "y": 0.5, "rotation": 0.0},
        {"name": "ソファ", "category": "Sofa", "width": 1.8, "depth": 0.9, "x": 3.5, "y": 4.0, "rotation": 180.0}
    ]

# 【修正点2】col_input を使用
with col_input:
    def add_furniture():
        st.session_state.furniture_list.append(
            {"name": "新規家具", "category": "Shelf", "width": 0.5, "depth": 0.5, "x": 1.0, "y": 1.0, "rotation": 0.0}
        )
    st.button("➕ 新しい家具を追加", on_click=add_furniture)

    furniture_inputs = [] 
    indices_to_delete = []

    for i, f in enumerate(st.session_state.furniture_list):
        with st.expander(f"**{f['name']}** ({f['category']})", expanded=False):
            if st.button(f"この家具を削除", key=f"delete_btn_{i}"):
                indices_to_delete.append(i)
            
            col_n, col_c = st.columns(2)
            f['name'] = col_n.text_input("名称", f['name'], key=f"name_{i}")
            f['category'] = col_c.selectbox("カテゴリ", ['Bed', 'Desk', 'Sofa', 'Shelf', 'Table', 'Other'], 
                                            index=['Bed', 'Desk', 'Sofa', 'Shelf', 'Table', 'Other'].index(f['category']), 
                                            key=f"cat_{i}")
            
            c1, c2, c3 = st.columns(3)
            f['x'] = c1.slider("X (横)", 0.0, room_width, f['x'], 0.1, key=f"x_{i}")
            f['y'] = c2.slider("Y (縦)", 0.0, room_depth, f['y'], 0.1, key=f"y_{i}")
            f['rotation'] = c3.slider("回転", 0.0, 359.0, f['rotation'], 1.0, key=f"rot_{i}")
            
            c4, c5 = st.columns(2)
            f['width'] = c4.number_input("幅", 0.1, 5.0, f['width'], 0.1, key=f"w_{i}")
            f['depth'] = c5.number_input("奥", 0.1, 5.0, f['depth'], 0.1, key=f"d_{i}")
            
        furniture_inputs.append(f)

    if indices_to_delete:
        for i in sorted(indices_to_delete, reverse=True):
            st.session_state.furniture_list.pop(i)
        st.rerun()

# --- 右側のプレビュー表示 (占有率30%に収める) ---
with col_preview:
    st.subheader("レイアウト図")
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.set_xlim(-0.2, room_width + 0.2)
    ax.set_ylim(-0.2, room_depth + 0.2)
    ax.set_aspect('equal')
    ax.axis('off') 

    room_rect = patches.Rectangle((0, 0), room_width, room_depth, fill=False, edgecolor='black', lw=3)
    ax.add_patch(room_rect)

    for f in furniture_inputs:
        rect = patches.Rectangle(
            (f['x'] - f['width']/2, f['y'] - f['depth']/2), 
            f['width'], f['depth'], 
            angle=f['rotation'], rotation_point='center',
            alpha=0.6, facecolor='#1f77b4', edgecolor='white'
        )
        ax.add_patch(rect)
        label_text = f"{f['category']}" # 例: Bed, Desk
        ax.text(f['x'], f['y'], label_text, ha='center', va='center', fontsize=6, fontweight='bold')

    for d in door_positions:
        ax.plot(d[0], d[1], 'rs', markersize=10)
    for w in window_positions:
        ax.plot(w[0], w[1], 'gs', markersize=10)

    st.pyplot(fig, use_container_width=True)
    st.caption("🔴:ドア 🟢:窓")
    st.info("スライダーを動かすと図が更新されます。")

# 【修正点3】重複していた巨大な図の描画コード（旧2.5）を削除しました

# --- 3. 診断ボタン ---
st.markdown("---")
if st.button("このレイアウトを診断する", type="primary"):
    diagnosis_request = {
        "room": {
            "width": room_width,
            "depth": room_depth,
            "door_positions": door_positions,
            "window_positions": window_positions
        },
        "placed_furniture_list": furniture_inputs
    }
    
    try:
        response = requests.post(FASTAPI_URL, json=diagnosis_request, timeout=10)
        if response.status_code == 200:
            result = response.json()
            st.success("診断が完了しました！")
            
            col_score, col_advice = st.columns([1, 2])
            with col_score:
                st.metric("総合スコア", f"{result['total_score']}点")
                st.write(f"動線: {result['details']['circulation']:.2f}")
                st.write(f"ゾーニング: {result['details']['zoning']:.2f}")
                st.write(f"美観: {result['details']['aesthetics']:.2f}")

            with col_advice:
                st.subheader("アドバイス")
                st.info(result['advice'])
                details = result['details']
                
                if details['circulation'] < 0.6:
                    st.warning("**動線スコアが低いです。** 家具を壁に寄せ、ドアからの経路を確保しましょう。")
                if details['zoning'] < 0.6:
                    st.warning("**ゾーニングスコアが低いです。** 寝る場所と働く場所を離しましょう。")
                if details['aesthetics'] < 0.8:
                    st.warning("**美観スコアを改善しましょう。** デスクの向きや窓との関係を見直してください。")
                if not result.get('is_valid', True):
                    st.error("**物理的な重なりがあります。** 配置を修正してください。")
        else:
            st.error(f"エラーが発生しました: {response.status_code}")
    except Exception as e:
        st.error(f"サーバーに接続できません: {e}")