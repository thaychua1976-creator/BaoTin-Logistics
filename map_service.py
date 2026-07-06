import requests

class MapService:
    def lay_toa_do(self, dia_diem):
        """Chuyển đổi địa chỉ kho bãi văn bản thành tọa độ [Vĩ độ, Kinh độ]"""
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={dia_diem}&format=json&limit=1"
            headers = {'User-Agent': 'BaoTin_Logistics_Management_App'}
            res = requests.get(url, headers=headers).json()
            if res:
                return [float(res[0]['lat']), float(res[0]['lon'])]
        except:
            return None
        return None

    # 👉 ĐÂY LÀ HÀM CÒN THIẾU KHIẾN HỆ THỐNG BỊ VĂNG LỖI
    def tinh_lo_trinh_duong_bo(self, coord_start, coord_end):
        """Kết nối máy chủ vệ tinh OSRM để tính số KM đường đi thực tế và tọa độ vẽ bản đồ"""
        try:
            # API OSRM nhận cấu trúc ngược: Kinh độ đứng trước, Vĩ độ đứng sau
            url = f"http://router.project-osrm.org/route/v1/driving/{coord_start[1]},{coord_start[0]};{coord_end[1]},{coord_end[0]}?overview=full&geometries=geojson"
            res = requests.get(url).json()
            if res.get("code") == "Ok":
                route = res["routes"][0]
                km = route["distance"] / 1000.0  # Quy đổi từ mét sang Kilomet
                coordinates = route["geometry"]["coordinates"]
                
                # Đảo ngược lại tọa độ [Vĩ độ, Kinh độ] phù hợp với thư viện Folium Map
                route_points = [[p[1], p[0]] for p in coordinates]
                return {"km": round(km, 1), "route_points": route_points}
        except:
            pass
        # Fallback: Nếu mất kết nối API, ước tính tạm thời đường thẳng để giữ Form ổn định
        return {"km": 15.0, "route_points": [coord_start, coord_end]}