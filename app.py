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
    # 既存のプロセスがあるか確認せずに起動を試みる
    subprocess.Popen(["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])
    st.session_state.backend_started = True
    time.sleep(3) # 起動を待つ

# FastAPIサーバーのエンドポイントURL
FASTAPI_URL = "http://127.0.0.1:8000/api/diagnose_layout"

st.set_page_config(page_title="AIレイアウト診断", layout="wide")

st.title("AIルームレイアウト診断アドバイザー")
st.markdown("現在の家具配置を入力すると、動線・ゾーニング・美観の観点からスコアとアドバイスを提供します。")

# --- 1. 部屋のサイズ入力 ---
st.header("1. 部屋の基本情報 (m)")
col_w, col_d = st.columns(2)
room_width = col_w.slider("部屋の横幅 (Width)", 3.0, 8.0, 4.0, 0.1)
room_depth = col_d.slider("部屋の奥行 (Depth)", 3.0, 8.0, 5.0, 0.1)

# --- 2. 家具情報の入力 ---
st.header("2. 家具の配置とサイズ (m)")

# 画面を 7:3 (または 6:4) の比率で分割
col_input, col_preview = st.columns([7, 3])

# --- 左側の操作パネル ---
with col_panel:
    if 'furniture_list' not in st.session_state:
        st.session_state.furniture_list = [
            {"name": "ダブルベッド", "category": "Bed", "width": 1.6, "depth": 2.0, "x": 2.0, "y": 1.5, "rotation": 0.0},
            {"name": "デスク", "category": "Desk", "width": 1.2, "depth": 0.7, "x": 2.0, "y": 3.0, "rotation": 90.0},
            {"name": "本棚", "category": "Shelf", "width": 0.8, "depth": 0.3, "x": 0.5, "y": 0.5, "rotation": 0.0},
            {"name": "ソファ", "category": "Sofa", "width": 1.8, "depth": 0.9, "x": 3.5, "y": 4.0, "rotation": 180.0}
        ]

    # 家具追加ボタン
    def add_furniture():
        st.session_state.furniture_list.append(
            {"name": "新規家具", "category": "Shelf", "width": 0.5, "depth": 0.5, "x": 1.0, "y": 1.0, "rotation": 0.0}
        )
    st.button("➕ 新しい家具を追加", on_click=add_furniture)

    # 現在の家具リストの編集
    furniture_inputs = [] 
    indices_to_delete = []

    for i, f in enumerate(st.session_state.furniture_list):
        with st.expander(f"**{f['name']}** ({f['category']})", expanded=False):
            if st.button(f"削除", key=f"delete_btn_{i}"):
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

    # 削除処理
    if indices_to_delete:
        for i in sorted(indices_to_delete, reverse=True):
            st.session_state.furniture_list.pop(i)
        st.rerun()

# --- 右側のプレビュー表示 (col_preview の中に入れる) ---
with col_preview:
    st.subheader("レイアウト図")
    
    # 図を小さく描画するために figsize を調整 (4x4インチ程度)
    fig, ax = plt.subplots(figsize=(4, 4))
    
    # 部屋のスケールに合わせて余裕を持たせる
    ax.set_xlim(-0.2, room_width + 0.2)
    ax.set_ylim(-0.2, room_depth + 0.2)
    ax.set_aspect('equal')
    ax.axis('off') # 軸目盛りを消してスッキリさせる

    # 部屋の枠
    room_rect = patches.Rectangle((0, 0), room_width, room_depth, fill=False, edgecolor='black', lw=3)
    ax.add_patch(room_rect)

    # 家具を一つずつ描画
    for f in furniture_inputs:
        rect = patches.Rectangle(
            (f['x'] - f['width']/2, f['y'] - f['depth']/2), 
            f['width'], f['depth'], 
            angle=f['rotation'], rotation_point='center',
            alpha=0.6, facecolor='#1f77b4', edgecolor='white'
        )
        ax.add_patch(rect)
        # ラベル表示
        ax.text(f['x'], f['y'], f['name'], ha='center', va='center', fontsize=6, fontweight='bold')

    # ドアと窓の表示 (赤=ドア, 緑=窓)
    ax.plot([room_width/2], [0], 'rs', markersize=8) 
    ax.plot([room_width/2], [room_depth], 'gs', markersize=8)

    # カラム幅いっぱいに表示。ただし占有しすぎないようにする。
    st.pyplot(fig, use_container_width=True)
    
    st.caption("🔴:ドア 🟢:窓")
    st.info("スライダーを動かすと図が更新されます。")

# --- 2.5 リアルタイム・レイアウトプレビュー ---
st.header("現在のレイアウト確認")

# グラフの作成
fig, ax = plt.subplots(figsize=(6, 6))
ax.set_xlim(-0.5, room_width + 0.5)
ax.set_ylim(-0.5, room_depth + 0.5)
ax.set_aspect('equal')
ax.grid(True, linestyle='--', alpha=0.6)

# 部屋の壁を描画
room_rect = patches.Rectangle((0, 0), room_width, room_depth, fill=False, edgecolor='black', lw=4)
ax.add_patch(room_rect)

# 家具を描画
for f in furniture_inputs:
    # 四角形の左下座標を計算（中心座標からサイズ分引く）
    # 回転を考慮するため、あえて patches.Rectangle の rotation を使用
    rect = patches.Rectangle(
        (f['x'] - f['width']/2, f['y'] - f['depth']/2), 
        f['width'], f['depth'], 
        angle=f['rotation'], 
        rotation_point='center',
        alpha=0.6, 
        facecolor='#1f77b4', 
        edgecolor='white',
        label=f['name']
    )
    ax.add_patch(rect)
    
    # 家具の名前を表示
    ax.text(f['x'], f['y'], f['name'], ha='center', va='center', fontsize=9, fontweight='bold')

# ドアと窓の簡易表示（位置固定）
ax.plot([room_width/2], [0], 'rs', markersize=10, label="Door") # Door
ax.plot([room_width/2], [room_depth], 'gs', markersize=10, label="Window") # Window

st.pyplot(fig)
st.caption("※ 青いボックスが家具、赤がドア、緑が窓です。スライダーを動かすとリアルタイムで更新されます。")

# --- 3. 診断ボタン ---
st.markdown("---")
if st.button("このレイアウトを診断する", type="primary"):
    
    # FastAPIに送信するJSONデータを作成
    diagnosis_request = {
        "room": {
            "width": room_width,
            "depth": room_depth,
            "door_position": "CenterBottom",
            "window_position": "CenterTop"
        },
        "placed_furniture_list": furniture_inputs
    }
    
    # FastAPIサーバーにPOSTリクエストを送信
    try:
        response = requests.post(FASTAPI_URL, json=diagnosis_request, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            st.success("診断が完了しました！")
            
            # --- 結果の表示 ---
            
            col_score, col_advice = st.columns([1, 2])
            
            with col_score:
                st.metric("総合スコア (100点満点)", f"{result['total_score']}点")
                st.subheader("スコア詳細")
                st.write(f"動線 (Circulation): {result['details']['circulation']:.2f}")
                st.write(f"ゾーニング (Zoning): {result['details']['zoning']:.2f}")
                st.write(f"美観 (Aesthetics): {result['details']['aesthetics']:.2f}")

            with col_advice:
                st.subheader("アドバイス")
                st.info(result['advice'])
                details = result['details']
                
                if details['circulation'] < 0.6:
                    st.warning("**動線スコアが低いです。**")
                    st.markdown("""
                        主要家具（ベッド、デスク、ソファ）がドアから離れていたり、移動経路を塞いでいる可能性があります。
                        **家具を壁側に寄せるか、ドアへの経路を確保**するとスコアが大きく向上します。
                    """)
                
                if details['zoning'] < 0.6:
                    st.warning("**ゾーニングスコアが低いです。**")
                    st.markdown("""
                        睡眠エリアと作業エリア（ベッドとデスク）が近すぎます。
                        **本棚やキャビネットで空間を仕切る**などして、視覚的にゾーニングを分離しましょう。
                    """)
                    
                if details['aesthetics'] < 0.8: # 美観が0.8未満の場合、具体的な向きを提案
                    st.warning("**美観スコアを改善しましょう。**")
                    st.markdown("""
                        デスクやベッドの向きが理想的ではありません。
                        **デスクの回転角度**を調整し、窓を正面または横に見る位置にし、ドアに背を向けないようにしてください。
                    """)
                
                if result['is_valid'] == False: # 物理的な重なりがあった場合
                    st.error("**【重大な問題】物理的な重なりがあります。**")
                    st.markdown("家具が重なっているか、部屋からはみ出しています。まずは**重なりを解消**してください。")
                
        else:
            st.error(f"FastAPI側でエラーが発生しました。ステータスコード: {response.status_code}")
            st.json(response.json())
            
    except requests.exceptions.RequestException as e:
        st.error(f"FastAPIサーバーに接続できませんでした。サーバーが起動しているか確認してください。エラー: {e}")