import os
import time
import json
import easyocr
import re
import pandas as pd
from PIL import Image
import google.generativeai as genai
from datetime import datetime, date, timedelta
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.6-flash') 
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOWNLOAD_DIR = os.path.join(BASE_DIR, "zalo_downloads")
    TEMP_FILE = os.path.join(BASE_DIR, "temp_parsing.txt")
    EXCEL_FILE = os.path.join(BASE_DIR, "Danh_Sach_Book_Xe_Tong_Hop.xlsx")
else:
    st.error("⚠️ Không tìm thấy GEMINI_API_KEY trong file .env")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@st.cache_resource
def load_ocr_model():
    return easyocr.Reader(['vi', 'en'], gpu=False)

def get_grouped_files():
    valid_extensions = ('.jpg', '.jpeg', '.png', '.txt')
    grouped_files = {}
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        valid_files = [f for f in files if f.lower().endswith(valid_extensions)]
        if valid_files:
            group_name = os.path.basename(root)
            if group_name == "zalo_downloads": 
                group_name = "Khong_Xac_Dinh"
            grouped_files[group_name] = [os.path.join(root, f) for f in valid_files]
    return grouped_files

# Hàm dọn dẹp thư mục rác
def clear_pending_files():
    deleted_count = 0
    for root, dirs, files in os.walk(DOWNLOAD_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
                deleted_count += 1
            except Exception:
                pass
    
    # Xóa luôn các thư mục rỗng
    for root, dirs, files in os.walk(DOWNLOAD_DIR, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                except:
                    pass
    return deleted_count

def process_offline_zalo_files():
    today_str = datetime.today().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today_date = date.today()
    
    grouped_files = get_grouped_files()
    total_groups = len(grouped_files)
    
    if total_groups == 0:
        return {"status": "info", "message": "Thư mục trống. Không có dữ liệu để xử lý."}

    reader = load_ocr_model()

    ui_group_status = st.empty()
    ui_file_status = st.empty()
    ui_progress = st.progress(0)
    ui_logs = st.empty()
    
    logs = []
    valid_records = []
    unprocessed_files = [] 
    
    prompt = f"""
    Bạn là chuyên gia phân tích dữ liệu Logistics. Nhiệm vụ: Chuyển đổi văn bản thành mảng JSON chứa các chuyến đi độc lập.

    **QUY TẮC 1: BÓC TÁCH DỮ LIỆU DẠNG BẢNG**
    - Nếu ảnh là dạng bảng (VD: "GOLDEN VICTORY OIA | 28,000 | PHUONG DONG | 14H"), BẮT BUỘC mỗi dòng ngang tương ứng với 1 chuyến xe. 
    - Cấu trúc ngầm định: [Điểm đi] | [Khối lượng] | [Điểm đến] | [Giờ giấc / Ghi chú].

    **QUY TẮC 2: BÓC TÁCH CHUỖI TEXT TỔNG HỢP (NHIỀU XE / NHIỀU ĐIỂM)**
    - Nếu khách đặt nhiều xe trong 1 tin nhắn, BẮT BUỘC tách thành các object riêng biệt cho từng chuyến.

    **QUY TẮC 3: CHUẨN HÓA KHỐI LƯỢNG (khoi_luong_kg)**
    - Các con số lớn đứng độc lập (VD: 35,000; 28,000) CHÍNH LÀ khối lượng tính bằng KG. 
    - BẮT BUỘC loại bỏ dấu phẩy (",") (VD: 35,000 -> 35000).
    - Nếu gặp "T", "TAN", "TẤN" (VD: 1TAN, 6T), nhân số đó với 1000. Đơn vị "KG" thì giữ nguyên.

    **QUY TẮC 4: CHUẨN HÓA THỂ TÍCH (the_tich_cbm)**
    - Nhận diện các từ "CBM", "KHỐI", "khoi". Lấy chính xác phần số.

    **QUY TẮC 5: LÀM SẠCH FORM "YÊU CẦU ĐIỀU XE" (F.T)**
    - Chỉ tạo 1 object. Ngày đi: "Thời gian yêu cầu xuất phát".
    - Điểm đi -> Điểm đến: Gom từ "Địa điểm xuất phát" -> "Điểm đến".

    **QUY TẮC 6: XỬ LÝ NGÀY THÁNG**
    - "Sáng mai", "mai" -> {tomorrow_str}. "Hôm nay", "tối nay" -> {today_str}.

    **SCHEMA JSON YÊU CẦU ĐẦU RA:**
    {{
        "is_booking": true,
        "danh_sach_xe": [
            {{
                "ngay_chuyen_di": "YYYY-MM-DD",
                "dia_diem_giao_nhan": "Điểm đi -> Điểm đến",
                "khoi_luong_kg": Số thực,
                "the_tich_cbm": Số thực,
                "ghi_chu": "Chi tiết giờ giấc, tên xưởng..."
            }}
        ]
    }}
    """
    
    group_idx = 1
    for nhom, file_paths in grouped_files.items():
        total_files_in_group = len(file_paths)
        ui_group_status.info(f"📁 Đang xử lý nhóm {group_idx}/{total_groups}: **{nhom}**")
        
        for idx, filepath in enumerate(file_paths, 1):
            filename = os.path.basename(filepath)
            is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png'))
            success = False
            
            while not success:
                try:
                    ui_file_status.write(f"👉 Phân tích file {idx}/{total_files_in_group}: `{filename}`...")
                    raw_text = ""
                    
                    if is_image:
                        ocr_result = reader.readtext(filepath, detail=0, paragraph=True)
                        raw_text = " \n".join(ocr_result)
                    else:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            raw_text = f.read()
                    
                    response = model.generate_content(prompt + f'\nNội dung cần phân tích: "{raw_text}"')
                    
                    clean_text = re.sub(r"^```json\s*", "", response.text.strip(), flags=re.IGNORECASE)
                    clean_text = re.sub(r"\s*```$", "", re.sub(r"^```\s*", "", clean_text, flags=re.IGNORECASE))
                    
                    record_count_before = len(valid_records)
                    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                    
                    if match:
                        parsed = json.loads(match.group(0))
                        if parsed.get("is_booking"):
                            for xe in parsed.get("danh_sach_xe", []):
                                xe["nhom_zalo_nguon"] = nhom
                                try:
                                    raw_date = str(xe.get("ngay_chuyen_di", "")).strip()[:10]
                                    ngay = datetime.strptime(raw_date, '%Y-%m-%d').date()
                                    if ngay >= today_date:
                                        xe["khoi_luong_kg"] = float(xe.get("khoi_luong_kg") or 0.0)
                                        xe["the_tich_cbm"] = float(xe.get("the_tich_cbm") or 0.0)
                                        valid_records.append(xe)
                                except Exception:
                                    pass
                    
                    success = True
                    
                    if len(valid_records) == record_count_before:
                        logs.append(f"⚠️ Không có đơn hàng: {filename}")
                        unprocessed_files.append(f"{nhom} / {filename} (Trống)")
                    else:
                        logs.append(f"✅ Bóc tách xong: {filename}")
                        
                    ui_logs.text("\n".join(logs[-4:]))
                    
                    if os.path.exists(filepath): 
                        os.remove(filepath)
                        
                    ui_progress.progress(idx / total_files_in_group)
                    
                    if idx < total_files_in_group:
                        ui_file_status.warning("⏳ Nghỉ 4s tránh nghẽn API...")
                        time.sleep(4)
                        
                except Exception as e:
                    if "429" in str(e).lower() or "quota" in str(e).lower():
                        ui_file_status.error("⚠️ Quá tải API! Nghỉ 30s...")
                        time.sleep(30)
                    else:
                        logs.append(f"❌ Lỗi: {filename}")
                        ui_logs.text("\n".join(logs[-4:]))
                        success = True 
            
            if not success:
                unprocessed_files.append(f"{nhom} / {filename}")
        
        group_path = os.path.join(DOWNLOAD_DIR, nhom)
        if os.path.exists(group_path) and not os.listdir(group_path):
            os.rmdir(group_path)
            
        if group_idx < total_groups:
            ui_group_status.warning(f"🛑 Xong nhóm {nhom}. Nghỉ 5s...")
            time.sleep(5)
        
        group_idx += 1
                        
    ui_progress.empty()
    ui_file_status.empty()
    ui_group_status.empty()
    ui_logs.empty()
                    
    if valid_records:
        df_new = pd.DataFrame(valid_records)
        if os.path.exists(EXCEL_FILE):
            df_existing = pd.read_excel(EXCEL_FILE)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(EXCEL_FILE, index=False)
        else:
            df_new.to_excel(EXCEL_FILE, index=False)
        return {"status": "success", "message": f"✅ Đã lưu {len(valid_records)} chuyến xe vào Excel.", "unprocessed": unprocessed_files}
    
    return {"status": "warning", "message": "⚠️ Không tìm thấy dữ liệu hợp lệ.", "unprocessed": unprocessed_files}

def main_app():
    st.title("🤖 RPA - Lấy thông tin điều xe từ file Zalo")
    
    # 📌 KHU VỰC DỌN RÁC
    st.subheader("🧹 Dọn dẹp dữ liệu tồn đọng")
    st.markdown("Nếu tiến trình trước đó bị lỗi hoặc dừng đột ngột, hãy dọn rác trước khi tải file mới lên để tránh quá tải AI.")
    if st.button("🗑️ Dọn sạch toàn bộ file Zalo cũ", type="secondary"):
        deleted = clear_pending_files()
        if deleted > 0:
            st.success(f"✅ Đã xóa thành công {deleted} file rác tồn đọng trong hệ thống!")
        else:
            st.info("✨ Thư mục hiện tại đang sạch sẽ, không có file rác.")

    st.markdown("---")
    
    st.subheader("📤 Tải lên dữ liệu Zalo (Hình ảnh / File Text)")
    
    existing_groups = [d for d in os.listdir(DOWNLOAD_DIR) if os.path.isdir(os.path.join(DOWNLOAD_DIR, d))]
    options = ["+ Tạo nhóm mới"] + existing_groups
    
    selected_option = st.selectbox("📂 Chọn nhóm Zalo đích (hoặc tạo mới):", options)
    
    if selected_option == "+ Tạo nhóm mới":
        group_name_input = st.text_input("Nhập tên nhóm Zalo mới:").strip()
    else:
        group_name_input = selected_option
    
    uploaded_files = st.file_uploader(
        "Chọn các file ảnh (.jpg, .png) hoặc văn bản (.txt) cần xử lý:", 
        type=["jpg", "jpeg", "png", "txt"], 
        accept_multiple_files=True
    )
    
    if uploaded_files and group_name_input:
        if st.button("📥 Lưu file lên hệ thống Cloud"):
            target_group_dir = os.path.join(DOWNLOAD_DIR, group_name_input)
            os.makedirs(target_group_dir, exist_ok=True) 
            
            saved_count = 0
            for uploaded_file in uploaded_files:
                file_path = os.path.join(target_group_dir, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_count += 1
                
            st.success(f"✅ Đã tải lên thành công {saved_count} file vào nhóm `{group_name_input}`.")

    st.markdown("---")
    st.subheader("⚙️ Xử lý dữ liệu")
    
    if st.button("🚀 Bắt đầu phân tích AI", type="primary"):
        with st.spinner("Đang kết nối thư viện OCR và Gemini AI..."):
            result = process_offline_zalo_files()
            if result:
                if result["status"] == "success": 
                    st.success(result["message"])
                elif result["status"] == "warning": 
                    st.warning(result["message"])
                elif result["status"] == "info": 
                    st.info(result["message"])
                
                if result.get("unprocessed"):
                    st.error(f"🚨 Có {len(result['unprocessed'])} file hệ thống không thể xử lý:")
                    for f in result["unprocessed"]:
                        st.markdown(f"- `{f}`")

    st.markdown("---")
    st.subheader("📥 Tải kết quả tổng hợp")
    if os.path.exists(EXCEL_FILE):
        with open(EXCEL_FILE, "rb") as file:
            st.download_button(
                label="⬇️ Tải file Danh_Sach_Book_Xe_Tong_Hop.xlsx",
                data=file,
                file_name="Danh_Sach_Book_Xe_Tong_Hop.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
    else:
        st.info("Chưa có dữ liệu Excel nào được xuất ra trên hệ thống.")

if __name__ == "__main__":
    main_app()