import json

def ghi_log_thao_tac(cursor, chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """Ghi nhận dấu vết thao tác của người dùng cho Chuyến đi."""
    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (%s, %s, %s, %s)
    """
    chi_tiet_json = json.dumps(chi_tiet_dict, ensure_ascii=False) if chi_tiet_dict else "Không có chi tiết"
    cursor.execute(sql_log, (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_json))

def log_thao_tac(cursor, xe_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """Ghi nhận dấu vết thao tác của người dùng trên dữ liệu Xe."""
    if xe_id:
        chi_tiet_dict['id_xe_tac_dong'] = xe_id
        
    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (NULL, %s, %s, %s)
    """
    chi_tiet_json = json.dumps(chi_tiet_dict, ensure_ascii=False) if chi_tiet_dict else "Không có chi tiết"
    cursor.execute(sql_log, (nguoi_dung, hanh_dong, chi_tiet_json))

def ghi_log_he_thong(cursor, phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet):
    """Hàm ghi nhận lịch sử thao tác cho toàn hệ thống (Users, Nhân viên...)."""
    sql_log = """
        INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet, thoi_gian)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    cursor.execute(sql_log, (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet))