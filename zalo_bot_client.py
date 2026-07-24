import os
import time
import pyperclip
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains



# Tạo thư mục lưu cấu hình đăng nhập (Cookie) ngay tại thư mục chứa code
PROFILE_DIR = os.path.join(os.getcwd(), "ZaloBot_Profile")

# ---------------------------------------------------------
# 2. HÀM ĐIỀU KHIỂN BOT RPA (SELENIUM) ĐÃ TỐI ƯU
# ---------------------------------------------------------
def mo_trinh_duyet_zalo():
    """Hàm chỉ chịu trách nhiệm mở và giữ Chrome luôn bật"""
    st.info("🚀 Đang khởi động Google Chrome...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    
    # LỆNH QUAN TRỌNG: Ngăn Chrome tự động đóng khi chạy xong hàm
    options.add_experimental_option("detach", True)
    
    # LỆNH QUAN TRỌNG: Lưu lại thông tin quét mã QR cho các lần sau
    options.add_argument(f"user-data-dir={PROFILE_DIR}")
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://chat.zalo.me")
        # Đưa driver vào session_state để dùng lại được khi bấm nút gửi
        st.session_state['zalo_driver'] = driver
        st.success("🌐 Trình duyệt đã mở! Nếu đây là lần đầu, hãy quét QR. Các lần sau máy sẽ tự nhớ.")
    except Exception as e:
        st.error(f"❌ Lỗi mở trình duyệt: {e}")

def chay_bot_gui_tin(df_lenh_chay):
    """Hàm lấy lại Chrome đang mở để điều khiển gửi tin"""
    driver = st.session_state.get('zalo_driver')
    
    if not driver:
        st.error("⚠️ Không tìm thấy trình duyệt! Vui lòng bấm '1. MỞ TRÌNH DUYỆT ZALO' trước.")
        return
        
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    tong_so = len(df_lenh_chay)
    thanh_cong = 0
    
    try:
        # Đợi thanh tìm kiếm hiển thị (Đảm bảo mạng đã load xong Zalo)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "contact-search-input"))
        )
        
        for idx, row in df_lenh_chay.iterrows():
            ten_nhom = str(row.get('ten_group', '')).strip()
            noi_dung = str(row.get('noi_dung_chat', '')).strip()
            
            if not ten_nhom or not noi_dung or ten_nhom == 'nan':
                continue
                
            status_text.text(f"Đang gửi lệnh xe: {ten_nhom} ({idx + 1}/{tong_so})")
            
            try:
                # 1. TÌM VÀ LÀM SẠCH Ô TÌM KIẾM BẰNG PHÍM ẢO
                search_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "contact-search-input"))
                )
                search_box.click()
                time.sleep(0.5)
                
                # Bôi đen toàn bộ (Ctrl + A) và Xóa (Backspace) để dọn sạch biển số xe cũ
                search_box.send_keys(Keys.CONTROL, 'a')
                time.sleep(0.2)
                search_box.send_keys(Keys.BACKSPACE)
                time.sleep(0.5)
                
                # Nhập tên nhóm xe mới
                search_box.send_keys(ten_nhom)
                
                # Chờ Zalo load danh sách kết quả 
                time.sleep(3) 
                
                # 2. Dùng ActionChains mô phỏng gõ phím vật lý để chọn nhóm
                actions = ActionChains(driver)
                actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
                
                # 3. FIX LỖI CHỜ KHUNG CHAT: Chờ tối đa 10 giây cho đến khi khung chat thực sự hiện ra
                chat_box = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "richInput"))
                )
                chat_box.click() 
                
                # Dán nội dung
                pyperclip.copy(noi_dung)
                
                actions_chat = ActionChains(driver)
                actions_chat.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                
                time.sleep(1) # Chờ Zalo giãn khung chat
                
                # Gửi tin nhắn
                actions_chat.send_keys(Keys.ENTER).perform()
                
                # Nghỉ một nhịp trước khi lặp qua chuyến xe tiếp theo
                time.sleep(1.5) 
                
                thanh_cong += 1
                
            except Exception as e:
                st.error(f"Lỗi khi gửi xe {ten_nhom}: {e}")
                
            progress_bar.progress(int(((idx + 1) / tong_so) * 100))
            
        st.success(f"🎉 Hoàn thành! Đã điều phối tự động vào {thanh_cong}/{tong_so} nhóm Zalo.")
        
        
            
    except Exception as e:
        st.error(f"❌ Lỗi hệ thống Bot hoặc Zalo chưa tải xong: {e}")

# ---------------------------------------------------------
# 3. GIAO DIỆN STREAMLIT NỘI BỘ
# ---------------------------------------------------------
def main():
    st.set_page_config(page_title="Bot Zalo Điều Xe", page_icon="🤖")
    
    st.title("🤖 BOT ĐIỀU XE BẢO TÍN (NỘI BỘ)")
    st.markdown("Phần mềm giả lập gửi tin nhắn Zalo tự động dành riêng cho phòng Điều hành.")
    
    #ten_nguoi_dung = st.text_input("👤 Nhập tên người điều hành (Để lưu Audit Log):", value="Admin_DieuHanh")
    
    st.divider()
    st.subheader("📂 Nạp lệnh chạy từ hệ thống Web")
    file_excel = st.file_uploader("Tải lên file Excel xuất từ Web (Chứa cột ten_group & noi_dung_chat)", type=["xlsx"])
    
    if file_excel:
        try:
            df = pd.read_excel(file_excel)
            if 'ten_group' not in df.columns or 'noi_dung_chat' not in df.columns:
                st.error("❌ File Excel không đúng định dạng. Cần có cột 'ten_group' và 'noi_dung_chat'.")
                return
                
            st.dataframe(df[['ten_group', 'noi_dung_chat']], width="stretch")
            
            st.markdown("### VẬN HÀNH BOT")
            st.info("Quy trình: Mở trình duyệt -> Chờ Zalo load xong tin nhắn -> Bấm gửi.")
            
            # Chia làm 2 cột cho 2 bước thao tác
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("1️⃣ MỞ TRÌNH DUYỆT ZALO", width="stretch"):
                    mo_trinh_duyet_zalo()
                    
            with col2:
                if st.button("2️⃣ BẮT ĐẦU GỬI TIN", type="primary", width="stretch"):
                    chay_bot_gui_tin(df)
                
        except Exception as e:
            st.error(f"Lỗi đọc file Excel: {e}")

if __name__ == "__main__":
    main()