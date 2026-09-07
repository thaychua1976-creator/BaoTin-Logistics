import mysql.connector
from mysql.connector import pooling
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os
import time

# Tải các biến từ file .env vào hệ thống
load_dotenv()

class Database:
    def __init__(self):
        # Tối ưu 1: Lazy Initialization - Chưa khởi tạo Pool ngay lập tức để giảm tải lúc khởi động App
        self.pool = None
        
    def _init_pool(self):
        """Hàm nội bộ để khởi tạo Pool khi thực sự cần thiết."""
        db_config = {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT", 25060)),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASS"),
            "database": os.getenv("DB_NAME"),
            "ssl_ca": "ca.pem",
            "ssl_disabled": False,
            "pool_reset_session": True 
        }
        
        try:
            # Tối ưu 2: Thêm timestamp vào pool_name để tránh lỗi trùng Pool Name khi Streamlit hot-reload
            pool_name = f"baotin_tms_pool_{int(time.time())}"
            self.pool = pooling.MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=10,
                **db_config
            )
        except mysql.connector.Error as err:
            st.error(f"❌ Lỗi khởi tạo Pool: {err}")

    def get_connection(self):
        try:
            # Nếu Pool chưa được khởi tạo, lúc này mới tạo
            if self.pool is None:
                self._init_pool()
                
            conn = self.pool.get_connection()
            
            # 🚀 TỐI ƯU 3: Bỏ delay=1. Nếu có delay, mỗi lần lấy kết nối app có thể bị treo 1s.
            # Chỉ cần attempts=1, delay=0 là đủ để tự động nối lại nếu bị đứt.
            conn.ping(reconnect=True, attempts=1, delay=0)
            return conn
        except mysql.connector.Error as err:
            st.error(f"❌ Mất kết nối hoàn toàn đến Aiven MySQL: {err}")
            return None

    def execute_query(self, query, params=None):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            if not conn:
                return "Lỗi: Không thể kết nối đến máy chủ cơ sở dữ liệu."
            
            is_select = query.strip().upper().startswith("SELECT")
            
            if is_select:
                df = pd.read_sql(query, conn, params=params)
                return df
            else:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()
                
                if query.strip().upper().startswith("INSERT"):
                    return cursor.lastrowid
                return cursor.rowcount
                
        except Exception as e:
            return str(e)
            
        finally:
            if cursor:
                cursor.close()
            # Luôn trả kết nối về Pool an toàn
            if conn and conn.is_connected():
                conn.close()
    
    def get_recent_trips_for_edit(self):
        """Lấy danh sách chuyến đi chưa hoàn thành hoặc gần đây để sửa (không có ngày chỉ có tạo mới)"""
        try:
            sql = """
                SELECT 
                    c.id, c.ngay_chuyen_di, c.ten_khach_hang, c.dia_chi_khach_hang,
                    c.xe_id, x.bien_so_xe,
                    txc.tai_xe_id, nv.ho_ten as ten_tai_xe,
                    c.dia_diem_giao_nhan, c.so_km_thuc_te, c.khoi_luong_kg, c.the_tich_cbm,
                    c.cong_chuyen, c.trang_thai_chuyen, c.ghi_chu
                FROM chuyen_di c
                JOIN xe x ON c.xe_id = x.id
                LEFT JOIN chuyen_di_tai_xe txc ON c.id = txc.chuyen_di_id
                LEFT JOIN nhan_vien nv ON txc.tai_xe_id = nv.id
                WHERE c.trang_thai_chuyen NOT IN ('Hoan_Thanh', 'Da_Huy')
                ORDER BY c.ngay_chuyen_di DESC, c.id DESC
                LIMIT 50;
            """
            df = self.execute_query(sql)
            if df is None or (isinstance(df, str) and "Lỗi" in df):
                return pd.DataFrame()
            return df
        except Exception as e:
            return pd.DataFrame()