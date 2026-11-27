import streamlit as st
import datetime
from db_config import Database
from hr_system_manager import thuc_hien_sao_luu_db_python

# Tự động khởi tạo lại Database nếu người dùng F5 trực tiếp tại trang Sao lưu
db = st.session_state.get("db")
if not db:
    db = Database()
    st.session_state["db"] = db

current_user = (
    st.session_state.get("username")
    or st.session_state.get("user")
    or st.session_state.get("logged_in_user", "Admin")
)

VN_TZ = datetime.timezone(datetime.timedelta(hours=7))

st.markdown(
    "<h3 style='text-align: center; color: #0b5394;'>🛡️ QUẢN LÝ SAO LƯU & AN TOÀN DỮ LIỆU CƠ SỞ DỮ LIỆU</h3>",
    unsafe_allow_html=True,
)
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
        st.session_state["backup_created_at"] = ""

    # Nút bấm kích hoạt tạo bản sao lưu
    if st.button("📦 KHỞI TẠO BẢN SAO LƯU MỚI (.SQL)", type="primary", use_container_width=True):
        # Xóa bản sao lưu cũ trong session trước khi tạo mới để tránh tải nhầm nếu lần này lỗi
        st.session_state["backup_sql_data"] = None
        st.session_state["backup_file_name"] = ""
        st.session_state["backup_created_at"] = ""

        with st.spinner("⏳ Đang truy xuất cấu trúc & dữ liệu từ Aiven Cloud... Vui lòng chờ trong giây lát."):
            success, result, file_name = thuc_hien_sao_luu_db_python(db, current_user)

            if success and result:
                sql_bytes = result.encode("utf-8") if isinstance(result, str) else result
                st.session_state["backup_sql_data"] = sql_bytes
                st.session_state["backup_file_name"] = file_name
                st.session_state["backup_created_at"] = datetime.datetime.now(VN_TZ).strftime(
                    "%H:%M:%S - %d/%m/%Y"
                )
                st.success("✅ Đã kết xuất bản sao lưu thành công!")
            else:
                st.error(f"❌ {result or 'Không nhận được dữ liệu sao lưu từ máy chủ.'}")

    # Nếu đã tạo xong file sao lưu, hiển thị nút Tải về máy
    if st.session_state["backup_sql_data"] is not None:
        size_kb = len(st.session_state["backup_sql_data"]) / 1024
        size_label = f"{size_kb / 1024:.2f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"

        st.markdown("---")
        st.success(
            f"📁 Bản sao lưu sẵn sàng: **{st.session_state['backup_file_name']}** ({size_label})\n\n"
            f"🕒 Thời điểm kết xuất: `{st.session_state['backup_created_at']}`"
        )

        st.download_button(
            label="⬇️ TẢI FILE SAO LƯU VỀ MÁY CÁ NHÂN",
            data=st.session_state["backup_sql_data"],
            file_name=st.session_state["backup_file_name"],
            mime="application/sql",
            type="secondary",
            use_container_width=True,
        )