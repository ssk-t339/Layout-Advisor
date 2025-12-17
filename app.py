# app.py
import streamlit as st
import requests
import json
import numpy as np

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

# 初期家具リスト（テストデータと同じもの）
# furniture_listをセッションステートで管理し、リロード後も状態を維持する
if 'furniture_list' not in st.session_state:
    st.session_state.furniture_list = [
        {"name": "ダブルベッド", "category": "Bed", "width": 1.6, "depth": 2.0, "x": 2.0, "y": 1.5, "rotation": 0.0},
        {"name": "デスク", "category": "Desk", "width": 1.2, "depth": 0.7, "x": 2.0, "y": 3.0, "rotation": 90.0},
        {"name": "本棚", "category": "Shelf", "width": 0.8, "depth": 0.3, "x": 0.5, "y": 0.5, "rotation": 0.0},
        {"name": "ソファ", "category": "Sofa", "width": 1.8, "depth": 0.9, "x": 3.5, "y": 4.0, "rotation": 180.0}
    ]

# --- 家具リスト操作ボタン ---
col_add, col_placeholder = st.columns([1, 5])

def add_furniture():
    """新しいデフォルト家具を追加する関数"""
    st.session_state.furniture_list.append(
        {"name": "新規家具", "category": "Shelf", "width": 0.5, "depth": 0.5, "x": 1.0, "y": 1.0, "rotation": 0.0}
    )
    # 追加後に画面を再描画するため、Rerunが必要になるが、Streamlitの仕様でボタンがクリックされた後自動的に再実行される

col_add.button("➕ 新しい家具を追加", on_click=add_furniture)


# --- 現在の家具リストの表示と編集 ---

# 編集後のリストを一時的に保持
furniture_inputs = [] 
# 削除候補のインデックスを保持
indices_to_delete = []

st.markdown("---")

for i, f in enumerate(st.session_state.furniture_list):
    # 各家具を expender で囲む
    with st.expander(f"**{f['name']} ({f['category']})** - 配置: ({f['x']:.1f}, {f['y']:.1f})m", expanded=False):
        
        # 削除ボタン
        if st.button(f"この家具を削除", key=f"delete_btn_{i}"):
            indices_to_delete.append(i)
        
        st.markdown("---")

        col_n, col_c = st.columns(2)
        # キーをiを使ってユニークにする
        f['name'] = col_n.text_input("名称", f['name'], key=f"name_{i}")
        f['category'] = col_c.selectbox("カテゴリ", ['Bed', 'Desk', 'Sofa', 'Shelf', 'Table', 'Other'], 
                                        index=['Bed', 'Desk', 'Sofa', 'Shelf', 'Table', 'Other'].index(f['category']), 
                                        key=f"cat_{i}")
        
        st.subheader("配置")
        col1, col2, col3 = st.columns(3)
        # 部屋のサイズに合わせてスライダーの最大値を動的に変更
        f['x'] = col1.slider("X座標 (横)", 0.0, room_width, f['x'], 0.1, key=f"x_{i}")
        f['y'] = col2.slider("Y座標 (縦)", 0.0, room_depth, f['y'], 0.1, key=f"y_{i}")
        f['rotation'] = col3.slider("回転 (度)", 0.0, 359.9, f['rotation'], 1.0, key=f"rot_{i}")
        
        st.subheader("サイズ")
        col4, col5 = st.columns(2)
        f['width'] = col4.number_input("横幅", 0.1, 5.0, f['width'], 0.1, key=f"w_{i}")
        f['depth'] = col5.number_input("奥行", 0.1, 5.0, f['depth'], 0.1, key=f"d_{i}")
        
    furniture_inputs.append(f)


# --- 削除処理の実行 ---
if indices_to_delete:
    # 削除フラグが立っているインデックスを逆順にソートして削除 (インデックスずれ防止)
    for i in sorted(indices_to_delete, reverse=True):
        st.session_state.furniture_list.pop(i)
    
    # 削除後に画面を再実行
    st.rerun()

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