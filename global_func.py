import json
import streamlit as st
import requests # Thêm thư viện này để gọi API

def parse_money_input(val_str):
    if not val_str: return 0
    try: return int(str(val_str).replace(',', '').replace('.', '').strip())
    except: return 0

####################################
def update_bonus_config_transaction(db_pool, updated_values: dict, nguoi_dung: str = "Admin"):
    """
    Cập nhật đồng loạt các tiêu chí thưởng bằng Transaction.
    updated_values: Dictionary dạng {'GOP_CHUYEN': 100000, 'VE_KHUYA': 50000}
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

def ghi_log_thao_tac(cursor, chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """
    Ghi nhận dấu vết thao tác của người dùng.
    """
    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (%s, %s, %s, %s)
    """
    # Chuyển đổi Dictionary thành chuỗi JSON để lưu trữ gọn gàng
    chi_tiet_json = json.dumps(chi_tiet_dict, ensure_ascii=False) if chi_tiet_dict else "Không có chi tiết"
    cursor.execute(sql_log, (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_json))
##################

# 2. HÀM TRANSACTION ĐA BẢNG (Chống rác dữ liệu và chống kẹt ID)
def save_trip_full_process(db_pool, trip_data, tai_xe_id):
    """
    trip_data CẦN ĐÚNG 8 BIẾN: (ngay_chuyen_di, ten_khach_hang,dia-chi_khach_hang, xe_id, dia_diem_giao_nhan, so_km_thuc_te, khoi_luong_kg, cong_chuyen, trang_thai_chuyen,ghi_chu,)
    tai_xe_id: INT
    chi_phi_data: tuple (so_tien, loai_chi_phi, ghi_chu)
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
        # 1. Lưu chuyến đi (Đã bổ sung cột khoi_luong_kg)
        sql_trip = """INSERT INTO chuyen_di 
            (ngay_chuyen_di, ten_khach_hang,dia_chi_khach_hang, xe_id, dia_diem_giao_nhan, so_km_thuc_te, khoi_luong_kg,the_tich_cbm, cong_chuyen, trang_thai_chuyen,ghi_chu) 
            VALUES (%s, %s, %s, %s, %s, %s, %s,%s, %s,%s,%s)"""
        cursor.execute(sql_trip, trip_data)
        
        new_cid = cursor.lastrowid # Lấy ID vừa tạo an toàn
        
        # 2. Lưu tài xế
        sql_tx = "INSERT INTO chuyen_di_tai_xe (chuyen_di_id, tai_xe_id, loai_tai_xe) VALUES (%s, %s, 'Tai_Chinh')"
        cursor.execute(sql_tx, (new_cid, tai_xe_id))
        
       
        # [THÊM MỚI] Ghi log tạo chuyến
        log_data = {
            "hanh_trinh": trip_data[3], 
            "khoi_luong": trip_data[5],
            "cong_tai_xe": trip_data[7]
        }
        # Nếu ứng dụng bạn có đăng nhập, thay chữ "Admin" bằng st.session_state['username']
        ghi_log_thao_tac(cursor, new_cid, st.session_state['username'], "TAO_MOI", log_data)
        conn.commit() # Xác nhận lưu tất cả
        return True, new_cid
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có bất kỳ lỗi nào xảy ra
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Quan trọng: Trả kết nối về Pool

########################        
def settle_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    """
    Hàm Giao dịch Quyết toán dùng chung.
    - data_chuyen_di: Truyền vào 1 Dictionary chứa tên cột và giá trị cần cập nhật.
    - trang_thai_enum: Trạng thái chuẩn ENUM (vd: 'Hoan_Thanh').
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
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
            WHERE id=%s AND trang_thai_chuyen NOT IN ('Hoan_Thanh','Huy_Chuyen')
        """
        
        # 3. Thực thi
        cursor.execute(sql_update, tuple(values))
        
        # 4. KIỂM TRA LỖI THÔNG MINH HƠN
        if cursor.rowcount == 0:
            # rowcount = 0 có 2 trường hợp: 
            # 1. Chuyến đi thật sự không tồn tại
            # 2. Tồn tại nhưng người dùng không thay đổi số liệu gì (dữ liệu mới y hệt cũ)
            
            # Ta truy vấn thử xem ID có thực sự tồn tại trong DB không
            cursor.execute("SELECT id FROM chuyen_di WHERE id = %s", (chuyen_di_id,))
            if cursor.fetchone() is None:
                # Nếu không tìm thấy ID -> Lỗi thật
                conn.rollback()
                return False, f"Lỗi: Chuyến đi mã {chuyen_di_id} không tồn tại trong hệ thống."
            
            # Nếu tìm thấy ID -> Tức là người dùng không sửa gì mà vẫn bấm Lưu -> Cho qua (không cần Rollback)
        
        # [THÊM MỚI] Ghi log quyết toán/cập nhật
        # (Giữ nguyên đoạn code ghi log của bạn ở bên dưới)
        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state['username'], hanh_dong, data_chuyen_di)    
        conn.commit() # Lưu thành công
        return True, chuyen_di_id
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi định dạng
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool
##########################################        

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
# 2. HÀM TRANSACTION CỦA XE (Đã đổi tên gọi hàm log_thao_tac)
def save_vehicle_transaction(db_pool, xe_data: dict, xe_id: int = None, nguoi_dung: str = "Admin"):
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Mở khiên bảo vệ Transaction
        
        if xe_id is None:
            # LOGIC THÊM XE MỚI
            if 'trang_thai' not in xe_data:
                xe_data['trang_thai'] = 'Dang_Hoat_Dong'
                
            columns = ", ".join(xe_data.keys())
            placeholders = ", ".join(["%s"] * len(xe_data))
            values = tuple(xe_data.values())
            
            sql = f"INSERT INTO xe ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)
            
            action_id = cursor.lastrowid # Lấy ID xe vừa được tạo
            hanh_dong = "THEM_XE_MOI"
            
        else:
            # LOGIC CẬP NHẬT XE ĐÃ CÓ
            columns_to_set = [f"{col}=%s" for col in xe_data.keys()]
            set_clause = ", ".join(columns_to_set)
            
            values = list(xe_data.values())
            values.append(xe_id) 
            
            sql = f"UPDATE xe SET {set_clause} WHERE id=%s"
            cursor.execute(sql, tuple(values))
            
            action_id = xe_id
            hanh_dong = "CAP_NHAT_XE"
            
        # GỌI HÀM LOG MỚI ĐỊNH NGHĨA Ở TRÊN
        log_thao_tac(
            cursor=cursor, 
            xe_id=action_id, 
            nguoi_dung=nguoi_dung, 
            hanh_dong=hanh_dong, 
            chi_tiet_dict=xe_data
        )
        
        conn.commit() 
        return True, action_id
        
    except Exception as e:
        conn.rollback() 
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
######################3
# 1. HÀM GHI LOG DÀNH RIÊNG CHO MODULE XE
def log_thao_tac(cursor, xe_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """
    Ghi nhận dấu vết thao tác của người dùng trên dữ liệu Xe.
    """
    # Bổ sung ID của xe vào biến chi tiết để lưu vào JSON
    if xe_id:
        chi_tiet_dict['id_xe_tac_dong'] = xe_id
        
    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (NULL, %s, %s, %s)
    """
    
    chi_tiet_json = json.dumps(chi_tiet_dict, ensure_ascii=False) if chi_tiet_dict else "Không có chi tiết"
    cursor.execute(sql_log, (nguoi_dung, hanh_dong, chi_tiet_json))
##########################

def delete_vehicle_transaction(db_pool, xe_id: int, nguoi_dung: str = "Admin"):
    """
    Xóa mềm (Soft Delete) phương tiện: Cập nhật trạng thái thành 'Ngung_Hoat_Dong'.
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Mở khiên bảo vệ Transaction
        
        # 1. Thực thi lệnh Soft Delete
        sql_soft_delete = "UPDATE xe SET trang_thai = 'Ngung_Hoat_Dong' WHERE id = %s"
        cursor.execute(sql_soft_delete, (xe_id,))
        
        # Kiểm tra xem có xe nào thực sự bị tác động không
        if cursor.rowcount == 0:
            conn.rollback()
            return False, "Không tìm thấy xe hoặc xe đã ở trạng thái ngừng hoạt động."
            
        # 2. Ghi log kiểm toán (Audit Trail)
        chi_tiet_log = {
            "hanh_dong_chi_tiet": "Xóa mềm phương tiện",
            "trang_thai_moi": "Ngung_Hoat_Dong"
        }
        
        # Gọi hàm log của module Xe
        log_thao_tac(
            cursor=cursor, 
            xe_id=xe_id, 
            nguoi_dung=nguoi_dung, 
            hanh_dong="XOA_XE_MEM", 
            chi_tiet_dict=chi_tiet_log
        )
        
        conn.commit() # Chốt lưu an toàn
        return True, "Đã xóa (ngừng hoạt động) phương tiện thành công!"
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu xảy ra lỗi
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
####################

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
            sql = """INSERT INTO users (username, password, ho_ten, role, trang_thai) 
                     VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(sql, (
                user_data['username'], user_data['password'], 
                user_data['ho_ten'], user_data['role'], user_data['trang_thai']
            ))
            # Lấy ID của tài khoản vừa tạo an toàn [cite: 25]
            target_user_id = cursor.lastrowid 
            
        elif action == "CAP_NHAT":
            sql = """UPDATE users 
                     SET ho_ten = %s, password = %s, role = %s, trang_thai = %s 
                     WHERE id = %s"""
            cursor.execute(sql, (
                user_data['ho_ten'], user_data['password'], 
                user_data['role'], user_data['trang_thai'], target_user_id
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
###############
def ghi_log_he_thong(cursor, phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet):
    """
    Hàm ghi nhận lịch sử thao tác. Chạy chung cursor với transaction chính.
    """
    sql_log = """
        INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet, thoi_gian)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    cursor.execute(sql_log, (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet))
##################

# ==========================================
# HÀM KẾT NỐI API ZALO (ZALO ZNS)
# ==========================================
def send_zalo_message(phone, khach_hang, lo_trinh):
    """
    Hàm gửi tin nhắn qua Zalo Official Account (Zalo ZNS).
    Lưu ý: Để mã này chạy thực tế, bạn cần đăng ký Zalo OA, 
    lấy Access Token và tạo ZNS Template.
    """
    # Chuẩn hóa số điện thoại từ 09... sang 849... (yêu cầu của Zalo)
    phone_str = str(phone).strip()
    if phone_str.startswith('0'):
        phone_str = '84' + phone_str[1:]
        
    url = "https://business.openapi.zalo.me/message/template"
    
    # ⚠️ THAY THẾ BẰNG THÔNG TIN THẬT CỦA BẠN
    access_token = "YOUR_ZALO_ACCESS_TOKEN" 
    template_id = "YOUR_ZNS_TEMPLATE_ID" 
    
    headers = {
        "access_token": access_token,
        "Content-Type": "application/json"
    }
    
    # Dữ liệu truyền vào mẫu tin nhắn Zalo
    payload = {
        "phone": phone_str,
        "template_id": template_id,
        "template_data": {
            "khach_hang": khach_hang,
            "lo_trinh": lo_trinh
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    except Exception as e:
        return {"error": str(e)}
#################3

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
########################        
def update_trip_transaction(db_pool, data_chuyen_di: dict, trang_thai_enum: str, chuyen_di_id: int):
    """
    Hàm Giao dịch Quyết toán dùng chung.
    - data_chuyen_di: Truyền vào 1 Dictionary chứa tên cột và giá trị cần cập nhật.
    - trang_thai_enum: Trạng thái chuẩn ENUM (vd: 'Hoan_Thanh').
    """
    conn = db_pool.get_connection()
    cursor = conn.cursor()
    try:
        conn.autocommit = False # Bắt đầu Transaction
        
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
        
        # 3. Thực thi
        cursor.execute(sql_update, tuple(values))
        
        # Nếu không có dòng nào bị tác động (sai ID hoặc chuyến đã khóa)
        if cursor.rowcount == 0:
            conn.rollback()
            return False, f"Chuyến đi mã {chuyen_di_id} không tồn tại hoặc đã được chốt từ trước."
        
        # [THÊM MỚI] Ghi log quyết toán/cập nhật
        # Ta tận dụng luôn biến data_chuyen_di mà ta đã truyền vào hàm này
        hanh_dong = "CHOT_SO" if trang_thai_enum == "Hoan_Thanh" else "CAP_NHAT"
        ghi_log_thao_tac(cursor, chuyen_di_id, st.session_state['username'], hanh_dong, data_chuyen_di)    
        conn.commit() # Lưu thành công
        return True, chuyen_di_id
        
    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi định dạng
        return False, str(e)
    finally:
        cursor.close()
        conn.close() # Trả kết nối về Pool
##########################################        

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
