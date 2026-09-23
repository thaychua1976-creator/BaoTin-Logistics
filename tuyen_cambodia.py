import streamlit as st
import os
import header
import footer

def show_page():
    # 1. Cấu hình trang cơ bản
    st.set_page_config(
        page_title="BẢO TÍN LOGISTICS - Tuyến Cambodia", 
        page_icon="🌍", 
        layout="wide"
    )

    # 2. GỌI HEADER (Truyền "tuyen_cambodia" để menu tự động sáng màu cam)
    header.render_header("tuyen_cambodia")

    # 3. CSS Tùy chỉnh (Chỉ giữ lại CSS đặc thù của các box thuộc trang Tuyến Cambodia)
    st.markdown("""
<style>
.left-container, .right-container {
    background-color: #ffffff; padding: 24px; border-radius: 16px;
    border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.04); height: 100%;
}

.route-box-1 {
    background: linear-gradient(135deg, #f0f4ff 0%, #dbeafe 100%);
    border: 2px solid #0B2E9E; padding: 16px; border-radius: 12px;
    text-align: center; height: 100%; box-shadow: 0 2px 6px rgba(11,46,158,0.08);
}
.route-box-2 {
    background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    border: 2px solid #FF6B00; padding: 16px; border-radius: 12px;
    text-align: center; height: 100%; box-shadow: 0 2px 6px rgba(255,107,0,0.1);
}
.route-box-3 {
    background: linear-gradient(135deg, #f8fafc 100%, #f1f5f9 0%);
    border: 2px solid #475569; padding: 16px; border-radius: 12px;
    text-align: center; height: 100%; box-shadow: 0 2px 6px rgba(71,85,105,0.08);
}

.timeline-wrapper { position: relative; padding-left: 35px; margin-top: 15px; }
.timeline-wrapper::before {
    content: ''; position: absolute; left: 12px; top: 8px; bottom: 8px;
    width: 3px; background-color: #0B2E9E; border-radius: 2px;
}
.timeline-item { position: relative; margin-bottom: 25px; }
.timeline-item:last-child { margin-bottom: 0; }
.timeline-badge {
    position: absolute; left: -35px; top: 0; width: 26px; height: 26px;
    background-color: #FF6B00; color: white; border-radius: 50%; text-align: center;
    font-weight: 900; font-size: 14px; line-height: 26px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2); border: 2px solid #ffffff;
}
.timeline-title { color: #0B2E9E; font-size: 16px; font-weight: 900; margin-bottom: 3px; }
.timeline-time { color: #FF6B00; font-size: 13px; font-weight: bold; margin-bottom: 5px; }
.timeline-desc { color: #334155; font-size: 13px; line-height: 1.5; }

.commitment-box {
    background: linear-gradient(135deg, #0B2E9E 0%, #1342c4 100%); color: white;
    padding: 16px; border-radius: 12px; margin-top: 25px;
    box-shadow: 0 4px 10px rgba(11,46,158,0.2); border-left: 5px solid #FF6B00;
}
</style>
""", unsafe_allow_html=True)

    # 4. TIÊU ĐỀ TRANG 3D
    st.markdown("""
<div style="width: 100%; text-align: center; margin-top: 10px;">
    <div style="color: #0B2E9E; font-size: 48px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 1px 1px 0px #e2e8f0, 2px 2px 0px #cbd5e1, 3px 3px 0px #94a3b8, 4px 4px 0px #64748b, 6px 6px 10px rgba(0,0,0,0.25);">
        Tuyến Cambodia
    </div>
    <div style="color: #475569; font-size: 20px; font-weight: 700; margin-bottom: 35px;">
        Dịch vụ vận tải quốc tế xuyên biên giới chuyên nghiệp, thông quan nhanh chóng
    </div>
</div>
""", unsafe_allow_html=True)

    # 5. BỐ CỤC 2 CỘT CHÍNH
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.markdown("""
<div class="left-container">
<h2 style="color: #0B2E9E; margin-top: 0; font-size: 22px; font-weight: 900; border-bottom: 2px solid #FF6B00; padding-bottom: 10px;">
🚀 LỢI THẾ TUYẾN CAMBODIA
</h2>
<div style="color: #1e293b; font-size: 24px; font-weight: 800; margin-bottom: 10px; color: #FF6B00;">
Tây Ninh → Mộc Bài → Phnom Penh
</div>
<div style="color: #334155; font-size: 14px; line-height: 1.6; margin-bottom: 20px;">
<span style="color: #FF6B00; font-size: 26px; font-weight: 900;"><b>Thông quan trong ngày:</b></span> Văn phòng đại diện tại Trảng Bàng – sát cửa khẩu. Quan hệ hải quan 2 đầu, xử lý hồ sơ trước khi xe tới cửa khẩu. Đội xe đầu kéo và xe tải nhỏ linh hoạt đổi xe tại biên giới nếu cần.
</div>

<h3 style="color: #0B2E9E; font-size: 17px; font-weight: 900; margin-bottom: 15px;">
Trạm & Cửa Khẩu Trọng Điểm:
</h3>
""", unsafe_allow_html=True)

        # 3 Box con nội dung
        sub_c1, sub_c2, sub_c3 = st.columns(3, gap="small")
        with sub_c1:
            st.markdown("""
<div class="route-box-1">
<div style="color: #0B2E9E; font-size: 15px; font-weight: 900; margin-bottom: 5px;">Mộc Bài</div>
<div style="color: #1e293b; font-size: 13px; font-weight: bold;">45 phút</div>
<div style="color: #64748b; font-size: 11px; margin-top: 5px;">Thông quan xuất</div>
</div>
""", unsafe_allow_html=True)
        with sub_c2:
            st.markdown("""
<div class="route-box-2">
<div style="color: #FF6B00; font-size: 15px; font-weight: 900; margin-bottom: 5px;">Xa Mát</div>
<div style="color: #1e293b; font-size: 13px; font-weight: bold;">Prey Veng</div>
<div style="color: #64748b; font-size: 11px; margin-top: 5px;">Tuyến linh hoạt</div>
</div>
""", unsafe_allow_html=True)
        with sub_c3:
            st.markdown("""
<div class="route-box-3">
<div style="color: #334155; font-size: 15px; font-weight: 900; margin-bottom: 5px;">Phnom Penh</div>
<div style="color: #1e293b; font-size: 13px; font-weight: bold;">Sihanoukville</div>
<div style="color: #64748b; font-size: 11px; margin-top: 5px;">Trung tâm & Cảng</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("""
<div class="right-container">
<div style="display: flex; justify-content: center; align-items: center; border-bottom: 2px solid #FF6B00; padding-bottom: 10px; margin-bottom: 20px;">
<h2 style="color: #0B2E9E; margin: 0; font-size: 22px; font-weight: 900;">
⏳ Timeline Vận Chuyển
</h2>
<span style="background-color: #f1f5f9; color: #475569; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; border: 1px solid #cbd5e1;">
Cập nhật 2026
</span>
</div>

<div class="timeline-wrapper">
<div class="timeline-item">
<div class="timeline-badge">1</div>
<div class="timeline-title">Tây Ninh - Trảng Bàng</div>
<div class="timeline-time">06:00 - Lấy hàng tại nhà máy</div>
<div class="timeline-desc">Kiểm tra chứng từ, đóng gói, kẹp seal cẩn thận. Tiến hành khai báo hải quan từ trước.</div>
</div>

<div class="timeline-item">
<div class="timeline-badge">2</div>
<div class="timeline-title">Cửa khẩu Mộc Bài</div>
<div class="timeline-time">09:30 - Thông quan xuất hàng</div>
<div class="timeline-desc">Đội ngũ chuyên trách túc trực làm thủ tục tại cửa khẩu. Xử lý nhanh các tờ khai luồng vàng hoặc luồng đỏ.</div>
</div>

<div class="timeline-item">
<div class="timeline-badge">3</div>
<div class="timeline-title">Bavet - Phnom Penh</div>
<div class="timeline-time">13:30 - Giao hàng Cambodia</div>
<div class="timeline-desc">Giao hàng tận nơi tới kho Phnom Penh, Sihanoukville, hoặc thực hiện chuyển tiếp nội địa Cambodia an toàn.</div>
</div>
</div>

<div class="commitment-box">
<div style="font-size: 15px; font-weight: 900; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
<span>🛡️</span> CAM KẾT DỊCH VỤ BẢO TÍN
</div>
<div style="font-size: 13px; line-height: 1.6; opacity: 0.95;">
• <b>Báo giá trong 15 phút</b>, có xe điều phối trong <b>60 phút</b> nội vùng Tây Ninh - TP.HCM - Bình Dương.<br>
• <b>Cam kết không phát sinh phí ẩn</b> trong suốt quá trình vận chuyển và thông quan.
</div>
</div>
</div>
""", unsafe_allow_html=True)
        
    # 6. GỌI FOOTER Ở CUỐI TRANG
    footer.render_footer()