import pandas as pd
import re
import json
import os

def tao_json_dieu_kien(row):
    # Lấy dữ liệu và làm sạch
    ten_phu_phi = str(row.get('TEN_PHU_PHI', '')).lower()
    khach_hang = str(row.get('KHACH_HANG', '')).upper()
    dk_goc = str(row.get('DIEU_KIEN_KICH_HOAT', '')).strip()
    
    js = {}
    
    # ==================================================
    # 1. BÓC TÁCH TẢI TRỌNG (TONNAGE) 
    # ==================================================
    ten_fix = ten_phu_phi.replace('tấn', 't').replace(' ', '')
    ton_match = re.search(r'(\d+)[\s-]*(\d+)t', ten_fix)
    if ton_match:
        js["tai_trong_min"] = float(ton_match.group(1))
        js["tai_trong_max"] = float(ton_match.group(2))
    elif ">=5t" in ten_fix:
        js["tai_trong_min"] = 5.0
        js["tai_trong_max"] = 999.0
    elif ">8t" in ten_fix or "hơn8t" in ten_fix:
        js["tai_trong_min"] = 8.01
        js["tai_trong_max"] = 999.0
    elif "15t" in ten_fix:
        js["tai_trong_min"] = 15.0
        js["tai_trong_max"] = 999.0
    elif "16t" in ten_fix:
        js["tai_trong_min"] = 16.0
        js["tai_trong_max"] = 999.0
    else:
        # Trường hợp số đơn (Ví dụ: xe 5 tấn)
        single_ton = re.search(r'xe\s*(\d+)\s*tấn', ten_phu_phi)
        if single_ton:
            val = float(single_ton.group(1))
            js["tai_trong_min"] = val
            js["tai_trong_max"] = val + 0.99
            
    # ==================================================
    # 2. PHÂN LOẠI NGHIỆP VỤ & LẬP LUẬT TÍNH TIỀN
    # ==================================================
    
    if "giao điểm thứ 2" in ten_phu_phi or "giao hàng 2 nơi" in ten_phu_phi:
        js["loai"] = "giao_diem_them"
        # Luật tính tiền riêng cho Wantai
        if "WANTAI" in khach_hang:
            if "<10km" in ten_fix:
                js["km_min"] = 0
                js["km_max"] = 10
            else:
                km_match = re.search(r'(\d+)km-->(\d+)km', ten_fix)
                if not km_match:
                    km_match = re.search(r'từ(\d+)km-->(\d+)km', ten_fix)
                if km_match:
                    js["km_min"] = float(km_match.group(1))
                    js["km_max"] = float(km_match.group(2))
        # Luật tính tiền riêng cho Young Il
        elif "YOUNG IL" in khach_hang:
            js["kieu_tinh"] = "phan_tram_diem_xa_nhat"
            
    elif "bốc xếp" in ten_phu_phi:
        js["loai"] = "boc_xep"
        
    elif "về khuya" in ten_phu_phi or "ngoài giờ" in ten_phu_phi:
        js["loai"] = "ve_khuya"
        
    elif "làm hàng" in ten_phu_phi:
        js["loai"] = "lam_hang_cang"
        
    elif "neo" in ten_phu_phi:
        if "cont" in ten_phu_phi:
            js["loai"] = "neo_cont"
            if "nhập" in ten_phu_phi: js["chieu"] = "nhap"
            elif "xuất" in ten_phu_phi: js["chieu"] = "xuat"
            
            if "ngày" in ten_phu_phi: js["thoi_gian"] = "ngay"
            else: js["thoi_gian"] = "dem" # Mặc định là neo qua đêm
        else:
            js["loai"] = "neo_xe_tai"
            
    elif "hủy" in ten_phu_phi or "huỷ" in ten_phu_phi:
        js["loai"] = "huy_chuyen"
        
    elif "chiều về" in ten_phu_phi:
        js["loai"] = "hang_tra_ve"
        
    elif "nâng hạ" in ten_phu_phi or "lift on" in dk_goc.lower():
        js["loai"] = "nang_ha_cont"
        if "đồng nai" in ten_phu_phi: js["cang"] = "Dong_Nai"
        elif "hiệp phước" in ten_phu_phi: js["cang"] = "Hiep_Phuoc"
        elif "vict" in ten_phu_phi: js["cang"] = "VICT"
        elif "cái mép" in ten_phu_phi: js["cang"] = "Cai_Mep"
        
    elif "qua cảng" in ten_phu_phi:
        js["loai"] = "phi_qua_cang"
        if "đồng nai" in ten_phu_phi: js["cang"] = "Dong_Nai"
        elif "hiệp phước" in ten_phu_phi: js["cang"] = "Hiep_Phuoc"
        
    elif "hạ xa" in ten_phu_phi or "lift off" in dk_goc.lower():
        js["loai"] = "ha_xa_trai_tuyen"
        
    elif "hải quan" in ten_phu_phi or "kiểm hóa" in ten_phu_phi or "kiểm dịch" in ten_phu_phi:
        js["loai"] = "hai_quan_kiem_dich"
        if "nội địa" in ten_phu_phi: js["nghiep_vu"] = "khai_bao_noi_dia"
        elif "luồng đỏ" in ten_phu_phi or "vàng" in ten_phu_phi: js["nghiep_vu"] = "luong_do_vang"
        elif "ngoài giờ" in ten_phu_phi: js["nghiep_vu"] = "kiem_hoa_ngoai_gio"
        elif "kiểm dịch" in ten_phu_phi: js["nghiep_vu"] = "kiem_dich"
        
    elif "bot" in ten_phu_phi:
        js["loai"] = "phi_bot"
        
    elif "chủ nhật" in ten_phu_phi:
        js["loai"] = "phu_thu_chu_nhat"
        
    elif "quá tải cont" in ten_phu_phi:
        js["loai"] = "qua_tai_cont"
        
    elif "lấy cont rỗng" in ten_phu_phi or "hạ cont rỗng" in ten_phu_phi:
        js["loai"] = "chuyen_cont_rong"
        if "trái tuyến" in ten_phu_phi: js["nghiep_vu"] = "trai_tuyen"
        
    elif "số cont/seal" in ten_phu_phi:
        js["loai"] = "lay_seal_som"
        
    elif "xe máy" in ten_phu_phi:
        js["loai"] = "xe_may"
        if "cồng kềnh" in ten_phu_phi: js["nghiep_vu"] = "cong_kenh"
        elif "chờ hàng" in ten_phu_phi: js["nghiep_vu"] = "cho_hang"
        
    else:
        # Nhóm các phụ phí ngoại lệ không thuộc nhóm nào ở trên
        js["loai"] = "phu_phi_khac"
        
    # Chuyển đối tượng dictionary Python thành chuỗi JSON chuẩn mực
    return json.dumps(js, ensure_ascii=False)

if __name__ == "__main__":
    file_goc = 'phu phi Bao Tin.xlsx'
    file_moi = 'phu_phi_Bao_Tin_Da_Chuyen_Doi.xlsx'
    
    print(f"⏳ Đang đọc dữ liệu từ file {file_goc}...")
    try:
        if not os.path.exists(file_goc):
            print(f"❌ Không tìm thấy file '{file_goc}' trong thư mục hiện tại!")
            exit()
            
        df = pd.read_excel(file_goc, sheet_name='PHU_PHI')
        
        print("⚙️ Đang áp dụng Động cơ Luật (Rule Engine) mã hóa JSON...")
        # Ghi đè trực tiếp kết quả JSON vào cột DIEU_KIEN_KICH_HOAT
        df['DIEU_KIEN_KICH_HOAT'] = df.apply(tao_json_dieu_kien, axis=1)
        
        # Bắt buộc In hoa các tên cột để chuẩn với hàm import backend
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Xuất file
        df.to_excel(file_moi, index=False)
        print(f"✅ HOÀN TẤT! Đã tạo thành công file: {file_moi}")
        print("💡 Hướng dẫn: Mở phần mềm Logistics -> Vào Tab 4 (Import Phụ phí) -> Upload file này lên!")
        
    except Exception as e:
        print(f"❌ Đã xảy ra lỗi trong quá trình xử lý: {e}")