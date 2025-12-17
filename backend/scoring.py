import numpy as np
import heapq
from typing import List, Tuple
from backend.models import Room, PlacedFurniture

RESOLUTION = 0.1  # グリッドの解像度 (10cm/マス)
DIAGONAL_COST = np.sqrt(2)

# --- ユーティリティ関数 ---

def get_furniture_facing_vector(furniture: PlacedFurniture, face: str = 'Front') -> np.ndarray:
    """家具の指定された面の方向ベクトルを取得"""
    base_direction = np.array([0, 1])
    if face == 'Back': base_direction = np.array([0, -1])
    if face == 'Right': base_direction = np.array([1, 0])
    if face == 'Left': base_direction = np.array([-1, 0])

    angle_rad = np.deg2rad(furniture.rotation)
    cos_theta = np.cos(angle_rad)
    sin_theta = np.sin(angle_rad)

    rx = base_direction[0] * cos_theta - base_direction[1] * sin_theta
    ry = base_direction[0] * sin_theta + base_direction[1] * cos_theta
    return np.array([rx, ry])

# --- A*アルゴリズム (動線計算) ---

def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def calculate_astar_path(grid: np.ndarray, start: Tuple[int, int], end: Tuple[int, int], resolution: float = RESOLUTION) -> float:
    rows, cols = grid.shape
    start_r, start_c = start
    end_r, end_c = end

    if not (0 <= start_r < rows and 0 <= start_c < cols and 0 <= end_r < rows and 0 <= end_c < cols):
        return np.inf
    if grid[start_r, start_c] == 1 or grid[end_r, end_c] == 1:
        return np.inf
    
    open_list = [(0.0, start_r, start_c)]
    g_cost = np.full((rows, cols), np.inf)
    g_cost[start_r, start_c] = 0.0
    
    while open_list:
        f_cost, r, c = heapq.heappop(open_list)
        if (r, c) == end:
            return g_cost[r, c] * resolution

        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or grid[nr, nc] == 1:
                continue
            move_cost = DIAGONAL_COST if dr != 0 and dc != 0 else 1.0
            new_g = g_cost[r, c] + move_cost
            if new_g < g_cost[nr, nc]:
                g_cost[nr, nc] = new_g
                heapq.heappush(open_list, (new_g + heuristic((nr, nc), end), nr, nc))
    return np.inf

# --- グリッド生成関数 ---

def create_occupancy_grid(room: Room, placed_furniture_list: List[PlacedFurniture]) -> np.ndarray:
    rows, cols = int(room.depth / RESOLUTION), int(room.width / RESOLUTION)
    grid = np.zeros((rows, cols), dtype=int)
    for item in placed_furniture_list:
        corners = item.get_corners()
        min_x = max(0, int(np.min([c[0] for c in corners]) / RESOLUTION))
        max_x = min(cols - 1, int(np.max([c[0] for c in corners]) / RESOLUTION))
        min_y = max(0, int(np.min([c[1] for c in corners]) / RESOLUTION))
        max_y = min(rows - 1, int(np.max([c[1] for c in corners]) / RESOLUTION))
        grid[min_y : max_y + 1, min_x : max_x + 1] = 1
    return grid

# --- スコアリング関数 ---

def score_circulation(room: Room, placed_furniture_list: List[PlacedFurniture], grid: np.ndarray) -> float:
    target_items = [f for f in placed_furniture_list if f.category in ['Bed', 'Desk', 'Sofa']]
    scores = []
    
    for item in target_items:
        best_path = np.inf
        for d_pos in room.door_positions:
            start = (int(d_pos[1] / RESOLUTION), int(d_pos[0] / RESOLUTION))
            end = (int(item.y / RESOLUTION), int(item.x / RESOLUTION))
            path_len = calculate_astar_path(grid, start, end)
            best_path = min(best_path, path_len)
        
        if best_path != np.inf:
            max_len = room.width + room.depth + 1.0
            scores.append(1.0 - np.clip(best_path / max_len, 0.0, 1.0))

    return float(np.mean(scores)) if scores else 0.5

def score_aesthetics(room: Room, placed_furniture_list: List[PlacedFurniture]) -> float:
    scores = []
    
    # デスク評価
    for desk in [f for f in placed_furniture_list if f.category == 'Desk']:
        desk_pos = np.array([desk.x, desk.y])
        facing = get_furniture_facing_vector(desk, 'Front')

        # 最も条件の良い窓を探す
        win_score = 0.0
        for w_pos in room.window_positions:
            w_dir = desk_pos - np.array(w_pos)
            norm = (np.linalg.norm(facing) * np.linalg.norm(w_dir))
            dot = np.dot(facing, w_dir) / norm if norm != 0 else 0
            win_score = max(win_score, 1.0 - abs(dot))

        # 最も条件の良いドアを探す (背後が壁=ドアから遠い/向きが逆)
        wall_score = 0.0
        for d_pos in room.door_positions:
            d_dir = np.array(d_pos) - desk_pos
            d_dir_u = d_dir / np.linalg.norm(d_dir) if np.linalg.norm(d_dir) != 0 else np.array([0,1])
            wall_score = max(wall_score, 1.0 - abs(np.dot(facing, d_dir_u)))

        scores.append(0.5 * win_score + 0.5 * wall_score)
        
    # ベッド評価 (コマンドポジション: ドアが見えるが直線上ではない)
    for bed in [f for f in placed_furniture_list if f.category == 'Bed']:
        bed_pos = np.array([bed.x, bed.y])
        # 頭の位置（正面の逆）がドアの方を向いているか
        facing_back = -get_furniture_facing_vector(bed, 'Front') 
        
        best_bed_score = 0.0
        for d_pos in room.door_positions:
            d_vec = np.array(d_pos) - bed_pos
            d_vec_u = d_vec / np.linalg.norm(d_vec) if np.linalg.norm(d_vec) != 0 else np.array([0, 1])
            dot = np.dot(facing_back, d_vec_u)
            best_bed_score = max(best_bed_score, 1.0 if dot > 0.7 else 0.5)
        scores.append(best_bed_score)
            
    return float(np.mean(scores)) if scores else 0.5

def score_zoning(placed_furniture_list: List[PlacedFurniture]) -> float:
    beds = [f for f in placed_furniture_list if f.category == 'Bed']
    desks = [f for f in placed_furniture_list if f.category == 'Desk']
    if not beds or not desks: return 0.5
    
    min_dist = np.min([np.linalg.norm(np.array([b.x, b.y]) - np.array([d.x, d.y])) for b in beds for d in desks])
    return float(np.clip(min_dist / 2.0, 0.0, 1.0))

def check_hard_constraints(room: Room, placed_furniture_list: List[PlacedFurniture]) -> Tuple[bool, List[str]]:
    warnings, is_valid = [], True
    for i, item in enumerate(placed_furniture_list):
        for x, y in item.get_corners():
            if not (0 <= x <= room.width and 0 <= y <= room.depth):
                warnings.append(f"{item.name}が部屋からはみ出しています。")
                is_valid = False
                break
        for j, other in enumerate(placed_furniture_list):
            if i >= j: continue
            dist = np.linalg.norm(np.array([item.x, item.y]) - np.array([other.x, other.y]))
            if dist < (item.width + item.depth + other.width + other.depth) / 4:
                warnings.append(f"{item.name}と{other.name}が重なっています。")
                is_valid = False
    return is_valid, warnings