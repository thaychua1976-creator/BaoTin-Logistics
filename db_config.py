import mysql.connector
from mysql.connector import pooling
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os

# Tải các biến từ file .env vào hệ thống
load_dotenv()

class Database:
    def __init__(self):
        # 1. Cấu hình thông số kết nối MySQL chuẩn bị cho Pool
        db_config = {
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT", 25060)), # Chuyển port sang kiểu số nguyên
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASS"),
            "database": os.getenv("DB_NAME"),
            "ssl_ca": "ca.pem",
            "ssl_disabled": False
        }
        
        # 2. Khởi tạo Bể chứa kết nối (Connection Pool)
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="baotin_tms_pool",
                pool_size=10,
                **db_config
            )
        except mysql.connector.Error as err:
            st.error(f"❌ Lỗi khởi tạo Pool: {err}")

    # Để file chuyen_di.py có thể mượn kết nối làm Transaction
    def get_connection(self):
        return self.pool.get_connection()

    def execute_query(self, query, params=None):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
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
            
        # Luôn trả kết nối về Pool dù code chạy đúng hay bị lỗi
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
    ######################
    
    def get_recent_trips_for_edit(self):
        """Lấy danh sách chuyến đi chưa hoàn thành hoặc gần đây để sửa khong có ngày chỉ có tao mới"""
        df = pd.DataFrame()
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
            if df is None:
                return pd.DataFrame()
            return df
        except Exception as e:
            return pd.DataFrame()
    ####