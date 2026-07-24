# file test để lấy kết quả trả về từ TechGlobal -- kết quả ok 16/7/2026
import streamlit as st
import pandas as pd
import datetime
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from db_config import Database 

# 1. Khởi tạo kết nối Database nếu chưa có
if 'db' not in st.session_state:
    try:
        st.session_state['db'] = Database()
        st.success("Đã kết nối Database thành công!")
    except Exception as e:
        st.error(f"Lỗi kết nối Database: {e}")
        st.stop()

db = st.session_state['db']

# 2. Khởi tạo ID test
TAI_XE_ID_HIENTAI = 1 #[cite: 3]
chuyen_di_id = 149 #[cite: 3]

def test_get_gps_chuyen_di_da_hoan_thanh(db_instance, chuyen_di_id):
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        st.write(f"🔄 **Đang kiểm tra dữ liệu chuyến đi ID: {chuyen_di_id}**")
        
        # 1. LẤY THÔNG TIN CHUYẾN ĐI (Không ghi đè thời gian kết thúc bằng Now)
        sql_get_info = """
            SELECT cd.thoi_gian_bat_dau, cd.thoi_gian_ket_thuc, x.bien_so_xe 
            FROM chuyen_di cd
            JOIN xe x ON cd.xe_id = x.id
            WHERE cd.id = %s
        """
        cursor.execute(sql_get_info, (chuyen_di_id,))
        trip_info = cursor.fetchone() #[cite: 3]
        
        if not trip_info or not trip_info['bien_so_xe'] or not trip_info['thoi_gian_bat_dau'] or not trip_info['thoi_gian_ket_thuc']:
            st.error("❌ Chuyến đi không tồn tại hoặc thiếu mốc thời gian bắt đầu/kết thúc trong DB!")
            return False
            
        bien_so = trip_info['bien_so_xe'] #[cite: 3]
        tg_bat_dau = trip_info['thoi_gian_bat_dau'] #[cite: 3]
        tg_ket_thuc = trip_info['thoi_gian_ket_thuc'] #[cite: 3]
        
        st.info(f"🚛 **Biển số:** {bien_so} | **Khung giờ chạy:** {tg_bat_dau} -> {tg_ket_thuc}")
        
        # 2. CẤU HÌNH API TECHGLOBAL
        api_url = "https://hanhtrinhxe.vn/api/gps/rpsummary" #[cite: 2]
        tong_km_chuyen_di = 0.0
        
        # THUẬT TOÁN CẮT LÁT THỜI GIAN (Vượt qua giới hạn 24h)
        thoi_gian_quet_hien_tai = tg_bat_dau
        
        while thoi_gian_quet_hien_tai < tg_ket_thuc:
            # Quét từng đoạn tối đa 23h59m59s
            moc_tiep_theo = thoi_gian_quet_hien_tai + datetime.timedelta(hours=23, minutes=59, seconds=59)
            if moc_tiep_theo > tg_ket_thuc:
                moc_tiep_theo = tg_ket_thuc
                
            from_date_str = thoi_gian_quet_hien_tai.strftime('%Y%m%d%H%M%S') #[cite: 2]
            to_date_str = moc_tiep_theo.strftime('%Y%m%d%H%M%S') #[cite: 2]
            
            payload = {
                "CustomerCode": "Baotran", #[cite: 3]
                "Key": "686868", #[cite: 3]
                "VehiclePlate": bien_so, #[cite: 2]
                "FromDate": from_date_str, #[cite: 2]
                "ToDate": to_date_str #[cite: 2]
                #"FromDate": 20260715000000, #[cite: 2]
                #"ToDate": 20260715235959 #[cite: 2]
            }
            
            try:
                # Đã thêm tham số verify=False để bỏ qua lỗi SSL
                response = requests.post(api_url, data=payload, timeout=20, verify=False)
                if response.status_code == 200: #[cite: 3]
                    api_data = response.json() #[cite: 3]
                    
                    if api_data.get('messageResult') == 'Success': #[cite: 2]
                        danh_sach_bao_cao = api_data.get('summaryReports', []) #[cite: 3]
                        
                        if danh_sach_bao_cao and len(danh_sach_bao_cao) > 0: #[cite: 3]
                            km_khuc_nay = float(danh_sach_bao_cao[0].get('totalKmGps', 0)) #[cite: 3]
                            tong_km_chuyen_di += km_khuc_nay
                            st.write(f"✔️ Quét đoạn `{from_date_str}` -> `{to_date_str}`: Trả về **{km_khuc_nay:.2f} km**")
                        else:
                            st.warning(f"⚠️ Đoạn `{from_date_str}` -> `{to_date_str}` không có phát sinh di chuyển.")
                    else:
                        st.error(f"❌ Lỗi API đoạn {from_date_str}: {api_data.get('messageResult')}") #[cite: 2]
                else:
                    st.error(f"Lỗi HTTP: {response.status_code}") #[cite: 3]
            except Exception as api_err:
                st.error(f"Lỗi kết nối TechGlobal: {api_err}") #[cite: 3]
            
            # Bước nhảy lặp
            thoi_gian_quet_hien_tai = moc_tiep_theo + datetime.timedelta(seconds=1)
            
        st.success(f"🎉 **TỔNG KẾT:** Xe {bien_so} chạy tổng cộng **{tong_km_chuyen_di:.2f} km**")
        
        # 3. CẬP NHẬT DATABASE
        if tong_km_chuyen_di > 0:
            sql_update_km = "UPDATE chuyen_di SET so_km_thuc_te = %s WHERE id = %s" #[cite: 3]
            cursor.execute(sql_update_km, (tong_km_chuyen_di, chuyen_di_id)) #[cite: 3]
            conn.commit() #[cite: 3]
            st.info("💾 Đã lưu số KM thực tế vào Cơ sở dữ liệu thành công!")
        
        return True
        
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback() #[cite: 3]
        st.error(f"Lỗi hệ thống: {e}")
        return False
    finally:
        if 'cursor' in locals() and cursor: cursor.close() #[cite: 3]
        if 'conn' in locals() and conn: conn.close() #[cite: 3]

# TẠO NÚT BẤM ĐỂ TEST TRỰC QUAN TRÊN GIAO DIỆN
st.title("Công cụ Test API GPS TechGlobal")
if st.button("🚀 Chạy Test Tính KM cho Chuyến 144", use_container_width=True):
    test_get_gps_chuyen_di_da_hoan_thanh(db, chuyen_di_id)