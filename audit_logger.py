import json


def ghi_log_thao_tac(cursor, chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """Ghi nhận dấu vết thao tác của người dùng cho Chuyến đi."""
    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (%s, %s, %s, %s)
    """
    if isinstance(chi_tiet_dict, (dict, list)):
        chi_tiet_json = json.dumps(chi_tiet_dict, ensure_ascii=False, default=str)
    else:
        chi_tiet_json = str(chi_tiet_dict) if chi_tiet_dict else "Không có chi tiết"

    cursor.execute(sql_log, (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_json))


def log_thao_tac(cursor, xe_id, nguoi_dung, hanh_dong, chi_tiet_dict):
    """Ghi nhận dấu vết thao tác của người dùng trên dữ liệu Xe."""
    if isinstance(chi_tiet_dict, dict):
        payload = dict(chi_tiet_dict)
    elif chi_tiet_dict:
        payload = {"noi_dung": str(chi_tiet_dict)}
    else:
        payload = {}

    if xe_id:
        payload['id_xe_tac_dong'] = xe_id

    sql_log = """
        INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) 
        VALUES (NULL, %s, %s, %s)
    """
    chi_tiet_json = json.dumps(payload, ensure_ascii=False, default=str) if payload else "Không có chi tiết"
    cursor.execute(sql_log, (nguoi_dung, hanh_dong, chi_tiet_json))


def ghi_log_he_thong(cursor, phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet):
    """Hàm ghi nhận lịch sử thao tác cho toàn hệ thống (Users, Nhân viên, Bảng giá...)."""
    if isinstance(chi_tiet, (dict, list)):
        chi_tiet_str = json.dumps(chi_tiet, ensure_ascii=False, default=str)
    else:
        chi_tiet_str = str(chi_tiet) if chi_tiet is not None else ""

    sql_log = """
        INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet, thoi_gian)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    cursor.execute(sql_log, (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet_str))