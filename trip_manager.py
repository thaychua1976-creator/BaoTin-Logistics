import streamlit as st
from audit_logger import ghi_log_thao_tac
import pandas as pd
import os, requests, datetime,time
from dotenv import load_dotenv
load_dotenv()

def tao_khach_hang_nhanh(db_pool, ten_khach_hang, so_dien_thoai, zalo_user_id, ma_so_thue, dia_chi):
    """
    Tạo nhanh khách hàng mới. Tự động sinh mã khách hàng KH_{ma_so_thue}.
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False
        
        # Tự động sinh mã khách hàng theo định dạng KH_{ma_so_thue}
        mst_clean = str(ma_so_thue).strip() if ma_so_thue else ""
        ma_kh_chuan = f"KH_{mst_clean}" if mst_clean else f"KH_TEMP_{int(time.time())}"
        
        sql = """
            INSERT INTO khach_hang (ten_khach_hang, ma_khach_hang, so_dien_thoai, zalo_user_id, ma_so_thue, dia_chi) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            ten_khach_hang.strip(), 
            ma_kh_chuan, 
            so_dien_thoai.strip() if so_dien_thoai else None,
            zalo_user_id.strip() if zalo_user_id else None,
            mst_clean if mst_clean else None,
            dia_chi.strip() if dia_chi else None
        ))
        new_id = cursor.lastrowid
        conn.commit()
        return True, new_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
#############################################        
def save_trip_full_process(db_pool, data_chuyen_di: dict, tai_xe_id: int, phu_phi_list: list = None):
    """
    Transaction tạo mới chuyến đi kèm tính năng lưu phụ phí động[cite: 3].
    - data_chuyen_di: dict linh hoạt chứa các cột và giá trị insert vào bảng chuyen_di.
    - phu_phi_list: danh sách các dict chứa [{'ma_phu_phi':..., 'so_tien':..., 'ghi_chu':...}]
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False  # Bắt buộc dùng Transaction cho nhiều thao tác[cite: 3]
        
        # 1. Tự động xác định loại hình xe nếu là xe nội bộ
        xe_id = data_chuyen_di.get('xe_id')
        if xe_id and data_chuyen_di.get('is_thue_ngoai', 0) == 0 and 'loai_hinh_xe' not in data_chuyen_di:
            cursor.execute("SELECT loai_xe, quy_cach_thung FROM xe WHERE id = %s", (xe_id,))
            xe_info = cursor.fetchone()
            if xe_info:
                loai_xe_str = f"{xe_info[0]} {xe_info[1]}".lower() if xe_info[0] or xe_info[1] else ""
                if any(k in loai_xe_str for k in ['cont', 'dau keo', 'container', 'rơ moóc']):
                    data_chuyen_di['loai_hinh_xe'] = 'Container'
                elif any(k in loai_xe_str for k in ['xe may', 'moto', 'motor', 'xe máy', 'winner', 'exciter', 'sh']):
                    data_chuyen_di['loai_hinh_xe'] = 'Xe_May'
                else:
                    data_chuyen_di['loai_hinh_xe'] = 'Xe_Tai'

        # 2. INSERT chuyến đi chính bằng cơ chế tự động render Dictionary
        columns = list(data_chuyen_di.keys())
        placeholders = ["%s"] * len(columns)
        values = list(data_chuyen_di.values())
        
        sql_trip = f"INSERT INTO chuyen_di ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(sql_trip, tuple(values))
        new_cid = cursor.lastrowid 
        
        # 3. INSERT phân công tài xế
        if tai_xe_id and data_chuyen_di.get('is_thue_ngoai', 0) == 0:
            sql_tx = "INSERT INTO chuyen_di_tai_xe (chuyen_di_id, tai_xe_id, loai_tai_xe) VALUES (%s, %s, 'Tai_Chinh')"
            cursor.execute(sql_tx, (new_cid, tai_xe_id))
            
        # 4. INSERT phụ phí động (Nếu có)
        if phu_phi_list and len(phu_phi_list) > 0:
            sql_pp = """
                INSERT INTO chuyen_di_phu_phi (chuyen_di_id, ma_phu_phi, so_tien, ghi_chu) 
                VALUES (%s, %s, %s, %s)
            """
            # Sử dụng tuple comprehensions để tạo danh sách insert và executemany để tối ưu tốc độ
            pp_data_tuples = [(new_cid, pp['ma_phu_phi'], pp['so_tien'], pp.get('ghi_chu', '')) for pp in phu_phi_list]
            cursor.executemany(sql_pp, pp_data_tuples)
            
            # Kiểm tra rowcount theo quy tắc coding bắt buộc[cite: 3]
            if cursor.rowcount != len(phu_phi_list):
                raise Exception("Lỗi: Không thể lưu toàn bộ các dòng phụ phí.")
        
        # 5. Ghi log thao tác (Gộp thêm tổng tiền phụ phí nếu có)
        log_data = {
            "hanh_trinh": data_chuyen_di.get('dia_diem_giao_nhan'), 
            "khach_hang": data_chuyen_di.get('ten_khach_hang'),
            "is_thue_ngoai": data_chuyen_di.get('is_thue_ngoai', 0),
            "loai_hinh_xe": data_chuyen_di.get('loai_hinh_xe', 'Container'),
            "so_luong_phu_phi": len(phu_phi_list) if phu_phi_list else 0
        }
        if phu_phi_list:
            log_data["tong_tien_phu_phi"] = sum(pp.get('so_tien', 0) for pp in phu_phi_list)
            
        ghi_log_thao_tac(cursor, new_cid, st.session_state.get('username', 'Admin'), "TAO_MOI", log_data)
        
        conn.commit()  # Cam kết toàn bộ thay đổi[cite: 3]
        return True, new_cid
    except Exception as e:
        conn.rollback()  # Hủy toàn bộ thay đổi nếu có lỗi để tránh rác DB[cite: 3]
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
#########################################################

def settle_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    """
    Hàm Giao dịch Quyết toán dùng chung (Tích hợp đồng bộ Odometer nếu là xe nội bộ).
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False
        
        columns_to_set = []
        values = []
        
        for col_name, value in data_chuyen_di.items():
            columns_to_set.append(f"{col_name}=%s")
            values.append(value)
            
        columns_to_set.append("trang_thai_chuyen=%s")
        values.append(trang_thai_enum)
        values.append(chuyen_di_id)
        
        set_clause_str = ", ".join(columns_to_set)
        sql_update = f"""
            UPDATE chuyen_di 
            SET {set_clause_str}
            WHERE id=%s AND trang_thai_chuyen NOT IN ('Hoan_Thanh','Huy_Chuyen')
        """
        cursor.execute(sql_update, tuple(values))
        
        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            if cursor.fetchone() is None:
                conn.rollback()
                return False, f"Lỗi: Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."
                
        # Cộng dồn Odometer nếu là xe nội bộ hoàn thành chuyến
        if trang_thai_enum == 'Hoan_Thanh':
            cursor.execute("SELECT xe_id, is_thue_ngoai FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            result_xe = cursor.fetchone()
            
            if result_xe and result_xe[0] is not None and result_xe[1] == 0:
                xe_id = result_xe[0]
                so_km_str = data_chuyen_di.get('so_km_thuc_te', 0.0)
                so_km = float(so_km_str) if so_km_str else 0.0
                
                if so_km > 0:
                    sql_update_odo = """
                        UPDATE xe 
                        SET tong_km_hien_tai = COALESCE(tong_km_hien_tai, 0) + %s 
                        WHERE id = %s
                    """
                    cursor.execute(sql_update_odo, (so_km, xe_id))
        
        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state.get('username', 'Admin'), hanh_dong, data_chuyen_di)    
        
        conn.commit() 
        return True, chuyen_di_id
    except Exception as e:
        conn.rollback() 
        return False, str(e)
    finally:
        cursor.close()
        conn.close() 

def update_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False 
        cursor.execute("SELECT xe_id, so_km_thuc_te, is_thue_ngoai FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
        old_data = cursor.fetchone()
        
        if old_data is None:
            conn.rollback()
            return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."
            
        xe_id = old_data[0]
        old_km = float(old_data[1]) if old_data[1] is not None else 0.0
        is_thue_ngoai = old_data[2]
        
        columns_to_set = []
        values = []
        for col_name, value in data_chuyen_di.items():
            columns_to_set.append(f"{col_name}=%s")
            values.append(value)
            
        columns_to_set.append("trang_thai_chuyen=%s")
        values.append(trang_thai_enum)
        values.append(chuyen_di_id)
        
        set_clause_str = ", ".join(columns_to_set)
        sql_update = f"""
            UPDATE chuyen_di 
            SET {set_clause_str}
            WHERE id=%s AND trang_thai_chuyen != 'Huy_Chuyen'
        """
        cursor.execute(sql_update, tuple(values))
        
        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            if cursor.fetchone() is None:
                conn.rollback()
                return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại hoặc đã được chốt từ trước."

        if trang_thai_enum == 'Hoan_Thanh' and 'so_km_thuc_te' in data_chuyen_di and is_thue_ngoai == 0:
            new_km_str = data_chuyen_di.get('so_km_thuc_te', 0.0)
            new_km = float(new_km_str) if new_km_str else 0.0
            km_diff = new_km - old_km
            if km_diff != 0 and xe_id is not None:
                sql_update_odo = """
                    UPDATE xe 
                    SET tong_km_hien_tai = COALESCE(tong_km_hien_tai, 0) + %s 
                    WHERE id = %s
                """
                cursor.execute(sql_update_odo, (km_diff, xe_id))

        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state.get('username', 'Admin'), hanh_dong, data_chuyen_di)    
        
        conn.commit()
        return True, chuyen_di_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close() 
###############################################
def update_trip_full_process(db_pool, chuyen_di_id: int, data_chuyen_di: dict, tai_xe_id: int):
    """
    Cập nhật toàn bộ thông tin chuyến đi đang ở trạng thái Tạo Mới / Đang Đi.
    Đảm bảo tuân thủ Transaction, kiểm tra rowcount và ghi Audit Log.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Tuân thủ quy tắc Transaction
        cursor = conn.cursor()
        
        # Kiểm tra xem chuyến đi có tồn tại không trước khi update
        cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
        if cursor.fetchone() is None:
            conn.rollback()
            return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."

        # 1. Cập nhật bảng chuyen_di
        set_clause = ", ".join([f"{k}=%s" for k in data_chuyen_di.keys()])
        values = list(data_chuyen_di.values())
        values.append(chuyen_di_id)
        
        sql_update = f"UPDATE chuyen_di SET {set_clause} WHERE id=%s"
        cursor.execute(sql_update, tuple(values))
        
        # Kiểm tra rowcount bắt buộc sau lệnh UPDATE
        if cursor.rowcount == 0:
            conn.rollback()
            return False, "Không có thay đổi dữ liệu hoặc chuyến đi không tồn tại."

        # 2. Xóa liên kết tài xế cũ và cập nhật tài xế mới (nếu là xe nội bộ)
        cursor.execute("DELETE FROM chuyen_di_tai_xe WHERE chuyen_di_id=%s", (chuyen_di_id,))
        if tai_xe_id and data_chuyen_di.get('is_thue_ngoai', 0) == 0:
            sql_tx = "INSERT INTO chuyen_di_tai_xe (chuyen_di_id, tai_xe_id, loai_tai_xe) VALUES (%s, %s, 'Tai_Chinh')"
            cursor.execute(sql_tx, (chuyen_di_id, tai_xe_id))
            
        # 3. Ghi vết thao tác bằng Audit Log
        ghi_log_thao_tac(
            cursor=cursor, 
            chuyen_di_id=chuyen_di_id, 
            nguoi_dung=st.session_state.get('username', 'Admin'), 
            hanh_dong="CAP_NHAT", 
            chi_tiet_dict=data_chuyen_di
        )
        
        conn.commit()
        return True, "Cập nhật chuyến đi thành công!"
    except Exception as e:
        if conn:
            conn.rollback()  # Rollback an toàn khi có lỗi
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
##################################################

def delete_trip_safe(db_pool, chuyen_di_id):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False
        cursor.execute("DELETE FROM chuyen_di_tai_xe WHERE chuyen_di_id = %s", (chuyen_di_id,))
        cursor.execute("DELETE FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
        
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state.get('username', 'Admin'), "XOA_CHUYEN", {"trang_thai": "Đã xóa vĩnh viễn"})
        conn.commit()
        return True, "Xóa chuyến đi thành công!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def get_bao_cao_pnl_chuyen_di(db_pool, tu_ngay, den_ngay, xe_id=0):
    try:
        conn = db_pool.get_connection()
        sql_base = """
            SELECT 
                cd.id AS `Mã Chuyến`,
                DATE_FORMAT(cd.ngay_chuyen_di, '%d/%m/%Y') AS `Ngày Chạy`,
                COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS `Biển Số Xe`,
                COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten, 'Chưa xác định') AS `Tài Xế`,
                cd.dia_diem_giao_nhan AS `Hành Trình`,
                COALESCE(cd.doanh_thu, 0) AS `Doanh Thu`, 
                COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.tien_them, 0) AS `Lương TX & Thêm`,
                COALESCE(cd.chi_phi_thue_ngoai, 0) AS `Chi Phí Thuê Ngoài`,
                COALESCE(cd.tien_xang, 0) AS `Tiền Xăng/Dầu`,
                COALESCE(cd.phi_hai_quan, 0) AS `Hải Quan`,
                COALESCE(cd.phi_boc_xep, 0) AS `Bốc Xếp`,
                COALESCE(cd.phi_khac, 0) AS `Phí Khác`,
                (COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.chi_phi_thue_ngoai, 0) + COALESCE(cd.tien_them, 0) + 
                 COALESCE(cd.tien_xang, 0) + COALESCE(cd.phi_hai_quan, 0) + COALESCE(cd.phi_boc_xep, 0) + COALESCE(cd.phi_khac, 0)) AS `Tổng Chi Phí`,
                COALESCE(cd.doanh_thu, 0) - (COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.chi_phi_thue_ngoai, 0) + COALESCE(cd.tien_them, 0) + 
                     COALESCE(cd.tien_xang, 0) + COALESCE(cd.phi_hai_quan, 0) + COALESCE(cd.phi_boc_xep, 0) + COALESCE(cd.phi_khac, 0)) AS `Lợi Nhuận Gộp`
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen = 'Hoan_Thanh' 
              AND cd.ngay_chuyen_di BETWEEN %s AND %s
        """
        if xe_id == 0:
            sql = sql_base + " ORDER BY cd.ngay_chuyen_di DESC"
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay))
        else:
            sql = sql_base + " AND cd.xe_id = %s ORDER BY cd.ngay_chuyen_di DESC"
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay, xe_id))
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn: conn.close()

HTX_CUSTOMER_CODE = os.getenv("HTX_CUSTOMER_CODE")
HTX_KEY = os.getenv("HTX_KEY")

def goi_gps_theo_thoi_gian_tuy_chinh(db_instance, chuyen_di_id, tg_bat_dau_quet, tg_ket_thuc_quet):
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        sql_get_info = """
            SELECT x.bien_so_xe, x.id as xe_id, cd.is_thue_ngoai
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            WHERE cd.id = %s
        """
        cursor.execute(sql_get_info, (chuyen_di_id,))
        trip_info = cursor.fetchone()
        
        if not HTX_CUSTOMER_CODE or not HTX_KEY:
            return False, "⚠️ Lỗi: Chưa cấu hình CustomerCode hoặc Key trong file .env" 
        if not trip_info or (not trip_info['bien_so_xe'] and trip_info['is_thue_ngoai'] == 1):
            return False, "Không tìm thấy thông tin xe nội bộ để quét GPS."
            
        bien_so = trip_info['bien_so_xe']
        xe_id = trip_info['xe_id']
        api_url = "https://hanhtrinhxe.vn/api/gps/rpsummary"
        tong_km_chuyen_di = 0.0
        thoi_gian_quet_hien_tai = tg_bat_dau_quet
        
        while thoi_gian_quet_hien_tai < tg_ket_thuc_quet:
            moc_tiep_theo = thoi_gian_quet_hien_tai + datetime.timedelta(hours=23, minutes=59, seconds=59)
            if moc_tiep_theo > tg_ket_thuc_quet: moc_tiep_theo = tg_ket_thuc_quet
                
            payload = {
                "CustomerCode": HTX_CUSTOMER_CODE, "Key": HTX_KEY,               
                "VehiclePlate": bien_so, 
                "FromDate": thoi_gian_quet_hien_tai.strftime('%Y%m%d%H%M%S'), 
                "ToDate": moc_tiep_theo.strftime('%Y%m%d%H%M%S')
            }
            try:
                response = requests.post(api_url, data=payload, timeout=20, verify=False)
                if response.status_code == 200:
                    api_data = response.json()
                    if api_data.get('messageResult') == 'Success':
                        danh_sach_bao_cao = api_data.get('summaryReports', [])
                        if danh_sach_bao_cao and len(danh_sach_bao_cao) > 0:
                            tong_km_chuyen_di += float(danh_sach_bao_cao[0].get('totalKmGps', 0))
            except Exception:
                pass 
            thoi_gian_quet_hien_tai = moc_tiep_theo + datetime.timedelta(seconds=1)

        sql_update_chuyen = """
            UPDATE chuyen_di 
            SET so_km_thuc_te = %s, trang_thai_chuyen = 'Quyet_Toan'
            WHERE id = %s
        """
        cursor.execute(sql_update_chuyen, (tong_km_chuyen_di, chuyen_di_id))
        if tong_km_chuyen_di > 0 and xe_id:
            cursor.execute("UPDATE xe SET tong_km_hien_tai = tong_km_hien_tai + %s WHERE id = %s", (tong_km_chuyen_di, xe_id))
            
        conn.commit()
        return True, f"✅ Đã quét thành công {tong_km_chuyen_di:.2f} KM từ GPS."
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        return False, f"Lỗi hệ thống: {e}"
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

def get_cong_no_khach_hang(db_pool, khach_hang_id, tu_ngay, den_ngay):
    sql = """
        SELECT cd.ngay_chuyen_di, cd.dia_diem_giao_nhan, COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) as bien_so_xe, cd.doanh_thu, kh.ten_khach_hang, kh.ma_so_thue, kh.dia_chi
        FROM chuyen_di cd
        JOIN khach_hang kh ON cd.khach_hang_id = kh.id
        LEFT JOIN xe x ON cd.xe_id = x.id
        WHERE cd.khach_hang_id = %s AND cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s AND cd.trang_thai_chuyen = 'Hoan_Thanh'
        ORDER BY cd.ngay_chuyen_di ASC
    """
    try:
        return db_pool.execute_query(sql, (khach_hang_id, tu_ngay, den_ngay))
    except Exception:
        return None

###############################################

import traceback
from audit_logger import ghi_log_he_thong # Hàm log bắt buộc của dự án[cite: 8]

def auto_calculate_trip_revenue(db_pool, tu_ngay, den_ngay, current_user="He_Thong_Batch"):
    """
    Quyết toán tự động cước vận chuyển.
    Nâng cấp: Xử lý linh hoạt Khuyến mãi chuyến tiếp nối (Cùng KH, cùng ngày, cùng tuyến) BẤT KỂ ĐI XE NÀO.
    Tuân thủ 100% nguyên tắc Transaction và Audit Log của dự án.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Nguyên tắc 1: Bắt buộc dùng Transaction[cite: 8]
        cursor = conn.cursor(dictionary=True) 

        # 1. Truy xuất các chuyến đi cần áp cước (Bổ sung ngay_chuyen_di để check cùng ngày)
        sql_trips = """
            SELECT cd.id, cd.khach_hang_id, cd.ngay_chuyen_di, cd.dia_diem_giao_nhan, 
                   cd.khoi_luong_kg, cd.the_tich_cbm, cd.loai_hinh_xe, 
                   cd.is_hang_tra_ve, cd.quy_cach_thuc_te, 
                   x.tai_trong_thiet_ke, cql.loai_cont, tk.phan_luong
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN container_quan_ly cql ON cd.id = cql.chuyen_di_id
            LEFT JOIN to_khai_hai_quan tk ON cd.id = tk.chuyen_di_id
            WHERE cd.ngay_chuyen_di BETWEEN %s AND %s 
              AND cd.trang_thai_chuyen = 'Hoan_Thanh'
              AND cd.is_tinh_cuoc_tu_dong = 0
            ORDER BY cd.id ASC  -- Quét theo thứ tự sinh ra chuyến đi (Thời gian)
        """
        cursor.execute(sql_trips, (tu_ngay, den_ngay))
        trips = cursor.fetchall()
        
        success_count = 0
        
        for trip in trips:                          # láy từ table chuyen di
            kh_id = trip['khach_hang_id']
            if not kh_id: continue
            
            lo_trinh = str(trip['dia_diem_giao_nhan'] or "").upper()
            loai_hinh = trip['loai_hinh_xe']
            is_tra_ve = trip['is_hang_tra_ve'] or 0
            phan_luong = str(trip['phan_luong'] or "").upper()
            quy_cach_chay = str(trip.get('quy_cach_thuc_te') or "").strip().upper() # xe tải thường, cont thường or lạnh or hàng nguy hiểm
            
            # Ép chuẩn định dạng xe
            loai_xe_khach = ""
            if loai_hinh == 'Container':
                loai_xe_khach = str(trip['loai_cont'] or "40HC").upper()
            else:
                tai_trong = float(trip['tai_trong_thiet_ke'] or 0)
                loai_xe_khach = f"{int(tai_trong)}T" if tai_trong.is_integer() else f"{tai_trong}T"
            
            kg_thuc = float(trip['khoi_luong_kg'] or 0)
            cbm_thuc = float(trip['the_tich_cbm'] or 0)

            # 2. Truy vấn Biểu cước
            cursor.execute("SELECT * FROM rate_cards WHERE khach_hang_id = %s ORDER BY don_gia_cuoc ASC", (kh_id,))
            rates = cursor.fetchall()
            
            matched_rate = 0.0
            gia_chuyen_tiep_noi = 0.0
            
            for rate in rates:
                diem_di_kw = str(rate['diem_di'] or "").upper()
                diem_den_kw = str(rate['diem_den'] or "").upper()
                loai_xe_rate = str(rate['loai_xe_quy_cach'] or "").strip().upper()
                rate_tra_ve = rate['is_hang_tra_ve']
                
                # Khớp lộ trình & chiều
                if (diem_di_kw in lo_trinh and diem_den_kw in lo_trinh) and (is_tra_ve == rate_tra_ve):
                    # LỚP ƯU TIÊN (Khớp quy cách)
                    if quy_cach_chay and quy_cach_chay == loai_xe_rate:
                        if rate['phan_loai_phuong_tien'] == 'Hang_Le':
                            if kg_thuc <= float(rate['gioi_han_kg']) and cbm_thuc <= float(rate['gioi_han_cbm']):
                                matched_rate = float(rate['don_gia_cuoc'])
                                gia_chuyen_tiep_noi = float(rate.get('gia_chuyen_tiep_noi', 0.0))
                                break
                        else:
                            matched_rate = float(rate['don_gia_cuoc'])
                            gia_chuyen_tiep_noi = float(rate.get('gia_chuyen_tiep_noi', 0.0))
                            break
                    # LỚP FALLBACK
                    elif not quy_cach_chay:
                        if rate['phan_loai_phuong_tien'] == 'Hang_Le':
                            if kg_thuc <= float(rate['gioi_han_kg']) and cbm_thuc <= float(rate['gioi_han_cbm']):
                                matched_rate = float(rate['don_gia_cuoc'])
                                gia_chuyen_tiep_noi = float(rate.get('gia_chuyen_tiep_noi', 0.0))
                                break 
                        elif loai_hinh == 'Container' and loai_xe_rate in loai_xe_khach:
                            matched_rate = float(rate['don_gia_cuoc'])
                            gia_chuyen_tiep_noi = float(rate.get('gia_chuyen_tiep_noi', 0.0))
                            break
                        elif (loai_hinh == 'Xe_Tai' or loai_hinh == 'Xe_May') and loai_xe_rate in loai_xe_khach:
                            matched_rate = float(rate['don_gia_cuoc'])
                            gia_chuyen_tiep_noi = float(rate.get('gia_chuyen_tiep_noi', 0.0))
                            break

            # =========================================================
            # BƯỚC MỚI (LINH HOẠT): XỬ LÝ KHUYẾN MÃI CHUYẾN TIẾP NỐI
            # =========================================================
            tien_giam = 0.0
            ly_do_giam = ""
            
            if matched_rate > 0:
                # Quét lịch sử: Khách hàng này có chuyến nào cùng tuyến, cùng ngày trước đó không?
                # (Không cần quan tâm mã chuyến ghép hay xe nào)
                sql_check_history = """
                    SELECT COUNT(id) as so_chuyen_truoc_do 
                    FROM chuyen_di 
                    WHERE khach_hang_id = %s 
                      AND ngay_chuyen_di = %s
                      AND dia_diem_giao_nhan = %s
                      AND id < %s
                      AND trang_thai_chuyen != 'Huy_Chuyen'
                """
                cursor.execute(sql_check_history, (
                    kh_id, 
                    trip['ngay_chuyen_di'], 
                    trip['dia_diem_giao_nhan'], 
                    trip['id']
                ))
                res_history = cursor.fetchone()
                
                # Nếu có chuyến trước đó -> Đây là chuyến nối (Thứ 2, 3...)
                if res_history and res_history['so_chuyen_truoc_do'] > 0:
                    chuyen_thu_may = res_history['so_chuyen_truoc_do'] + 1
                    if gia_chuyen_tiep_noi > 0 and gia_chuyen_tiep_noi < matched_rate:
                        tien_giam = matched_rate - gia_chuyen_tiep_noi
                        matched_rate = gia_chuyen_tiep_noi
                        ly_do_giam = f" | Khuyến mãi chuyến tiếp nối (Chuyến {chuyen_thu_may} trong ngày): -{tien_giam:,.0f}đ"
            
            # 3. Kết tính Phụ phí
            if matched_rate > 0:
                cursor.execute("SELECT * FROM phu_phi_khach_hang WHERE khach_hang_id = %s AND loai_ap_dung = 'Tu_Dong'", (kh_id,))
                surcharges = cursor.fetchall()
                
                tong_phu_phi = 0.0
                ghi_chu_phu_phi = []
                
                for sc in surcharges:
                    dk_kich_hoat = str(sc['dieu_kien_kich_hoat'] or "").upper()
                    if dk_kich_hoat and (dk_kich_hoat in lo_trinh or dk_kich_hoat in phan_luong):
                        tong_phu_phi += float(sc['don_gia_phu_phi'])
                        ghi_chu_phu_phi.append(sc['ten_phu_phi'])

                tong_doanh_thu = matched_rate + tong_phu_phi
                ghi_chu_str = f"[Hệ thống tự tính]: Cước {matched_rate:,.0f}"
                if ghi_chu_phu_phi:
                    ghi_chu_str += f" | Phụ phí ({', '.join(ghi_chu_phu_phi)}): {tong_phu_phi:,.0f}"
                if ly_do_giam:
                    ghi_chu_str += ly_do_giam
                if quy_cach_chay:
                    ghi_chu_str += f" | (Mã Quy cách: {quy_cach_chay})"

                # Cập nhật kết quả vào chuyến đi
                cursor.execute("""
                    UPDATE chuyen_di 
                    SET doanh_thu = %s,
                        tien_giam_gia = %s,
                        is_tinh_cuoc_tu_dong = 1,
                        ghi_chu_quyet_toan = CASE 
                            WHEN ghi_chu_quyet_toan IS NULL OR ghi_chu_quyet_toan = '' THEN %s 
                            ELSE CONCAT_WS(' - ', ghi_chu_quyet_toan, %s) 
                        END
                    WHERE id = %s
                """, (tong_doanh_thu, tien_giam, ghi_chu_str, ghi_chu_str, trip['id']))
                
                # Nguyên tắc 2: Kiểm tra rowcount sau lệnh UPDATE[cite: 8]
                if cursor.rowcount > 0:
                    success_count += 1

        # Nguyên tắc 4: Ghi vết Audit Log[cite: 8]
        ghi_log_he_thong(cursor, "QUYET_TOAN_TU_DONG", None, current_user, "CHAY_BATCH_BILLING", f"Đã áp cước tự động & Check chuyến tiếp nối thành công: {success_count} chuyến.")
        
        conn.commit()
        return True, f"✅ Đã xử lý cước phí linh hoạt thành công {success_count} chuyến đi!"

    except Exception as e:
        if conn: conn.rollback()  # Nguyên tắc 1: Rollback khi có lỗi[cite: 8]
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
####################################
import uuid
import json
from audit_logger import ghi_log_thao_tac # Đã có sẵn trong utils

def group_trips_transaction(db_pool, list_chuyen_di_ids: list, current_user: str):
    """
    Nghiệp vụ Ghép Chuyến: Gom nhiều ID chuyến đi vào chung 1 xe và lộ trình.
    Quy tắc:
    1. Dùng Transaction đảm bảo update đồng thời.
    2. Gán ma_chuyen_ghep và đánh số thứ tự (stt_chuyen_ghep).
    3. Ghi log thao tác.
    """
    if not list_chuyen_di_ids or len(list_chuyen_di_ids) < 2:
        return False, "Cần ít nhất 2 chuyến đi để thực hiện ghép chuyến."

    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Nguyên tắc 1: Bắt buộc dùng Transaction
        cursor = conn.cursor(dictionary=True)

        # 1. Kiểm tra tính hợp lệ (Các chuyến phải cùng xe_id và chưa hoàn thành)
        format_strings = ','.join(['%s'] * len(list_chuyen_di_ids))
        cursor.execute(f"SELECT id, xe_id, trang_thai_chuyen FROM chuyen_di WHERE id IN ({format_strings})", tuple(list_chuyen_di_ids))
        trips = cursor.fetchall()
        
        if len(trips) != len(list_chuyen_di_ids):
            raise Exception("Một số chuyến đi không tồn tại trong hệ thống.")
            
        first_xe_id = trips[0].get('xe_id')
        for t in trips:
            if t.get('xe_id') != first_xe_id:
                raise Exception(f"Lỗi: Các chuyến đi phải được phân công cho cùng một xe trước khi ghép.")
            if t.get('trang_thai_chuyen') in ['Hoan_Thanh', 'Huy_Chuyen']:
                raise Exception(f"Lỗi: Không thể ghép chuyến đi mã {t['id']} vì đã hoàn thành hoặc bị hủy.")

        # 2. Sinh mã nhóm ghép chuyến (Có thể dùng mã tự tăng hoặc UID ngắn)
        ma_ghep = f"GC-{uuid.uuid4().hex[:6].upper()}"

        # 3. Cập nhật từng chuyến đi theo thứ tự truyền vào
        stt = 1
        for cid in list_chuyen_di_ids:
            sql_update = """
                UPDATE chuyen_di 
                SET is_gop_chuyen = 1, ma_chuyen_ghep = %s, stt_chuyen_ghep = %s 
                WHERE id = %s
            """
            cursor.execute(sql_update, (ma_ghep, stt, cid))
            
            # Nguyên tắc 2: Phải kiểm tra rowcount
            if cursor.rowcount == 0:
                raise Exception(f"Lỗi cập nhật dữ liệu tại chuyến đi mã {cid}.")
                
            # Nguyên tắc 4: Ghi Audit Log cho từng chuyến đi bị ảnh hưởng
            log_detail = {
                "ma_chuyen_ghep": ma_ghep,
                "stt_chuyen": stt,
                "loai_thao_tac": "GHEP_CHUYEN_LIEN_TUC"
            }
            ghi_log_thao_tac(cursor, cid, current_user, "CAP_NHAT", log_detail)
            stt += 1

        conn.commit()  # Chốt giao dịch thành công
        return True, f"✅ Đã ghép thành công {len(list_chuyen_di_ids)} chuyến đi. Mã nhóm: {ma_ghep}"

    except Exception as e:
        if conn:
            conn.rollback()  # Rollback chặn rác Database
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()