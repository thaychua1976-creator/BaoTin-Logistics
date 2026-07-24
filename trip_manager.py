import streamlit as st
from audit_logger import ghi_log_thao_tac
import pandas as pd
import os, requests, datetime
from dotenv import load_dotenv
load_dotenv()


def save_trip_full_process(db_pool, trip_data, tai_xe_id):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False 
        sql_trip = """INSERT INTO chuyen_di 
            (ngay_chuyen_di, ten_khach_hang, dia_chi_khach_hang, xe_id, dia_diem_giao_nhan, so_km_thuc_te, khoi_luong_kg, the_tich_cbm, cong_chuyen, trang_thai_chuyen, ghi_chu) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql_trip, trip_data)
        new_cid = cursor.lastrowid 
        
        sql_tx = "INSERT INTO chuyen_di_tai_xe (chuyen_di_id, tai_xe_id, loai_tai_xe) VALUES (%s, %s, 'Tai_Chinh')"
        cursor.execute(sql_tx, (new_cid, tai_xe_id))
        
        log_data = {"hanh_trinh": trip_data[3], "khoi_luong": trip_data[5], "cong_tai_xe": trip_data[7]}
        ghi_log_thao_tac(cursor, new_cid, st.session_state.get('username', 'Admin'), "TAO_MOI", log_data)
        conn.commit() 
        return True, new_cid
    except Exception as e:
        conn.rollback() 
        return False, str(e)
    finally:
        cursor.close()
        conn.close() 

def settle_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    """
    Hàm Giao dịch Quyết toán dùng chung (Đã tích hợp đồng bộ Odometer).
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
        # 1. Lắp ráp SQL động từ Dictionary
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
        
        # 2. Thực thi cập nhật chuyến đi
        cursor.execute(sql_update, tuple(values))
        
        # 3. KIỂM TRA LỖI THÔNG MINH (Phải đặt ngay sau execute UPDATE chuyen_di)
        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            if cursor.fetchone() is None:
                conn.rollback()
                return False, f"Lỗi: Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."
                
        # 4. TÍNH NĂNG MỚI: CỘNG DỒN ODOMETER BẢO DƯỠNG XE
        # Chỉ cộng khi trạng thái truyền vào là 'Hoan_Thanh'
        if trang_thai_enum == 'Hoan_Thanh':
            cursor.execute("SELECT xe_id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            result_xe = cursor.fetchone()
            
            # result_xe[0] để lấy giá trị đầu tiên của tuple
            if result_xe and result_xe[0] is not None:
                xe_id = result_xe[0]
                # Lấy an toàn số km từ data_chuyen_di
                so_km_str = data_chuyen_di.get('so_km_thuc_te', 0.0)
                so_km = float(so_km_str) if so_km_str else 0.0
                
                if so_km > 0:
                    sql_update_odo = """
                        UPDATE xe 
                        SET tong_km_hien_tai = COALESCE(tong_km_hien_tai, 0) + %s 
                        WHERE id = %s
                    """
                    cursor.execute(sql_update_odo, (so_km, xe_id))
        
        # 5. GHI LOG THAO TÁC
        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        # Lưu ý: cần import thư viện Streamlit (st) ở đầu file nếu dùng st.session_state tại đây
        import streamlit as st 
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state['username'], hanh_dong, data_chuyen_di)    
        
        # 6. LƯU THÀNH CÔNG
        conn.commit() 
        return True, chuyen_di_id
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi định dạng
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool
################################


def update_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    """
    Hàm Giao dịch Quyết toán dùng chung (Tích hợp sửa lỗi lệch đồng hồ Odometer).
    - data_chuyen_di: Truyền vào 1 Dictionary chứa tên cột và giá trị cần cập nhật.
    - trang_thai_enum: Trạng thái chuẩn ENUM (vd: 'Hoan_Thanh').
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
        # --- [THÊM MỚI] BƯỚC 0: LẤY SỐ KM CŨ TRƯỚC KHI GHI ĐÈ ---
        cursor.execute("SELECT xe_id, so_km_thuc_te FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
        old_data = cursor.fetchone()
        
        if old_data is None:
            conn.rollback()
            return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."
            
        xe_id = old_data[0]
        # Lấy số km cũ an toàn (nếu null thì cho bằng 0)
        old_km = float(old_data[1]) if old_data[1] is not None else 0.0
        
        # 1. Khởi tạo mảng linh hoạt để build câu lệnh SET
        columns_to_set = []
        values = []
        
        # Duyệt qua Dictionary để lắp ráp các cột cần Update
        for col_name, value in data_chuyen_di.items():
            columns_to_set.append(f"{col_name}=%s")
            values.append(value)
            
        # Thêm cột trạng thái (bắt buộc luôn có)
        columns_to_set.append("trang_thai_chuyen=%s")
        values.append(trang_thai_enum)
        
        # Thêm ID cho điều kiện WHERE
        values.append(chuyen_di_id)
        
        # 2. Lắp ráp chuỗi SQL hoàn chỉnh
        set_clause_str = ", ".join(columns_to_set)
        
        sql_update = f"""
            UPDATE chuyen_di 
            SET {set_clause_str}
            WHERE id=%s AND trang_thai_chuyen != 'Huy_Chuyen'
        """
        
        # 3. Thực thi cập nhật chuyến đi
        cursor.execute(sql_update, tuple(values))
        
        # Nếu không có dòng nào bị tác động (do sai ID hoặc trùng lặp)
        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            if cursor.fetchone() is None:
                conn.rollback()
                return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại hoặc đã được chốt từ trước."

        # --- [THÊM MỚI] BƯỚC 4: TÍNH TOÁN BÙ TRỪ ODOMETER CHO XE ---
        # Chỉ can thiệp Odometer nếu chuyến này đang Hoàn Thành và người dùng có sửa số km
        if trang_thai_enum == 'Hoan_Thanh' and 'so_km_thuc_te' in data_chuyen_di:
            new_km_str = data_chuyen_di.get('so_km_thuc_te', 0.0)
            new_km = float(new_km_str) if new_km_str else 0.0
            
            # Tính độ chênh lệch (VD: Lúc đầu quyết toán 100km, nay sửa thành 120km => Chênh lệch +20km)
            km_diff = new_km - old_km
            
            if km_diff != 0 and xe_id is not None:
                sql_update_odo = """
                    UPDATE xe 
                    SET tong_km_hien_tai = COALESCE(tong_km_hien_tai, 0) + %s 
                    WHERE id = %s
                """
                # Nếu km_diff là âm (VD: sửa từ 150km xuống 100km), SQL vẫn tự động hiểu và trừ đi 50km
                cursor.execute(sql_update_odo, (km_diff, xe_id))

        # 5. Ghi log quyết toán/cập nhật
        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        import streamlit as st
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state['username'], hanh_dong, data_chuyen_di)    
        
        conn.commit() # Lưu thành công
        return True, chuyen_di_id
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi định dạng
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool

#############################
# Giả sử file database.py
def update_trip_full_process(pool, trip_id, trip_data_tuple, tai_xe_id):
    """
    Transaction cập nhật thông tin chuyến đi và tài xế
    Nhận vào 4 tham số khớp với Frontend: pool, id chuyến, tuple 11 trường, và id tài xế
    """
    conn = pool.get_connection()
    cursor = conn.cursor()
    try:
        # 1. Bắt đầu Transaction
        conn.start_transaction()

        # 2. Cập nhật bảng chuyen_di
        sql_update_chuyen = """
            UPDATE chuyen_di 
            SET 
                ngay_chuyen_di = %s, 
                ten_khach_hang = %s, 
                dia_chi_khach_hang = %s,
                xe_id = %s, 
                dia_diem_giao_nhan = %s, 
                so_km_thuc_te = %s,
                khoi_luong_kg = %s, 
                the_tich_cbm = %s, 
                cong_chuyen = %s,
                trang_thai_chuyen = %s, 
                ghi_chu = %s
            WHERE id = %s
        """
        # Cộng gộp Tuple 11 trường với tham số trip_id ở cuối cùng để đưa vào WHERE id = %s
        params_chuyen = trip_data_tuple + (trip_id,)
        cursor.execute(sql_update_chuyen, params_chuyen)

        # 3. Cập nhật bảng chuyen_di_tai_xe (Tài xế chạy chuyến)
        # Cách an toàn nhất để update là xoá bản ghi cũ của chuyến này và chèn bản ghi mới
        sql_delete_tx = "DELETE FROM chuyen_di_tai_xe WHERE chuyen_di_id = %s"
        cursor.execute(sql_delete_tx, (trip_id,))
        
        sql_insert_tx = "INSERT INTO chuyen_di_tai_xe (chuyen_di_id, tai_xe_id) VALUES (%s, %s)"
        cursor.execute(sql_insert_tx, (trip_id, tai_xe_id))

        # 4. Lưu thay đổi
        conn.commit()
        return True, "Cập nhật thành công"

    except Exception as e:
        # Hủy bỏ mọi thao tác nếu có lỗi
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
###############################

def delete_trip_safe(db_pool, chuyen_di_id):
    """
    #Xóa an toàn một chuyến đi bằng cách dọn dẹp các dữ liệu liên quan trước (Tránh lỗi Khóa ngoại).
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False
        
        # 1. Xóa phân công tài xế
        cursor.execute("DELETE FROM chuyen_di_tai_xe WHERE chuyen_di_id = %s", (chuyen_di_id,))
        
        # 2. Xóa chi phí bên bảng chi_phi_chuyen_di (nếu có)
        cursor.execute("DELETE FROM chi_phi_chuyen_di WHERE chuyen_di_id = %s", (chuyen_di_id,))
        
        # 3. Cuối cùng mới Xóa chuyến đi
        cursor.execute("DELETE FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
        
        # [THÊM MỚI] Ghi log hành động xóa
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state['username'], "XOA_CHUYEN", {"trang_thai": "Đã xóa vĩnh viễn"})
        conn.commit()
        return True, "Xóa chuyến đi thành công!"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool
###



def get_bao_cao_pnl_chuyen_di(db_pool, tu_ngay, den_ngay, xe_id=0):
    """
    Trích xuất báo cáo Lãi/Lỗ (P&L) dựa trên bảng chuyen_di mới nhất.
    Đã bổ sung thông tin Tài Xế phụ trách chuyến.
    """
    try:
        conn = db_pool.get_connection()
        
        sql_base = """
            SELECT 
                cd.id AS `Mã Chuyến`,
                DATE_FORMAT(cd.ngay_chuyen_di, '%d/%m/%Y') AS `Ngày Chạy`,
                x.bien_so_xe AS `Biển Số Xe`,
                COALESCE(nv.ho_ten, 'Chưa xác định') AS `Tài Xế`,
                cd.dia_diem_giao_nhan AS `Hành Trình`,
                
                COALESCE(cd.doanh_thu, 0) AS `Doanh Thu`, 
                
                -- CÁC KHOẢN CHI TIẾT
                COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.tien_them, 0) AS `Lương TX & Thêm`,
                COALESCE(cd.tien_xang, 0) AS `Tiền Xăng/Dầu`,
                COALESCE(cd.phi_hai_quan, 0) AS `Hải Quan`,
                COALESCE(cd.phi_boc_xep, 0) AS `Bốc Xếp`,
                COALESCE(cd.phi_khac, 0) AS `Phí Khác`,
                
                -- TỔNG CHI CỘNG GỘP
                (COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.tien_them, 0) + 
                 COALESCE(cd.tien_xang, 0) + 
                 COALESCE(cd.phi_hai_quan, 0) + COALESCE(cd.phi_boc_xep, 0) + COALESCE(cd.phi_khac, 0)) AS `Tổng Chi Phí`,
                
                -- LỢI NHUẬN RÒNG
                COALESCE(cd.doanh_thu, 0) - (COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.tien_them, 0) + 
                     COALESCE(cd.tien_xang, 0) + 
                     COALESCE(cd.phi_hai_quan, 0) + COALESCE(cd.phi_boc_xep, 0) + COALESCE(cd.phi_khac, 0)) AS `Lợi Nhuận Gộp`
                
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            
            -- [MỚI BỔ SUNG] JOIN qua bảng phân công để lấy Tên tài xế chính
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
    except Exception as e:
        print(f"Lỗi truy vấn P&L: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn: conn.close()
###################
# Lấy thông tin xác thực từ file .env
HTX_CUSTOMER_CODE = os.getenv("HTX_CUSTOMER_CODE")
HTX_KEY = os.getenv("HTX_KEY")


def goi_gps_theo_thoi_gian_tuy_chinh(db_instance, chuyen_di_id, tg_bat_dau_quet, tg_ket_thuc_quet):
    """
    Hàm gọi GPS độc lập, sử dụng mốc thời gian do Kế toán chốt trên UI.
    """
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Lấy thông tin xe
        sql_get_info = """
            SELECT x.bien_so_xe, x.id as xe_id
            FROM chuyen_di cd
            JOIN xe x ON cd.xe_id = x.id
            WHERE cd.id = %s
        """
        cursor.execute(sql_get_info, (chuyen_di_id,))
        trip_info = cursor.fetchone()
        
        # Kiểm tra an toàn trước khi gọi API
        if not HTX_CUSTOMER_CODE or not HTX_KEY:
            return False, "⚠️ Lỗi: Chưa cấu hình CustomerCode hoặc Key trong file .env" 
        if not trip_info or not trip_info['bien_so_xe']:
            return False, "Không tìm thấy thông tin xe."
            
        bien_so = trip_info['bien_so_xe']
        xe_id = trip_info['xe_id']
        
        api_url = "https://hanhtrinhxe.vn/api/gps/rpsummary"
        tong_km_chuyen_di = 0.0
        thoi_gian_quet_hien_tai = tg_bat_dau_quet
        
        # Vòng lặp chia nhỏ request nếu thời gian dài
        while thoi_gian_quet_hien_tai < tg_ket_thuc_quet:
            moc_tiep_theo = thoi_gian_quet_hien_tai + datetime.timedelta(hours=23, minutes=59, seconds=59)
            if moc_tiep_theo > tg_ket_thuc_quet:
                moc_tiep_theo = tg_ket_thuc_quet
                
            from_date_str = thoi_gian_quet_hien_tai.strftime('%Y%m%d%H%M%S')
            to_date_str = moc_tiep_theo.strftime('%Y%m%d%H%M%S')
            
            payload = {
                "CustomerCode": HTX_CUSTOMER_CODE,     
                "Key": HTX_KEY,               
                "VehiclePlate": bien_so,
                "FromDate": from_date_str,
                "ToDate": to_date_str
            }
            
            try:
                response = requests.post(api_url, data=payload, timeout=20, verify=False)
                if response.status_code == 200:
                    api_data = response.json()
                    if api_data.get('messageResult') == 'Success':
                        danh_sach_bao_cao = api_data.get('summaryReports', [])
                        if danh_sach_bao_cao and len(danh_sach_bao_cao) > 0:
                            tong_km_chuyen_di += float(danh_sach_bao_cao[0].get('totalKmGps', 0))
            except Exception as api_err:
                pass # Có thể ghi log lỗi API ở đây
                
            thoi_gian_quet_hien_tai = moc_tiep_theo + datetime.timedelta(seconds=1)

        # CẬP NHẬT DATABASE
        sql_update_chuyen = """
            UPDATE chuyen_di 
            SET so_km_thuc_te = %s,
                thoi_gian_bat_dau = %s, 
                thoi_gian_ket_thuc = %s,
                trang_thai_chuyen = 'Quyet_Toan'
            WHERE id = %s
        """
        cursor.execute(sql_update_chuyen, (tong_km_chuyen_di, tg_bat_dau_quet, tg_ket_thuc_quet, chuyen_di_id))
        
        if tong_km_chuyen_di > 0:
            sql_update_xe = "UPDATE xe SET tong_km_hien_tai = tong_km_hien_tai + %s WHERE id = %s"
            cursor.execute(sql_update_xe, (tong_km_chuyen_di, xe_id))
            
        conn.commit()
        return True, f"✅ Đã quét thành công {tong_km_chuyen_di:.2f} KM."
        
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        return False, f"Lỗi hệ thống: {e}"
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()