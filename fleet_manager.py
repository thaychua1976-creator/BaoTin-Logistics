import pandas as pd
from audit_logger import log_thao_tac

#2. HÀM TRANSACTION CỦA XE (Đã đổi tên gọi hàm log_thao_tac)
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
######################

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
###############################

def get_canh_bao_bao_duong(db_pool):
    """Lấy danh sách xe và tính toán số KM đã chạy từ Odometer"""
    sql = """
        SELECT 
            id AS xe_id,
            bien_so_xe,
            COALESCE(dinh_muc_bao_duong, 5000) AS dinh_muc_km,
            ngay_bao_duong_gan_nhat AS ngay_bd_cuoi,
            -- Số KM đã chạy = Tổng Odometer hiện tại - Mốc Odometer lúc bảo dưỡng
            (COALESCE(tong_km_hien_tai, 0) - COALESCE(km_bao_duong_gan_nhat, 0)) AS km_da_chay
        FROM xe
        WHERE trang_thai = 'Dang_Hoat_Dong'
        -- Sắp xếp: Ưu tiên những xe có tỷ lệ chạy/định mức cao nhất lên đầu
        ORDER BY ( (COALESCE(tong_km_hien_tai, 0) - COALESCE(km_bao_duong_gan_nhat, 0)) / COALESCE(dinh_muc_bao_duong, 5000) ) DESC;
    """
    try:
        # Tùy theo cách cấu hình class DB, dùng hàm tương ứng
        conn = db_pool.get_connection()
        df = pd.read_sql(sql, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Lỗi truy vấn bảo dưỡng: {e}")
        return None
############################################
def save_lich_su_bao_duong(db_pool, data_dict):
    """Lưu lịch sử và cập nhật đồng bộ mốc bảo dưỡng sang bảng Xe"""
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        
        # 1. Ghi vào bảng lịch sử bảo dưỡng
        sql_insert = """
            INSERT INTO lich_su_bao_duong 
            (xe_id, ngay_bao_duong, km_thuc_te, hang_muc_sua_chua, chi_phi, don_vi_thuc_hien, loai_bao_duong, ghi_chu)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_insert, (
            data_dict['xe_id'], data_dict['ngay_bao_duong'], data_dict['km_thuc_te'],
            data_dict['hang_muc_sua_chua'], data_dict['chi_phi'], data_dict['don_vi_thuc_hien'],
            data_dict['loai_bao_duong'], data_dict['ghi_chu']
        ))
        
        # 2. CHỈ RESET mốc bảo dưỡng trên bảng `xe` nếu đây là Bảo dưỡng Định kỳ
        if data_dict['loai_bao_duong'] == 'Dinh_Ky':
            sql_update_xe = """
                UPDATE xe 
                SET ngay_bao_duong_gan_nhat = %s,
                    km_bao_duong_gan_nhat = %s,
                    tong_km_hien_tai = %s -- Đồng bộ lại đồng hồ phần mềm theo đồng hồ thật của xe
                WHERE id = %s
            """
            cursor.execute(sql_update_xe, (
                data_dict['ngay_bao_duong'], 
                data_dict['km_thuc_te'], 
                data_dict['km_thuc_te'], 
                data_dict['xe_id']
            ))
            
        conn.commit()
        return True, "✅ Đã lưu phiếu và đồng bộ thông số xe thành công!"
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        return False, f"❌ Lỗi Database: {str(e)}"
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
############################## 
##### function thống kê bảo dưỡng xe, tiêu thụ nhiên liệu 12/7/2026

def get_thong_ke_hoat_dong_xe(db_pool, xe_id, tu_ngay, den_ngay):
    """Thống kê tổng KM và Lít dầu tiêu thụ (Hỗ trợ tra cứu Tất cả phương tiện)"""
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Nếu xe_id == 0 nghĩa là chọn "Tất cả phương tiện"
        if xe_id == 0:
            sql = """
                SELECT 
                    COALESCE(SUM(so_km_thuc_te), 0) as tong_km,
                    COALESCE(SUM(so_lit_xang), 0) as tong_nhien_lieu,
                    COUNT(id) as tong_so_chuyen
                FROM chuyen_di
                WHERE trang_thai_chuyen = 'Hoan_Thanh'
                  AND ngay_chuyen_di BETWEEN %s AND %s
            """
            cursor.execute(sql, (tu_ngay, den_ngay))
        else:
            sql = """
                SELECT 
                    COALESCE(SUM(so_km_thuc_te), 0) as tong_km,
                    COALESCE(SUM(so_lit_xang), 0) as tong_nhien_lieu,
                    COUNT(id) as tong_so_chuyen
                FROM chuyen_di
                WHERE xe_id = %s 
                  AND trang_thai_chuyen = 'Hoan_Thanh'
                  AND ngay_chuyen_di BETWEEN %s AND %s
            """
            cursor.execute(sql, (xe_id, tu_ngay, den_ngay))
            
        result = cursor.fetchone()
        return result if result else {'tong_km': 0, 'tong_nhien_lieu': 0, 'tong_so_chuyen': 0}
    except Exception as e:
        print(f"Lỗi thống kê xe: {e}")
        return {'tong_km': 0, 'tong_nhien_lieu': 0, 'tong_so_chuyen': 0}
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
##############################################################
def get_chi_tiet_bao_duong_xe(db_pool, xe_id, tu_ngay, den_ngay):
    """Lấy lịch sử bảo dưỡng chi tiết (Kèm Biển số xe và Tài xế cố định)"""
    try:
        conn = db_pool.get_connection()
        
        if xe_id == 0:
            sql = """
                SELECT 
                    x.bien_so_xe, 
                    nv.ho_ten AS ten_tai_xe,
                    l.ngay_bao_duong, l.loai_bao_duong,
                    l.km_thuc_te, l.hang_muc_sua_chua, l.don_vi_thuc_hien, 
                    l.chi_phi, l.ghi_chu
                FROM lich_su_bao_duong l
                JOIN xe x ON l.xe_id = x.id
                LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                WHERE l.ngay_bao_duong BETWEEN %s AND %s
                ORDER BY l.ngay_bao_duong DESC
            """
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay))
        else:
            sql = """
                SELECT 
                    x.bien_so_xe, 
                    nv.ho_ten AS ten_tai_xe,
                    l.ngay_bao_duong, l.loai_bao_duong,
                    l.km_thuc_te, l.hang_muc_sua_chua, l.don_vi_thuc_hien, 
                    l.chi_phi, l.ghi_chu
                FROM lich_su_bao_duong l
                JOIN xe x ON l.xe_id = x.id
                LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                WHERE l.xe_id = %s 
                  AND l.ngay_bao_duong BETWEEN %s AND %s
                ORDER BY l.ngay_bao_duong DESC
            """
            df = pd.read_sql(sql, conn, params=(xe_id, tu_ngay, den_ngay))
            
        return df
    except Exception as e:
        print(f"Lỗi chi tiết bảo dưỡng: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn: conn.close()
##################### ending thống kê #################### 12/07/2026