import streamlit as st
import pandas as pd
import datetime
import time, math
from hr_system_manager import save_nhan_vien_transaction

db = st.session_state['db']

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(_db_instance, query, params=None):
    return _db_instance.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

# Khởi tạo trạng thái mặc định cho form bằng các BỘ ĐẾM (Counters) để xóa form 100%
def init_nv_session_state():
    if 'nv_add_counter' not in st.session_state: st.session_state['nv_add_counter'] = 0
    if 'nv_edit_counter' not in st.session_state: st.session_state['nv_edit_counter'] = 0

init_nv_session_state()

tab1, tab2, tab3 = st.tabs(["📋 Danh sách Nhân viên", "➕ Thêm Nhân viên Mới", "📝 Sửa thông tin & Thôi việc"])

# ==========================================
# CSS ẨN HƯỚNG DẪN "PRESS ENTER TO SUBMIT"
# ==========================================
hide_enter_submit_css = """
<style>
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)
current_user = st.session_state.get('username', 'Admin')


# ==========================================
# TAB 1: DANH SÁCH NHÂN VIÊN
# ==========================================
with tab1:
    try:
        sql_nv = """
            SELECT 
                id AS 'Mã', ma_nhan_vien AS 'Mã NV', ho_ten AS 'Họ và Tên', 
                so_dien_thoai AS 'Số ĐT', cccd AS 'CCCD', giay_phep_lai_xe AS 'GPLX', 
                hang_gplx AS 'Hạng', han_gplx AS 'Hạn Bằng', han_the_tap_huan AS 'Hạn Tập Huấn',
                loai_nhan_vien AS 'Chức vụ', trang_thai AS 'Tình trạng' 
            FROM nhan_vien ORDER BY id ASC
        """
        df_nv_list = get_cached_master_data(db, sql_nv)
        
        if isinstance(df_nv_list, pd.DataFrame) and not df_nv_list.empty:
            df_nv_list['Trạng thái'] = df_nv_list['Tình trạng'].apply(lambda x: "🟢 Đang làm việc" if x == "Dang_Lam_Viec" else "🔴 Đã nghỉ việc")
            df_nv_list['CCCD'] = df_nv_list['CCCD'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() != 'nan' else '')
            df_nv_list['GPLX'] = df_nv_list['GPLX'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() != 'nan' else '')
            df_nv_list['Hạng'] = df_nv_list['Hạng'].fillna('Khác').apply(lambda x: str(x).strip() if str(x).strip().lower() != 'nan' else 'Khác')
            
            df_nv_list['Hạn Bằng'] = pd.to_datetime(df_nv_list['Hạn Bằng'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("---")
            df_nv_list['Hạn Tập Huấn'] = pd.to_datetime(df_nv_list['Hạn Tập Huấn'], errors='coerce').dt.strftime('%d/%m/%Y').fillna("---")
            
            df_nv_list = df_nv_list.drop(columns=['Tình trạng'])
            
            col_opt1, col_opt2 = st.columns([1, 7])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"])
            
            if che_do_xem == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_nv_list)} nhân viên.")
                st.dataframe(df_nv_list, use_container_width=True, hide_index=True)
            else:
                rows_per_page = 10
                total_rows = len(df_nv_list)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    if 'page_nv' not in st.session_state:
                        st.session_state['page_nv'] = 1
                        
                    if st.session_state['page_nv'] < 1:
                        st.session_state['page_nv'] = 1
                    elif st.session_state['page_nv'] > total_pages:
                        st.session_state['page_nv'] = total_pages
                        
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        if st.button("⬅️ Trước", key="btn_prev_nv", disabled=(st.session_state['page_nv'] <= 1)):
                            if st.session_state['page_nv'] > 1:
                                st.session_state['page_nv'] -= 1
                                st.rerun()
                            
                    with col3:
                        if st.button("Sau ➡️", key="btn_next_nv", disabled=(st.session_state['page_nv'] >= total_pages)):
                            if st.session_state['page_nv'] < total_pages:
                                st.session_state['page_nv'] += 1
                                st.rerun()
                            
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_nv']} / {total_pages}</div>", unsafe_allow_html=True)

                    start_idx = (st.session_state['page_nv'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page = df_nv_list.iloc[start_idx:end_idx]
                    
                    st.dataframe(df_page, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu nhân viên.")
    except Exception as e:
        st.error(f"⚠️ Không thể tải danh sách nhân viên. Lỗi: {e}")

# ==========================================
# TAB 2: THÊM NHÂN VIÊN (ÁP DỤNG DYNAMIC KEY ĐỂ RESET)
# ==========================================
with tab2:
    ac = st.session_state['nv_add_counter']

    st.subheader("Thông tin cơ bản")
    c1, c2, c3 = st.columns(3)
    ma_nv = c1.text_input("Mã nhân viên*", placeholder="VD: NV001", key=f"add_ma_nv_{ac}")
    ten_nv = c2.text_input("Họ và tên*", placeholder="VD: Nguyễn Văn A", key=f"add_ten_nv_{ac}")
    sdt_nv = c3.text_input("Số điện thoại*", placeholder="VD: 0912345678", key=f"add_sdt_nv_{ac}")
    
    st.subheader("Thông tin Pháp lý & Bằng lái")
    c4, c5, c6 = st.columns(3)
    cccd = c4.text_input("Số CCCD", key=f"add_cccd_{ac}")
    gplx = c5.text_input("Số GPLX", key=f"add_gplx_{ac}")
    hang_gplx = c6.selectbox("Hạng Bằng", ["A1","D","D2","C","CE", "E", "FC", "FD", "B2", "Khác"], index=0, key=f"add_hang_{ac}")
    
    c7, c8 = st.columns(2)
    han_gplx = c7.date_input("Ngày Hết Hạn Bằng Lái", value=datetime.date.today() + datetime.timedelta(days=365), format="DD/MM/YYYY", key=f"add_han_gplx_{ac}")
    han_tth = c8.date_input("Ngày Hết Hạn Thẻ Tập Huấn", value=datetime.date.today() + datetime.timedelta(days=365), format="DD/MM/YYYY", key=f"add_han_tth_{ac}")
    
    dict_chuc_vu = {
        "Tai_Chinh": "Tài xế chính",
        "Tai_Phu": "Tài xế phụ",
        "Van_Phong": "NV văn phòng",
        "Dieu_Hanh": "Điều hành"
    }

    loai_nv = st.selectbox("Chức vụ", options=list(dict_chuc_vu.keys()), format_func=lambda x: dict_chuc_vu[x], key=f"add_loai_{ac}")
    
    if st.button("💾 Lưu Nhân Viên", type="primary", use_container_width=True):
        if not ma_nv or not ten_nv or not sdt_nv:
            st.error("⚠️ Vui lòng điền đầy đủ Mã, Họ tên và Số điện thoại!")
        else:
            ma_nv_clean = ma_nv.strip().upper()
            ten_nv_clean = ten_nv.strip().upper()
            han_gplx_db = han_gplx.strftime('%Y-%m-%d')
            han_tth_db = han_tth.strftime('%Y-%m-%d')
            nv_data = (ma_nv_clean, ten_nv_clean, sdt_nv, cccd, gplx, hang_gplx, han_gplx_db, han_tth_db, loai_nv)
            
            is_ok, msg = save_nhan_vien_transaction(db.pool, action='ADD', nv_data=nv_data, current_user=current_user)
            
            if is_ok:
                clear_master_cache()
                st.success("✅ Đã thêm nhân viên mới thành công!")
                st.balloons()
                
                # --- TĂNG BIẾN ĐẾM ĐỂ XÓA TRẮNG FORM ---
                st.session_state['nv_add_counter'] += 1
                
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(f"❌ Lỗi: {msg}")
                

# ==========================================
# TAB 3: SỬA THÔNG TIN & THÔI VIỆC
# ==========================================
with tab3:
    ec = st.session_state['nv_edit_counter']
    df_nv_active = get_cached_master_data(db, "SELECT * FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' ORDER BY ho_ten")
    
    if isinstance(df_nv_active, pd.DataFrame) and not df_nv_active.empty:
        dict_nv = {row['id']: f"{row['ma_nhan_vien']} - {row['ho_ten']}" for _, row in df_nv_active.iterrows()}
        
        # Áp dụng Dynamic Key vào ô tìm kiếm để nó có thể tự reset về None
        nv_id = st.selectbox(
            "🔍 Chọn nhân viên cần thao tác:", 
            options=list(dict_nv.keys()), 
            index=None, 
            format_func=lambda x: dict_nv[x], 
            key=f"select_edit_nv_{ec}"
        )
        
        if nv_id is not None:
            nv_data = df_nv_active[df_nv_active['id'] == nv_id].iloc[0]
            
            def get_safe_val(key, default=""):
                val = nv_data.get(key)
                if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                    return default
                return str(val).strip()

            def get_safe_date(key):
                val = nv_data.get(key)
                if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                    return datetime.date.today()
                try:
                    return pd.to_datetime(val).date()
                except:
                    return datetime.date.today()

            with st.form("form_update_nv", clear_on_submit=True):
                c_edit1, c_edit2, c_edit3 = st.columns(3)
                edit_ma = c_edit1.text_input("Mã NV", value=get_safe_val('ma_nhan_vien'))
                edit_ten = c_edit2.text_input("Họ tên", value=get_safe_val('ho_ten'))
                edit_sdt = c_edit3.text_input("SĐT", value=get_safe_val('so_dien_thoai'))
                
                c_edit4, c_edit5, c_edit6 = st.columns(3)
                edit_cccd = c_edit4.text_input("CCCD", value=get_safe_val('cccd'))
                edit_gplx = c_edit5.text_input("GPLX", value=get_safe_val('giay_phep_lai_xe'))
                
                opts_hang = ["C", "E", "FC", "FD", "B2", "Khác", "A1", "D", "D2"]
                db_hang = get_safe_val('hang_gplx', 'C')
                idx_hang = opts_hang.index(db_hang) if db_hang in opts_hang else 0
                edit_hang = c_edit6.selectbox("Hạng Bằng", opts_hang, index=idx_hang)
                
                c_edit7, c_edit8 = st.columns(2)
                edit_han_gplx = c_edit7.date_input("Hạn Bằng", value=get_safe_date('han_gplx'), format="DD/MM/YYYY")
                edit_han_tth = c_edit8.date_input("Hạn Thẻ Tập Huấn", value=get_safe_date('han_the_tap_huan'), format="DD/MM/YYYY")
                
                opts_chuc_vu = ["Tai_Chinh", "Tai_Phu", "Van_Phong", "Dieu_Hanh"]
                db_loai = get_safe_val('loai_nhan_vien', 'Tai_Chinh')
                idx_loai = opts_chuc_vu.index(db_loai) if db_loai in opts_chuc_vu else 0
                edit_loai = st.selectbox("Chức vụ", opts_chuc_vu, index=idx_loai)
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.form_submit_button("🔄 Lưu thay đổi", type="primary"):
                    edit_ma_clean = edit_ma.strip().upper()
                    edit_ten_clean = edit_ten.strip().upper()
                    edit_han_gplx_db = edit_han_gplx.strftime('%Y-%m-%d')
                    edit_han_tth_db = edit_han_tth.strftime('%Y-%m-%d')
                    update_data = (edit_ma_clean, edit_ten_clean, edit_sdt, edit_cccd, edit_gplx, edit_hang, edit_han_gplx_db, edit_han_tth_db, edit_loai)
                    
                    is_ok, msg = save_nhan_vien_transaction(db.pool, action='UPDATE', nv_data=update_data, nv_id=nv_id, current_user=current_user)
                    
                    if is_ok:
                        clear_master_cache()
                        st.success("✅ Cập nhật thành công!")
                        
                        # Tăng đếm để ẩn form
                        st.session_state['nv_edit_counter'] += 1
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi: {msg}")
                        
                if col_btn2.form_submit_button("🚫 Báo Cáo Nghỉ Việc"):
                    is_ok, msg = save_nhan_vien_transaction(db.pool, action='DELETE', nv_data=None, nv_id=nv_id, current_user=current_user)
                    
                    if is_ok:
                        clear_master_cache()
                        st.success("✅ Đã xoá (chuyển trạng thái nghỉ việc) thành công!")
                        
                        # --- CẬP NHẬT: Tăng đếm khi xóa thành công để ẩn form ---
                        st.session_state['nv_edit_counter'] += 1
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi: {msg}")