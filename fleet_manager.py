import pandas as pd
from audit_logger import log_thao_tac
from utils_core import parse_money_input
import json

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
    """Lấy lịch sử bảo dưỡng chi tiết (Đã tích hợp tự động tính Lít dầu theo chu kỳ)"""
    try:
        conn = db_pool.get_connection()
        
        # CÔNG THỨC THÔNG MINH: Tự động quét bảng chuyen_di để cộng dồn lít dầu 
        # tính từ lần bảo dưỡng gần nhất trước đó cho đến ngày bảo dưỡng hiện tại.
        subquery_dau = """
            (SELECT COALESCE(SUM(cd.so_lit_xang), 0)
             FROM chuyen_di cd
             WHERE cd.xe_id = l.xe_id
               AND cd.trang_thai_chuyen = 'Hoan_Thanh'
               AND cd.ngay_chuyen_di <= l.ngay_bao_duong
               AND cd.ngay_chuyen_di > COALESCE(
                   (SELECT MAX(l2.ngay_bao_duong) 
                    FROM lich_su_bao_duong l2 
                    WHERE l2.xe_id = l.xe_id AND l2.ngay_bao_duong < l.ngay_bao_duong),
                   '1970-01-01'
               )
            ) AS lit_dau_tieu_thu
        """
        
        if xe_id == 0:
            sql = f"""
                SELECT 
                    x.bien_so_xe, 
                    nv.ho_ten AS ten_tai_xe,
                    l.ngay_bao_duong, l.loai_bao_duong,
                    l.km_thuc_te, 
                    {subquery_dau},
                    l.hang_muc_sua_chua, l.don_vi_thuc_hien, 
                    l.chi_phi, l.ghi_chu
                FROM lich_su_bao_duong l
                JOIN xe x ON l.xe_id = x.id
                LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                WHERE l.ngay_bao_duong BETWEEN %s AND %s
                ORDER BY l.ngay_bao_duong DESC
            """
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay))
        else:
            sql = f"""
                SELECT 
                    x.bien_so_xe, 
                    nv.ho_ten AS ten_tai_xe,
                    l.ngay_bao_duong, l.loai_bao_duong,
                    l.km_thuc_te, 
                    {subquery_dau},
                    l.hang_muc_sua_chua, l.don_vi_thuc_hien, 
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
def get_bieu_do_hoat_dong(db_pool, xe_id, tu_ngay, den_ngay):
    """Lấy dữ liệu vận hành (KM và Nhiên liệu) gom nhóm theo từng tháng để vẽ biểu đồ"""
    try:
        conn = db_pool.get_connection()
        
        # Gom nhóm theo tháng-năm (VD: 04/2026)
        sql_base = """
            SELECT 
                DATE_FORMAT(ngay_chuyen_di, '%m/%Y') AS Thang,
                YEAR(ngay_chuyen_di) AS Nam_Sort,
                MONTH(ngay_chuyen_di) AS Thang_Sort,
                COALESCE(SUM(so_km_thuc_te), 0) AS Tong_KM,
                COALESCE(SUM(so_lit_xang), 0) AS Tong_Nhien_Lieu
            FROM chuyen_di
            WHERE trang_thai_chuyen = 'Hoan_Thanh'
              AND ngay_chuyen_di BETWEEN %s AND %s
        """
        
        if xe_id == 0:
            sql = sql_base + " GROUP BY Thang, Nam_Sort, Thang_Sort ORDER BY Nam_Sort, Thang_Sort"
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay))
        else:
            sql = sql_base + " AND xe_id = %s GROUP BY Thang, Nam_Sort, Thang_Sort ORDER BY Nam_Sort, Thang_Sort"
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay, xe_id))
            
        return df
    except Exception as e:
        print(f"Lỗi truy vấn biểu đồ: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn: conn.close()
###########################################################
import pandas as pd

def get_bang_ke_tong_hop_xe(db_pool, xe_id, tu_ngay, den_ngay):
    """Lấy bảng thống kê tổng hợp hiệu suất của (các) xe trong khoảng thời gian"""
    try:
        conn = db_pool.get_connection()
        
        # Nếu chọn "Tất cả", lấy toàn bộ xe đang hoạt động
        if xe_id == 0:
            sql = """
                SELECT 
                    x.bien_so_xe AS `Biển Số Xe`,
                    COALESCE(nv.ho_ten, 'Chưa gán') AS `Tài Xế`,
                    COALESCE(SUM(cd.so_km_thuc_te), 0) AS `Tổng KM Vận Hành`,
                    COALESCE(SUM(cd.so_lit_xang), 0) AS `Dầu Tiêu Thụ (Lít)`
                FROM xe x
                LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                LEFT JOIN chuyen_di cd ON x.id = cd.xe_id 
                    AND cd.trang_thai_chuyen = 'Hoan_Thanh' 
                    AND cd.ngay_chuyen_di BETWEEN %s AND %s
                WHERE x.trang_thai = 'Dang_Hoat_Dong'
                GROUP BY x.id, x.bien_so_xe, nv.ho_ten
                ORDER BY `Tổng KM Vận Hành` DESC
            """
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay))
        else:
            # Nếu chọn 1 xe cụ thể
            sql = """
                SELECT 
                    x.bien_so_xe AS `Biển Số Xe`,
                    COALESCE(nv.ho_ten, 'Chưa gán') AS `Tài Xế`,
                    COALESCE(SUM(cd.so_km_thuc_te), 0) AS `Tổng KM Vận Hành`,
                    COALESCE(SUM(cd.so_lit_xang), 0) AS `Dầu Tiêu Thụ (Lít)`
                FROM xe x
                LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                LEFT JOIN chuyen_di cd ON x.id = cd.xe_id 
                    AND cd.trang_thai_chuyen = 'Hoan_Thanh' 
                    AND cd.ngay_chuyen_di BETWEEN %s AND %s
                WHERE x.id = %s
                GROUP BY x.id, x.bien_so_xe, nv.ho_ten
            """
            df = pd.read_sql(sql, conn, params=(tu_ngay, den_ngay, xe_id))
        
        # Thêm cột Từ ngày, Đến ngày vào DataFrame
        if not df.empty:
            df['Từ Ngày'] = pd.to_datetime(tu_ngay).strftime('%d/%m/%Y')
            df['Đến Ngày'] = pd.to_datetime(den_ngay).strftime('%d/%m/%Y')
            
        return df
    except Exception as e:
        print(f"Lỗi lấy bảng kê tổng hợp: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals() and conn: conn.close()
###############


def save_do_xang_transaction(db_pool, data_dict, nguoi_dung):
    """
    Xử lý lưu lịch sử đổ xăng, tự động tính hiệu suất Lít/100km và cảnh báo hao hụt.
    Tuân thủ nguyên tắc Transaction và Audit Log của Bảo Tín Logistics.
    """
    conn = db_pool.get_connection()
    if not conn:
        return False, "❌ Lỗi kết nối cơ sở dữ liệu."

    try:
        # Bắt buộc: Tắt autocommit để bắt đầu Transaction
        conn.autocommit = False 
        cursor = conn.cursor(dictionary=True)

        xe_id = data_dict['xe_id']
        odo_moi = float(data_dict['odo_hien_tai'])
        so_lit = float(data_dict['so_lit'])
        # Xử lý chuỗi tiền tệ qua hàm chuẩn của hệ thống
        tong_tien = parse_money_input(data_dict['tong_tien']) 
        ghi_chu = data_dict.get('ghi_chu', '')
        don_gia = tong_tien / so_lit if so_lit > 0 else 0

        # 1. Truy vấn ODO cũ và Định mức của xe
        cursor.execute("SELECT tong_km_hien_tai, dinh_muc_nhien_lieu FROM xe WHERE id = %s", (xe_id,))
        xe_info = cursor.fetchone()
        if not xe_info:
            raise Exception("Không tìm thấy thông tin phương tiện.")

        odo_cu = float(xe_info['tong_km_hien_tai'] or 0.0)
        dinh_muc_chuan = float(xe_info['dinh_muc_nhien_lieu'] or 0.0)

        if odo_moi < odo_cu:
            raise Exception(f"Chỉ số ODO mới ({odo_moi}) không được nhỏ hơn ODO hiện tại của xe ({odo_cu}).")

        # 2. Tính toán Hiệu suất & Cảnh báo (Cho phép sai số vượt 10% so với định mức)
        quang_duong_da_chay = odo_moi - odo_cu
        hieu_suat_thuc_te = 0.0
        trang_thai_canh_bao = 'Binh_Thuong'

        if quang_duong_da_chay > 0:
            hieu_suat_thuc_te = (so_lit / quang_duong_da_chay) * 100
            
            if dinh_muc_chuan > 0 and hieu_suat_thuc_te > (dinh_muc_chuan * 1.1):
                trang_thai_canh_bao = 'Hao_Hut_Bat_Thuong'

        # 3. INSERT vào bảng lich_su_do_xang
        sql_insert_xang = """
            INSERT INTO lich_su_do_xang 
            (xe_id, odo_hien_tai, so_lit, tong_tien, don_gia, hieu_suat_tieu_hao, trang_thai_canh_bao, ghi_chu, nguoi_nhap)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_insert_xang, (
            xe_id, odo_moi, so_lit, tong_tien, don_gia, hieu_suat_thuc_te, trang_thai_canh_bao, ghi_chu, nguoi_dung
        ))
        
        # Kiểm tra rowcount theo nguyên tắc bắt buộc
        if cursor.rowcount == 0:
            raise Exception("Lỗi: Không thể ghi nhận lịch sử đổ xăng.")

        # 4. CẬP NHẬT ODO mới vào bảng `xe`
        cursor.execute("UPDATE xe SET tong_km_hien_tai = %s WHERE id = %s", (odo_moi, xe_id))
        if cursor.rowcount == 0:
            raise Exception("Lỗi: Không thể cập nhật chỉ số ODO cho xe.")

        # 5. Ghi vết hệ thống (Audit Log)
        chi_tiet_log = {
            "odo_cu": odo_cu,
            "odo_moi": odo_moi,
            "quang_duong_tinh": quang_duong_da_chay,
            "so_lit": so_lit,
            "hieu_suat": hieu_suat_thuc_te,
            "canh_bao": trang_thai_canh_bao
        }
        log_thao_tac(cursor, xe_id, nguoi_dung, "CAP_NHAT_NHIEN_LIEU", chi_tiet_log) 

        # Hoàn tất Giao dịch
        conn.commit() 
        return True, "✅ Lưu biên lai đổ xăng và cập nhật ODO thành công!"

    except Exception as e:
        conn.rollback() # Hoàn tác nếu có lỗi
        return False, f"❌ Lỗi hệ thống: {str(e)}"
        
    finally:
        if 'cursor' in locals(): cursor.close()
        conn.close()

###########################

def update_do_xang_transaction(db_pool, record_id, data_dict, nguoi_dung):
    """
    Hàm cập nhật lịch sử đổ xăng đã lưu. Tự động tính toán lại hiệu suất nhiên liệu.
    Tuân thủ nghiêm ngặt nguyên tắc Transaction và Audit Log[cite: 4].
    """
    conn = db_pool.get_connection()
    if not conn:
        return False, "❌ Lỗi kết nối cơ sở dữ liệu."

    try:
        # Bắt buộc: Tắt autocommit để quản lý Transaction[cite: 4]
        conn.autocommit = False 
        cursor = conn.cursor(dictionary=True)

        odo_moi = float(data_dict['odo_hien_tai'])
        so_lit = float(data_dict['so_lit'])
        # Xử lý chuỗi tiền tệ qua hàm chuẩn[cite: 4]
        tong_tien = parse_money_input(data_dict['tong_tien']) 
        ghi_chu = data_dict.get('ghi_chu', '')
        don_gia = tong_tien / so_lit if so_lit > 0 else 0

        # 1. Truy xuất bản ghi đang cần sửa để lấy xe_id
        cursor.execute("SELECT xe_id, odo_hien_tai FROM lich_su_do_xang WHERE id = %s", (record_id,))
        current_record = cursor.fetchone()
        if not current_record:
            raise Exception("Không tìm thấy dữ liệu đổ xăng này trong hệ thống.")
            
        xe_id = current_record['xe_id']

        # 2. Truy vấn ODO của lần đổ xăng NGAY TRƯỚC ĐÓ để tính quãng đường
        cursor.execute("SELECT dinh_muc_nhien_lieu FROM xe WHERE id = %s", (xe_id,))
        xe_info = cursor.fetchone()
        dinh_muc_chuan = float(xe_info['dinh_muc_nhien_lieu'] or 0.0)
        
        cursor.execute("""
            SELECT odo_hien_tai FROM lich_su_do_xang 
            WHERE xe_id = %s AND id < %s 
            ORDER BY id DESC LIMIT 1
        """, (xe_id, record_id))
        prev_record = cursor.fetchone()
        odo_cu = float(prev_record['odo_hien_tai']) if prev_record else 0.0

        # Chốt chặn logic
        if odo_moi < odo_cu and odo_cu > 0:
            raise Exception(f"ODO mới ({odo_moi}) không được nhỏ hơn ODO lần đổ trước ({odo_cu}).")

        # 3. Tính toán lại Hiệu suất & Cảnh báo
        quang_duong_da_chay = odo_moi - odo_cu if odo_cu > 0 else 0
        hieu_suat_thuc_te = 0.0
        trang_thai_canh_bao = 'Binh_Thuong'

        if quang_duong_da_chay > 0:
            hieu_suat_thuc_te = (so_lit / quang_duong_da_chay) * 100
            if dinh_muc_chuan > 0 and hieu_suat_thuc_te > (dinh_muc_chuan * 1.1):
                trang_thai_canh_bao = 'Hao_Hut_Bat_Thuong'

        # 4. Thực thi UPDATE vào cơ sở dữ liệu
        sql_update = """
            UPDATE lich_su_do_xang 
            SET odo_hien_tai=%s, so_lit=%s, tong_tien=%s, don_gia=%s, hieu_suat_tieu_hao=%s, trang_thai_canh_bao=%s, ghi_chu=%s
            WHERE id = %s
        """
        cursor.execute(sql_update, (odo_moi, so_lit, tong_tien, don_gia, hieu_suat_thuc_te, trang_thai_canh_bao, ghi_chu, record_id))
        
        # Bắt buộc kiểm tra rowcount theo nguyên tắc của dự án[cite: 4]
        if cursor.rowcount == 0:
            # Nếu người dùng bấm Lưu nhưng không thay đổi số liệu, rowcount sẽ = 0. 
            pass 

        # 5. CẬP NHẬT ODO cho xe NẾU đây là phiếu đổ xăng mới nhất của xe đó
        cursor.execute("SELECT MAX(id) as max_id FROM lich_su_do_xang WHERE xe_id = %s", (xe_id,))
        max_id_row = cursor.fetchone()
        if max_id_row and max_id_row['max_id'] == record_id:
            cursor.execute("UPDATE xe SET tong_km_hien_tai = %s WHERE id = %s", (odo_moi, xe_id))

        # 6. Ghi vết hệ thống (Audit Log)[cite: 4]
        chi_tiet_log = {
            "record_id": record_id,
            "odo_cu": odo_cu,
            "odo_moi": odo_moi,
            "so_lit_moi": so_lit,
            "tong_tien_moi": tong_tien
        }
        log_thao_tac(cursor, xe_id, nguoi_dung, "SUA_LICH_SU_XANG", chi_tiet_log) #[cite: 4]

        # Hoàn tất Giao dịch thành công[cite: 4]
        conn.commit() 
        return True, "✅ Đã cập nhật thành công dữ liệu xăng dầu!"

    except Exception as e:
        # Bắt buộc rollback nếu có lỗi xảy ra[cite: 4]
        conn.rollback() 
        return False, f"❌ Lỗi hệ thống: {str(e)}"
        
    finally:
        if 'cursor' in locals(): cursor.close()
        conn.close()