# ==========================================
# FILE: gps_service.py (KẾT NỐI API HỘP ĐEN)
# ==========================================
import requests
import random
import streamlit as st

class GpsService:
    def __init__(self):
        # Khai báo các URL API của nhà cung cấp (Thay bằng URL thật khi bàn giao)
        self.api_endpoints = {
            "VIETMAP": "https://api.vietmap.vn/v1/device/status",
            "ADSUN": "https://api.adsun.vn/api/v2/odometer",
            "VIETTEL": "https://vtracking.viettel.vn/api/merchant/v1"
        }
        # Mã Token bảo mật do bên bán thiết bị cấp cho công ty Bảo Tín
        self.api_token = "BAOTIN_SECRET_API_TOKEN_XYZ"

    def lay_so_km_hien_tai(self, ma_dinh_vi, nha_cung_cap):
        """
        Gửi mã thiết bị lên tổng đài GPS để lấy Số KM hiển thị trên đồng hồ xe (Odometer)
        """
        if not ma_dinh_vi or not nha_cung_cap:
            return None
            
        # -------------------------------------------------------------
        # KHÚC CODE THẬT: Khi có tài khoản thật, bạn mở chặn đoạn code này
        # -------------------------------------------------------------
        # try:
        #     url = self.api_endpoints.get(nha_cung_cap.upper())
        #     headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        #     params = {"device_id": ma_dinh_vi}
        #
        #     response = requests.get(url, headers=headers, params=params, timeout=5)
        #     if response.status_code == 200:
        #         data = response.json()
        #         # Tùy cấu trúc JSON của mỗi bên, ví dụ: data["result"]["total_km"]
        #         return float(data.get("odometer", 0))
        #     return None
        # except Exception:
        #     return None
        
        # -------------------------------------------------------------
        # CHẾ ĐỘ GIẢ LẬP (SIMULATION): Phục vụ lập trình và nghiệm thu giao diện
        # -------------------------------------------------------------
        # Giả lập trả về số KM tăng dần một cách ngẫu nhiên từ 150,000 KM đến 150,500 KM
        import time
        seed_value = int(time.time()) % 1000
        return float(150000 + seed_value + random.randint(10, 50))