import datetime
import pandas as pd
import io
import os
from apscheduler.schedulers.background import BackgroundScheduler
# Import các hàm tiện ích đã có trong hệ thống
from audit_logger import ghi_log_he_thong
from utils_core import gui_file_excel_len_telegram

def task_gui_bao_cao_phap_ly_tu_dong(db_pool):
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        today = pd.Timestamp(datetime.date.today())
        
        # Hàm kiểm tra hạn (30 ngày)
        def is_danger(han):
            if pd.isna(han): return False
            return (pd.Timestamp(han) - today).days <= 30

        # --- 1. KIỂM TRA PHÁP LÝ XE ---
        sql_xe = "SELECT bien_so_xe, han_dang_kiem, han_bao_hiem_ds, han_phu_hieu FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'"
        df_xe = pd.read_sql(sql_xe, conn)
        df_xe_danger = df_xe[df_xe.apply(lambda r: is_danger(r['han_dang_kiem']) or is_danger(r['han_bao_hiem_ds']) or is_danger(r['han_phu_hieu']), axis=1)]

        # --- 2. KIỂM TRA PHÁP LÝ TÀI XẾ ---
        sql_tx = "SELECT ho_ten, han_gplx, han_the_tap_huan FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' AND loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu')"
        df_tx = pd.read_sql(sql_tx, conn)
        df_tx_danger = df_tx[df_tx.apply(lambda r: is_danger(r['han_gplx']) or is_danger(r['han_the_tap_huan']), axis=1)]

        # --- 3. TỔNG HỢP VÀ GỬI BÁO CÁO NẾU CÓ CẢNH BÁO ---
        if not df_xe_danger.empty or not df_tx_danger.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                if not df_xe_danger.empty: df_xe_danger.to_excel(writer, sheet_name='Canh_Bao_Xe', index=False)
                if not df_tx_danger.empty: df_tx_danger.to_excel(writer, sheet_name='Canh_Bao_Tai_Xe', index=False)
            
            file_name = f"Bao_Cao_Phap_Ly_Tong_Hop_{datetime.date.today().strftime('%d%m%Y')}.xlsx"
            caption = (f"🔔 [AUTO-ALERT] Báo cáo pháp lý tới hạn!\n"
                       f"- Số xe tới hạn: {len(df_xe_danger)}\n"
                       f"- Số tài xế tới hạn: {len(df_tx_danger)}")
            
            success, _ = gui_file_excel_len_telegram(buffer, file_name, caption)
            
            if success:
                ghi_log_he_thong(cursor, "HE_THONG", 0, "AUTO_BOT", "GUI_BAO_CAO_PHAP_LY_TONG_HOP", {"xe": len(df_xe_danger), "tx": len(df_tx_danger)})
                conn.commit()
                
    except Exception as e:
        print(f"Lỗi tác vụ tự động: {e}")
    finally:
        cursor.close()
        conn.close()