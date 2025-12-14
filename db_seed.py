from pymongo import MongoClient
from werkzeug.security import generate_password_hash

client = MongoClient('mongodb://localhost:27017/')
db = client['LibManagerDB']

# Xóa dữ liệu cũ để tránh trùng lặp
db.users.delete_many({})
db.books.delete_many({})
db.book_copies.delete_many({})
db.transactions.delete_many({})

print("Đang nạp dữ liệu...")

# 1. Tạo Users
users = [
    {
        "username": "admin",
        "password": generate_password_hash("123"),
        "role": "admin",
        "fullname": "Thủ Thư (Admin)",
        "email": "admin@ptit.edu.vn"
    },
    {
        "username": "B20DCCN001",
        "msv": "B20DCCN001",
        "password": generate_password_hash("123"),
        "role": "user",
        "fullname": "Nguyễn Văn A",
        "email": "sv@ptit.edu.vn"
    }
]
db.users.insert_many(users)

# 2. Tạo Sách (Dựa trên UI bạn gửi)
books = [
    {"isbn": "978-1", "title": "Clean Code", "author": "Robert C. Martin", "category": "CNTT", "qty": 15},
    {"isbn": "978-2", "title": "Kinh tế Vĩ mô", "author": "N. Gregory Mankiw", "category": "Kinh tế", "qty": 5},
    {"isbn": "978-3", "title": "Đắc Nhân Tâm", "author": "Dale Carnegie", "category": "Kỹ năng", "qty": 10},
    {"isbn": "978-4", "title": "Tư duy nhanh và chậm", "author": "Daniel Kahneman", "category": "Kỹ năng", "qty": 8}
]

for b in books:
    # Đầu sách
    db.books.insert_one({
        "isbn": b['isbn'], "title": b['title'], "author": b['author'],
        "category": b['category'], "qty_total": b['qty'], "qty_avail": b['qty']
    })
    # Bản lưu (Copies)
    copies = []
    for i in range(b['qty']):
        copies.append({
            "isbn_ref": b['isbn'],
            "barcode": f"{b['isbn']}-{i+1}",
            "status": "available"
        })
    db.book_copies.insert_many(copies)

print("XONG! Tài khoản Admin: admin/123 | User: B20DCCN001/123")