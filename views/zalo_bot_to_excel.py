import os
import time, queue
import json,sys,re
import pandas as pd
import threading
from playwright.sync_api import sync_playwright
import google.generativeai as genai
from datetime import datetime, date, timedelta
import streamlit as st
import hashlib
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.6-flash')
    # 🚀 BẢN VÁ: Ép các file dữ liệu phải lưu cùng thư mục với file code Python
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXCEL_FILE = os.path.join(BASE_DIR, "Danh_Sach_Book_Xe_Tong_Hop.xlsx")
    HISTORY_FILE = os.path.join(BASE_DIR, "zalo_history_hash.json")
else:
    st.error("⚠️ Không tìm thấy GEMINI_API_KEY trong file .env")



# 🚀 Tạo thư mục riêng chứa ảnh tạm để dễ quản lý và dọn dẹp
TEMP_IMG_DIR = os.path.join(BASE_DIR, "zalo_temp_images")
os.makedirs(TEMP_IMG_DIR, exist_ok=True)

DANH_SACH_NHOM = [
    "XẮP XE FORTUNATE-BAOTIN",
    "F.T & BẢO TÍN (XE)",
    "YOUNG IL - BẢO TÍN",
    "XE TẢI BẢO TIN-HỒNG BẢO",
    "My FAMILY-LOVE",
    "Điều xe SINCETECH - BẢO TÍN",
    "BẢO TÍN - BINNA"
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_history(hash_set):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(list(hash_set), f)

PROCESSED_HASHES = load_history()

def get_msg_hash(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()

# ==========================================
# 2. HÀM AI XỬ LÝ TASK (ĐÃ NÂNG CẤP NHẬN DIỆN FORM ERP & TEXT NGẮN)
# ==========================================
def process_single_task(task):
    today_str = datetime.today().strftime('%Y-%m-%d')
    tomorrow_str = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today_date = date.today()
    
    # 🚀 PROMPT ĐÃ ĐƯỢC TỐI ƯU ĐẶC BIỆT CHO ẢNH FORM ERP & TEXT ĐIỀU PHỐI NGẮN
    prompt = f"""
    Bạn là AI Logistics cốt lõi của Bảo Tín. Nhiệm vụ: Trích xuất thông tin ĐẶT XE, ĐỔI XE hoặc LỊCH ĐIỀU XE từ nội dung văn bản hoặc hình ảnh.
    
    QUY TẮC NHẬN DIỆN BẮT BUỘC (KHÔNG ĐƯỢC BỎ QUA):
    
    1. NHẬN DIỆN ẢNH FORM ERP / CHỨNG TỪ ĐIỀU XE (Như ảnh chụp form có các trường: "Số đơn điều xe", "Địa điểm xuất phát", "Điểm đến", "Lý do sử dụng xe"):
       - ĐÂY 100% LÀ ĐƠN BOOK XE / ĐIỀU XE HỢP LỆ. BẮT BUỘC TRẢ VỀ "is_booking": true.
       - Cách bóc dữ liệu từ form:
         + Ngày đi: Lấy từ ô "Thời gian yêu cầu xuất phát" hoặc "Ngày yêu cầu" (Format YYYY-MM-DD).
         + Điểm đi -> Điểm đến: Lấy từ "Địa điểm xuất phát" -> "Điểm đến" (VD: FIRST TEAM -> TCS).
         + Khối lượng & Thể tích: Bắt buộc đọc kỹ ô "Lý do sử dụng xe" (VD: "800 KG, 5 KHỐI" -> khoi_luong_kg: 800, the_tich_cbm: 5). Nếu không có số liệu, điền 0.
    
    2. NHẬN DIỆN TEXT NGẮN HOẶC DÀI (Kể cả các câu ngắn gọn như "xe 5 tấn vào đóng hàng...", "xe 1 tấn..."):
       - Trích xuất toàn bộ thông tin về loại xe, khối lượng, điểm giao nhận.
       - Đưa các thông tin chi tiết về giờ giấc, số kiện, tài xế vào phần "ghi_chu".
    
    3. XỬ LÝ NGÀY THÁNG (Format YYYY-MM-DD):
       - Lấy chính xác ngày trong ảnh/text. Nếu không ghi rõ, mặc định là hôm nay ({today_str}) hoặc ngày mai ({tomorrow_str}).
       - Tuyệt đối không chọn ngày trong quá khứ xa.
    
    CHỈ BỎ QUA ("is_booking": false) KHI: Đó là tin nhắn chat chit không liên quan, hoặc thông báo xác nhận tài xế, biển số xe đơn thuần.
    
    CHỈ TRẢ VỀ JSON HỢP LỆ:
    {{
        "is_booking": true,
        "danh_sach_xe": [
            {{
                "ngay_chuyen_di": "YYYY-MM-DD",
                "ten_khach_hang": "Tên khách / Xưởng xuất phát",
                "nguoi_gui_zalo": "Người gửi",
                "dia_diem_giao_nhan": "Điểm đi -> Điểm đến",
                "khoi_luong_kg": Số thực (hoặc 0),
                "the_tich_cbm": Số thực (hoặc 0),
                "ghi_chu": "Chi tiết số kiện, giờ giấc..."
            }}
        ]
    }}
    """
    
    task_type, content, nhom, msg_hash = task['type'], task['content'], task['nhom'], task['hash']
    success = False
    valid_records = []
    
    if task_type == 'image':
        if not os.path.exists(content):
            PROCESSED_HASHES.add(msg_hash)
            return
        try:
            file_size = os.path.getsize(content)
            if file_size < 2048: 
                PROCESSED_HASHES.add(msg_hash)
                os.remove(content)
                return
            with Image.open(content) as img_check:
                width, height = img_check.size
                if width < 50 and height < 50:
                    PROCESSED_HASHES.add(msg_hash)
                    os.remove(content) 
                    return
        except Exception:
            pass

    while not success:
        try:
            print(f"   👉 [AI] Đang phân tích ({task_type}) từ [{nhom}]...")
            if task_type == 'image':
                with Image.open(content) as img_obj:
                    img_obj.load()
                    response = model.generate_content([prompt, img_obj])
            else:
                response = model.generate_content(prompt + f'\nNội dung văn bản: "{content}"')
                
            if not response.text:
                success = True
                break

            clean_text = response.text.strip()
            clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r"\s*```$", "", clean_text)

            match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("is_booking"):
                    for xe in parsed.get("danh_sach_xe", []):
                        xe["nhom_zalo_nguon"] = nhom
                        try:
                            raw_date = str(xe.get("ngay_chuyen_di", "")).strip()[:10]
                            ngay = datetime.strptime(raw_date, '%Y-%m-%d').date()
                            
                            # Chốt chặn thời gian hợp lệ
                            if ngay >= today_date:
                                try:
                                    xe["khoi_luong_kg"] = float(xe.get("khoi_luong_kg") or 0.0)
                                except (ValueError, TypeError):
                                    xe["khoi_luong_kg"] = 0.0
                                    
                                try:
                                    xe["the_tich_cbm"] = float(xe.get("the_tich_cbm") or 0.0)
                                except (ValueError, TypeError):
                                    xe["the_tich_cbm"] = 0.0
                                    
                                valid_records.append(xe)
                        except:
                            pass
            
            PROCESSED_HASHES.add(msg_hash)
            success = True
            time.sleep(8) 
            
        except Exception as e:
            if "429" in str(e).lower() or "quota" in str(e).lower():
                print("   ⚠️ [AI] Bị giới hạn 429! Đóng băng 60s...")
                time.sleep(60)
            else:
                PROCESSED_HASHES.add(msg_hash)
                success = True 
                
    if task_type == 'image' and os.path.exists(content):
        try: os.remove(content)
        except: pass

    save_history(PROCESSED_HASHES)
    
    if valid_records:
        df_new = pd.DataFrame(valid_records)
        if os.path.exists(EXCEL_FILE):
            df_existing = pd.read_excel(EXCEL_FILE)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(EXCEL_FILE, index=False)
        else:
            df_new.to_excel(EXCEL_FILE, index=False)
        print(f"   ✅ [LƯU DATA] Đã ghi {len(valid_records)} chuyến vào Excel!")

# ==========================================
# 3. LUỒNG ZALO (CUỘN CHẬM & LỌC TEXT THÔNG MINH)
# ==========================================
def run_zalo_sequential_pipeline():
    zalo_search_css = "#contact-search-input, [data-translate-placeholder='STR_SEARCH_CONTACT'], input[placeholder*='Tìm kiếm'], input[placeholder*='Search']"
    
    print("\n🚀 [ZALO] Đang khởi động trình duyệt...")
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir="./zalo_profile_data", headless=False, args=["--disable-notifications"]
                )
            except Exception as e:
                print(f"❌ Lỗi khởi động Playwright: {e}")
                return

            page = browser.new_page()
            page.goto("https://chat.zalo.me", timeout=60000)
            
            try:
                page.locator(zalo_search_css).first.wait_for(state="visible", timeout=20000)
                print("✅ [ZALO] Kết nối thành công!")
            except:
                print("❌ [LỖI] Zalo yêu cầu quét mã QR hoặc timeout!")
                browser.close()
                return

            for nhom in DANH_SACH_NHOM:
                print(f"\n----------------------------------------")
                print(f"🔎 [ZALO] Đang quét nhóm: {nhom}")
                group_tasks = []
                
                try:
                    search_box = page.locator(zalo_search_css).first
                    search_box.click(force=True)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    time.sleep(0.3) 
                    search_box.fill(nhom)
                    time.sleep(2.0) 
                    page.keyboard.press("Enter")
                    time.sleep(5.0) 
                    
                    # 🚀 CẢI TIẾN TỐC ĐỘ CUỘN: Cuộn chậm, mượt mà từng đoạn để Zalo kịp load ảnh và text
                    chat_box_locator = page.locator(".message-view__scroll__inner")
                    if chat_box_locator.count() > 0:
                        chat_box = chat_box_locator.first
                        print("   🔄 Đang cuộn chậm để tải đầy đủ lịch sử tin nhắn và hình ảnh...")
                        for _ in range(4):
                            chat_box.evaluate("el => el.scrollBy(0, -600)") # Cuộn từng đoạn vừa phải
                            time.sleep(1.2) # Dừng đủ lâu để render DOM
                    
                    time.sleep(2.5) 
                    
                    msg_elements = page.locator(".chat-message, .message-view__blur__inner, [class*='picture-message']").all()
                    if not msg_elements: continue
                    
                    skipped = 0
                    for msg_el in msg_elements[-25:]: # Lấy 25 tin nhắn mới nhất để không bỏ sót
                        msg_html = msg_el.inner_html()
                        msg_text = msg_el.inner_text().strip()
                        current_hash = get_msg_hash(msg_html + msg_text)
                        
                        if current_hash in PROCESSED_HASHES:
                            skipped += 1
                            continue 
                            
                        lower_txt = msg_text.lower()
                        
                        # Chỉ chặn rác tuyệt đối (CCCD, GPLX, biển số xe đơn thuần không kèm đơn hàng)
                        is_chi_la_bien_so = bool(re.search(r'^(bsx|biển số|cccd|gplx)[:\s]', lower_txt))
                        if is_chi_la_bien_so:
                            PROCESSED_HASHES.add(current_hash)
                            save_history(PROCESSED_HASHES)
                            continue

                        # 🚀 MỞ RỘNG TỪ KHÓA NHẬN DIỆN TEXT VẬN TẢI (Bắt trọn kg, tấn, cbm, giao, đóng hàng...)
                        has_transport_keyword = bool(re.search(r'xe|tấn|tan|kg|cbm|khối|khoi|đóng|dong|giao|nhận|vào|xp|xuất phát|tới|hàng|c|k', lower_txt))
                        img_locators = msg_el.locator("img:not(.emoji):not([src*='emoji']):not([src*='avatar'])").all()
                        has_image = len(img_locators) > 0

                        if not has_image and not has_transport_keyword:
                            PROCESSED_HASHES.add(current_hash)
                            save_history(PROCESSED_HASHES)
                            continue

                        if has_image:
                            for idx, img in enumerate(img_locators):
                                try:
                                    if not img.is_visible(): continue
                                    img.scroll_into_view_if_needed(timeout=2000)
                                    time.sleep(1.5) # Chờ ảnh nét hẳn mới chụp
                                    
                                    img_path = os.path.join(TEMP_IMG_DIR, f"zalo_img_{nhom}_{current_hash}_{idx}.jpg")
                                    img.screenshot(path=img_path, timeout=4000)
                                    group_tasks.append({'type': 'image', 'content': img_path, 'nhom': nhom, 'hash': current_hash})
                                except Exception:
                                    pass
                                
                        elif has_transport_keyword:
                            # Bắt cả nội dung text vận tải chi tiết mà bạn vừa đề cập
                            group_tasks.append({'type': 'text', 'content': msg_text, 'nhom': nhom, 'hash': current_hash})
                        else:
                            PROCESSED_HASHES.add(current_hash)
                            save_history(PROCESSED_HASHES)
                    
                except Exception as e:
                    print(f"   ❌ Lỗi khi quét tại nhóm {nhom}: {e}")
                    if "connection closed" in str(e).lower() or "target closed" in str(e).lower():
                        raise e 
                
                if group_tasks:
                    print(f"   🧠 [AI] Nhóm [{nhom}] có {len(group_tasks)} tác vụ. Bắt đầu xử lý...")
                    for task in group_tasks:
                        process_single_task(task)
                    print(f"   🛑 Đã xử lý xong nhóm {nhom}. Chờ 20s hồi sức API...")
                    time.sleep(20)
                
                time.sleep(5)

            browser.close()
            print("\n🔒 [ZALO] Đã quét xong mẻ và đóng trình duyệt an toàn.")
            
    except Exception as outer_e:
        print(f"\n⚠️ HỆ THỐNG PHỤC HỒI: Trình duyệt bị lỗi ({outer_e}). Tự động thử lại ở mẻ sau.")

# ==========================================
# 4. CHƯƠNG TRÌNH CHÍNH
# ==========================================
def main():
    print("🚀 HỆ THỐNG RPA BẢO TÍN KHỞI ĐỘNG (OPTIMIZED SCROLLING & TEXT FILTER)")
    while True:
        run_zalo_sequential_pipeline()
        
        print("\n=============================================")
        print("🛑 HOÀN TẤT MỘT VÒNG. NGHỈ 3 PHÚT (180s)...")
        print("=============================================")
        for i in range(180, 0, -30):
            print(f"Đang nghỉ... Còn {i}s")
            time.sleep(30)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Đã dừng an toàn.")
        sys.exit(0)