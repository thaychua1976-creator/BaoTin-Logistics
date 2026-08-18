import io
import json
import traceback
from audit_logger import ghi_log_he_thong

def save_co_transaction(db_pool, co_data, co_id, current_user):
    """
    Thêm mới hoặc Cập nhật chứng từ C/O. Tuân thủ Transaction & Audit Log JSON.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False 
        cursor = conn.cursor()

        if co_id:
            sql = """UPDATE to_khai_co 
                     SET to_khai_id=%s, form_co=%s, so_co=%s, ngay_co=%s, 
                         phi_co=%s, phi_dvhq=%s , so_hoa_don_co=%s, ghi_chu=%s
                     WHERE id=%s"""
            val = (co_data['to_khai_id'], co_data.get('form_co'), co_data['so_co'], 
                   co_data.get('ngay_co'), co_data.get('phi_co', 0),co_data.get('phi_dvhq'), 
                   co_data.get('so_hoa_don_co'), co_data.get('ghi_chu'), co_id)
            cursor.execute(sql, val)
            
            if cursor.rowcount == 0:
                conn.rollback()
                return False, "Không tìm thấy chứng từ C/O hoặc không có sự thay đổi dữ liệu."
            action = "CAP_NHAT"
        else:
            sql = """INSERT INTO to_khai_co 
                     (to_khai_id, form_co, so_co, ngay_co, phi_co,phi_dvhq, so_hoa_don_co, ghi_chu) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            val = (co_data['to_khai_id'], co_data.get('form_co'), co_data['so_co'], 
                   co_data.get('ngay_co'), co_data.get('phi_co', 0), co_data.get('phi_dvhq'),
                   co_data.get('so_hoa_don_co'), co_data.get('ghi_chu'))
            cursor.execute(sql, val)
            co_id = cursor.lastrowid
            action = "TAO_MOI"

        # Ghi log Audit an toàn
        chi_tiet_json = json.dumps(co_data, ensure_ascii=False, default=str)
        ghi_log_he_thong(cursor, "QUAN_LY_CO", co_id, current_user, action, chi_tiet_json)

        conn.commit()
        return True, co_id
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_co_transaction(db_pool, co_id, current_user):
    """
    Xóa chứng từ C/O an toàn, kiểm tra rowcount và ghi Audit Log.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False 
        cursor = conn.cursor()
        
        cursor.execute("SELECT so_co FROM to_khai_co WHERE id=%s", (co_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Không tìm thấy chứng từ C/O trong hệ thống."
            
        cursor.execute("DELETE FROM to_khai_co WHERE id=%s", (co_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return False, "Xóa thất bại. Chứng từ C/O không tồn tại."
            
        ghi_log_he_thong(cursor, "QUAN_LY_CO", co_id, current_user, "XOA", json.dumps({"so_co_bi_xoa": row[0]}, ensure_ascii=False))
        
        conn.commit()
        return True, "Thành công"
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
##########################
# Thêm hàm này vào file co_manager.py
def get_don_gia_co_theo_khach_hang(db_pool, khach_hang_id, phan_loai_chi_tiet):
    """
    Truy xuất giá làm C/O tự động từ bảng bang_gia_hai_quan.
    - nhom_dich_vu: Cố định là 'Làm C/O'
    - phan_loai_chi_tiet: Thay đổi theo UI (Thường, Gấp, Ghép)
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT don_gia_hq 
            FROM bang_gia_hai_quan 
            WHERE khach_hang_id = %s 
              AND nhom_dich_vu = 'Làm C/O' 
              AND phan_loai_chi_tiet = %s
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(sql, (khach_hang_id, phan_loai_chi_tiet))
        result = cursor.fetchone()
        
        if result and result['don_gia_hq']:
            return float(result['don_gia_hq'])
        return 0.0
    except Exception as e:
        print(f"Lỗi truy xuất giá C/O: {e}")
        return 0.0
    finally:
        if cursor: cursor.close()
        if conn: conn.close()