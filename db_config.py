import mysql.connector
from mysql.connector import pooling
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os
import re
import uuid

# Tải các biến từ file .env vào hệ thống
load_dotenv(override=False)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Database:
    def __init__(self):
        # Lazy Initialization - Chưa khởi tạo Pool ngay lập tức để giảm tải lúc khởi động App
        self._pool = None

    @property
    def pool(self):
        """Đảm bảo mọi lời gọi trực tiếp db.pool.get_connection() luôn có Pool hợp lệ."""
        if self._pool is None:
            self._init_pool()
        return self._pool

    @pool.setter
    def pool(self, value):
        self._pool = value

    def _init_pool(self):
        """Hàm nội bộ để khởi tạo Pool khi thực sự cần thiết."""
        db_host = db_port = db_user = db_pass = db_name = None

        # Ưu tiên đọc từ st.secrets (Streamlit Cloud), bọc try/except tránh lỗi khi chạy Local không có secrets.toml
        try:
            if "mysql" in st.secrets:
                db_host = st.secrets["mysql"]["host"]
                db_port = int(st.secrets["mysql"]["port"])
                db_user = st.secrets["mysql"]["user"]
                db_pass = st.secrets["mysql"]["password"]
                db_name = st.secrets["mysql"]["database"]
        except Exception:
            pass

        if not db_host:
            db_host = os.getenv("DB_HOST")
            db_port = int(os.getenv("DB_PORT", 25060))
            db_user = os.getenv("DB_USER")
            db_pass = os.getenv("DB_PASS")
            db_name = os.getenv("DB_NAME")

        ca_path = os.path.join(BASE_DIR, "ca.pem")
        db_config = {
            "host": db_host,
            "port": db_port,
            "user": db_user,
            "password": db_pass,
            "database": db_name,
            "pool_reset_session": True,
            "connect_timeout": 10,
        }

        if os.path.exists(ca_path):
            db_config["ssl_ca"] = ca_path
            db_config["ssl_disabled"] = False

        try:
            # Dùng UUID ngắn để không bao giờ trùng Pool Name khi nhiều session hot-reload cùng giây
            pool_name = f"baotin_tms_{uuid.uuid4().hex[:8]}"
            self._pool = pooling.MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=6,
                **db_config,
            )
        except mysql.connector.Error as err:
            st.error(f"❌ Lỗi khởi tạo Pool: {err}")

    def get_connection(self):
        try:
            if self._pool is None:
                self._init_pool()
            if self._pool is None:
                return None

            conn = self._pool.get_connection()
            conn.ping(reconnect=True, attempts=1, delay=0)
            return conn
        except mysql.connector.Error as err:
            print(f"\n[CRITICAL ERROR] CHI TIẾT LỖI TỪ AIVEN: {err}\n")
            st.error(f"❌ Mất kết nối hoàn toàn đến Aiven MySQL: {err}")
            return None

    def execute_query(self, query, params=None):
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            if not conn:
                return "Lỗi: Không thể kết nối đến máy chủ cơ sở dữ liệu."

            is_read_query = bool(
                re.match(r"^\s*(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b", query, re.IGNORECASE)
            )

            if is_read_query:
                df = pd.read_sql(query, conn, params=params)
                return df
            else:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()

                if re.match(r"^\s*INSERT\b", query, re.IGNORECASE):
                    return cursor.lastrowid
                return cursor.rowcount

        except Exception as e:
            return str(e)

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            # Luôn trả kết nối về Pool an toàn
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_recent_trips_for_edit(self):
        """Lấy danh sách chuyến đi chưa hoàn thành hoặc gần đây để sửa."""
        try:
            sql = """
                SELECT 
                    c.id, c.ngay_chuyen_di, 
                    COALESCE(kh.ten_khach_hang, c.ten_khach_hang) AS ten_khach_hang, 
                    c.dia_chi_khach_hang,
                    c.xe_id, COALESCE(x.bien_so_xe, c.bien_so_xe_ngoai) AS bien_so_xe,
                    txc.tai_xe_id, COALESCE(nv.ho_ten, c.tai_xe_ngoai_ten) AS ten_tai_xe,
                    c.dia_diem_giao_nhan, c.so_km_thuc_te, c.khoi_luong_kg, c.the_tich_cbm,
                    c.trang_thai_chuyen, c.ghi_chu
                FROM chuyen_di c
                LEFT JOIN khach_hang kh ON c.khach_hang_id = kh.id
                LEFT JOIN xe x ON c.xe_id = x.id
                LEFT JOIN chuyen_di_tai_xe txc ON c.id = txc.chuyen_di_id AND txc.loai_tai_xe = 'Tai_Chinh'
                LEFT JOIN nhan_vien nv ON txc.tai_xe_id = nv.id
                WHERE c.trang_thai_chuyen NOT IN ('Hoan_Thanh', 'Huy_Chuyen')
                ORDER BY c.ngay_chuyen_di DESC, c.id DESC
                LIMIT 50;
            """
            df = self.execute_query(sql)
            if df is None or (isinstance(df, str) and "Lỗi" in df):
                return pd.DataFrame()
            return df
        except Exception:
            return pd.DataFrame()