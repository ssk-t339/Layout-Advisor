import numpy as np
import heapq
from typing import List, Tuple
from backend.models import Room, PlacedFurniture # 新しいモデルをインポート

RESOLUTION = 0.1  # グリッドの解像度 (10cm/マス)
DIAGONAL_COST = np.sqrt(2)

# --- ユーティリティ関数 ---

def get_position_m(room: Room, position: str) -> np.ndarray:
    """ドア/窓の位置文字列をメートル座標に変換 (簡略版)"""
    if position == "CenterBottom":
        return np.array([room.width / 2, 0.0])
    if position == "CenterTop":
        return np.array([room.width / 2, room.depth])
    # ... (必要に応じて他の位置も追加可能)
    return np.array([room.width / 2, 0.0])

def get_furniture_facing_vector(furniture: PlacedFurniture, face: str = 'Front') -> np.ndarray:
    """家具の指定された面の方向ベクトルを取得 (簡略版)"""
    # 0度: Y軸正方向(奥)
    base_direction = np.array([0, 1])
    if face == 'Back': base_direction = np.array([0, -1])
    if face == 'Right': base_direction = np.array([1, 0])
    if face == 'Left': base_direction = np.array([-1, 0])

    angle_rad = np.deg2rad(furniture.rotation)
    cos_theta = np.cos(angle_rad)
    sin_theta = np.sin(angle_rad)

    # 回転行列を適用
    rx = base_direction[0] * cos_theta - base_direction[1] * sin_theta
    ry = base_direction[0] * sin_theta + base_direction[1] * cos_theta
    return np.array([rx, ry])

# --- A*アルゴリズム (動線計算) ---

def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def calculate_astar_path(
    grid: np.ndarray, 
    start: Tuple[int, int], 
    end: Tuple[int, int], 
    resolution: float = RESOLUTION
) -> float:
    rows, cols = grid.shape
    
    start_r, start_c = start
    end_r, end_c = end

    # 必須チェック (グリッド内にあり、障害物でないか)
    if not (0 <= start_r < rows and 0 <= start_c < cols and 
            0 <= end_r < rows and 0 <= end_c < cols):
        return np.inf

    if grid[start_r, start_c] == 1 or grid[end_r, end_c] == 1:
        return np.inf
    
    open_list = [(0.0, start_r, start_c)]
    g_cost = np.full((rows, cols), np.inf)
    g_cost[start_r, start_c] = 0.0
    
    while open_list:
        f_cost, r, c = heapq.heappop(open_list)
        current = (r, c)

        if current == end:
            return g_cost[r, c] * resolution

        for dr, dc in [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]:
            neighbor_r, neighbor_c = r + dr, c + dc
            
            if not (0 <= neighbor_r < rows and 0 <= neighbor_c < cols):
                continue
            
            if grid[neighbor_r, neighbor_c] == 1:
                continue

            move_cost = DIAGONAL_COST if dr != 0 and dc != 0 else 1.0
            new_g_cost = g_cost[r, c] + move_cost
            
            if new_g_cost < g_cost[neighbor_r, neighbor_c]:
                g_cost[neighbor_r, neighbor_c] = new_g_cost
                h = heuristic((neighbor_r, neighbor_c), end)
                f = new_g_cost + h
                heapq.heappush(open_list, (f, neighbor_r, neighbor_c))

    return np.inf

# --- グリッド生成関数 ---

def create_occupancy_grid(room: Room, placed_furniture_list: List[PlacedFurniture]) -> np.ndarray:
    """部屋と家具から占有グリッドマップを生成する。"""
    
    rows = int(room.depth / RESOLUTION)
    cols = int(room.width / RESOLUTION)
    grid = np.zeros((rows, cols), dtype=int)
    
    # 家具をグリッドに配置
    for item in placed_furniture_list:
        corners = item.get_corners()
        
        # 軸に沿ったバウンディングボックスを見つける
        min_x = int(np.min([c[0] for c in corners]) / RESOLUTION)
        max_x = int(np.max([c[0] for c in corners]) / RESOLUTION)
        min_y = int(np.min([c[1] for c in corners]) / RESOLUTION)
        max_y = int(np.max([c[1] for c in corners]) / RESOLUTION)
        
        # グリッドの境界にクリップ
        min_x = max(0, min_x)
        max_x = min(cols - 1, max_x)
        min_y = max(0, min_y)
        max_y = min(rows - 1, max_y)
        
        # バウンディングボックス内のセルを占有マーク（1）する
        # ここでは回転を完全に考慮せず、単純なAABBでマークします（簡略化）
        grid[min_y : max_y + 1, min_x : max_x + 1] = 1
        
    return grid

# --- スコアリング関数 ---

def score_circulation(room: Room, placed_furniture_list: List[PlacedFurniture], grid: np.ndarray) -> float:
    """動線のスコア (ドアから主要家具までの最短経路)"""
    
    door_pos_m = get_position_m(room, room.door_position)
    circulation_scores = []
    
    # 評価対象: ベッド、デスク、ソファ
    target_categories = ['Bed', 'Desk', 'Sofa']
    target_items = [f for f in placed_furniture_list if f.category in target_categories]
    
    for item in target_items:
        item_center_m = np.array([item.x, item.y])
        
        # メートル座標をグリッド座標に変換 (y軸はroom.depthと逆転しているため注意)
        # グリッド座標 (row, col) = (Y, X)
        start_grid = (int(door_pos_m[1] / RESOLUTION), int(door_pos_m[0] / RESOLUTION))
        end_grid = (int(item_center_m[1] / RESOLUTION), int(item_center_m[0] / RESOLUTION))
        
        path_length_m = calculate_astar_path(grid, start_grid, end_grid, resolution=RESOLUTION)
        
        if path_length_m != np.inf:
            # 経路長が短いほどスコアが高い (最大経路長 10m を想定)
            max_path_length = room.width + room.depth + 1.0
            path_score = 1.0 - np.clip(path_length_m / max_path_length, 0.0, 1.0)
            circulation_scores.append(path_score)

    if not circulation_scores:
        return 0.5 # 対象がない場合は中間スコア
        
    return float(np.mean(circulation_scores))

def score_aesthetics(room: Room, placed_furniture_list: List[PlacedFurniture]) -> float:
    """美観・心理的快適性のスコア (窓やドアに対する向き)"""
    # シンプルな実装のため、前のバージョンをそのまま利用
    aesthetics_scores = []
    DOOR_CENTER = get_position_m(room, room.door_position)
    WINDOW_CENTER = get_position_m(room, room.window_position)
    
    # デスク評価
    desks = [f for f in placed_furniture_list if f.category == 'Desk']
    for desk in desks:
        # 評価1: 窓との向き
        desk_pos = np.array([desk.x, desk.y])
        window_to_desk = desk_pos - WINDOW_CENTER
        desk_facing = get_furniture_facing_vector(desk, 'Front') # Frontは座面方向と仮定

        norm_product = (np.linalg.norm(desk_facing) * np.linalg.norm(window_to_desk))
        dot_product = np.dot(desk_facing, window_to_desk) / norm_product if norm_product != 0 else 0
        window_score = 1.0 - abs(dot_product) 

        # 評価2: ドア方向への壁の向き (壁を背にする)
        door_dir = DOOR_CENTER - desk_pos
        door_dir_unit = door_dir / np.linalg.norm(door_dir) if np.linalg.norm(door_dir) != 0 else np.array([0, 1])
        wall_orientation_score = 1.0 - abs(np.dot(desk_facing, door_dir_unit))

        desk_score = 0.5 * window_score + 0.5 * wall_orientation_score
        aesthetics_scores.append(desk_score)
        
    # ベッド評価 (コマンドポジション)
    beds = [f for f in placed_furniture_list if f.category == 'Bed']
    for bed in beds:
        bed_facing = get_furniture_facing_vector(bed, 'Front')
        bed_pos = np.array([bed.x, bed.y])
        bed_to_door = DOOR_CENTER - bed_pos
        
        bed_to_door_unit = bed_to_door / np.linalg.norm(bed_to_door) if np.linalg.norm(bed_to_door) != 0 else np.array([0, 1])

        # ベッドの頭部側 (-bed_facing) がドア方向を向いているか (ドット積 > 0.7)
        command_dot = np.dot(-bed_facing, bed_to_door_unit) 
        aesthetics_scores.append(1.0 if command_dot > 0.7 else 0.5)
            
    if not aesthetics_scores: return 0.5
    return float(np.mean(aesthetics_scores))

def score_zoning(placed_furniture_list: List[PlacedFurniture]) -> float:
    """ゾーニングのスコア (類似家具の近接度)"""
    
    # 簡略化のため、BedとDeskの近接度のみを評価
    beds = [f for f in placed_furniture_list if f.category == 'Bed']
    desks = [f for f in placed_furniture_list if f.category == 'Desk']
    
    if not beds or not desks:
        return 0.5
        
    # すべてのベッドとデスクの組み合わせの最短距離を計算
    min_distance = np.inf
    for bed in beds:
        bed_pos = np.array([bed.x, bed.y])
        for desk in desks:
            desk_pos = np.array([desk.x, desk.y])
            distance = np.linalg.norm(bed_pos - desk_pos)
            min_distance = min(min_distance, distance)
            
    # 距離が近いほどスコアが低い (ゾーン分離)
    # 2.0m以上離れていれば満点
    max_desired_distance = 2.0 
    
    # 距離 0 でスコア 0、距離 2.0m でスコア 1.0
    zoning_score = np.clip(min_distance / max_desired_distance, 0.0, 1.0)
    
    return float(zoning_score)

def check_hard_constraints(room: Room, placed_furniture_list: List[PlacedFurniture]) -> Tuple[bool, List[str]]:
    """
    家具の重なりや、部屋の境界からの逸脱などのハード制約をチェックする。
    """
    warnings = []
    is_valid = True

    for i, item in enumerate(placed_furniture_list):
        # 1. 部屋の境界チェック
        corners = item.get_corners()
        
        # すべての角が部屋の範囲内にあるか確認
        for x, y in corners:
            if not (0 <= x <= room.width and 0 <= y <= room.depth):
                warnings.append(f"{item.name} ({item.category}) が部屋からはみ出しています。")
                is_valid = False
                break
        
        # 2. 家具同士の重なりチェック (簡易版: 中心距離ベース)
        # より正確にはSATやPolygon Intersectionを使うが、ここでは簡略化
        for j, other in enumerate(placed_furniture_list):
            if i >= j: continue # 同じ組み合わせを二度チェックしない

            # 中心間の距離を計算
            dist_centers = np.linalg.norm(np.array([item.x, item.y]) - np.array([other.x, other.y]))
            
            # 簡易的な最小距離を推定（幅と奥行きの平均の合計）
            min_required_dist = (item.width + item.depth) / 4 + (other.width + other.depth) / 4
            
            if dist_centers < min_required_dist:
                warnings.append(f"{item.name} と {other.name} が重なっている可能性があります。")
                is_valid = False
    
    return is_valid, warnings