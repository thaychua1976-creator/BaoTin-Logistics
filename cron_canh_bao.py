import datetime
import requests
import pandas as pd
from db_config import Database 

# ==========================================
# 1. HÀM BẮN TIN NHẮN TELEGRAM
# ==========================================
def send_telegram_message(noi_dung):
    BOT_TOKEN = "TELEGRAM_BOT_TOKEN" 
    CHAT_ID = "CHAT_ID"
    
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": noi_dung,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.datetime.now()}] ✅ Đã gửi báo cáo Telegram thành công!")
        else:
            print(f"[{datetime.datetime.now()}] ⚠️ Lỗi gửi Telegram: {response.text}")
    except Exception as e:
        print(f"Lỗi kết nối API Telegram: {e}")

# ==========================================
# 2. HÀM QUÉT DỮ LIỆU CẢNH BÁO TỪ BẢNG XE
# ==========================================
def quet_va_gui_canh_bao():
    print(f"[{datetime.datetime.now()}] Đang quét dữ liệu đội xe...")
    db = Database()
    
    # Đã sửa lại đúng tên cột: trang_thai, han_dang_kiem, han_bao_hiem_ds, han_phu_hieu
    # Công thức KM còn lại = (KM bảo dưỡng gần nhất + Định mức bảo dưỡng) - Tổng KM hiện tại
    sql_quet = """
        SELECT 
            bien_so_xe, 
            han_dang_kiem, 
            han_bao_hiem_ds,
            han_phu_hieu,
            (km_bao_duong_gan_nhat + dinh_muc_bao_duong - tong_km_hien_tai) AS km_con_lai
        FROM xe
        WHERE trang_thai = 'Dang_Hoat_Dong'
    """
    
    try:
        df_xe = db.execute_query(sql_quet)
        
        if not isinstance(df_xe, pd.DataFrame) or df_xe.empty:
            print("Chưa có dữ liệu xe hoạt động.")
            return
        
        hom_nay = datetime.date.today()
        canh_bao_list = []
        
        for index, xe in df_xe.iterrows():
            bien_so = xe['bien_so_xe']
            loi_nhac = []
            
            # 1. KIỂM TRA HẠN ĐĂNG KIỂM (han_dang_kiem)
            if pd.notna(xe['han_dang_kiem']):
                ngay_dk = xe['han_dang_kiem']
                if isinstance(ngay_dk, datetime.datetime): ngay_dk = ngay_dk.date()
                so_ngay_dk = (ngay_dk - hom_nay).days
                if 0 <= so_ngay_dk <= 7:
                    loi_nhac.append(f"⚠️ Đăng kiểm còn *{so_ngay_dk} ngày* ({ngay_dk.strftime('%d/%m/%Y')})")
                elif so_ngay_dk < 0:
                    loi_nhac.append(f"❌ *QUÁ HẠN ĐĂNG KIỂM {abs(so_ngay_dk)} ngày!*")

            # 2. KIỂM TRA HẠN BẢO HIỂM DÂN SỰ (han_bao_hiem_ds)
            if pd.notna(xe['han_bao_hiem_ds']):
                ngay_bh = xe['han_bao_hiem_ds']
                if isinstance(ngay_bh, datetime.datetime): ngay_bh = ngay_bh.date()
                so_ngay_bh = (ngay_bh - hom_nay).days
                if 0 <= so_ngay_bh <= 7:
                    loi_nhac.append(f"⚠️ Bảo hiểm còn *{so_ngay_bh} ngày* ({ngay_bh.strftime('%d/%m/%Y')})")
                elif so_ngay_bh < 0:
                    loi_nhac.append(f"❌ *QUÁ HẠN BẢO HIỂM {abs(so_ngay_bh)} ngày!*")

            # 3. KIỂM TRA HẠN PHÙ HIỆU XE (han_phu_hieu - Cực kỳ quan trọng với xe tải)
            if pd.notna(xe['han_phu_hieu']):
                ngay_ph = xe['han_phu_hieu']
                if isinstance(ngay_ph, datetime.datetime): ngay_ph = ngay_ph.date()
                so_ngay_ph = (ngay_ph - hom_nay).days
                if 0 <= so_ngay_ph <= 7:
                    loi_nhac.append(f"🏷️ Phù hiệu xe còn *{so_ngay_ph} ngày* ({ngay_ph.strftime('%d/%m/%Y')})")
                elif so_ngay_ph < 0:
                    loi_nhac.append(f"❌ *QUÁ HẠN PHÙ HIỆU {abs(so_ngay_ph)} ngày!*")

            # 4. KIỂM TRA BẢO DƯỠNG (Dựa vào km_con_lai)
            if pd.notna(xe['km_con_lai']):
                km_con_lai = int(xe['km_con_lai'])
                if 0 < km_con_lai <= 500:
                    loi_nhac.append(f"🛢️ Sắp đến hạn bảo dưỡng (còn *{km_con_lai} km*)")
                elif km_con_lai <= 0:
                    loi_nhac.append(f"🚨 *QUÁ HẠN BẢO DƯỠNG {abs(km_con_lai)} km!*")

            # Gộp lỗi nếu xe này có vấn đề
            if loi_nhac:
                canh_bao_list.append(f"🚛 *Xe {bien_so}:*\n- " + "\n- ".join(loi_nhac))
        
        # ==========================================
        # 3. ĐÓNG GÓI VÀ BẮN TIN NHẮN TỔNG HỢP
        # ==========================================
        if canh_bao_list:
            noi_dung_tin_nhan = f"🔔 *BÁO CÁO ĐỘI XE NGÀY {hom_nay.strftime('%d/%m/%Y')}*\n\n"
            noi_dung_tin_nhan += f"Phát hiện *{len(canh_bao_list)} xe* cần được xử lý:\n\n"
            noi_dung_tin_nhan += "\n\n".join(canh_bao_list)
            noi_dung_tin_nhan += "\n\n👉 _Vui lòng truy cập hệ thống ERP để cập nhật._"
            
            send_telegram_message(noi_dung_tin_nhan)
        else:
            print(f"[{datetime.datetime.now()}] 🟢 Mọi xe đều an toàn, không có cảnh báo nào.")
            
    except Exception as e:
        print(f"Lỗi khi chạy quét cảnh báo: {e}")

if __name__ == "__main__":
    quet_va_gui_canh_bao()