import streamlit as st
import pandas as pd
import datetime
import urllib3
from trip_manager import goi_gps_theo_thoi_gian_tuy_chinh


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  



# 1. Lấy kết nối Database
if 'db' not in st.session_state:
    st.error("Chưa kết nối cơ sở dữ liệu.")
    st.stop()
db_chinh = st.session_state['db']

# 2. Lấy ID tài xế
TAI_XE_ID_HIENTAI = st.session_state.get('nhan_vien_id')


# ==========================================================
# CÁC HÀM XỬ LÝ DỮ LIỆU
# ==========================================================

import time

def tai_xe_chot_chuyen_va_goi_gps(db_instance, chuyen_di_id):
    """
    Hàm cầu nối: Tự động trích xuất thời gian bắt đầu từ DB và gọi API GPS.
    """
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Lấy thông tin thời gian bắt đầu và ngày chuyến đi từ hệ thống
        sql_get = "SELECT thoi_gian_bat_dau, ngay_chuyen_di FROM chuyen_di WHERE id = %s"
        cursor.execute(sql_get, (chuyen_di_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "Không tìm thấy dữ liệu chuyến đi trong hệ thống."
            
        tg_ket_thuc = datetime.datetime.now()
        
        # Nếu tài xế có bấm "XÁC NHẬN BẮT ĐẦU CHẠY", hệ thống đã lưu thoi_gian_bat_dau
        if row.get('thoi_gian_bat_dau'):
            tg_bat_dau = row['thoi_gian_bat_dau']
        else:
            # Rủi ro: Tài xế quên bấm bắt đầu -> Lấy mặc định 00:00:00 của ngày chuyến đi
            ngay_cd = row['ngay_chuyen_di']
            if isinstance(ngay_cd, str):
                ngay_cd = datetime.datetime.strptime(ngay_cd.strip()[:10], '%Y-%m-%d').date()
            tg_bat_dau = datetime.datetime.combine(ngay_cd, datetime.time.min)
            
    except Exception as e:
        return False, f"Lỗi truy vấn Database khi chốt chuyến: {e}"
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
        
    # Gọi lại hàm GPS chuẩn với các mốc thời gian đã được tự động xác định
    return goi_gps_theo_thoi_gian_tuy_chinh(db_instance, chuyen_di_id, tg_bat_dau, tg_ket_thuc)
############################################################
def get_chuyen_di_cua_tai_xe(db_instance, tx_id):
    tx_id_chuan = int(tx_id) if pd.notna(tx_id) else 0
    sql = f"""
        SELECT 
            cd.id, cd.xe_id, x.bien_so_xe,
            cd.dia_diem_giao_nhan, cd.trang_thai_chuyen, cd.ngay_chuyen_di 
        FROM chuyen_di cd
        JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
        LEFT JOIN xe x ON cd.xe_id = x.id
        WHERE ctx.tai_xe_id = {tx_id_chuan} 
          AND TRIM(cd.trang_thai_chuyen) IN ('Tao_Moi', 'Dang_Di')
    """
    try:
        df = db_instance.execute_query(sql)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.to_dict('records')
        return []
    except Exception as e:
        st.error(f"⚠️ Lỗi truy vấn chuyến đi: {e}")
        return []

def lay_chuyen_di_dang_chay(db_instance, tx_id):
    """Hàm mới: Tự động tìm ID chuyến đi và ID xe ĐANG CHẠY của tài xế"""
    tx_id_chuan = int(tx_id) if pd.notna(tx_id) else 0
    sql = f"""
        SELECT cd.id AS chuyen_di_id, cd.xe_id 
        FROM chuyen_di cd
        JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
        WHERE ctx.tai_xe_id = {tx_id_chuan} 
          AND cd.trang_thai_chuyen = 'Dang_Di'
        ORDER BY cd.id DESC LIMIT 1
    """
    try:
        df = db_instance.execute_query(sql)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.iloc[0]['chuyen_di_id'], df.iloc[0]['xe_id']
        return None, None
    except Exception as e:
        st.error(f"Lỗi truy vấn chuyến đi đang chạy: {e}")
        return None, None

def cap_nhat_bat_dau_chay(db_instance, chuyen_di_id):
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor()
        sql = "UPDATE chuyen_di SET trang_thai_chuyen = 'Dang_Di', thoi_gian_bat_dau = %s WHERE id = %s"
        cursor.execute(sql, (datetime.datetime.now(), chuyen_di_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Lỗi: {e}")
        return False
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()
##################################



#############################################################

def luu_chi_phi_nhien_lieu(db_instance, xe_id, chuyen_di_id, data):
    try:
        conn = db_instance.pool.get_connection()
        cursor = conn.cursor()
        
        sql = """
            UPDATE chuyen_di 
            SET so_lit_xang = COALESCE(so_lit_xang, 0) + %s, 
                tien_xang = COALESCE(tien_xang, 0) + %s
            WHERE id = %s AND xe_id = %s
        """
        
        # BẮT BỆNH Ở ĐÂY: Ép kiểu về chuẩn Python (int/float) để xóa bỏ kiểu dữ liệu int64 của Pandas
        so_lit_chuan = float(data['so_lit'])
        tong_tien_chuan = int(data['tong_tien'])
        chuyen_di_id_chuan = int(chuyen_di_id)
        xe_id_chuan = int(xe_id)
        
        # Đưa các biến đã được ép kiểu vào câu lệnh execute
        cursor.execute(sql, (so_lit_chuan, tong_tien_chuan, chuyen_di_id_chuan, xe_id_chuan))
        
        if cursor.rowcount == 0:
            st.warning(f"⚠️ Không tìm thấy Chuyến đi ID {chuyen_di_id} gắn với Xe ID {xe_id}. Dữ liệu chưa được lưu!")
            conn.rollback()
            return False
            
        conn.commit()
        return True
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback()
        st.error(f"Lỗi cập nhật Database: {e}")
        return False
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

# ==========================================================
# GIAO DIỆN APP DI ĐỘNG TÀI XẾ
# ==========================================================
st.markdown("<h3 style='text-align: center; color: #1E3A8A;'>BẢO TÍN LOGISTICS</h3>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 14px;'>Phiên bản dành cho Tài xế</p>", unsafe_allow_html=True)
st.divider()

# --- PHẦN 1: QUẢN LÝ DANH SÁCH CHUYẾN ĐI ---
ds_chuyen = get_chuyen_di_cua_tai_xe(db_chinh, TAI_XE_ID_HIENTAI)

if not ds_chuyen:
    st.info("🎉 Hiện tại bạn không có chuyến đi nào đang chờ xử lý.")
else:
    for chuyen in ds_chuyen:
        with st.container(border=True):
            st.markdown(f"📍 **Điểm đến:** {chuyen['dia_diem_giao_nhan']}")
            st.markdown(f"🚛 **Xe phụ trách:** {chuyen['bien_so_xe'] if pd.notna(chuyen['bien_so_xe']) else 'Chưa gán xe'}")
            st.markdown(f"📅 **Ngày tạo:** {chuyen['ngay_chuyen_di'].strftime('%d/%m/%Y') if pd.notna(chuyen['ngay_chuyen_di']) else ''}")
            st.markdown(f"📅 **Mã chuyến đi:** {chuyen['id']}")
            
            if chuyen['trang_thai_chuyen'] == 'Tao_Moi':
                if st.button("🚀 XÁC NHẬN BẮT ĐẦU CHẠY", key=f"start_{chuyen['id']}", type="primary", use_container_width=True):
                    if cap_nhat_bat_dau_chay(db_chinh, chuyen['id']):
                        st.toast("✅ Đã ghi nhận thời gian xuất phát!")
                        st.rerun()
                        
            elif chuyen['trang_thai_chuyen'] == 'Dang_Di':
                st.markdown("""<style>div.stButton > button:first-child {background-color: #059669; color: white;}</style>""", unsafe_allow_html=True)
                
                if st.button("✅ ĐÃ GIAO HÀNG XONG", key=f"done_{chuyen['id']}", use_container_width=True):
                    with st.spinner("Đang chốt chuyến và đồng bộ dữ liệu GPS..."):
                        
                        # Sử dụng hàm trung gian thay cho hàm cũ
                        success, msg = tai_xe_chot_chuyen_va_goi_gps(db_chinh, chuyen['id'])
                        
                        if success:
                            st.balloons()
                            st.toast("🎉 Chúc mừng bạn đã hoàn thành chuyến đi!")
                            st.success(msg)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ Có lỗi xảy ra: {msg}")
