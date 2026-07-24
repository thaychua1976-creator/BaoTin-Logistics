import requests
import json

def lay_danh_sach_user_id():
    # Điền mã Access Token của bạn vào đây
    access_token = "GTu75lzfuZf4tmCR-MFiDKlU56YuEP0z2y5tSRS-o01FrYXEYZAjRt7-5ptA5A9X8w9DCErWn103kLT1x4QuDHU01K_LRx0TQfLHHT5lxGu2c5XHuLN5SJkBJ2hgGiXR3fXo8-PmzsnTqsKouWZgQHlZPK7V9TXh0FjRFUOJ_4qVv6jvsLhPA1cTF0RZOArT2juK5j0JcqqAg1aTpHALV2ZrTWUG6jDSAQDj1knAt2OLicLg-6ZSHqkFM1-NT_HyQumJ1j9jdIvhbp9RZtwq1dU6LYg_RjO5Nj16IBeTvYPzemD8hnYUPKlY2Yxv8UHaGyXNJQuLwIHK_tjOYZ_7TMJTLIsjOD5ZIfi-89Dlh59pp1mHjYszR0dK10Rr6wOfBFaqTD4-amnlnXKilJs5HKVY311PPNYBZjOP_dxfE0"
    
    # API lấy danh sách những người quan tâm OA mới nhất (tối đa 5 người)
    url = 'https://openapi.zalo.me/v2.0/oa/getfollowers?data={"offset":0,"count":5}'
    
    headers = {
        "access_token": access_token
    }
    
    try:
        response = requests.get(url, headers=headers)
        ket_qua = response.json()
        
        if ket_qua.get('error') == 0:
            danh_sach = ket_qua.get('data', {}).get('followers', [])
            if not danh_sach:
                print("Chưa có ai quan tâm OA này. Hãy dùng điện thoại bấm Quan tâm OA nhé!")
            else:
                print(f"✅ TÌM THẤY {len(danh_sach)} NGƯỜI QUAN TÂM:")
                for index, nguoi in enumerate(danh_sach):
                    print(f"Người thứ {index + 1}: user_id = {nguoi['user_id']}")
                print("\n👉 BẠN HÃY COPY MÃ USER_ID Ở TRÊN ĐỂ DÙNG CHO FILE GỬI TIN NHẮN!")
        else:
            print("⚠️ CÓ LỖI TỪ ZALO:", ket_qua.get('message'))
            
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    lay_danh_sach_user_id()