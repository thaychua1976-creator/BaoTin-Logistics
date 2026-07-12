import streamlit as st
from audit_logger import ghi_log_thao_tac

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