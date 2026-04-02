from pymongo import MongoClient

# Kết nối database
client = MongoClient('mongodb://localhost:27017/')
db = client['LibManagerDB']

# ==========================================
# THAY ĐỔI 2 THÔNG TIN DƯỚI ĐÂY THÀNH CỦA BẠN
# ==========================================
TARGET_MSV = "B20DCAT694"  # Nhập chính xác MSV bạn vừa nhắm tới trên web
YOUR_REAL_EMAIL = "ducnvb22dccn236@gmail.com"  # Điền Gmail thật của bạn vào đây

# Thực hiện cập nhật email vào DB
result = db.users.update_one(
    {'msv': TARGET_MSV},
    {'$set': {'email': YOUR_REAL_EMAIL}}
)

if result.modified_count > 0:
    print(f"✅ Tuyệt vời! Đã đổi email của {TARGET_MSV} thành {YOUR_REAL_EMAIL}")
    print("Bây giờ bạn hãy lên web và bấm nút 'Báo cáo' của sinh viên này nhé!")
else:
    print("❌ Lỗi: Không tìm thấy MSV này, bạn hãy kiểm tra lại xem gõ đúng chưa nhé!")