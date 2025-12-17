# main.py (最終修正版)
from fastapi import FastAPI, HTTPException
from backend.models import DiagnosisRequest, Room, PlacedFurniture
from backend.scoring import (
    create_occupancy_grid,
    score_circulation,
    score_zoning,
    score_aesthetics,
    check_hard_constraints # check_hard_constraints は backend/scoring.py に定義されています
)

app = FastAPI()

# --- 診断用APIエンドポイント ---

@app.post("/api/diagnose_layout")
def diagnose_layout(request: DiagnosisRequest):
    try:
        # 1. 入力データを内部モデルに変換
        room = Room(
            width=request.room.width,
            depth=request.room.depth,
            door_x=request.room.door_positions[0][0],
            door_y=request.room.door_positions[0][1],
            window_x=request.room.window_positions[0][0],
            window_y=request.room.window_positions[0][1]
        )
        
        placed_items = [PlacedFurniture(item) for item in request.placed_furniture_list]

        # 2. 【重要】ハード制約チェックを実行し、is_validとwarningsを定義
        is_valid, warnings = check_hard_constraints(room, placed_items)
        
        # 3. スコアリング（採点）の実行
        grid = create_occupancy_grid(room, placed_items)
        
        circulation_score = score_circulation(room, placed_items, grid)
        zoning_score = score_zoning(placed_items)
        aesthetics_score = score_aesthetics(room, placed_items)
        
        # 総合点 (重み付け)
        total_score = (circulation_score * 0.4) + (zoning_score * 0.3) + (aesthetics_score * 0.3)
        total_score_100 = round(total_score * 100, 1)

        # 4. 診断コメントの生成 (LLMの代わりとなるロジック)
        advice = ["診断結果です。"]
        
        # 【重要】物理的な重なりがある場合の処理を最優先
        if not is_valid:
             advice.insert(0, f"【重大】物理的制約違反が{len(warnings)}件あります: {'; '.join(warnings)}")
             total_score_100 = 10.0 # 物理エラー時はスコアを10点に固定
        else:
             # is_validな場合のみ、点数に基づいた評価を行う
             if total_score_100 < 50:
                 advice.append("全体的に再配置が必要です。主要家具間の距離を見直しましょう。")
             elif total_score_100 < 75:
                 advice.append("合格点ですが、微調整で快適性が向上します。")
             else:
                 advice.append("非常に優れた配置です！快適な空間が実現されています。")

             # 個別スコアに基づいたアドバイスもここで追加 (以前のロジック)
             if circulation_score < 0.5:
                 advice.append("動線が悪いです。家具が部屋の移動を妨げています。")
             
             if zoning_score < 0.5:
                 advice.append("ゾーンが分離されていません。仕事場と休息の場をもう少し離しましょう。")
                 
             if aesthetics_score < 0.5:
                 advice.append("家具の向きを見直しましょう。机は窓に背を向けず、ベッドからはドアが見える位置が理想です。")

        # 5. 結果を返す
        return {
            "total_score": total_score_100,
            "details": {
                "circulation": round(circulation_score, 2),
                "zoning": round(zoning_score, 2),
                "aesthetics": round(aesthetics_score, 2)
            },
            "is_valid": is_valid, 
            "warnings": warnings, 
            "advice": " ".join(advice)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        # エラー時に is_valid や warnings が定義されていない可能性を考慮
        response_detail = f"内部エラー: {e}"
        raise HTTPException(status_code=500, detail=response_detail)