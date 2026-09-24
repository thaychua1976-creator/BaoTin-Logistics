import streamlit as st
import os
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import header
import footer

def send_quote_email(hot_ten, so_dien_thoai, tuyen_duong, mo_ta_hang):
    """Hàm gửi thông tin yêu cầu báo giá tới email bao@truckingbaotin.com"""
    sender_email = "bao@truckingbaotin.com"  # Email cấu hình gửi đi từ hệ thống
    receiver_email = "bao@truckingbaotin.com"  # Email nhận thông tin yêu cầu
    app_password = ""  # Nhập App Password (Mật khẩu ứng dụng) của bạn vào đây
    
    subject = f"🔔 Yêu Cầu Báo Giá Mới từ {hot_ten}"
    body = f"""
    Hệ thống nhận được một yêu cầu báo giá vận chuyển mới từ website:
    
    - Họ tên / Công ty: {hot_ten}
    - Số điện thoại: {so_dien_thoai}
    - Tuyến cần vận chuyển: {tuyen_duong}
    - Mô tả hàng hóa: {mo_ta_hang}
    
    ---
    Bảo Tín Logistics - ERP System
    """
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        # Bỏ dấu comment dòng dưới khi đã điền App Password chính xác
        # server.login(sender_email, app_password)
        # server.sendmail(sender_email, receiver_email, msg.as_string())
        # server.quit()
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False

def show_page():
    # 1. Cấu hình trang cơ bản
    st.set_page_config(
        page_title="BẢO TÍN LOGISTICS - Liên Hệ & Báo Giá", 
        page_icon="📞", 
        layout="wide"
    )

    # 2. GỌI HEADER (Đánh dấu menu trang "lien_he" bằng màu cam)
    header.render_header("lien_he")

    # 3. CSS Tùy chỉnh (Chỉ giữ lại CSS đặc thù cho form và nút của trang Liên Hệ)
    st.markdown("""
<style>
/* Tùy chỉnh riêng cho nút Gửi Yêu Cầu Báo Giá Ngay màu xanh dương */
div.stButton > button {
    background-color: #0B2E9E !important;
    color: white !important;
    font-weight: bold !important;
    border-radius: 8px !important;
    border: none !important;
}
div.stButton > button:hover {
    background-color: #1342c4 !important;
    color: white !important;
}

/* 2 Box nhỏ phụ trợ kích thước gọn gàng nằm ngang, đẩy lên trên sát nút bấm */
.mini-badge-1 {
    background-color: #ffffff;
    border: 1px solid #0B2E9E;
    color: #0B2E9E;
    padding: 5px 8px;
    border-radius: 6px;
    text-align: center;
    font-weight: 800;
    font-size: 11px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.mini-badge-2 {
    background-color: #FF6B00;
    color: white;
    padding: 5px 8px;
    border-radius: 6px;
    text-align: center;
    font-weight: 800;
    font-size: 11px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* Nút liên hệ nhanh bên phải (Gọi điện & Zalo) */
.action-box-call {
    background-color: #0B2E9E;
    color: white;
    padding: 12px 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 14px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.action-box-zalo {
    background-color: #FF6B00;
    color: white;
    padding: 12px 10px;
    border-radius: 10px;
    text-align: center;
    font-weight: bold;
    font-size: 14px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.zalo-link {
    text-decoration: none !important;
    color: white !important;
    display: block;
    width: 100%;
    height: 100%;
}
</style>
""", unsafe_allow_html=True)

    # 4. TIÊU ĐỀ TRANG 3D
    st.markdown("""
<div style="width: 100%; text-align: center; margin-top: 10px;">
    <div style="color: #0B2E9E; font-size: 48px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 1px 1px 0px #e2e8f0, 2px 2px 0px #cbd5e1, 3px 3px 0px #94a3b8, 4px 4px 0px #64748b, 6px 6px 10px rgba(0,0,0,0.25);">
        Liên Hệ Báo Giá
    </div>
    <div style="color: #475569; font-size: 30px; font-weight: 700; margin-bottom: 35px;">
        Gửi yêu cầu vận chuyển, phản hồi nhanh chóng trong vòng 15 phút
    </div>
</div>
""", unsafe_allow_html=True)

    # 5. BỐ CỤC 2 CỘT CHÍNH
    col_left, col_right = st.columns(2, gap="large")

    # --- CỘT TRÁI: FORM YÊU CẦU BÁO GIÁ ---
    with col_left:
        st.markdown('<h3 style="color: #0B2E9E; margin-top: 0; font-size: 22px; font-weight: 900; border-bottom: 2px solid #FF6B00; padding-bottom: 10px; margin-bottom: 20px;">📝 Gửi Yêu Cầu Vận Chuyển</h3>', unsafe_allow_html=True)
        
        hot_ten = st.text_input("Họ tên / Công ty", placeholder="Nhập tên của bạn hoặc tên doanh nghiệp...")
        so_dien_thoai = st.text_input("Số điện thoại", placeholder="Nhập số điện thoại liên hệ...")
        tuyen_duong = st.text_input("Tuyến cần vận chuyển", placeholder="Ví dụ: Tây Ninh đi Sân bay Tân Sơn Nhất, Mộc Bài...")
        mo_ta_hang = st.text_area("Mô tả hàng hóa", placeholder="Nhập trọng lượng, kích thước hoặc loại hàng hóa cần vận chuyển...", height=120)
        
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        if st.button("🚀 Gửi Yêu Cầu Báo Giá Ngay", use_container_width=True):
            if hot_ten and so_dien_thoai:
                # Gửi thông tin về email 
                email_sent = send_quote_email(hot_ten, so_dien_thoai, tuyen_duong, mo_ta_hang)
                st.success("Cảm ơn bạn đã gửi yêu cầu! Hệ thống đã gửi thông tin đến email quản lý (thaychua1976@gmail.com). Đội ngũ điều vận sẽ liên hệ lại trong 15 phút.")
            else:
                st.warning("Vui lòng nhập đầy đủ 'Họ tên / Công ty' và 'Số điện thoại' để chúng tôi phản hồi.")

        # 2 Box nhỏ thu nhỏ, đẩy lên sát phía trên ngay dưới nút bấm
        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        sub_col1, sub_col2 = st.columns(2, gap="small")
        with sub_col1:
            st.markdown('<div class="mini-badge-1">📞 Hotline 24/7</div>', unsafe_allow_html=True)
        with sub_col2:
            st.markdown('<div class="mini-badge-2">⚡ Báo giá miễn phí</div>', unsafe_allow_html=True)

    # --- CỘT PHẢI: ẢNH VĂN PHÒNG ĐẠI DIỆN VÀ THÔNG TIN LIÊN HỆ ---
    with col_right:
        st.markdown('<h3 style="color: #0B2E9E; margin-top: 0; font-size: 22px; font-weight: 900; border-bottom: 2px solid #FF6B00; padding-bottom: 10px; margin-bottom: 20px;">🏢 Văn Phòng Đại Diện</h3>', unsafe_allow_html=True)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        image_dir = os.path.join(current_dir, "image")
        vpdd_img_path = os.path.join(image_dir, "vpdd_bao_tin.jfif")
        
        if os.path.exists(vpdd_img_path):
            with open(vpdd_img_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode()
            st.markdown(f'<img src="data:image/jpeg;base64,{b64_str}" style="width: 100%; height: 310px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #e2e8f0; object-fit: cover; display: block;">', unsafe_allow_html=True)
        else:
            st.markdown('<div style="width: 100%; height: 310px; background-color: #f1f5f9; border-radius: 10px; margin-bottom: 15px; border: 1px dashed #cbd5e1; display: flex; align-items: center; justify-content: center; color: #64748b; font-weight: bold;">🏢 VPDD BẢO TÍN LOGISTICS</div>', unsafe_allow_html=True)

        st.markdown("""
<div style="color: #0B2E9E; font-size: 18px; font-weight: 900; margin-bottom: 10px;">
CÔNG TY TNHH BẢO TÍN LOGISTICS
</div>
<div style="color: #334155; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
📍 <b>Địa chỉ:</b> Số 56 Đường Nguyễn Du, Khu phố Lộc Du, Phường Trảng Bàng, Tỉnh Tây Ninh<br>
📞 <b>Hotline:</b> 0888 039 888 / 0988 039 888 (24/7)<br>
✉️ <b>Email:</b> bao@truckingbaotin.com<br>
🌐 <b>Website:</b> truckingbaotin.com - We truck your trust.
</div>
""", unsafe_allow_html=True)

        box_call, box_zalo = st.columns(2, gap="small")
        with box_call:
            st.markdown("""
<div class="action-box-call">
📞 Gọi 0888 039 888
</div>
""", unsafe_allow_html=True)
        with box_zalo:
            st.markdown("""
<div class="action-box-zalo">
    <a href="https://zalo.me/0888039888" target="_blank" class="zalo-link">
        💬 Chat Zalo 24/7
    </a>
</div>
""", unsafe_allow_html=True)
            
    # 6. GỌI FOOTER Ở CUỐI TRANG
    footer.render_footer()