import io
import pandas as pd
import traceback,json
from datetime import datetime
from utils_core import parse_money_input
from audit_logger import ghi_log_he_thong



def save_to_khai_transaction(db_pool, tk_data, chi_tiet_phi_list, tk_id, current_user):

    """
    Lưu trữ Tờ khai Hải quan kèm theo danh sách chi tiết phí phát sinh (Luồng đỏ, sửa tờ khai, xin seal...).: phí khác 
    Đảm bảo tuân thủ Transaction, rowcount & Audit Log. Không bao gồm xử lý C/O (tách form riêng).
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False # Tuân thủ quy tắc Database Transaction
        cursor = conn.cursor()

        # Chuẩn hóa tiền tệ cơ bản của tờ khai
        phi_khac_val = parse_money_input(tk_data.get('phi_khac', 0))
        phi_dv_hq_val = parse_money_input(tk_data.get('phi_dich_vu_hq', 0))

        if tk_id:
            # --- CẬP NHẬT TỜ KHAI ---
            sql = """UPDATE to_khai_hai_quan 
                     SET so_to_khai=%s, so_van_don=%s, loai_to_khai=%s, ngay_khai=%s, khach_hang_id=%s, 
                         so_hoa_don_tm=%s, kho_cang_lay_hang=%s, ten_doi_tac=%s, ma_loai_hinh=%s, so_kien=%s, tong_trong_luong_hang=%s,
                         phan_luong=%s, phi_khac=%s, phi_dich_vu_hq=%s, ghi_chu=%s 
                     WHERE id=%s"""
            val = (
                tk_data['so_to_khai'], tk_data.get('so_van_don'), tk_data['loai_to_khai'], tk_data['ngay_khai'], 
                tk_data['khach_hang_id'], tk_data.get('so_hoa_don_tm'), 
                tk_data.get('kho_cang_lay_hang'), tk_data.get('ten_doi_tac'), tk_data.get('ma_loai_hinh'), 
                tk_data.get('so_kien'), tk_data.get('tong_trong_luong_hang', 0), tk_data['phan_luong'],
                phi_khac_val, phi_dv_hq_val, tk_data.get('ghi_chu'), tk_id
            )
            cursor.execute(sql, val)
            
            # Kiểm tra rowcount bắt buộc sau lệnh UPDATE
            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM to_khai_hai_quan WHERE id = %s", (tk_id,))
                if cursor.fetchone() is None:
                    raise Exception(f"Lỗi: Tờ khai mã {tk_id} không tồn tại trong hệ thống.")

            # Đối với chi tiết phí phát sinh khi cập nhật: Xóa cũ insert lại cho sạch hoặc xử lý đồng bộ
            cursor.execute("DELETE FROM chi_tiet_phi_hai_quan WHERE to_khai_id = %s", (tk_id,))
            action = "CAP_NHAT"
        else:
            # --- THÊM MỚI TỜ KHAI ---
            sql = """INSERT INTO to_khai_hai_quan 
                     (so_to_khai, so_van_don, loai_to_khai, ngay_khai, khach_hang_id,  
                      so_hoa_don_tm, kho_cang_lay_hang, ten_doi_tac, ma_loai_hinh, so_kien, tong_trong_luong_hang, 
                      phan_luong, phi_khac, phi_dich_vu_hq, ghi_chu) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            val = (
                tk_data['so_to_khai'], tk_data.get('so_van_don'), tk_data['loai_to_khai'], tk_data['ngay_khai'], 
                tk_data['khach_hang_id'], tk_data.get('so_hoa_don_tm'), 
                tk_data.get('kho_cang_lay_hang'), tk_data.get('ten_doi_tac'), tk_data.get('ma_loai_hinh'), 
                tk_data.get('so_kien'), tk_data.get('tong_trong_luong_hang', 0), tk_data['phan_luong'],
                phi_khac_val, phi_dv_hq_val, tk_data.get('ghi_chu')
            )
            cursor.execute(sql, val)
            tk_id = cursor.lastrowid
            action = "TAO_MOI"

        # --- XỬ LÝ LƯU DANH SÁCH CHI TIẾT PHÍ HẢI QUAN ĐỘNG (`chi_tiet_phi_list`) ---
        if chi_tiet_phi_list and len(chi_tiet_phi_list) > 0:
            sql_phi = """
                INSERT INTO chi_tiet_phi_hai_quan (to_khai_id, ten_loai_phi, so_tien, ghi_chu) 
                VALUES (%s, %s, %s, %s)
            """
            phi_tuples = []
            for phi in chi_tiet_phi_list:
                ten_phi = str(phi.get('ten_loai_phi', '')).strip()
                so_tien = parse_money_input(phi.get('so_tien', 0))
                ghi_chu_phi = str(phi.get('ghi_chu', '')).strip()
                
                if ten_phi and so_tien > 0:
                    phi_tuples.append((tk_id, ten_phi, so_tien, ghi_chu_phi if ghi_chu_phi else None))
            
            if phi_tuples:
                cursor.executemany(sql_phi, phi_tuples)
                # Kiểm tra rowcount cho executemany
                if cursor.rowcount != len(phi_tuples):
                    raise Exception("Lỗi: Không thể lưu toàn bộ danh sách chi tiết phụ phí hải quan.")

        # --- GHI AUDIT LOG HỆ THỐNG ---
        log_payload = {
            "tk_data": tk_data,
            "so_luong_chi_tiet_phi": len(chi_tiet_phi_list) if chi_tiet_phi_list else 0
        }
        chi_tiet_json = json.dumps(log_payload, ensure_ascii=False, default=str)
        ghi_log_he_thong(cursor, "QUAN_LY_HAI_QUAN", tk_id, current_user, action, chi_tiet_json)

        # Cam kết giao dịch thành công
        conn.commit()
        return True, tk_id

    except Exception as e:
        if conn: 
            conn.rollback() # Hoàn tác toàn bộ nếu có lỗi xảy ra
        traceback.print_exc()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
################################################
def delete_to_khai_transaction(db_pool, tk_id, current_user):
    """
    Xóa tờ khai an toàn, ghi Audit Log
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False 
        cursor = conn.cursor()
        
        cursor.execute("SELECT so_to_khai FROM to_khai_hai_quan WHERE id=%s", (tk_id,))
        row = cursor.fetchone()
        if not row:
            return False, "Không tìm thấy Tờ khai trong hệ thống."
            
        cursor.execute("DELETE FROM to_khai_hai_quan WHERE id=%s", (tk_id,))
        ghi_log_he_thong(cursor, "QUAN_LY_HAI_QUAN", tk_id, current_user, "XOA", json.dumps({"so_to_khai_bi_xoa": row[0]}))
        
        conn.commit()
        return True, "Thành công"
    except Exception as e:
        if conn: conn.rollback()
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
##########################################################
def save_bang_gia_hai_quan_transaction(db_pool, data_dict, current_user):
    """Lưu bảng giá cấu hình Hải Quan"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False
        cursor = conn.cursor()

        sql = """
            INSERT INTO bang_gia_hai_quan (khach_hang_id, nhom_dich_vu, phan_loai_chi_tiet, don_gia_hq,dia_diem_thong_quan, ghi_chu) 
            VALUES (%s, %s, %s, %s, %s,%s)
        """
        don_gia = parse_money_input(data_dict.get('don_gia_hq', '0'))
        values = (
            data_dict['khach_hang_id'], data_dict['nhom_dich_vu'], 
            data_dict['phan_loai_chi_tiet'], don_gia,data_dict.get('dia_diem_thong_quan', 'Cang_Bien'), data_dict.get('ghi_chu', '')
        )
        
        cursor.execute(sql, values)
        if cursor.rowcount == 0:
            raise Exception("Không thể lưu bảng giá hải quan.")
            
        new_id = cursor.lastrowid
        
        # Ghi log hệ thống
        ghi_log_he_thong(cursor, "CAU_HINH_BANG_GIA_HQ", new_id, current_user, "TAO_MOI", json.dumps(data_dict, ensure_ascii=False))
        
        conn.commit()
        return True, "Cấu hình giá Hải Quan thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
###################################################################
def update_bang_gia_hai_quan_transaction(db_pool, bg_id, data_dict, current_user):
    """Cập nhật bảng giá cấu hình Hải Quan"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction
        cursor = conn.cursor()

        sql = """
            UPDATE bang_gia_hai_quan 
            SET khach_hang_id = %s, nhom_dich_vu = %s, phan_loai_chi_tiet = %s, 
                dia_diem_thong_quan = %s, don_gia_hq = %s, ghi_chu = %s
            WHERE id = %s
        """
        don_gia = parse_money_input(data_dict.get('don_gia_hq', '0'))
        
        values = (
            data_dict['khach_hang_id'], 
            data_dict['nhom_dich_vu'], 
            data_dict['phan_loai_chi_tiet'],
            data_dict.get('dia_diem_thong_quan', 'Cang_Bien'),
            don_gia, 
            data_dict.get('ghi_chu', ''), 
            bg_id
        )
        
        cursor.execute(sql, values)
        
        # Kiểm tra rowcount sau lệnh UPDATE
        if cursor.rowcount == 0:
            cursor.execute("SELECT id FROM bang_gia_hai_quan WHERE id = %s", (bg_id,))
            if cursor.fetchone() is None:
                raise Exception("Không tìm thấy bản ghi cấu hình bảng giá này.")
            
        # Ghi log hệ thống
        ghi_log_he_thong(cursor, "CAU_HINH_BANG_GIA_HQ", bg_id, current_user, "CAP_NHAT", json.dumps(data_dict, ensure_ascii=False))
        
        conn.commit()
        return True, "Cập nhật Cấu hình giá Hải Quan thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
###################################################
def delete_bang_gia_hai_quan_transaction(db_pool, bg_id, current_user):
    """Xóa an toàn bảng giá cấu hình Hải Quan"""
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        conn.autocommit = False  # Bắt buộc Transaction
        cursor = conn.cursor()

        # Thực thi xóa
        cursor.execute("DELETE FROM bang_gia_hai_quan WHERE id = %s", (bg_id,))
        
        # Kiểm tra rowcount sau lệnh DELETE
        if cursor.rowcount == 0:
            raise Exception("Không thể xóa. Bản ghi không tồn tại hoặc đã bị xóa trước đó.")
            
        # Ghi log hệ thống
        ghi_log_he_thong(cursor, "CAU_HINH_BANG_GIA_HQ", bg_id, current_user, "XOA", json.dumps({"bang_gia_id": bg_id}, ensure_ascii=False))
        
        conn.commit()
        return True, "Xóa Cấu hình giá Hải Quan thành công!"
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return False, f"Lỗi hệ thống: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
################################################


def xuat_excel_hai_quan_bao_tin(db, tu_ngay, den_ngay, khach_hang_id=None):
    # 1. Truy vấn chi tiết tờ khai (Chỉ lấy khách hàng ICHIHIRO,ZEHENXING)
    sql_tk = """
        SELECT 
            tk.id AS tk_id,
            tk.so_to_khai, 
            tk.loai_to_khai,
            tk.ngay_khai,
            tk.so_hoa_don_tm,
            tk.ma_loai_hinh,
            tk.so_kien,
            COALESCE(tk.tong_trong_luong_hang, cd.khoi_luong_kg, 0) AS tong_trong_luong,
            tk.phan_luong,
            COALESCE(tk.phi_khac, 0) AS phi_khac,
            kh.ten_khach_hang, 
            cd.dia_diem_giao_nhan, 
            COALESCE(cd.doanh_thu, 0) AS phi_van_chuyen,
            c.loai_cont,
            c.so_cont,
            cd.is_thue_ngoai,
            cd.bien_so_xe_ngoai,
            xe.bien_so_xe AS bien_so_noi_bo,
            xe.loai_xe AS loai_xe_noi_bo,
            xe.tai_trong_thiet_ke,
            COALESCE(c.phi_nang_ha_on, 0) AS phi_nang_ha_on,
            c.so_hoa_don_lift_on,
            COALESCE(c.phi_nang_ha_off, 0) AS phi_nang_ha_off,
            c.so_hoa_don_lift_off,
            (IFNULL(c.phi_to_khai, 0) + IFNULL(tk.phi_dich_vu_hq, 0)) AS phi_to_khai
        FROM to_khai_hai_quan tk
        JOIN khach_hang kh ON tk.khach_hang_id = kh.id
        LEFT JOIN chuyen_di cd ON tk.chuyen_di_id = cd.id
        LEFT JOIN xe ON cd.xe_id = xe.id
        LEFT JOIN container_quan_ly c ON tk.id = c.to_khai_id
        WHERE tk.ngay_khai BETWEEN %s AND %s 
          AND (
              UPPER(kh.ten_khach_hang) LIKE '%ICHIHIRO%' 
              OR UPPER(kh.ten_khach_hang) LIKE '%ZHENGXING%'
          )
    """
    
    # Truyền từ khóa ICHIHIRO vào Params
    params = [tu_ngay, den_ngay]
    if khach_hang_id:
        sql_tk += " AND tk.khach_hang_id = %s"
        params.append(khach_hang_id)
    sql_tk += " ORDER BY tk.ngay_khai ASC, tk.id ASC, c.id ASC"
    
    df_raw = db.execute_query(sql_tk, tuple(params))
    if not isinstance(df_raw, pd.DataFrame) or df_raw.empty:
        return None

    # Làm sạch các cột số liệu
    numeric_cols_tk = ['phi_to_khai', 'phi_nang_ha_on', 'phi_nang_ha_off', 'tong_trong_luong', 'phi_van_chuyen', 'phi_khac']
    for col in numeric_cols_tk:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0)

    # 2. Truy vấn dữ liệu bảng C/O (Cũng chỉ lấy ICHIHIRO,ZHENGXING)
    sql_co = """
        SELECT 
            co.*, 
            tk.so_to_khai, 
            kh.ten_khach_hang
        FROM to_khai_co co
        JOIN to_khai_hai_quan tk ON co.to_khai_id = tk.id
        JOIN khach_hang kh ON tk.khach_hang_id = kh.id
        WHERE co.ngay_co BETWEEN %s AND %s
          AND (
              UPPER(kh.ten_khach_hang) LIKE '%ICHIHIRO%' 
              OR UPPER(kh.ten_khach_hang) LIKE '%ZHENGXING%'
          )
    """
   # params_co = [tu_ngay, den_ngay, '%ICHIHIRO%']
    params_co = [tu_ngay, den_ngay]
    if khach_hang_id:
        sql_co += " AND tk.khach_hang_id = %s"
        params_co.append(khach_hang_id)
    sql_co += " ORDER BY co.ngay_co ASC"
    
    df_co_raw = db.execute_query(sql_co, tuple(params_co))
    if isinstance(df_co_raw, pd.DataFrame) and not df_co_raw.empty:
        for col_co in ['phi_co', 'phi_dvhq']:
            if col_co in df_co_raw.columns:
                df_co_raw[col_co] = pd.to_numeric(df_co_raw[col_co], errors='coerce').fillna(0)

    # Phân tích biến thời gian
    dt_tu_ngay = datetime.strptime(tu_ngay, '%Y-%m-%d')
    mm = dt_tu_ngay.strftime('%m')
    yyyy = dt_tu_ngay.strftime('%Y')
    mmm_eng = dt_tu_ngay.strftime('%b').upper()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
        workbook = writer.book
        
        # ĐỊNH DẠNG XlsxWriter
        fmt_company = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'text_wrap': True, 'valign': 'top', 'align': 'center'})
        fmt_title = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        fmt_subtitle = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter'})
        fmt_header = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        fmt_center = workbook.add_format({'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_money = workbook.add_format({'font_name': 'Times New Roman', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'border': 1})
        
        header_company_text = "CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN\nBAO TIN TRANSPORTATION CO., LTD\n TRỤ SỞ: Số 4, Đường Gia Tân 1, Khu phố Gia Tân, Phường Gia Lộc, Thị xã Trảng Bàng, Tỉnh Tây Ninh \n Address: 4th Gia Tan 1 Road, Gia Loc Commune, Trang Bang District, Tay Ninh Province, Vietnam.\n CN VP : Số 888, Quốc Lộ 22 , Khu phố Suối Sâu, Phường An Tịnh, Thị Xã Trảng Bàng, Tỉnh Tây Ninh \nRepresentative office: Highway 22, Suoi Sau, An Tinh Ward, Trang Bang Town, Tay Ninh Province, Vietnam\n Tel: 0888 039 888 | Tax code: 3901229506| Email: bao@truckingbaotin.com & baoxnk@gmail.com"

        # =========================================================
        # 1. SHEET HÀNG NHẬP KHẨU / XUẤT KHẨU
        # =========================================================
        for loai in ['Nhap_Khau', 'Xuat_Khau']:
            df_loai = df_raw[df_raw['loai_to_khai'] == loai]
            if df_loai.empty: continue
            
            prefix_vn = 'NHẬP' if loai == 'Nhap_Khau' else 'XUẤT'
            prefix_en = 'IMPORT' if loai == 'Nhap_Khau' else 'EXPORT'
            prefix_code = 'NK' if loai == 'Nhap_Khau' else 'EX'
            sheet_name = f"HÀNG {prefix_vn} KHẨU {mm}.{yyyy}"
            
            ws = workbook.add_worksheet(sheet_name)
            ws.set_row(0, 120)
            ws.merge_range('A1:T1', header_company_text, fmt_company)
            ws.merge_range('A2:T2', f"BẢNG ĐỐI CHIẾU CÔNG NỢ HÀNG {prefix_vn} KHẨU THÁNG {mm}.{yyyy}\n(DEBIT NOTE {prefix_en} FEE {mmm_eng}.{yyyy})", fmt_title)
            ws.merge_range('A3:T3', f"SỐ: {mm}{prefix_code} Kèm Hóa đơn số :     Ngày    tháng  {mm}   năm {yyyy}\n", fmt_subtitle)
            
            ws.set_row(3, 40)
            ws.set_row(4, 25)
            
            ws.merge_range('A4:A5', 'STT\nNO.\n\n', fmt_header)
            ws.merge_range('B4:B5', '\n TỜ KHAI HQ\nCustoms declaration form\n', fmt_header)
            ws.merge_range('C4:C5', 'NGÀY TK\nCustoms declaration Date', fmt_header)
            ws.merge_range('D4:D5', 'SỐ HÓA ĐƠN TM\nInvoice No.\n', fmt_header)
            ws.merge_range('E4:E5', '\nKHO/CẢNG LẤY HÀNG\nWarehouse\n', fmt_header)
            ws.merge_range('F4:F5', 'MÃ LOẠI HÌNH \nCode of declaration type', fmt_header)
            ws.merge_range('G4:G5', 'SỐ KIỆN\nQuantity of packages', fmt_header)
            ws.merge_range('H4:H5', 'TỔNG TRỌNG LƯỢNG HÀNG\nGross Weight\n', fmt_header)
            ws.merge_range('I4:I5', 'LOẠI CONT/XE\nTruck/Cont\nSize\n', fmt_header)
            ws.merge_range('J4:J5', 'SỐ CONT/XE\nTruck/Cont\nNo.\n', fmt_header)
            
            ws.merge_range('K4:N4', 'PHÍ NÂNG HẠ\nLift on - Lift off\n', fmt_header)
            ws.write(4, 10, 'Lift on', fmt_header)
            ws.write(4, 11, 'Inv No.', fmt_header)
            ws.write(4, 12, 'Lift off', fmt_header)
            ws.write(4, 13, 'Inv No.', fmt_header)
            
            ws.merge_range('O4:P4', 'PHÍ CSHT\nInfrastructure expenditure\n', fmt_header)
            ws.write(4, 14, 'Fees', fmt_header)
            ws.write(4, 15, 'Inv No.', fmt_header)
            
            ws.merge_range('Q4:Q5', 'PHÍ VẬN CHUYỂN\nTrucking Fee\n ', fmt_header)
            ws.merge_range('R4:R5', 'PHÍ DVHQ\nCustoms declaration fee', fmt_header)
            ws.merge_range('S4:S5', 'PHÍ PHÁT SINH\nFees incurred', fmt_header)
            ws.merge_range('T4:T5', 'PHÂN LUỒNG\nSelectivity of customs declaration form', fmt_header)
            
            row = 5
            stt = 1
            grouped = df_loai.groupby('tk_id', sort=False)
            
            for tk_id, group in grouped:
                num_rows = len(group)
                start_row = row
                end_row = row + num_rows - 1
                
                for i, (_, r) in enumerate(group.iterrows()):
                    current_row = row + i
                    
                    if i == 0:
                        if num_rows > 1:
                            ws.merge_range(start_row, 0, end_row, 0, stt, fmt_center)
                        else:
                            ws.write(current_row, 0, stt, fmt_center)
                    
                    # --- XỬ LÝ CHỐNG LỖI HIỂN THỊ CHỮ "nan" ---
                    val_so_cont = r.get('so_cont')
                    cont_so = str(val_so_cont).strip() if pd.notna(val_so_cont) else ""
                    
                    val_loai_cont = r.get('loai_cont')
                    cont_loai = str(val_loai_cont).strip() if pd.notna(val_loai_cont) else ""
                    
                    val_is_thue = r.get('is_thue_ngoai')
                    is_thue_ngoai = int(val_is_thue) if pd.notna(val_is_thue) else 0
                    
                    if not cont_so and not cont_loai:
                        if is_thue_ngoai == 1:
                            val_bs_ngoai = r.get('bien_so_xe_ngoai')
                            hien_thi_so = str(val_bs_ngoai).strip() if pd.notna(val_bs_ngoai) else ""
                            hien_thi_loai = "Xe Thuê Ngoài"
                        else:
                            val_bs_noibo = r.get('bien_so_noi_bo')
                            hien_thi_so = str(val_bs_noibo).strip() if pd.notna(val_bs_noibo) else ""
                            
                            val_loai_xe = r.get('loai_xe_noi_bo')
                            loai_xe_db = str(val_loai_xe).strip() if pd.notna(val_loai_xe) else ""
                            
                            tai_trong = r.get('tai_trong_thiet_ke')
                            if loai_xe_db and loai_xe_db.lower() != 'nan':
                                hien_thi_loai = loai_xe_db
                            elif pd.notna(tai_trong) and float(tai_trong) > 0:
                                hien_thi_loai = f"{float(tai_trong):.1f} Tấn".replace('.0', '')
                            else:
                                hien_thi_loai = "Xe tải"
                    else:
                        hien_thi_loai = cont_loai
                        hien_thi_so = cont_so

                    # Các cột từ B đến I (index 1 đến 8)
                    vals = [
                        str(r.get('so_to_khai') or ''),
                        pd.to_datetime(r['ngay_khai']).strftime('%d/%m/%Y') if pd.notna(r.get('ngay_khai')) else '',
                        str(r.get('so_hoa_don_tm') or ''),
                        str(r.get('dia_diem_giao_nhan') or ''),
                        str(r.get('ma_loai_hinh') or ''),
                        str(r.get('so_kien') or ''),
                        float(r.get('tong_trong_luong') or 0),
                        hien_thi_loai  # Cột I: LOẠI CONT/XE
                    ]
                    
                    for c_idx, val in enumerate(vals, start=1):
                        if i == 0:
                            if num_rows > 1:
                                fmt_cell = fmt_money if c_idx == 7 else fmt_center
                                ws.merge_range(start_row, c_idx, end_row, c_idx, val, fmt_cell)
                            else:
                                fmt_cell = fmt_money if c_idx == 7 else fmt_center
                                ws.write(current_row, c_idx, val, fmt_cell)
                    
                    # Cột J (index 9): SỐ CONT/XE 
                    ws.write(current_row, 9, hien_thi_so, fmt_center)
                    
                    # Các cột chi phí nâng hạ, cước vận chuyển, DVHQ
                    ws.write(current_row, 10, float(r.get('phi_nang_ha_on') or 0), fmt_money)
                    ws.write(current_row, 11, str(r.get('so_hoa_don_lift_on') or ''), fmt_center)
                    ws.write(current_row, 12, float(r.get('phi_nang_ha_off') or 0), fmt_money)
                    ws.write(current_row, 13, str(r.get('so_hoa_don_lift_off') or ''), fmt_money)
                    ws.write(current_row, 14, 0.0, fmt_money) # Phí CSHT
                    ws.write(current_row, 15, "", fmt_center) # Inv No CSHT
                    ws.write(current_row, 16, float(r.get('phi_van_chuyen') or 0), fmt_money)
                    
                    # Phí DVHQ đã được gộp cả Container và Xe Tải
                    phi_to_khai_val = float(r.get('phi_to_khai') or 0) / num_rows if num_rows > 0 else 0.0
                    ws.write(current_row, 17, phi_to_khai_val, fmt_money)
                    
                    # Phí phát sinh (phi_khac)
                    phi_khac_val = float(r.get('phi_khac') or 0) / num_rows if num_rows > 0 else 0.0
                    ws.write(current_row, 18, phi_khac_val, fmt_money)
                    
                    # Phân luồng
                    val_phan_luong = str(r.get('phan_luong') or '')
                    if i == 0:
                        if num_rows > 1:
                            ws.merge_range(start_row, 19, end_row, 19, val_phan_luong, fmt_center)
                        else:
                            ws.write(current_row, 19, val_phan_luong, fmt_center)
                
                row += num_rows
                stt += 1
                
            ws.set_column('A:A', 6); ws.set_column('B:E', 18); ws.set_column('F:J', 14); ws.set_column('K:T', 15)

        # =========================================================
        # 2. SHEET NHẬP NỘI ĐỊA
        # =========================================================
        df_nd = df_raw[df_raw['loai_to_khai'] == 'Noi_Dia']
        if not df_nd.empty:
            ws_nd = workbook.add_worksheet(f'NHẬP NỘI ĐỊA {mm}.{yyyy}')
            ws_nd.set_row(0, 120)
            ws_nd.merge_range('A1:L1', header_company_text, fmt_company)
            ws_nd.merge_range('A2:L2', f"BẢNG ĐỐI CHIẾU CÔNG NỢ HÀNG NHẬP NỘI ĐỊA THÁNG {mm}.{yyyy}\n(DEBIT NOTE DOMESTIC FEE {mmm_eng}.{yyyy})", fmt_title)
            ws_nd.merge_range('A3:L3', f"SỐ: {mm}NNĐ Kèm Hóa đơn số :   Ngày     tháng  {mm} năm {yyyy}", fmt_subtitle)
            
            headers_nd = [
                "STT\n\n", "\n TỜ KHAI HQ\nCustoms declaration form\n", "NGÀY TK\nCustoms declaration Date", 
                "SỐ HÓA ĐƠN TM\nInvoice No.\n", "TÊN ĐỐI TÁC\n", "MÃ\n LOẠI HÌNH", "Số lượng kiện", 
                "Tổng trọng lượng hàng\nGross Weight\n", "PHÍ DVHQ\nCustoms declaration fee", "PHÍ PHÁT SINH\n\n", 
                "TOTAL", "NOTE"
            ]
            ws_nd.set_row(3, 40)
            for c, data in enumerate(headers_nd): 
                ws_nd.write(3, c, data, fmt_header)
            
            row = 4
            for idx, r in df_nd.reset_index().iterrows():
                ws_nd.write(row, 0, idx + 1, fmt_center)
                ws_nd.write(row, 1, str(r.get('so_to_khai') or ''), fmt_center)
                ws_nd.write(row, 2, pd.to_datetime(r['ngay_khai']).strftime('%d/%m/%Y') if pd.notna(r.get('ngay_khai')) else '', fmt_center)
                ws_nd.write(row, 3, str(r.get('so_hoa_don_tm') or ''), fmt_center)
                
                ten_dt = r.get('ten_doi_tac')
                if not ten_dt: ten_dt = r.get('ten_khach_hang', '')
                
                ws_nd.write(row, 4, str(ten_dt), fmt_center)
                ws_nd.write(row, 5, str(r.get('ma_loai_hinh') or ''), fmt_center)
                ws_nd.write(row, 6, str(r.get('so_kien') or ''), fmt_center)
                ws_nd.write(row, 7, float(r.get('tong_trong_luong') or 0), fmt_money)
                ws_nd.write(row, 8, float(r.get('phi_to_khai') or 0), fmt_money)
                ws_nd.write(row, 9, float(r.get('phi_khac') or 0), fmt_money)
                
                total_fee = float(r.get('phi_to_khai') or 0) + float(r.get('phi_khac') or 0)
                ws_nd.write(row, 10, total_fee, fmt_money)
                ws_nd.write(row, 11, str(r.get('phan_luong') or ''), fmt_center)
                row += 1
                
            ws_nd.set_column('A:A', 6); ws_nd.set_column('B:E', 22); ws_nd.set_column('F:L', 16)

        # =========================================================
        # 3. SHEET BẢNG C.O
        # =========================================================
        if isinstance(df_co_raw, pd.DataFrame) and not df_co_raw.empty:
            ws_co = workbook.add_worksheet(f'BẢNG C.O {mm}.{yyyy}')
            ws_co.set_row(0, 120)
            ws_co.merge_range('A1:I1', header_company_text, fmt_company)
            ws_co.merge_range('A2:I2', f"BẢNG ĐỐI CHIẾU CÔNG NỢ C/O THÁNG {mm}.{yyyy}\n(DEBIT NOTE C/O {mmm_eng}.{yyyy})", fmt_title)
            ws_co.merge_range('A3:I3', f"SỐ: {mm}CO Kèm Hóa đơn số :     Ngày     tháng {mm} năm {yyyy}", fmt_subtitle)
            
            ws_co.set_row(3, 40)
            ws_co.set_row(4, 20)
            
            ws_co.merge_range('A4:A5', "STT\nNo.\n", fmt_header)
            ws_co.merge_range('B4:B5', "FORM C/O\nC/O form", fmt_header)
            ws_co.merge_range('C4:C5', "SỐ C/O\nC/O No.", fmt_header)
            ws_co.merge_range('D4:D5', "NGÀY C/O\nC/O Date", fmt_header)
            ws_co.merge_range('E4:E5', "\n TỜ KHAI HQ\nCustoms declaration form\n", fmt_header)
            
            ws_co.merge_range('F4:G4', "LỆ PHÍ C/O\nC/O fee", fmt_header)
            ws_co.write(4, 5, 'Inv No.', fmt_header)
            ws_co.write(4, 6, 'Fees', fmt_header)
            
            ws_co.merge_range('H4:H5', "PHÍ DVHQ\nCustoms fees", fmt_header)
            ws_co.merge_range('I4:I5', "NOTE", fmt_header)
            
            row = 5
            for idx, r in df_co_raw.reset_index().iterrows():
                ws_co.write(row, 0, idx + 1, fmt_center)
                ws_co.write(row, 1, str(r.get('form_co') or ''), fmt_center)
                ws_co.write(row, 2, str(r.get('so_co') or ''), fmt_center)
                ws_co.write(row, 3, pd.to_datetime(r['ngay_co']).strftime('%d/%m/%Y') if pd.notna(r.get('ngay_co')) else "", fmt_center)
                ws_co.write(row, 4, str(r.get('so_to_khai') or ''), fmt_center)
                ws_co.write(row, 5, str(r.get('so_hoa_don_co') or ''), fmt_center)
                ws_co.write(row, 6, float(r.get('phi_co') or 0), fmt_money)
                ws_co.write(row, 7, float(r.get('phi_dvhq') or 0), fmt_money)
                ws_co.write(row, 8, str(r.get('ghi_chu') or ''), fmt_center)
                row += 1
                
            ws_co.set_column('A:A', 6); ws_co.set_column('B:I', 18)

    output.seek(0)
    return output.getvalue()
#######################################
def xuat_excel_hai_quan_continental(db, tu_ngay, den_ngay, khach_hang_id=None):
    """
    Xuất File Excel chuẩn Form CONTINENTAL:
    - 1 Sheet BẢNG TỔNG (Kèm Summary & Merge Header)
    - N Sheet riêng lẻ chia tách theo từng Số Vận Đơn (HBL) / Tờ Khai (Kèm Summary & Công thức Footer)
    - Merge Cell các phí gộp chung theo chuẩn file mẫu.
    """
    # 1. Truy vấn toàn bộ dữ liệu
    sql_tk = """
        SELECT 
            tk.id AS tk_id, tk.so_to_khai, tk.so_van_don, tk.loai_to_khai, tk.ngay_khai,
            tk.so_hoa_don_tm, tk.ma_loai_hinh, tk.so_kien, tk.phan_luong,
            COALESCE(tk.tong_trong_luong_hang, cd.khoi_luong_kg, 0) AS tong_trong_luong,
            COALESCE(tk.phi_khac, 0) AS phi_khac,
            kh.ten_khach_hang, cd.dia_diem_giao_nhan, 
            c.loai_cont, c.so_cont,
            COALESCE(c.phi_van_chuyen, 0) AS phi_van_chuyen,
            COALESCE(cd.doanh_thu, 0) AS doanh_thu_chuyen,
            COALESCE(c.phi_to_khai, 0) AS phi_to_khai,
            COALESCE(c.phi_nang_ha_on, 0) AS phi_nang_ha_on, c.so_hoa_don_lift_on,
            COALESCE(c.phi_nang_ha_off, 0) AS phi_nang_ha_off, c.so_hoa_don_lift_off,
            COALESCE(c.phi_bot, 0) AS phi_bot, COALESCE(c.phi_lay_mau, 0) AS phi_lay_mau,
            COALESCE(c.phi_kiem_dich, 0) AS phi_kiem_dich, c.so_hoa_don_kiem_dich,
            COALESCE(c.phi_luu_bai, 0) AS phi_luu_bai, c.so_hoa_don_luu_bai,
            COALESCE(c.phi_do, 0) AS phi_do, c.so_hoa_don_do,
            COALESCE(c.phi_handling, 0) AS phi_handling, c.so_hoa_don_handling,
            COALESCE(c.phi_khu_trung, 0) AS phi_khu_trung, c.so_hoa_don_khu_trung
        FROM to_khai_hai_quan tk
        JOIN khach_hang kh ON tk.khach_hang_id = kh.id
        LEFT JOIN chuyen_di cd ON tk.chuyen_di_id = cd.id
        LEFT JOIN container_quan_ly c ON tk.id = c.to_khai_id
        WHERE tk.ngay_khai BETWEEN %s AND %s 
        AND UPPER(kh.ten_khach_hang) LIKE %s
    """
    params = [tu_ngay, den_ngay,'%CONTINENTAL%']
    if khach_hang_id:
        sql_tk += " AND tk.khach_hang_id = %s"
        params.append(khach_hang_id)
        
    sql_tk += " ORDER BY tk.ngay_khai ASC, tk.id ASC, c.id ASC"
    
    df_raw = db.execute_query(sql_tk, tuple(params))
    if not isinstance(df_raw, pd.DataFrame) or df_raw.empty:
        return None

    # Làm sạch dữ liệu số
    numeric_cols = ['phi_van_chuyen', 'doanh_thu_chuyen', 'phi_to_khai', 'phi_nang_ha_on', 'phi_nang_ha_off', 'phi_bot', 'phi_lay_mau', 'phi_kiem_dich', 'phi_luu_bai', 'phi_do', 'phi_handling', 'phi_khu_trung', 'phi_khac', 'tong_trong_luong']
    for col in numeric_cols:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors='coerce').fillna(0)

    # Đảm bảo group bằng HBL không bị lỗi NaN
    df_raw['so_van_don'] = df_raw['so_van_don'].replace('', pd.NA).fillna(df_raw['so_to_khai']).fillna('CHUA_CO_SO')

    dt_tu_ngay = datetime.strptime(tu_ngay, '%Y-%m-%d')
    mm = dt_tu_ngay.strftime('%m')
    yyyy = dt_tu_ngay.strftime('%Y')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
        workbook = writer.book
        
        # Định dạng chuẩn CONTINENTAL
        fmt_company = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 10, 'text_wrap': True, 'valign': 'top', 'align': 'center'})
        fmt_title = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        fmt_header = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
        fmt_center = workbook.add_format({'font_name': 'Times New Roman', 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_money = workbook.add_format({'font_name': 'Times New Roman', 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'border': 1})
        
        # Format cho phần Footer Summary
        fmt_center_bold = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_money_bold = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter', 'border': 1})
        fmt_bold_left = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'align': 'left', 'valign': 'vcenter'})
        fmt_bold_left_wrap = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        fmt_money_bold_no_border = workbook.add_format({'font_name': 'Times New Roman', 'bold': True, 'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter'})
        
        header_company_text = "CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN\n宝信运输贸易责任有限公司\nTRỤ SỞ: Số 4, Đường Gia Tân 1, Khu phố Gia Tân, Phường Gia Lộc, Thị xã Trảng Bàng, Tỉnh Tây Ninh. \n 地址： 西宁省，展鹏县，嘉绿社，嘉新丘，嘉新一路，四号\n CN VP : Số 888, Quốc Lộ 22 , Khu phố Suối Sâu, Phường An Tịnh, Thị Xã Trảng Bàng, Tỉnh Tây Ninh. \n 分办公司： 西宁省，展鹏县，安静社，深泉丘，22号公路，888号。\n Mã số thuế/ 税号: 3901229506         Telephone: 0888039888/ 0988039888/ 0918694143                  Email: baoxnk@gmail.com"

        # ==========================================
        # 1. SHEET BẢNG TỔNG
        # ==========================================
        ws_tong = workbook.add_worksheet('BANG TONG')
        ws_tong.set_row(0, 50); ws_tong.set_row(1, 70)
        ws_tong.merge_range('A1:L1', header_company_text, fmt_company)
        ws_tong.merge_range('A3:L3', f"BẢNG ĐỐI CHIẾU CÔNG NỢ THÁNG {mm}/{yyyy}", fmt_title)
        ws_tong.merge_range('A5:L5', "DEBIT NOTE FOR CÔNG TY TNHH DỆT SỢI CONTINENTAL", fmt_title)

        ws_tong.set_row(6, 25); ws_tong.set_row(7, 25)
        
        # Ghi Header cột A->I (Trộn 2 dòng)
        headers_tong = ["STT", "SỐ TỜ KHAI", "NGÀY TỜ KHAI", "HBL", "INVOICE NO", "QTY", "PHÍ VẬN CHUYỂN", "PHÍ DỊCH VỤ", "PHÍ CHI HỘ"]
        for col_idx, h in enumerate(headers_tong):
            ws_tong.merge_range(6, col_idx, 7, col_idx, h, fmt_header)
            
        # Ghi Header cột J->L (INVOICE nằm trên, VNĐ/VAT/DATE nằm dưới)
        ws_tong.merge_range(6, 9, 6, 11, "INVOICES", fmt_header)
        ws_tong.write(7, 9, "VNĐ", fmt_header)
        ws_tong.write(7, 10, "VAT INVOICE NO", fmt_header)
        ws_tong.write(7, 11, "DATE INVOICE", fmt_header)
            
        row_tong = 8
        stt_tong = 1
        
        # Các biến cộng dồn Footer Bảng Tổng
        total_vc_tong = 0; total_dv_tong = 0; total_chiho_tong = 0; total_tong_tong = 0
        
        grouped_tk = df_raw.groupby('tk_id', sort=False)
        for tk_id, group in grouped_tk:
            r = group.iloc[0]
            num_cont = len(group) if pd.notna(r.get('so_cont')) and str(r.get('so_cont')).strip() != '' else 0
            
            # Tính QTY tự động
            qty_str = ""
            if num_cont > 0:
                loai_counts = group['loai_cont'].value_counts()
                qty_parts = [f"{count}x{str(loai).replace('DC', '').replace('HC', '').replace('RF', '')}" for loai, count in loai_counts.items() if str(loai).strip()]
                qty_str = " + ".join(qty_parts)
            else:
                qty_str = str(r.get('tong_trong_luong') or '')
                
            # Tính toán chi phí
            sum_phi_vc = group['phi_van_chuyen'].sum()
            phi_vc = sum_phi_vc if sum_phi_vc > 0 else float(r.get('doanh_thu_chuyen') or 0)
            phi_dv = group['phi_to_khai'].sum()
            sum_chi_ho_cont = group[['phi_nang_ha_on', 'phi_nang_ha_off', 'phi_bot', 'phi_lay_mau', 'phi_kiem_dich', 'phi_luu_bai', 'phi_do', 'phi_handling', 'phi_khu_trung']].sum().sum()
            phi_chi_ho = sum_chi_ho_cont + float(r.get('phi_khac') or 0)
            tong_invoice = phi_vc + phi_dv + phi_chi_ho
            
            # Cộng dồn cho bảng Tổng
            total_vc_tong += phi_vc
            total_dv_tong += phi_dv
            total_chiho_tong += phi_chi_ho
            total_tong_tong += tong_invoice
            
            ws_tong.write(row_tong, 0, stt_tong, fmt_center)
            ws_tong.write(row_tong, 1, str(r.get('so_to_khai') or ''), fmt_center)
            ws_tong.write(row_tong, 2, pd.to_datetime(r['ngay_khai']).strftime('%d/%m/%Y') if pd.notna(r.get('ngay_khai')) else '', fmt_center)
            ws_tong.write(row_tong, 3, str(r.get('so_van_don') or ''), fmt_center)
            ws_tong.write(row_tong, 4, str(r.get('so_hoa_don_tm') or ''), fmt_center)
            ws_tong.write(row_tong, 5, qty_str, fmt_center)
            ws_tong.write(row_tong, 6, phi_vc, fmt_money)
            ws_tong.write(row_tong, 7, phi_dv, fmt_money)
            ws_tong.write(row_tong, 8, phi_chi_ho, fmt_money)
            ws_tong.write(row_tong, 9, tong_invoice, fmt_money)
            ws_tong.write(row_tong, 10, "", fmt_center) 
            ws_tong.write(row_tong, 11, "", fmt_center) 
            
            row_tong += 1; stt_tong += 1
            
        # ==========================================
        # BỔ SUNG: Dòng GRAND TOTAL cho Bảng Tổng
        # ==========================================
        ws_tong.merge_range(row_tong, 0, row_tong, 5, "GRAND TOTAL", fmt_center_bold)
        for c_idx in range(6, 12):
            if c_idx == 6: ws_tong.write(row_tong, c_idx, total_vc_tong, fmt_money_bold)
            elif c_idx == 7: ws_tong.write(row_tong, c_idx, total_dv_tong, fmt_money_bold)
            elif c_idx == 8: ws_tong.write(row_tong, c_idx, total_chiho_tong, fmt_money_bold)
            elif c_idx == 9: ws_tong.write(row_tong, c_idx, total_tong_tong, fmt_money_bold)
            else: ws_tong.write(row_tong, c_idx, "", fmt_center_bold)
            
        ws_tong.set_column('A:A', 6); ws_tong.set_column('B:E', 18); ws_tong.set_column('F:L', 15)
        
        # ==========================================
        # 2. SHEET CHI TIẾT TỪNG VẬN ĐƠN (HBL)
        # ==========================================
        grouped_hbl = df_raw.groupby('so_van_don', dropna=False, sort=False)
        sheet_idx = 1
        
        for hbl, group_hbl in grouped_hbl:
            hbl_name = str(hbl)
            invalid_chars = ['[', ']', ':', '*', '?', '/', '\\']
            safe_sheet_name = f"{sheet_idx}. {hbl_name}"
            for char in invalid_chars: safe_sheet_name = safe_sheet_name.replace(char, '')
            safe_sheet_name = safe_sheet_name[:31] 
            
            ws = workbook.add_worksheet(safe_sheet_name)
            
            ws.set_row(0, 50); ws.set_row(1, 70)
            ws.merge_range('A1:V1', header_company_text, fmt_company)
            ws.merge_range('A3:V3', "BẢNG ĐỐI CHIẾU CÔNG NỢ", fmt_title)
            ws.set_row(4, 30); ws.set_row(5, 30); ws.set_row(6, 30)
            
            # Cấu trúc Header
            ws.merge_range('A4:A6', "STT", fmt_header)
            ws.merge_range('B4:B5', "TỜ KHAI\n(Customs declaration No.)", fmt_header)
            ws.write('B6', "Số (no.)", fmt_header)
            
            ws.merge_range('C4:F4', "NHẬP-XUẤT\n(Import-Export)", fmt_header)
            ws.merge_range('C5:C6', "Ngày\n(Date)", fmt_header)
            ws.merge_range('D5:D6', "20'", fmt_header)
            ws.merge_range('E5:E6', "40'", fmt_header)
            ws.merge_range('F5:F6', "Lẻ(LCL)", fmt_header)
            
            ws.merge_range('G4:G6', "SỐ VẬN ĐƠN\n(Bill No)", fmt_header)
            ws.merge_range('H4:H6', "SỐ HÓA ĐƠN THƯƠNG MẠI\n(Invoice No)", fmt_header)
            ws.merge_range('I4:I6', "Phí vận chuyển\n(Trucking fee)", fmt_header)
            ws.merge_range('J4:J6', "BOT", fmt_header)
            ws.merge_range('K4:K6', "PHÍ DỊCH VỤ\n(Service fee)", fmt_header)
            ws.merge_range('L4:L6', "PHÍ LẤY MẪU\n(Fee for sampling)", fmt_header)
            
            ws.merge_range('M4:T4', "CHI HỘ", fmt_header)
            ws.merge_range('M5:N5', "Phí kiểm dịch", fmt_header)
            ws.write('M6', "Số tiền", fmt_header); ws.write('N6', "Số HĐ", fmt_header)
            
            ws.merge_range('O5:P5', "Phí lưu bãi", fmt_header)
            ws.write('O6', "Số tiền", fmt_header); ws.write('P6', "Số HĐ", fmt_header)
            
            ws.merge_range('Q5:R5', "Phí nâng hạ, Phí khử trùng", fmt_header)
            ws.write('Q6', "Số tiền", fmt_header); ws.write('R6', "Số HĐ", fmt_header)
            
            ws.merge_range('S5:T5', "D/O, handling, Bill", fmt_header)
            ws.write('S6', "Số tiền", fmt_header); ws.write('T6', "Số HĐ", fmt_header)
            
            ws.merge_range('U4:U6', "SỐ CONTAINER", fmt_header)
            ws.merge_range('V4:V6', "GHI CHÚ (Note)", fmt_header)
            
            row = 6
            stt = 1
            
            # Các biến cộng dồn Footer HBL
            hbl_total_vc = 0; hbl_total_bot = 0; hbl_total_dv = 0; hbl_total_laymau = 0
            hbl_total_kiemdich = 0; hbl_total_luubai = 0; hbl_total_nangha = 0; hbl_total_do = 0
            
            grouped_tk = group_hbl.groupby('tk_id', sort=False)
            for tk_id, group in grouped_tk:
                r_first = group.iloc[0]
                has_cont = pd.notna(r_first.get('so_cont')) and str(r_first.get('so_cont')).strip() != ''
                num_cont = len(group) if has_cont else 0
                num_rows_group = num_cont * 2 if num_cont > 0 else 1 
                
                start_row = row
                end_row = row + num_rows_group - 1
                
                def write_merge(col, val, fmt):
                    if num_rows_group > 1:
                        ws.merge_range(start_row, col, end_row, col, val, fmt)
                    else:
                        ws.write(start_row, col, val, fmt)

                phi_vc = group['phi_van_chuyen'].sum()
                if phi_vc == 0: phi_vc = float(r_first.get('doanh_thu_chuyen') or 0)
                
                phi_bot = group['phi_bot'].sum()
                phi_dv = group['phi_to_khai'].sum() + float(r_first.get('phi_khac') or 0)
                phi_lay_mau = group['phi_lay_mau'].sum()
                phi_kiem_dich = group['phi_kiem_dich'].sum()
                phi_luu_bai = group['phi_luu_bai'].sum()
                phi_do_handling = group['phi_do'].sum() + group['phi_handling'].sum()
                phi_nang_ha_khu_trung = group['phi_nang_ha_on'].sum() + group['phi_nang_ha_off'].sum() + group['phi_khu_trung'].sum()
                
                # Cộng dồn HBL
                hbl_total_vc += phi_vc; hbl_total_bot += phi_bot; hbl_total_dv += phi_dv; hbl_total_laymau += phi_lay_mau
                hbl_total_kiemdich += phi_kiem_dich; hbl_total_luubai += phi_luu_bai
                hbl_total_nangha += phi_nang_ha_khu_trung; hbl_total_do += phi_do_handling
                
                # Lấy ID Hóa Đơn
                def get_unique_inv(col_name):
                    invs = group[col_name].dropna().astype(str).str.strip()
                    return ", ".join(sorted(set([x for x in invs if x])))
                
                inv_kiem_dich = get_unique_inv('so_hoa_don_kiem_dich')
                inv_luu_bai = get_unique_inv('so_hoa_don_luu_bai')
                inv_d_h_combined = ", ".join(filter(None, [get_unique_inv('so_hoa_don_do'), get_unique_inv('so_hoa_don_handling')]))
                
                # Setup Type QTY
                loai_counts = group['loai_cont'].value_counts()
                c_20 = sum(count for loai, count in loai_counts.items() if '20' in str(loai)) or ""
                c_40 = sum(count for loai, count in loai_counts.items() if '40' in str(loai) or '45' in str(loai)) or ""
                c_le = "" if has_cont else 1

                write_merge(0, stt, fmt_center); write_merge(1, str(r_first.get('so_to_khai') or ''), fmt_center)
                write_merge(2, pd.to_datetime(r_first['ngay_khai']).strftime('%d/%m/%Y') if pd.notna(r_first.get('ngay_khai')) else '', fmt_center)
                write_merge(3, c_20, fmt_center); write_merge(4, c_40, fmt_center); write_merge(5, c_le, fmt_center)
                write_merge(6, str(r_first.get('so_van_don') or ''), fmt_center); write_merge(7, str(r_first.get('so_hoa_don_tm') or ''), fmt_center)
                write_merge(8, phi_vc, fmt_money); write_merge(9, phi_bot, fmt_money); write_merge(10, phi_dv, fmt_money); write_merge(11, phi_lay_mau, fmt_money)
                write_merge(12, phi_kiem_dich, fmt_money); write_merge(13, inv_kiem_dich, fmt_center)
                write_merge(14, phi_luu_bai, fmt_money); write_merge(15, inv_luu_bai, fmt_center)
                write_merge(18, phi_do_handling, fmt_money); write_merge(19, inv_d_h_combined, fmt_center)
                
                ghi_chu_arr = [x for x in [str(r_first.get('ma_loai_hinh') or ''), str(r_first.get('dia_diem_giao_nhan') or ''), str(r_first.get('phan_luong') or '')] if x]
                write_merge(21, " - ".join(ghi_chu_arr), fmt_center)
                
                # Ghi phí Nâng / Hạ (Mỗi cont 2 dòng)
                if num_rows_group == 1: 
                    phi_on = float(r_first.get('phi_nang_ha_on') or 0) + float(r_first.get('phi_khu_trung') or 0)
                    inv_on = ", ".join(filter(None, [str(r_first.get('so_hoa_don_lift_on') or ''), str(r_first.get('so_hoa_don_khu_trung') or '')]))
                    ws.write(start_row, 16, phi_on, fmt_money)
                    ws.write(start_row, 17, inv_on, fmt_center)
                    ws.write(start_row, 20, "", fmt_center)
                else:
                    current_row = start_row
                    for _, r_cont in group.iterrows():
                        cont_name = str(r_cont.get('so_cont') or '')
                        ws.merge_range(current_row, 20, current_row + 1, 20, cont_name, fmt_center)
                        
                        phi_on = float(r_cont.get('phi_nang_ha_on') or 0) + float(r_cont.get('phi_khu_trung') or 0)
                        inv_on = ", ".join(filter(None, [str(r_cont.get('so_hoa_don_lift_on') or ''), str(r_cont.get('so_hoa_don_khu_trung') or '')]))
                        ws.write(current_row, 16, phi_on, fmt_money); ws.write(current_row, 17, inv_on, fmt_center)
                        
                        phi_off = float(r_cont.get('phi_nang_ha_off') or 0)
                        inv_off = str(r_cont.get('so_hoa_don_lift_off') or '')
                        ws.write(current_row + 1, 16, phi_off, fmt_money); ws.write(current_row + 1, 17, inv_off, fmt_center)
                        
                        current_row += 2
                
                row += num_rows_group; stt += 1
                
            # ==========================================
            # BỔ SUNG: Dòng FOOTER Tổng cho từng Sheet HBL
            # ==========================================
            hbl_grand_total = hbl_total_vc + hbl_total_bot + hbl_total_dv + hbl_total_laymau + hbl_total_kiemdich + hbl_total_luubai + hbl_total_nangha + hbl_total_do
            
            # --- 1. Dòng TỔNG CỘNG ---
            ws.merge_range(row, 0, row, 2, "TỔNG CỘNG", fmt_center_bold)
            for c_idx in range(3, 22):
                if c_idx == 8: ws.write(row, c_idx, hbl_total_vc, fmt_money_bold)
                elif c_idx == 9: ws.write(row, c_idx, hbl_total_bot, fmt_money_bold)
                elif c_idx == 10: ws.write(row, c_idx, hbl_total_dv, fmt_money_bold)
                elif c_idx == 11: ws.write(row, c_idx, hbl_total_laymau, fmt_money_bold)
                elif c_idx == 12: ws.write(row, c_idx, hbl_total_kiemdich, fmt_money_bold)
                elif c_idx == 14: ws.write(row, c_idx, hbl_total_luubai, fmt_money_bold)
                elif c_idx == 16: ws.write(row, c_idx, hbl_total_nangha, fmt_money_bold)
                elif c_idx == 18: ws.write(row, c_idx, hbl_total_do, fmt_money_bold)
                elif c_idx == 20: ws.write(row, c_idx, hbl_grand_total, fmt_money_bold)
                else: ws.write(row, c_idx, "", fmt_center_bold)
            
            # --- 2. Dòng TỔNG THU (Grand Total) & Cột Ngày Tháng ---
            row += 2
            ws.merge_range(row, 0, row, 1, "TỔNG THU: (total)", fmt_bold_left)
            ws.merge_range(row, 2, row, 5, hbl_grand_total, fmt_money_bold_no_border)
            ws.write(row, 6, "đồng", fmt_bold_left)
            
            try:
                dt_den_ngay = datetime.strptime(den_ngay, '%Y-%m-%d')
                date_str = f"Ngày {dt_den_ngay.strftime('%d')} tháng {dt_den_ngay.strftime('%m')} năm {dt_den_ngay.strftime('%Y')}"
            except:
                date_str = ""
            ws.merge_range(row, 16, row, 18, date_str, fmt_bold_left)
            
            # --- 3. Phí dịch vụ chưa VAT ---
            row += 1
            ws.merge_range(row, 0, row, 2, "Phí dịch vụ chưa VAT\n( the service fee not\ninclude value Add Tax): ", fmt_bold_left_wrap)
            phi_dich_vu_chua_vat = hbl_total_vc + hbl_total_bot + hbl_total_dv + hbl_total_laymau
            ws.merge_range(row, 3, row, 5, phi_dich_vu_chua_vat, fmt_money_bold_no_border)
            ws.write(row, 6, "đồng", fmt_bold_left)
            
            # --- 4. Tổng Chi hộ ---
            row += 2
            ws.merge_range(row, 0, row, 2, "Chi hộ( pay on behaft)", fmt_bold_left)
            chi_ho_pay = hbl_total_kiemdich + hbl_total_luubai + hbl_total_nangha + hbl_total_do
            ws.merge_range(row, 3, row, 5, chi_ho_pay, fmt_money_bold_no_border)
            ws.write(row, 6, "đồng", fmt_bold_left)
                
            ws.set_column('A:A', 5); ws.set_column('B:I', 15); ws.set_column('J:V', 14)
            sheet_idx += 1
            
    output.seek(0)
    return output.getvalue()
###########################################
def get_phu_phi_theo_khach_hang(db_pool, khach_hang_id):
    """
    Truy xuất danh sách phụ phí cấu hình riêng cho từng khách hàng.
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = """
            SELECT id, ten_phu_phi, don_gia_phu_phi 
            FROM phu_phi_khach_hang 
            WHERE khach_hang_id = %s
        """
        cursor.execute(sql, (khach_hang_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"Lỗi lấy phụ phí: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
#########################################
def get_don_gia_hq_tu_dong(db_pool, khach_hang_id, phan_loai_chi_tiet):
    """
    Truy xuất giá Dịch vụ Hải quan tự động từ bảng bang_gia_hai_quan.
    Tìm kiếm dựa theo Nhóm dịch vụ (chứa chữ Tờ Khai hoặc Hải Quan) và Phân loại chi tiết (Nhập, Xuất...).
    """
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Tìm giá gần nhất áp dụng cho Khách hàng + Loại hình tờ khai
        sql = """
            SELECT don_gia_hq 
            FROM bang_gia_hai_quan 
            WHERE khach_hang_id = %s 
              AND phan_loai_chi_tiet LIKE %s
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(sql, (khach_hang_id, f"%{phan_loai_chi_tiet}%"))
        result = cursor.fetchone()
        
        if result and result['don_gia_hq']:
            return float(result['don_gia_hq'])
        return 0.0
    except Exception as e:
        print(f"Lỗi truy xuất giá Tờ khai HQ: {e}")
        return 0.0
    finally:
        if cursor: cursor.close()
        if conn: conn.close()