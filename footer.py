import streamlit as st
import os
import base64

def render_footer():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(current_dir, "image")
    
    vpdd_path = os.path.join(image_dir, "vpdd_bao_tin.jfif")
    logo_path = os.path.join(image_dir, "logo_baotin.jfif")

    def get_base64_image(path):
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None

    vpdd_b64 = get_base64_image(vpdd_path)
    logo_b64 = get_base64_image(logo_path)

    footer_html = f"""
<style>
.footer-container {{
    background: linear-gradient(135deg, #0B2E9E 0%, #1342c4 100%);
    color: #ffffff;
    padding: 25px 40px;
    box-shadow: 0 -4px 15px rgba(11,46,158,0.15);
    margin-top: 40px;
    border-top: 3px solid #FF6B00;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 20px;
    font-family: "Times New Roman", Times, serif !important;
    margin-left: -2.5rem !important;
    margin-right: -2.5rem !important;
    width: calc(100% + 5rem) !important;
    box-sizing: border-box;
    border-radius: 0px !important;
}}

.footer-left {{ display: flex; align-items: center; gap: 15px; flex: 1.2; min-width: 250px; }}
.footer-img-box {{ display: flex; gap: 8px; }}
.footer-img {{ width: 50px; height: 50px; object-fit: cover; border-radius: 8px; border: 1px solid rgba(255,255,255,0.3); }}
.footer-company-info {{ line-height: 1.3; }}
.footer-center {{ flex: 1.5; text-align: center; font-size: 14px; line-height: 1.5; min-width: 250px; opacity: 0.95; }}
.footer-right {{ flex: 0.8; text-align: right; font-size: 13px; min-width: 150px; opacity: 0.9; }}

@media (max-width: 768px) {{
    .footer-container {{ flex-direction: column; text-align: center; padding: 20px; }}
    .footer-left, .footer-right {{ justify-content: center; text-align: center; }}
}}
</style>

<div class="footer-container">
<div class="footer-left">
<div class="footer-img-box">
{f'<img src="data:image/jpeg;base64,{logo_b64}" class="footer-img">' if logo_b64 else '<div style="width:50px;height:50px;background:#ddd;border-radius:8px;text-align:center;line-height:50px;color:#333;font-size:10px;">LOGO</div>'}
{f'<img src="data:image/jpeg;base64,{vpdd_b64}" class="footer-img">' if vpdd_b64 else '<div style="width:50px;height:50px;background:#ddd;border-radius:8px;text-align:center;line-height:50px;color:#333;font-size:10px;">VPDD</div>'}
</div>
<div class="footer-company-info">
<div style="font-size: 16px; font-weight: 900; letter-spacing: 0.5px; color: #ffffff;">BẢO TÍN LOGISTICS</div>
<div style="font-size: 12px; color: #FF6B00; font-weight: bold;">We truck your trust • truckingbaotin.com</div>
</div>
</div>
<div class="footer-center">
Chuyên tuyến nhà máy → Sân bay Tân Sơn Nhất/Long Thành, Cảng Cát Lái/Cái Mép, ICD & tuyến quốc tế Cambodia qua Mộc Bài, Xa Mát. Khai báo hải quan trọn gói.
</div>
<div class="footer-right">
© 2026 Bao Tin Logistics.<br>All rights reserved.
</div>
</div>
"""
    st.markdown(footer_html, unsafe_allow_html=True)