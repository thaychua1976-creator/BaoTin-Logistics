import json
from audit_logger import ghi_log_he_thong, ghi_log_thao_tac

def handle_user_transaction_with_audit(db_pool, action, user_data, current_user):
    """
    Hàm xử lý Transaction cho hệ thống Tài khoản (Thêm/Sửa/Xóa) và ghi log Audit.
    
    Args:
        db_pool: Đối tượng Connection Pool của CSDL [cite: 24]
        action (str): Loại thao tác ("TAO_MOI", "CAP_NHAT", hoặc "XOA")
        user_data (dict): Từ điển chứa dữ liệu user (id, username, password, ho_ten, role, trang_thai)
        current_user (str): Tên tài khoản đang thực hiện thao tác (thường là st.session_state['username']) [cite: 27]
        
    Returns:
        tuple: (bool, int/str) -> (Thành công/Thất bại, ID tài khoản hoặc câu thông báo lỗi) [cite: 27, 28]
    """
    conn = db_pool.get_connection() 
    cursor = conn.cursor() 
    
    try:
        # Bắt đầu Transaction
        conn.autocommit = False 
        target_user_id = user_data.get('id')
        
        # 1. THỰC THI CÂU LỆNH CHÍNH DỰA TRÊN HÀNH ĐỘNG
        if action == "TAO_MOI":
            sql = """INSERT INTO users (username, password, ho_ten, role, trang_thai, nhan_vien_id) 
                     VALUES (%s, %s, %s, %s, %s,%s)"""
            cursor.execute(sql, (
                user_data['username'], user_data['password'], 
                user_data['ho_ten'], user_data['role'], user_data['trang_thai'], user_data.get('nhan_vien_id')
            ))
            # Lấy ID của tài khoản vừa tạo an toàn [cite: 25]
            target_user_id = cursor.lastrowid 
            
        elif action == "CAP_NHAT":
            sql = """UPDATE users 
                     SET ho_ten = %s, password = %s, role = %s, trang_thai = %s, nhan_vien_id=%s 
                     WHERE id = %s"""
            cursor.execute(sql, (
                user_data['ho_ten'], user_data['password'], 
                user_data['role'], user_data['trang_thai'],user_data.get('nhan_vien_id'), target_user_id
            ))
            
        elif action == "XOA":
            sql = "DELETE FROM users WHERE id = %s"
            cursor.execute(sql, (target_user_id,))
        
        else:
            raise ValueError("Hành động (action) không hợp lệ!")

        # 2. GHI LOG AUDIT CÙNG TRONG TRANSACTION [cite: 26]
        # Gom các thông tin quan trọng vào JSON để lưu xuống Database
        log_data = {
            "username_bi_tac_dong": user_data.get('username', ''),
            "ho_ten": user_data.get('ho_ten', ''),
            "quyen_han": user_data.get('role', ''),
            "trang_thai": user_data.get('trang_thai', '')
        }
        
        # Gọi hàm ghi log (Lưu ý: phải truyền cursor hiện tại vào để đi chung Transaction) [cite: 27]
        ghi_log_he_thong(
            cursor=cursor, 
            phan_he="QUAN_LY_TAI_KHOAN", 
            record_id=target_user_id, 
            nguoi_thuc_hien=current_user, 
            hanh_dong=action, 
            chi_tiet=json.dumps(log_data, ensure_ascii=False)
        )
        
        # Xác nhận lưu tất cả thay đổi [cite: 27]
        conn.commit() 
        return True, target_user_id
        
    except Exception as e:
        # Hoàn tác toàn bộ nếu có lỗi ở bất kỳ bước nào (Thêm user hoặc ghi log) [cite: 27, 28]
        conn.rollback() 
        return False, str(e) 
        
    finally:
        # Quan trọng: Luôn luôn đóng cursor và trả kết nối về Pool [cite: 28]
        cursor.close() 
        conn.close() 

def save_nhan_vien_transaction(db_pool, action, nv_data=None, nv_id=None, current_user="Hệ thống"):
    """
    Hàm xử lý Thêm/Sửa/Xoá nhân viên với Transaction và Audit Log.
    - action: 'ADD', 'UPDATE', hoặc 'DELETE' (Báo cáo nghỉ việc)
    - nv_data: Tuple chứa thông tin (không cần truyền khi DELETE)
    - nv_id: Bắt buộc truyền ID khi action='UPDATE' hoặc 'DELETE'
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
        hinh_thuc_log = ""
        chi_tiet_thay_doi = {}
        affected_id = nv_id
        
        if action == 'ADD':
            # 1. Thêm mới
            sql_add = """INSERT INTO nhan_vien 
                (ma_nhan_vien, ho_ten, so_dien_thoai, cccd, giay_phep_lai_xe, hang_gplx, han_gplx, han_the_tap_huan, loai_nhan_vien, trang_thai) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Dang_Lam_Viec')"""
            cursor.execute(sql_add, nv_data)
            affected_id = cursor.lastrowid
            
            hinh_thuc_log = "THEM_MOI"
            chi_tiet_thay_doi = {"ma_nhan_vien": nv_data[0], "ho_ten": nv_data[1], "sdt": nv_data[2]}
            
        elif action == 'UPDATE':
            # 2. Cập nhật
            sql_upd = """UPDATE nhan_vien 
                SET ma_nhan_vien=%s, ho_ten=%s, so_dien_thoai=%s, cccd=%s, giay_phep_lai_xe=%s, hang_gplx=%s, han_gplx=%s, han_the_tap_huan=%s, loai_nhan_vien=%s 
                WHERE id=%s"""
            update_params = tuple(list(nv_data) + [nv_id])
            cursor.execute(sql_upd, update_params)
            
            hinh_thuc_log = "CAP_NHAT"
            chi_tiet_thay_doi = {"ma_nhan_vien": nv_data[0], "ho_ten": nv_data[1], "sdt": nv_data[2]}
            
        elif action == 'DELETE':
            # 3. Xoá / Báo cáo nghỉ việc
            sql_del = "UPDATE nhan_vien SET trang_thai='Da_Nghi_Viec' WHERE id=%s"
            cursor.execute(sql_del, (nv_id,))
            
            hinh_thuc_log = "XOA_NGHI_VIEC"
            chi_tiet_thay_doi = {"trang_thai_moi": "Da_Nghi_Viec"}
            
        else:
            raise ValueError("Hành động không hợp lệ.")

        # ==========================================
        # GỌI HÀM GHI LOG HỆ THỐNG
        # ==========================================
        # Truyền chính xác cursor của giao dịch hiện tại vào hàm log
        ghi_log_he_thong(
            cursor=cursor, 
            phan_he='NHAN_VIEN', 
            record_id=affected_id, 
            nguoi_thuc_hien=current_user, 
            hanh_dong=hinh_thuc_log, 
            chi_tiet=json.dumps(chi_tiet_thay_doi, ensure_ascii=False)
        )
        
        conn.commit() # Xác nhận lưu tất cả dữ liệu (Cả DB chính và Log)
        return True, "Thành công"
        
    except Exception as e:
        conn.rollback() # Hoàn tác mọi thay đổi nếu có lỗi
        return False, str(e)
        
    finally:
        cursor.close()
        conn.close()
##################3

def update_bonus_config_transaction(db_pool, updated_values: dict, nguoi_dung: str = "Admin"):
    """
    Cập nhật đồng loạt các tiêu chí thưởng bằng Transaction.
    updated_values: Dictionary dạng {'GOP_CHUYEN': 100000, 'VE_KHUYA': 100000}
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Giao dịch
        
        # 1. Chạy vòng lặp cập nhật từng tiêu chí
        sql_update = "UPDATE cau_hinh_thuong SET muc_thuong = %s WHERE ma_tieu_chi = %s"
        for ma_tc, val_num in updated_values.items():
            cursor.execute(sql_update, (val_num, ma_tc))
            
        # 2. Ghi log lưu vết (Audit Trail)
        # Truyền chuyen_di_id = None vì thao tác này ảnh hưởng toàn hệ thống chứ không phải 1 chuyến cụ thể
        ghi_log_thao_tac(
            cursor=cursor, 
            chuyen_di_id=None, 
            nguoi_dung=nguoi_dung, 
            hanh_dong="CAP_NHAT_CAU_HINH_THUONG", 
            chi_tiet_dict=updated_values
        )
        
        conn.commit() # Lưu tất cả xuống ổ cứng
        return True, "Cập nhật bảng định mức thưởng thành công!"
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool
################################