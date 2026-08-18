import streamlit as st
import datetime
from hr_system_manager import thuc_hien_sao_luu_db_python

db = st.session_state.get('db')
current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🛡️ QUẢN LÝ SAO LƯU & AN ATÒAN DỮ LIỆU CƠ SỞ DỮ LIỆU</h3>", unsafe_allow_html=True)
st.divider()

col_info, col_action = st.columns([1, 1])

with col_info:
    st.markdown("#### 📌 Thông Tin Hệ Thống Sao Lưu")
    st.info("""
    * **Phạm vi sao lưu:** Toàn bộ bảng dữ liệu (`xe`, `chuyen_di`, `nhan_vien`, `khach_hang`, `audit_logs`...).
    * **Định dạng kết xuất:** File kịch bản SQL (`.sql`).
    * **Mã hóa ký tự:** UTF-8 (Đảm bảo không lỗi tiếng Việt).
    * **Tính an toàn:** Đã bao gồm các cờ vô hiệu hóa ràng buộc khóa ngoại (`FOREIGN_KEY_CHECKS`) để khôi phục nhanh chóng.
    """)

with col_action:
    st.markdown("#### 🚀 Thao Tác Sao Lưu")
    st.write("Bấm nút bên dưới để tiến hành kết xuất bản sao lưu mới nhất từ máy chủ AivenCloud.")
    
    # Khởi tạo state lưu trữ dữ liệu sao lưu
    if "backup_sql_data" not in st.session_state:
        st.session_state["backup_sql_data"] = None
        st.session_state["backup_file_name"] = ""

    # Nút bấm kích hoạt tạo bản sao lưu
    if st.button("📦 KHỞI TẠO BẢN SAO LƯU MỚI (.SQL)", type="primary", use_container_width=True):
        with st.spinner("⏳ Đang truy xuất cấu trúc & dữ liệu từ Aiven Cloud... Vui lòng chờ trong giây lát."):
            success, result, file_name = thuc_hien_sao_luu_db_python(db, current_user)
            
            if success:
                st.session_state["backup_sql_data"] = result
                st.session_state["backup_file_name"] = file_name
                st.success("✅ Đã kết xuất bản sao lưu thành công!")
            else:
                st.error(f"❌ {result}")

    # Nếu đã tạo xong file sao lưu, hiển thị nút Tải về máy
    if st.session_state["backup_sql_data"] is not None:
        st.markdown("---")
        st.success(f"📁 Bản sao lưu sẵn sàng: **{st.session_state['backup_file_name']}**")
        
        st.download_button(
            label="⬇️ TẢI FILE SAO LƯU VỀ MÁY CÁ NHÂN",
            data=st.session_state["backup_sql_data"],
            file_name=st.session_state["backup_file_name"],
            mime="application/sql",
            type="secondary",
            use_container_width=True
        )