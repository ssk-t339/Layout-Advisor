from pydantic import BaseModel
from typing import List, Optional, Tuple
import numpy as np

# --- 1. Pydantic入力モデル (ユーザーからのリクエストボディ) ---

class RoomInput(BaseModel):
    width: float
    depth: float
    door_position: str = "CenterBottom"
    window_position: str = "CenterTop"

class PlacedFurnitureInput(BaseModel):
    name: str
    category: str # "Bed", "Desk", "Sofa", "Shelf" など
    width: float
    depth: float
    height: Optional[float] = None
    x: float
    y: float
    rotation: float = 0.0 # 角度（度）

class DiagnosisRequest(BaseModel):
    room: RoomInput
    placed_furniture_list: List[PlacedFurnitureInput]

# --- 2. 内部クラス (計算ロジック用) ---

class Room:
    def __init__(self, width: float, depth: float, door_position: str, window_position: str):
        self.width = width
        self.depth = depth
        self.door_position = door_position
        self.window_position = window_position

class PlacedFurniture:
    def __init__(self, item: PlacedFurnitureInput):
        self.name = item.name
        self.category = item.category
        self.width = item.width
        self.depth = item.depth
        self.height = item.height
        self.x = item.x
        self.y = item.y
        self.rotation = item.rotation

    # 幾何学計算：回転を考慮した四隅のワールド座標を取得するメソッド
    def get_corners(self) -> List[Tuple[float, float]]:
        w, d = self.width / 2, self.depth / 2
        
        local_corners = [(w, d), (-w, d), (-w, -d), (w, -d)]
        
        corners = []
        angle_rad = np.deg2rad(self.rotation)
        cos_theta = np.cos(angle_rad)
        sin_theta = np.sin(angle_rad)
        
        for lx, ly in local_corners:
            rx = lx * cos_theta - ly * sin_theta
            ry = lx * sin_theta + ly * cos_theta
            
            wx = self.x + rx
            wy = self.y + ry
            corners.append((wx, wy))
            
        return corners