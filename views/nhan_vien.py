import streamlit as st
import pandas as pd
#from st_aggrid import AgGrid, GridOptionsBuilder
import datetime
import time, math
from global_func import save_nhan_vien_transaction
db = st.session_state['db']
tab1, tab2, tab3 = st.tabs(["📋 Danh sách Nhân viên", "➕ Thêm Nhân viên Mới", "📝 Sửa thông tin & Thôi việc"])

# ==========================================
# CSS ẨN HƯỚNG DẪN "PRESS ENTER TO SUBMIT"
# ==========================================
hide_enter_submit_css = """
<style>
    /* Nhắm mục tiêu chính xác vào thẻ div chứa dòng chữ hướng dẫn của Streamlit */
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
"""
# Thực thi CSS
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)
# Thêm dòng này để định nghĩa current_user
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
        df_nv_list = db.execute_query(sql_nv)
        
        if isinstance(df_nv_list, pd.DataFrame) and not df_nv_list.empty:
            df_nv_list['Trạng thái'] = df_nv_list['Tình trạng'].apply(lambda x: "🟢 Đang làm việc" if x == "Dang_Lam_Viec" else "🔴 Đã nghỉ việc")
            df_nv_list['Hạn Bằng'] = pd.to_datetime(df_nv_list['Hạn Bằng']).dt.strftime('%d-%m-%Y').fillna("---")
            df_nv_list['Hạn Tập Huấn'] = pd.to_datetime(df_nv_list['Hạn Tập Huấn']).dt.strftime('%d-%m-%Y').fillna("---")
            df_nv_list = df_nv_list.drop(columns=['Tình trạng'])
            # Sử dụng st.dataframe thay cho AgGrid để mượt mà trên thiết bị di động
            #st.dataframe(
            #    df_nv_list,
            #    use_container_width=True,  # Tự động giãn cột vừa khít màn hình
            #    hide_index=True            # Ẩn cột số thứ tự (index) cho gọn gàng
            #)
            # --- BẮT ĐẦU XỬ LÝ PHÂN TRANG VÀ HIỂN THỊ TẤT CẢ ---
        
            # Tạo thanh chọn chế độ hiển thị (đặt ngang hàng để tiết kiệm diện tích)
            col_opt1, col_opt2 = st.columns([1, 6])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"])
            
            if che_do_xem == "Tất cả":
                # CHẾ ĐỘ 1: HIỂN THỊ TẤT CẢ (Không dùng nút phân trang)
                st.caption(f"Đang hiển thị toàn bộ {len(df_nv_list)} nhân viên.")
                st.dataframe(
                    df_nv_list,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                # CHẾ ĐỘ 2: PHÂN TRANG 10 DÒNG
                rows_per_page = 10
                total_rows = len(df_nv_list)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    # Khởi tạo và bảo vệ biến nhớ
                    if 'page_nv' not in st.session_state:
                        st.session_state['page_nv'] = 1
                        
                    if st.session_state['page_nv'] < 1:
                        st.session_state['page_nv'] = 1
                    elif st.session_state['page_nv'] > total_pages:
                        st.session_state['page_nv'] = total_pages
                        
                    # Dàn 3 cột cho nút bấm
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

                    # Tính toán vị trí và cắt dữ liệu
                    start_idx = (st.session_state['page_nv'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page = df_nv_list.iloc[start_idx:end_idx]
                    
                    # In bảng 10 dòng ra màn hình
                    st.dataframe(
                        df_page,
                        use_container_width=True,
                        hide_index=True
                    )
            #gb = GridOptionsBuilder.from_dataframe(df_nv_list)
            #gb.configure_default_column(resizable=True, filter=True, sortable=True, minWidth=140)
            #gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
            # 2. Đổi fit_columns_on_grid_load thành False ở hàm gọi AgGrid
            #AgGrid(df_display, gridOptions=gb.build(), custom_css=custom_css, theme="streamlit", fit_columns_on_grid_load=False, width="100%")
            #AgGrid(df_nv_list, gridOptions=gb.build(), theme="streamlit", fit_columns_on_grid_load=False, width="100%")
        else:
            st.info("Chưa có dữ liệu nhân viên.")
    except Exception as e:
        st.error(f"⚠️ Không thể tải danh sách nhân viên. Lỗi: {e}")

# ==========================================
# TAB 2: THÊM NHÂN VIÊN
# ==========================================
with tab2:
    with st.form("form_them_nv", clear_on_submit=True, enter_to_submit=False):
        st.subheader("Thông tin cơ bản")
        c1, c2, c3 = st.columns(3)
        ma_nv = c1.text_input("Mã nhân viên*", placeholder="VD: NV001")
        ten_nv = c2.text_input("Họ và tên*", placeholder="VD: Nguyễn Văn A")
        sdt_nv = c3.text_input("Số điện thoại*", placeholder="VD: 0912345678")
        
        st.subheader("Thông tin Pháp lý & Bằng lái")
        c4, c5, c6 = st.columns(3)
        cccd = c4.text_input("Số CCCD")
        gplx = c5.text_input("Số GPLX")
        hang_gplx = c6.selectbox("Hạng Bằng", ["A1","D","D2","C","CE", "E", "FC", "FD", "B2", "Khác"], index=0)
        
        c7, c8 = st.columns(2)
        han_gplx = c7.date_input("Ngày Hết Hạn Bằng Lái", value=datetime.date.today() + datetime.timedelta(days=365),format="DD/MM/YYYY")
        han_tth = c8.date_input("Ngày Hết Hạn Thẻ Tập Huấn", value=datetime.date.today() + datetime.timedelta(days=365),format="DD/MM/YYYY")
        
        # 1. Tạo một từ điển map giữa Mã trong CSDL và Tên hiển thị
        dict_chuc_vu = {
            "Tai_Chinh": "Tài xế chính",
            "Tai_Phu": "Tài xế phụ",
            "Van_Phong": "NV văn phòng",
            "Dieu_Hanh": "Điều hành"
        }

        # 2. Đưa vào Selectbox rất gọn gàng
        loai_nv = st.selectbox(
            "Chức vụ", 
            options=list(dict_chuc_vu.keys()), 
            format_func=lambda x: dict_chuc_vu[x]
        )
        #loai_nv = st.selectbox("Chức vụ", ["Tai_Chinh", "Tai_Phu", "Van_Phong", "Dieu_Hanh"], format_func=lambda x: "Tài xế chính" if x == "Tai_Chinh" else ("Tài xế phụ" if x == "Tai_Phu" else ("NV văn phòng " if x == "Van_Phong" else "Dieu_Hanh")))
        #st.selectbox("Chức vụ", ["Tai_Chinh", "Tai_Phu", "Van_Phong","Dieu_Hanh"], index=["Tai_Chinh", "Tai_Phu", "Van_Phong","Dieu_Hanh"].index(nv_data['loai_nhan_vien']))
        
        if st.form_submit_button("💾 Lưu Nhân Viên", type="primary"):
            if not ma_nv or not ten_nv or not sdt_nv:
                st.error("⚠️ Vui lòng điền đầy đủ Mã, Họ tên và Số điện thoại!")
            else:
                han_gplx_db = han_gplx.strftime('%Y-%m-%d')
                han_tth_db = han_tth.strftime('%Y-%m-%d')
                nv_data = (ma_nv, ten_nv, sdt_nv, cccd, gplx, hang_gplx, han_gplx_db, han_tth_db, loai_nv)
                
                # GỌI HÀM TRANSACTION ĐỂ THÊM
                is_ok, msg = save_nhan_vien_transaction(db.pool, action='ADD', nv_data=nv_data, current_user=current_user)
                
                if is_ok:
                    st.success("✅ Đã thêm nhân viên mới thành công!")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi: {msg}")
                

# ==========================================
# TAB 3: SỬA THÔNG TIN & THÔI VIỆC
# ==========================================
with tab3:
    if "reset_nv_form" not in st.session_state: st.session_state["reset_nv_form"] = 0
    df_nv_active = db.execute_query("SELECT * FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' ORDER BY ho_ten")
    
    if isinstance(df_nv_active, pd.DataFrame) and not df_nv_active.empty:
        dict_nv = {row['id']: f"{row['ma_nhan_vien']} - {row['ho_ten']}" for _, row in df_nv_active.iterrows()}
        nv_id = st.selectbox("🔍 Chọn nhân viên cần thao tác:", options=list(dict_nv.keys()), index=None, format_func=lambda x: dict_nv[x], key=f"nv_key_{st.session_state['reset_nv_form']}")
        
        if nv_id is not None:
            nv_data = df_nv_active[df_nv_active['id'] == nv_id].iloc[0]
            with st.form("form_update_nv"):
                c_edit1, c_edit2, c_edit3 = st.columns(3)
                edit_ma = c_edit1.text_input("Mã NV", value=nv_data['ma_nhan_vien'])
                edit_ten = c_edit2.text_input("Họ tên", value=nv_data['ho_ten'])
                edit_sdt = c_edit3.text_input("SĐT", value=nv_data['so_dien_thoai'])
                
                c_edit4, c_edit5, c_edit6 = st.columns(3)
                edit_cccd = c_edit4.text_input("CCCD", value=nv_data['cccd'] if pd.notna(nv_data['cccd']) else "")
                edit_gplx = c_edit5.text_input("GPLX", value=nv_data['giay_phep_lai_xe'] if pd.notna(nv_data['giay_phep_lai_xe']) else "")
                opts_hang = ["C", "E", "FC", "FD", "B2", "Khác"]
                edit_hang = c_edit6.selectbox("Hạng Bằng", opts_hang, index=opts_hang.index(nv_data['hang_gplx']) if nv_data['hang_gplx'] in opts_hang else 0)
                
                c_edit7, c_edit8 = st.columns(2)
                edit_han_gplx = c_edit7.date_input("Hạn Bằng", value=nv_data['han_gplx'] if pd.notna(nv_data['han_gplx']) else datetime.date.today())
                edit_han_tth = c_edit8.date_input("Hạn Thẻ Tập Huấn", value=nv_data['han_the_tap_huan'] if pd.notna(nv_data['han_the_tap_huan']) else datetime.date.today())
                
                edit_loai = st.selectbox("Chức vụ", ["Tai_Chinh", "Tai_Phu", "Van_Phong","Dieu_Hanh"], index=["Tai_Chinh", "Tai_Phu", "Van_Phong","Dieu_Hanh"].index(nv_data['loai_nhan_vien']))
                
                col_btn1, col_btn2 = st.columns(2)
                # 1. NÚT LƯU THAY ĐỔI
                if col_btn1.form_submit_button("🔄 Lưu thay đổi", type="primary"):
                    edit_han_gplx_db = edit_han_gplx.strftime('%Y-%m-%d')
                    edit_han_tth_db = edit_han_tth.strftime('%Y-%m-%d')
                    update_data = (edit_ma, edit_ten, edit_sdt, edit_cccd, edit_gplx, edit_hang, edit_han_gplx_db, edit_han_tth_db, edit_loai)
                    
                    # GỌI HÀM TRANSACTION ĐỂ SỬA
                    is_ok, msg = save_nhan_vien_transaction(db.pool, action='UPDATE', nv_data=update_data, nv_id=nv_id, current_user=current_user)
                    
                    if is_ok:
                        st.success("✅ Cập nhật thành công!")
                        st.session_state["reset_nv_form"] += 1
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi: {msg}")
                        
                # 2. NÚT BÁO CÁO NGHỈ VIỆC
                if col_btn2.form_submit_button("🚫 Báo Cáo Nghỉ Việc"):
                    # GỌI HÀM TRANSACTION ĐỂ XOÁ
                    is_ok, msg = save_nhan_vien_transaction(db.pool, action='DELETE', nv_data=None, nv_id=nv_id, current_user=current_user)
                    
                    if is_ok:
                        st.success("✅ Đã xoá (chuyển trạng thái nghỉ việc) thành công!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi: {msg}")