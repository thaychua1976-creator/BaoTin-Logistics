## HÀM NÀY DÙNG ĐỂ CẤU HÌNH GIÁ LIÊN QUAN THỦ TỤC HẢI QUAN: TỜ KHAI/ C/O
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid  
import json

from declare_hq_manager import (
    save_bang_gia_hai_quan_transaction, 
    update_bang_gia_hai_quan_transaction, 
    delete_bang_gia_hai_quan_transaction 
)
from utils_core import parse_money_input
from audit_logger import ghi_log_he_thong

db = st.session_state.get('db')

# Lấy chính xác username từ phiên đăng nhập thực tế của người dùng, nếu không có mặc định là 'Admin'
current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(query, params=None):
    return db.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🏢 NHẬP SỐ LIỆU BÁO GIÁ THỦ TỤC HẢI QUAN </h3>", unsafe_allow_html=True)
st.divider()

st.title("🚢 Quản Lý Nghiệp Vụ Hải Quan")
    
# Lấy danh sách khách hàng qua CACHE thay vì gọi DB thủ công
try:
    df_kh = get_cached_master_data("SELECT id, ten_khach_hang FROM khach_hang")
    dict_kh = {row['ten_khach_hang']: row['id'] for _, row in df_kh.iterrows()} if isinstance(df_kh, pd.DataFrame) and not df_kh.empty else {}
    list_kh = list(dict_kh.keys())
except Exception as e:
    st.error(f"❌ Lỗi tải danh sách khách hàng: {e}")
    dict_kh, list_kh = {}, []

tab1, tab2, tab3 = st.tabs([
    "➕ 1. Tạo Cấu Hình Giá", 
    "✏️ 2. Sửa Cấu Hình Hàng Loạt", 
    "🗑️ 3. Xóa Cấu Hình Giá"
])

nhom_dv_list = [
    "Nhập Cont", "Nhập Lẻ", "Xuất Cont","Xin số Cont/Seal","Phí thanh khoản","Tạm nhập tái xuất",
    "Xuất Lẻ","Làm C/O","Phí tờ khai","Sửa tờ khai","Ghép tờ khai","Phụ phí luồng",
    "Tờ khai nhánh","Thanh lý tờ khai", "Kiểm hàng hoá NX luồng đỏ"
]

# ==========================================
# TAB 1: CẤU HÌNH BẢNG GIÁ HẢI QUAN (MASTER)
# ==========================================
with tab1:
    st.subheader("Thiết lập giá theo hợp đồng (Continental, Tân Châu, Zhengxing...)")
    
    if "form_tao_bg_key" not in st.session_state:
        st.session_state["form_tao_bg_key"] = "form_bang_gia_hq_1"
        
    try:
        with st.form(st.session_state["form_tao_bg_key"], clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 2, 2])
            
            with col1:
                kh_chon = st.selectbox("Khách hàng", options=list_kh, index=None, placeholder="-- Chọn khách hàng --")
                nhom_dv = st.selectbox("Nhóm dịch vụ", nhom_dv_list, index=None, placeholder="-- Chọn nhóm dịch vụ --")
                
            with col2:
                dia_diem_ui = st.selectbox("Địa điểm thông quan", ["Cảng Biển (Cát Lái...)", "Sân Bay (Tân Sơn Nhất...)"], index=None, placeholder="-- Chọn địa điểm --")
                don_gia = st.text_input("Đơn giá (VNĐ)", value="0", help="Có thể nhập dấu phẩy. VD: 500,000")
                
            with col3:
                phan_loai = st.text_input("Phân loại (Nguyên liệu, <= 50 dòng...)", placeholder="Nhập điều kiện...")
                ghi_chu = st.text_input("Ghi chú bổ sung")
            
            submit_bg = st.form_submit_button("💾 Lưu Cấu Hình Bảng Giá", type="primary")
            
            if submit_bg:
                if not kh_chon or not nhom_dv or not dia_diem_ui:
                    st.error("⚠️ Vui lòng chọn đầy đủ Khách hàng, Nhóm dịch vụ và Địa điểm thông quan!")
                else:
                    map_dia_diem = "San_Bay" if "Sân Bay" in dia_diem_ui else "Cang_Bien"
                    
                    data_dict = {
                        "khach_hang_id": dict_kh[kh_chon],
                        "nhom_dich_vu": nhom_dv,
                        "phan_loai_chi_tiet": phan_loai,
                        "dia_diem_thong_quan": map_dia_diem, 
                        "don_gia_hq": parse_money_input(don_gia), # CHỐNG LỖI VÀ ÉP KIỂU TIỀN TỆ
                        "ghi_chu": ghi_chu
                    }
                    
                    success, msg = save_bang_gia_hai_quan_transaction(db, data_dict, current_user)
                    if success: 
                        clear_master_cache() 
                        st.success(msg)
                        st.session_state["form_tao_bg_key"] = f"form_bang_gia_hq_{uuid.uuid4()}"
                        time.sleep(1)
                        st.rerun()
                    else: 
                        st.error(msg)
    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi không mong muốn ở Form Thêm Mới: {str(e)}")

# ==========================================
# TAB 2: SỬA BẢNG GIÁ HẢI QUAN (DẠNG GRID EXCEL)
# ==========================================
with tab2:
    st.subheader("Chỉnh sửa Bảng giá Hải Quan Hàng Loạt")
    st.info("💡 Hướng dẫn: Click đúp vào ô Đơn Giá, Phân loại hoặc Ghi chú để sửa trực tiếp. Bấm LƯU THAY ĐỔI để chốt.")
    
    try:
        sql_bg = """
            SELECT bg.id, bg.khach_hang_id, kh.ten_khach_hang, bg.nhom_dich_vu, 
                   bg.phan_loai_chi_tiet, bg.dia_diem_thong_quan, bg.don_gia_hq, bg.ghi_chu 
            FROM bang_gia_hai_quan bg
            JOIN khach_hang kh ON bg.khach_hang_id = kh.id
            ORDER BY bg.id DESC
        """
        df_bang_gia = get_cached_master_data(sql_bg)

        if not isinstance(df_bang_gia, pd.DataFrame) or df_bang_gia.empty:
            st.info("📭 Chưa có dữ liệu bảng giá nào để chỉnh sửa.")
        else:
            # 1. Định dạng DataFrame để hiển thị đẹp trên UI
            df_display = df_bang_gia[['id', 'ten_khach_hang', 'nhom_dich_vu', 'phan_loai_chi_tiet', 'dia_diem_thong_quan', 'don_gia_hq', 'ghi_chu']].copy()
            df_display['dia_diem_thong_quan'] = df_display['dia_diem_thong_quan'].replace({'Cang_Bien': 'Cảng Biển', 'San_Bay': 'Sân Bay'})
            
            # FORMAT: Ép kiểu sang int rồi chuyển thành chuỗi có dấu phẩy phân cách nhóm ngàn
            df_display['don_gia_hq'] = df_display['don_gia_hq'].apply(lambda x: f"{int(float(x)):,}" if pd.notnull(x) else "0")

            # 2. Tạo Data Editor
            edited_df = st.data_editor(
                df_display,
                column_config={
                    "id": None, # Ẩn ID khỏi màn hình
                    "ten_khach_hang": st.column_config.TextColumn("Khách Hàng (Không sửa)", disabled=True),
                    "nhom_dich_vu": st.column_config.SelectboxColumn("Nhóm Dịch Vụ", options=nhom_dv_list, required=True),
                    "phan_loai_chi_tiet": st.column_config.TextColumn("Phân Loại"),
                    "dia_diem_thong_quan": st.column_config.SelectboxColumn("Địa Điểm", options=["Cảng Biển", "Sân Bay"], required=True),
                    # ĐỔI THÀNH TEXT COLUMN để người dùng thấy/nhập được dấu phẩy
                    "don_gia_hq": st.column_config.TextColumn("Đơn Giá (VNĐ)", required=True),
                    "ghi_chu": st.column_config.TextColumn("Ghi Chú")
                },
                use_container_width=True,
                num_rows="fixed",
                key="data_editor_bang_gia_hq"
            )

            # 3. Nút Lưu và Xử lý Transaction cập nhật hàng loạt
            if st.button("💾 LƯU THAY ĐỔI TOÀN BỘ BẢNG GIÁ", type="primary"):
                conn = None
                cursor = None
                try:
                    conn = db.pool.get_connection()
                    conn.autocommit = False
                    cursor = conn.cursor()
                    thay_doi_count = 0
                    
                    for idx, row in edited_df.iterrows():
                        orig_row = df_display.loc[idx]
                        
                        # So sánh an toàn: Parse lại số tiền để kiểm tra xem user có thực sự đổi số không (ví dụ: gõ "2000000" vs "2,000,000" là bằng nhau)
                        old_price = parse_money_input(str(orig_row['don_gia_hq']))
                        new_price = parse_money_input(str(row['don_gia_hq']))
                        
                        is_changed = (
                            row['nhom_dich_vu'] != orig_row['nhom_dich_vu'] or
                            row['phan_loai_chi_tiet'] != orig_row['phan_loai_chi_tiet'] or
                            row['dia_diem_thong_quan'] != orig_row['dia_diem_thong_quan'] or
                            row['ghi_chu'] != orig_row['ghi_chu'] or
                            old_price != new_price
                        )
                        
                        if is_changed:
                            real_id = orig_row['id']
                            loc_db = 'San_Bay' if row['dia_diem_thong_quan'] == 'Sân Bay' else 'Cang_Bien'
                            price = new_price # Lưu số đã được parse chuẩn
                            
                            cursor.execute("""
                                UPDATE bang_gia_hai_quan 
                                SET nhom_dich_vu=%s, phan_loai_chi_tiet=%s, dia_diem_thong_quan=%s, don_gia_hq=%s, ghi_chu=%s
                                WHERE id=%s
                            """, (row['nhom_dich_vu'], row['phan_loai_chi_tiet'], loc_db, price, row['ghi_chu'], real_id))
                            
                            if cursor.rowcount > 0:
                                thay_doi_count += 1
                                
                    if thay_doi_count > 0:
                        ghi_log_he_thong(cursor, "QUAN_LY_GIA_HAI_QUAN", 0, current_user, "CAP_NHAT_HANG_LOAT", json.dumps({"so_dong_thay_doi": thay_doi_count}))
                        conn.commit()
                        clear_master_cache()
                        st.success(f"✅ Đã cập nhật thành công {thay_doi_count} cấu hình giá!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        conn.rollback()
                        st.info("💡 Bạn chưa thay đổi thông tin nào trong bảng.")
                        
                except Exception as ex:
                    if conn: conn.rollback()
                    st.error(f"❌ Lỗi SQL khi lưu dữ liệu hàng loạt: {ex}")
                finally:
                    if cursor: cursor.close()
                    if conn: conn.close()
                    
    except Exception as e:
        st.error(f"❌ Lỗi hiển thị bảng giá: {str(e)}")

# ==========================================
# TAB 3: XÓA BẢNG GIÁ HẢI QUAN
# ==========================================
with tab3:
    st.subheader("Xóa Bảng giá Hải Quan")
    
    try:
        if 'df_bang_gia' not in locals() or not isinstance(df_bang_gia, pd.DataFrame) or df_bang_gia.empty:
            st.info("📭 Không có dữ liệu để xóa.")
        else:
            ds_bang_gia = df_bang_gia.to_dict('records')
            bg_opts = {
                r['id']: f"[{r['ten_khach_hang']}] - {r['nhom_dich_vu']} - {r['phan_loai_chi_tiet']} (Giá: {int(r['don_gia_hq']):,})"
                for r in ds_bang_gia
            }
            
            if "key_del_bg" not in st.session_state:
                st.session_state["key_del_bg"] = "sel_del_bg_1"
                
            bg_del_id = st.selectbox("🗑️ Chọn bảng giá cần xóa:", options=list(bg_opts.keys()), index=None, placeholder="-- Vui lòng click chọn 1 bảng giá --", format_func=lambda x: bg_opts[x], key=st.session_state["key_del_bg"])
            
            if bg_del_id:
                st.warning(f"⚠️ Thao tác này sẽ xóa vĩnh viễn cấu hình giá của **{bg_opts[bg_del_id].split('-')[0]}**. Bạn có chắc chắn không?")
                
                if st.button("Xóa Vĩnh Viễn Cấu Hình Này", type="primary"):
                    with st.spinner("Đang xóa dữ liệu..."):
                        success, msg = delete_bang_gia_hai_quan_transaction(db, bg_del_id, current_user)
                        if success:
                            clear_master_cache()
                            st.success(msg)
                            st.session_state["key_del_bg"] = f"sel_del_bg_{uuid.uuid4()}"
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)
    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi ở chức năng Xóa: {str(e)}")