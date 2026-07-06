import os
import pandas as pd
import mysql.connector
from mysql.connector import Error
import re
# =====================================================================
# 1. CẤU HÌNH THÔNG TIN KẾT NỐI DATABASE
# =====================================================================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'LoveYou#1976',  # Thay bằng mật khẩu của bạn
    'database': 'logistics_app',     # Thay bằng tên database của bạn
    'charset': 'utf8mb4'
}

# =====================================================================
# 2. CÁC HÀM LÀM SẠCH VÀ TÌM CỘT (Đã tối ưu cho file mới)
# =====================================================================
def find_col(df, keywords):
    """Tìm cột linh hoạt: tự động cắt bỏ khoảng trắng và nhận diện cả chữ hoa/thường"""
    for col in df.columns:
        col_str = str(col).strip().lower()
        for kw in keywords:
            if kw.lower() in col_str:
                return col
    return None

def clean_numeric(val):
    """Xử lý triệt để số thập phân dùng dấu phẩy (VD: '3,5' -> 3.5, 'REMOOC, 5' -> 5.0)"""
    if pd.isna(val) or str(val).strip() == '': 
        return 0.0
    if isinstance(val, (int, float)): 
        return float(val)
    
    # Đổi phẩy thành chấm để hệ thống hiểu là số thập phân
    val_str = str(val).strip().replace(',', '.')
    # Dùng regex tóm lấy cụm số (kể cả số thập phân)
    matches = re.findall(r'\d+\.?\d*', val_str)
    
    if matches:
        return float(matches[0]) # Lấy con số đầu tiên tìm thấy
    return 0.0

def clean_date(val):
    if pd.isna(val) or str(val).strip() in ['', 'NaN', 'None', 'CHƯA CÓ']: return None
    try:
        return pd.to_datetime(str(val).strip(), format='%d/%m/%Y', errors='coerce').strftime('%Y-%m-%d')
    except:
        try:
            return pd.to_datetime(str(val).strip(), errors='coerce').strftime('%Y-%m-%d')
        except:
            return None

def clean_string(val):
    if pd.isna(val): return None
    string_val = str(val).strip()
    return string_val if string_val != '' else None

# =====================================================================
# 3. CHƯƠNG TRÌNH CHÍNH
# =====================================================================
def main():
    file_path = 'driver_phuongtien.xlsx'
    
    if not os.path.exists(file_path):
        print(f"❌ Lỗi: Không tìm thấy file '{file_path}'.")
        return

    print("📖 Bước 1: Đọc dữ liệu từ Excel...")
    df = pd.read_excel(file_path, sheet_name='Sheet1', header=4)
    # BƯỚC QUAN TRỌNG: Làm sạch tên cột ngay sau khi đọc
    # Loại bỏ khoảng trắng thừa hai đầu, chuyển hết thành chữ hoa
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Kiểm tra xem tên cột đã chuẩn chưa
    print("Các cột hiện có sau khi làm sạch:", df.columns.tolist())

    # Bây giờ dùng tên cột chuẩn để lọc (BIEN_SO_XE đã được chuẩn hóa)
    target_col = 'BIEN_SO_XE'
    if target_col in df.columns:
        df = df.dropna(subset=[target_col])
    else:
        print(f"❌ Vẫn không tìm thấy cột {target_col}. Hãy kiểm tra print ở trên!")
    
    # --- ÁNH XẠ CỘT CHÍNH XÁC THEO FILE MỚI CỦA BẠN ---
    # Tôi đã update tên cột khớp hoàn toàn với cấu trúc mới bạn gửi
    col_bien_so   = 'BIEN_SO_XE'
    col_nhan_hieu = 'NHAN_HIEU'
    col_quy_cach  = 'QUY_CACH_THUNG'
    col_cbm       = 'CBM'
    col_cua_xe    = 'CUA_XE'
    col_tai_trong = 'TAI_TRONG_LOAI' # Cột tải trọng mới
    col_loai_xe   = 'LOAI_XE'        # Cột loại xe mới
    
    col_taixe     = 'TEN_TAI_XE'
    col_cccd      = 'CCCD'
    col_gplx      = 'GPLX'
    col_hang      = 'HANG_GPLX'
    col_gplx_date = 'HAN_GPLX'
    col_taphuan   = 'HAN_TAP_HUAN'
    col_sdt       = 'SDT'
    col_email     = 'EMAIL'
    
        
    col_phu_hieu  = find_col(df, ['phu_hieu_xe', 'phù hiệu xe'])
    col_han_phu   = find_col(df, ['han_phu_hieu', 'hạn phù hiệu'])
    col_han_dang  = find_col(df, ['han_dang_kiem', 'đăng kiểm'])
    col_han_bh_ds = find_col(df, ['han_bh', 'bảo hiểm ds'])

    if not col_bien_so:
        print("❌ Lỗi: Không tìm thấy cột Biển số xe.")
        return

    df = df.dropna(subset=[col_bien_so])

    print("🔌 Bước 2: Kết nối Database...")
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            cursor = conn.cursor()
            
            print("🔄 Bước 3: Đang đẩy dữ liệu...\n")
            
            for index, row in df.iterrows():
                # XỬ LÝ NHÂN VIÊN
                #cccd = clean_string(row.get(col_cccd)) if col_cccd else None
                cccd = str(row.get('CCCD', '')).strip()
                ho_ten = str(row.get('TEN_TAI_XE', '')).strip()
                print(f"Row {index}: CCCD='{cccd}', Ten='{ho_ten}'")
                
                
                nhan_vien_id = None 

                # CHỈ XỬ LÝ NHÂN VIÊN NẾU CÓ ĐỦ CCCD VÀ HỌ TÊN (loại bỏ trường hợp 'None' hoặc rỗng)
                if cccd and cccd.lower() != 'nan' and cccd != '' and ho_ten and ho_ten.lower() != 'nan' and ho_ten != '':
                    cursor.execute("SELECT id FROM nhan_vien WHERE cccd = %s", (cccd,))
                    result_nv = cursor.fetchone()
                    
                    
                    giay_phep_lai_xe = clean_string(row.get(col_gplx)) if col_gplx else None
                    hang_gplx = clean_string(row.get(col_hang)) if col_hang else None
                    han_gplx = clean_date(row.get(col_gplx_date)) if col_gplx_date else None
                    han_the_tap_huan = clean_date(row.get(col_taphuan)) if col_taphuan else None
                    sdt_raw = clean_string(row.get(col_sdt)) if col_sdt else None
                    so_dien_thoai = f"0{sdt_raw}" if sdt_raw and not sdt_raw.startswith('0') and len(sdt_raw) >= 9 else sdt_raw
                    
                    if result_nv:
                        nhan_vien_id = result_nv[0]
                        #sql_update_nv = """
                        #    UPDATE nhan_vien SET ho_ten=%s, so_dien_thoai=%s, giay_phep_lai_xe=%s, 
                        #        hang_gplx=%s, han_gplx=%s, han_the_tap_huan=%s WHERE id=%s
                        #"""
                        #cursor.execute(sql_update_nv, (ho_ten, so_dien_thoai, giay_phep_lai_xe, hang_gplx, han_gplx, han_the_tap_huan, nhan_vien_id))
                    else:
                        ma_nhan_vien = f"NV_{cccd}"
                        sql_insert_nv = """
                            INSERT INTO nhan_vien (ma_nhan_vien, ho_ten, so_dien_thoai, cccd, giay_phep_lai_xe, hang_gplx, han_gplx, han_the_tap_huan)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_insert_nv, (ma_nhan_vien, ho_ten, so_dien_thoai, cccd, giay_phep_lai_xe, hang_gplx, han_gplx, han_the_tap_huan))
                        nhan_vien_id = cursor.lastrowid
                        print(f"👉 Chuẩn bị nhân viên: {ho_ten}, {ma_nhan_vien} ")   
                #else:
                        # Nếu không có tài xế, nhan_vien_id sẽ là None, xe vẫn được lưu bình thường
                        
                #    ho_ten = "CHƯA GÁN TÀI XẾ"
                #    nhan_vien_id = None
                # XỬ LÝ XE
                bien_so_xe = clean_string(row.get(col_bien_so))
                if not bien_so_xe: continue
                    
                nhan_hieu_xe       = clean_string(row.get(col_nhan_hieu)) if col_nhan_hieu else None
                quy_cach_thung     = clean_string(row.get(col_quy_cach)) if col_quy_cach else None
                loai_xe            = clean_string(row.get(col_loai_xe)) if col_loai_xe else None
                
                # Ép về string trước khi clean để đảm bảo không bị lỗi NoneType
                val_cbm = row.get(col_cbm)
                val_tai_trong = row.get(col_tai_trong)
                val_loai_xe = row.get(col_loai_xe)
                cua_xe_bam_seal    = row.get(col_cua_xe) if col_cua_xe else 0.0
                print(f"👉 Cửa bấm seal: {cua_xe_bam_seal}")
                dung_tich_cbm      = clean_numeric(val_cbm)
                tai_trong_thiet_ke = clean_numeric(val_tai_trong)
                loai_xe            = clean_string(val_loai_xe)
                
                
                # IN RA MÀN HÌNH ĐỂ BẠN KIỂM CHỨNG TẬN MẮT
                print(f"👉 Chuẩn bị lưu Xe: {bien_so_xe} | Loại: {loai_xe} | Tải Trọng: {tai_trong_thiet_ke} | CBM: {dung_tich_cbm}" )

                han_dang_kiem      = clean_date(row.get(col_han_dang)) if col_han_dang else None
                han_bao_hiem_ds    = clean_date(row.get(col_han_bh_ds)) if col_han_bh_ds else None
                phu_hieu_xe        = clean_string(row.get(col_phu_hieu)) if col_phu_hieu else None
                han_phu_hieu       = clean_date(row.get(col_han_phu)) if col_han_phu else None
                email_xac_thuc     = clean_string(row.get(col_email)) if col_email else None
                sdt_raw_xe         = clean_string(row.get(col_sdt)) if col_sdt else None
                sdt_xac_thuc       = f"0{sdt_raw_xe}" if sdt_raw_xe and not sdt_raw_xe.startswith('0') and len(sdt_raw_xe) >= 9 else sdt_raw_xe

                

                # Cập nhật Database
                sql_xe = """
                    INSERT INTO xe (
                        bien_so_xe, nhan_hieu_xe, quy_cach_thung, dung_tich_cbm, 
                        cua_xe_bam_seal, tai_trong_thiet_ke, loai_xe, han_dang_kiem, 
                        han_bao_hiem_ds, phu_hieu_xe, han_phu_hieu, 
                        sdt_xac_thuc, email_xac_thuc, tai_xe_co_dinh_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        nhan_hieu_xe = VALUES(nhan_hieu_xe),
                        quy_cach_thung = VALUES(quy_cach_thung),
                        dung_tich_cbm = VALUES(dung_tich_cbm),
                        cua_xe_bam_seal = VALUES(cua_xe_bam_seal),
                        tai_trong_thiet_ke = VALUES(tai_trong_thiet_ke),
                        loai_xe = VALUES(loai_xe),
                        han_dang_kiem = VALUES(han_dang_kiem),
                        han_bao_hiem_ds = VALUES(han_bao_hiem_ds),
                        phu_hieu_xe = VALUES(phu_hieu_xe),
                        han_phu_hieu = VALUES(han_phu_hieu),
                        sdt_xac_thuc = VALUES(sdt_xac_thuc),
                        email_xac_thuc = VALUES(email_xac_thuc),
                        tai_xe_co_dinh_id = VALUES(tai_xe_co_dinh_id);
                """
                
                values_xe = (
                    bien_so_xe, nhan_hieu_xe, quy_cach_thung, dung_tich_cbm, 
                    cua_xe_bam_seal, tai_trong_thiet_ke, loai_xe, han_dang_kiem, 
                    han_bao_hiem_ds, phu_hieu_xe, han_phu_hieu, 
                    sdt_xac_thuc, email_xac_thuc, nhan_vien_id
                )
                cursor.execute(sql_xe, values_xe)

            conn.commit()
            print("\n🎉 THÀNH CÔNG! Dữ liệu đã được nạp chuẩn xác.")

    except Error as e:
        print(f"\n❌ Lỗi Database: {e}")
        if conn: conn.rollback()
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    main()