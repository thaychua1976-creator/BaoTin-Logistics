import pandas as pd
from datetime import datetime
from db_config import Database

def chay_nhap_lieu():
    print("⏳ Bắt đầu đọc file Excel...")
    db = Database()
    
    try:
        # Đọc file Excel, bỏ qua 4 dòng tiêu đề trắng/công ty ở trên cùng
        df = pd.read_excel('driver_phuongtien.xlsx', skiprows=4)
        
        # Chuẩn hóa tên cột để dễ truy cập theo vị trí file của bạn
        df.columns = [
            'STT', 'NHAN_HIEU', 'QUY_CACH_THUNG','CBM', 'CUA_XE', 'BIEN_SO_XE', 'TAI_TRONG_LOAI',
            'TEN_TAI_XE', 'CCCD', 'GPLX', 'HANG_GPLX', 'HAN_GPLX', 'HAN_DANG_KIEM',
            'HAN_BAO_HIEM', 'HAN_TAP_HUAN', 'PHU_HIEU_XE', 'CHUNG_TU', 'HAN_PHU_HIEU',
             'HAN_BH_VC', 'SDT', 'EMAIL', 'LOAI_HINH'
        ]
    except Exception as e:
        print(f"❌ Lỗi đọc file Excel: Vui lòng kiểm tra lại tên file có đúng là 'driver_phuongtien.xlsx' không! ({e})")
        return

    # Hàm xử lý làm sạch ngày tháng
    def parse_date(val):
        if pd.isna(val): return None
        if isinstance(val, datetime): return val.strftime('%Y-%m-%d')
        if isinstance(val, str):
            try:
                # Cắt chuỗi và chuyển từ dd/mm/yyyy sang định dạng MySQL yyyy-mm-dd
                return datetime.strptime(val.strip().split(' ')[0], '%d/%m/%Y').strftime('%Y-%m-%d')
            except:
                return None
        return None

    # Hàm thông minh phân tách Tải trọng và Loại xe do bị gộp chung trong Excel
    def parse_taitrong(val):
        if pd.isna(val): return 0.0, "Khác"
        val_str = str(val).upper().strip()
        if "KÉO" in val_str:
            return 0.0, "ĐẦU KÉO"
        if "REM" in val_str:
             return 0.0, "REMOOC"
        if "4 CHỖ" in val_str:
            return 0.0, "4 CHỖ"
        if "7 CHỖ" in val_str:
             return 0.0, "7 CHỖ"
        if "CONT" in val_str:
             return 0.0, "CONT RỖNG"

        elif "T" in val_str:
            try:
                tt = float(val_str.replace("T", "").strip())
                return tt, "XE TẢI THÙNG"
            except:
                return 0.0, "XE TẢI THÙNG"
        return 0.0, "Khác"

    so_dong_thanh_cong = 0
    
    for index, row in df.iterrows():
        bien_so = str(row['BIEN_SO_XE']).strip() if pd.notna(row['BIEN_SO_XE']) else ""
        if not bien_so or bien_so.lower() == 'nan':
            continue # Bỏ qua các dòng trống không có biển số
            
        tai_trong, loai_xe = parse_taitrong(row['TAI_TRONG_LOAI'])
        quy_cach = str(row['QUY_CACH_THUNG']).strip() if pd.notna(row['QUY_CACH_THUNG']) else None
        cua_seal = str(row['CUA_XE']).strip() if pd.notna(row['CUA_XE']) else None
        cbm_index = str(row['CBM']).strip() if pd.notna(row['CBM']) else None
        ten_tx = str(row['TEN_TAI_XE']).strip() if pd.notna(row['TEN_TAI_XE']) else None
        
        # Khắc phục lỗi Excel tự biến CCCD/SĐT/GPLX thành số khoa học
        cccd = str(row['CCCD']).strip() if pd.notna(row['CCCD']) else None
        if cccd and cccd.endswith('.0'): cccd = cccd[:-2]
        
        gplx = str(row['GPLX']).strip() if pd.notna(row['GPLX']) else None
        if gplx and gplx.endswith('.0'): gplx = gplx[:-2]
        
        hang_gplx = str(row['HANG_GPLX']).strip() if pd.notna(row['HANG_GPLX']) else None
        
        han_gplx = parse_date(row['HAN_GPLX'])
        han_dk = parse_date(row['HAN_DANG_KIEM'])
        han_bh = parse_date(row['HAN_BAO_HIEM'])
        han_th = parse_date(row['HAN_TAP_HUAN'])
        
        phu_hieu = str(row['PHU_HIEU_XE']).strip() if pd.notna(row['PHU_HIEU_XE']) else None
        han_ph = parse_date(row['HAN_PHU_HIEU'])
        
        sdt = str(row['SDT']).strip() if pd.notna(row['SDT']) else None
        if sdt:
            if sdt.endswith('.0'): sdt = "0" + sdt[:-2]
            elif not sdt.startswith('0'): sdt = "0" + sdt # Bù số 0 ở đầu
            
        email = str(row['EMAIL']).strip() if pd.notna(row['EMAIL']) else None
        # Lấy thêm thông tin Nhãn hiệu từ dòng dữ liệu Excel
        nhan_hieu = str(row['NHAN_HIEU']).strip() if pd.notna(row['NHAN_HIEU']) else None

        # 1. CHÈN DỮ LIỆU TÀI XẾ (Chỉ thực hiện nếu có tên tài xế hợp lệ)
        if ten_tx and ten_tx.lower() != 'nan' and len(ten_tx) > 2:
            #ma_nv = f"NV_{str(index+1).zfill(3)}"
            #sql_nv = """
            #    INSERT INTO nhan_vien (ma_nhan_vien, ho_ten, so_dien_thoai, cccd, giay_phep_lai_xe, 
            #    hang_gplx, han_gplx, han_the_tap_huan, loai_nhan_vien, trang_thai) 
            #    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Tai_Chinh', 'Dang_Lam_Viec')
            #"""
            #db.execute_query(sql_nv, (ma_nv, ten_tx, sdt, cccd, gplx, hang_gplx, han_gplx, han_th))
            print(f"✔️ Đã import tài xế: {ten_tx}")
        else:
            print(f"⏭️ Bỏ qua tạo tài xế cho xe {bien_so} (Dữ liệu trống)")
        

        # 2. CHÈN DỮ LIỆU ĐỘI XE (Bổ sung nhan_hieu_xe)
        if bien_so and bien_so.lower() != 'nan':
            sql_xe = """
                INSERT INTO xe (bien_so_xe, nhan_hieu_xe,dung_tich_cbm, tai_trong_thiet_ke, loai_xe, quy_cach_thung, cua_xe_bam_seal, 
                han_dang_kiem, han_bao_hiem_ds, phu_hieu_xe, han_phu_hieu, sdt_xac_thuc, email_xac_thuc, trang_thai) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Dang_Hoat_Dong')
            
                    """
            
            db.execute_query(sql_xe, (bien_so, nhan_hieu, cbm_index, tai_trong, loai_xe, quy_cach, cua_seal, han_dk, han_bh, phu_hieu, han_ph, sdt, email))
            
        
        
        
        print(f"✔️ Đã import thành công: {bien_so} - {ten_tx}")
        so_dong_thanh_cong += 1

    print(f"\n🎉 HOÀN TẤT! Đã import {so_dong_thanh_cong} hồ sơ Xe và Tài xế vào Database.")

if __name__ == "__main__":
    chay_nhap_lieu()