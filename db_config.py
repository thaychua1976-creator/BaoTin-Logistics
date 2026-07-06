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