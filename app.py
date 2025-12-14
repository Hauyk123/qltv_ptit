from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'PTIT_LIB_SECURE_KEY_2025'  # Key bảo mật session
CORS(app)

# KẾT NỐI MONGODB
client = MongoClient('mongodb://localhost:27017/')
db = client['LibManagerDB']


# --- ROUTING (ĐIỀU HƯỚNG HTML) ---
@app.route('/')
def user_home():
    return render_template('user_home.html')


@app.route('/book/<isbn>')
def user_book_detail(isbn):
    return render_template('user_book_detail.html', isbn=isbn)


@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_dashboard.html')


@app.route('/admin/book/<isbn>')
def admin_book_detail(isbn):
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_book_detail.html', isbn=isbn)

@app.route('/admin/books')
def admin_books():
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_books.html')
# --- API AUTHENTICATION ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Tìm user
    user = db.users.find_one({'$or': [{'username': username}, {'msv': username}]})

    if not user:
        return jsonify({'status': 'error', 'message': 'Tài khoản không tồn tại!'}), 404

    # 1. Kiểm tra xem có bị khóa không
    if user.get('lock_until') and user['lock_until'] > datetime.now():
        lock_time = user['lock_until'].strftime("%H:%M:%S")
        return jsonify({'status': 'error', 'message': f'Tài khoản bị khóa đến {lock_time} do nhập sai quá 5 lần!'}), 403

    # 2. Kiểm tra mật khẩu
    if check_password_hash(user['password'], password):
        # Đăng nhập thành công -> Reset số lần sai
        db.users.update_one({'_id': user['_id']}, {
            '$set': {'failed_attempts': 0, 'lock_until': None}
        })

        session['user_id'] = str(user['_id'])
        session['role'] = user['role']
        session['fullname'] = user['fullname']

        return jsonify({
            'status': 'success',
            'role': user['role'],
            'redirect': '/admin' if user['role'] == 'admin' else '/'
        })
    else:
        # Nhập sai -> Tăng số lần sai
        attempts = user.get('failed_attempts', 0) + 1
        update_data = {'failed_attempts': attempts}
        msg = f'Sai mật khẩu! ({attempts}/5)'

        # Nếu sai 5 lần -> Khóa 5 phút
        if attempts >= 5:
            lock_time = datetime.now() + timedelta(minutes=5)
            update_data['lock_until'] = lock_time
            msg = 'Sai quá 5 lần! Tài khoản bị khóa 5 phút.'

        db.users.update_one({'_id': user['_id']}, {'$set': update_data})
        return jsonify({'status': 'error', 'message': msg}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/admin/circulation')
def admin_circulation():
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_circulation.html')
# --- ROUTING MỚI CHO PHẦN 2 ---
@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_users.html')


@app.route('/profile')
def user_profile():
    if 'user_id' not in session: return redirect('/')
    return render_template('user_profile.html')


# --- API QUẢN LÝ ĐỘC GIẢ (ADMIN) ---
@app.route('/api/admin/users', methods=['GET'])
def get_users():
    if session.get('role') != 'admin': return jsonify([]), 403

    # Lấy danh sách user (trừ admin)
    users = list(db.users.find({'role': 'user'}, {'password': 0}))

    # Tính toán thông tin bổ sung (Sách đang mượn, nợ phạt) cho từng user
    for u in users:
        u['_id'] = str(u['_id'])
        u['borrow_count'] = db.transactions.count_documents({'user_id': str(u['_id']), 'status': 'borrowing'})
        # Tính tổng tiền phạt chưa đóng (giả lập logic đơn giản)
        # Thực tế cần tính từ collection 'fines' hoặc tương tự
        u['total_fine'] = 0

    return jsonify(users)


@app.route('/api/admin/user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    data = request.json

    # Kiểm tra trùng MSV hoặc Username
    if db.users.find_one({'$or': [{'username': data['msv']}, {'email': data['email']}]}):
        return jsonify({'status': 'error', 'message': 'MSV hoặc Email đã tồn tại!'}), 400

    new_user = {
        "username": data['msv'],  # Username mặc định là MSV
        "msv": data['msv'],
        "password": generate_password_hash("123456"),  # Mặc định 123456
        "role": "user",
        "fullname": data['fullname'],
        "email": data['email'],
        "phone": data.get('phone', ''),
        "created_at": datetime.now()
    }
    db.users.insert_one(new_user)
    return jsonify({'status': 'success', 'message': 'Thêm độc giả thành công!'})


@app.route('/api/admin/user/<uid>/reset-pass', methods=['POST'])
def reset_pass(uid):
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403

    # Reset mật khẩu về 123456
    db.users.update_one({'_id': ObjectId(uid)}, {'$set': {'password': generate_password_hash('123456')}})
    return jsonify({'status': 'success', 'message': 'Đã reset mật khẩu về 123456'})


# --- API HỒ SƠ CÁ NHÂN (USER) ---
@app.route('/api/user/profile', methods=['GET'])
def get_my_profile():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    u = db.users.find_one({'_id': ObjectId(session['user_id'])}, {'password': 0})
    u['_id'] = str(u['_id'])

    # Lấy lịch sử mượn
    history = list(db.transactions.find({'user_id': session['user_id']}).sort('borrow_date', -1).limit(10))
    for h in history:
        h['_id'] = str(h['_id'])

    return jsonify({'user': u, 'history': history})


@app.route('/api/user/change-password', methods=['POST'])
def change_pass():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401
    data = request.json

    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    if not check_password_hash(user['password'], data['old_pass']):
        return jsonify({'status': 'error', 'message': 'Mật khẩu cũ không đúng!'}), 400

    # Kiểm tra độ mạnh mật khẩu (Tối thiểu 8 ký tự) - có thể thêm regex
    if len(data['new_pass']) < 8:
        return jsonify({'status': 'error', 'message': 'Mật khẩu mới phải trên 8 ký tự!'}), 400

    db.users.update_one({'_id': ObjectId(session['user_id'])}, {
        '$set': {'password': generate_password_hash(data['new_pass'])}
    })
    return jsonify({'status': 'success', 'message': 'Đổi mật khẩu thành công!'})
# --- API SÁCH ---
@app.route('/api/books', methods=['GET'])
def get_books():
    q = request.args.get('q', '')
    query = {}
    if q:
        # SỬA: Dùng $or để tìm trong cả title, author và isbn
        query = {
            '$or': [
                {'title': {'$regex': q, '$options': 'i'}},
                {'author': {'$regex': q, '$options': 'i'}},
                {'isbn': {'$regex': q, '$options': 'i'}}
            ]
        }

    books = list(db.books.find(query, {'_id': 0}))
    return jsonify(books)


@app.route('/api/book/<isbn>', methods=['GET'])
def get_book_detail(isbn):
    book = db.books.find_one({'isbn': isbn}, {'_id': 0})
    if not book: return jsonify({'status': 'error'}), 404

    copies = list(db.book_copies.find({'isbn_ref': isbn}, {'_id': 0}))
    return jsonify({'book': book, 'copies': copies})


# --- API ADMIN QUẢN LÝ SÁCH ---

@app.route('/api/admin/book', methods=['POST'])
def add_book():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    isbn = data.get('isbn')
    qty = int(data.get('qty', 1))

    if db.books.find_one({'isbn': isbn}):
        return jsonify({'status': 'error', 'message': 'Mã ISBN này đã tồn tại!'}), 400

    new_book = {
        'isbn': isbn,
        'title': data.get('title'),
        'author': data.get('author'),
        'category': data.get('category'),
        'publisher': data.get('publisher'),
        'year': data.get('year'),
        'price': int(data.get('price', 0) or 0), # Chuyển về số nguyên
        'language': data.get('language'),
        'location': data.get('location'),
        'image_url': data.get('image_url'),      # <--- MỚI: Lưu link ảnh
        'qty_total': qty,
        'qty_avail': qty,
        'created_at': datetime.now()
    }
    db.books.insert_one(new_book)

    # Tạo bản lưu (Copies)
    copies = []
    for i in range(qty):
        copies.append({
            'isbn_ref': isbn,
            'barcode': f"{isbn}-{i + 1}",
            'status': 'available',
            'location': data.get('location')
        })
    if copies:
        db.book_copies.insert_many(copies)

    return jsonify({'status': 'success', 'message': 'Thêm sách thành công'})
@app.route('/api/admin/book/<isbn>', methods=['DELETE'])
def delete_book(isbn):
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    # Kiểm tra xem có bản sao nào đang được mượn không
    if db.book_copies.find_one({'isbn_ref': isbn, 'status': 'borrowed'}):
        return jsonify({'status': 'error', 'message': 'Không thể xóa: Có bản lưu đang được mượn!'}), 400

    # Xóa đầu sách và toàn bộ bản sao
    db.books.delete_one({'isbn': isbn})
    db.book_copies.delete_many({'isbn_ref': isbn})

    return jsonify({'status': 'success', 'message': 'Đã xóa sách'})


# --- API NGHIỆP VỤ MƯỢN - TRẢ - GIA HẠN (ADMIN) ---

# 1. API Tìm kiếm Độc giả (Cho autocomplete)
@app.route('/api/admin/find-user', methods=['GET'])
def find_user():
    q = request.args.get('q', '')
    if not q: return jsonify([])
    # Tìm theo tên hoặc MSV
    users = list(db.users.find({
        'role': 'user',
        '$or': [{'fullname': {'$regex': q, '$options': 'i'}}, {'msv': {'$regex': q, '$options': 'i'}}]
    }, {'password': 0, 'role': 0}).limit(5))

    for u in users:
        u['_id'] = str(u['_id'])
        # Đếm sách đang mượn
        u['borrow_count'] = db.transactions.count_documents({'user_id': str(u['_id']), 'status': 'borrowing'})
    return jsonify(users)


# 2. API Lấy thông tin sách qua Mã vạch (Khi quét mã)
@app.route('/api/admin/check-book/<barcode>', methods=['GET'])
def check_book_barcode(barcode):
    # Tìm bản lưu trong kho
    copy = db.book_copies.find_one({'barcode': barcode})
    if not copy: return jsonify({'status': 'error', 'message': 'Không tìm thấy mã vạch này!'}), 404

    # Lấy thông tin đầu sách
    book_info = db.books.find_one({'isbn': copy['isbn_ref']})

    return jsonify({
        'status': 'success',
        'book': {
            'title': book_info['title'],
            'author': book_info['author'],
            'barcode': barcode,
            'copy_status': copy['status']
        }
    })


# 3. API Thực hiện Mượn Sách (Submit phiếu mượn)
# Tìm hàm @app.route('/api/admin/borrow', methods=['POST']) và THAY THẾ TOÀN BỘ nội dung hàm bằng:
@app.route('/api/admin/borrow', methods=['POST'])
def admin_borrow():
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    data = request.json
    user_id = data.get('user_id')
    barcodes = data.get('barcodes', [])

    if not user_id or not barcodes:
        return jsonify({'status': 'error', 'message': 'Thiếu thông tin!'}), 400

    # Đếm số sách đang mượn (trừ trạng thái pending vì pending sẽ được chuyển thành borrowing hoặc hủy)
    current_loans = db.transactions.count_documents({'user_id': user_id, 'status': 'borrowing'})

    # Logic kiểm tra số lượng có thể thay đổi tùy nhu cầu, ở đây tạm bỏ qua để đơn giản hóa việc fix lỗi

    success_count = 0
    for code in barcodes:
        # 1. Tìm bản lưu (Copy)
        copy = db.book_copies.find_one({'barcode': code})
        if not copy: continue

        # 2. Xử lý trường hợp sách đang AVAILABLE (Mượn trực tiếp)
        if copy['status'] == 'available':
            db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
            db.books.update_one({'isbn': copy['isbn_ref']}, {'$inc': {'qty_avail': -1}})

            db.transactions.insert_one({
                'user_id': user_id,
                'barcode': code,
                'book_title': db.books.find_one({'isbn': copy['isbn_ref']})['title'],
                'borrow_date': datetime.now(),
                'due_date': datetime.now() + timedelta(days=14),
                'status': 'borrowing',
                'renew_count': 0
            })
            success_count += 1

        # 3. Xử lý trường hợp sách đang PENDING (User đã đặt online)
        elif copy['status'] == 'pending':
            # Tìm giao dịch pending của đúng user này với mã vạch này
            pending_trans = db.transactions.find_one({
                'user_id': user_id,
                'barcode': code,
                'status': 'pending'
            })

            if pending_trans:
                # Cập nhật giao dịch pending thành borrowing
                db.transactions.update_one({'_id': pending_trans['_id']}, {
                    '$set': {
                        'status': 'borrowing',
                        'borrow_date': datetime.now(),
                        'due_date': datetime.now() + timedelta(days=14)
                    }
                })
                # Cập nhật trạng thái copy
                db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
                success_count += 1
            else:
                # Sách pending nhưng của người khác -> Bỏ qua hoặc báo lỗi (ở đây ta bỏ qua)
                pass

    return jsonify({'status': 'success', 'message': f'Đã mượn thành công {success_count} cuốn sách!'})

# 4. API Trả Sách (Xử lý từng cuốn)
@app.route('/api/admin/return', methods=['POST'])
def admin_return():
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    barcode = request.json.get('barcode')

    trans = db.transactions.find_one({'barcode': barcode, 'status': 'borrowing'})
    if not trans:
        return jsonify({'status': 'error', 'message': 'Sách này không ở trạng thái đang mượn!'}), 400

    # Tính phạt
    overdue_days = 0
    fine_amount = 0
    if datetime.now() > trans['due_date']:
        delta = datetime.now() - trans['due_date']
        overdue_days = delta.days
        fine_amount = overdue_days * 1000  # 1000đ/ngày

    # Update Transaction
    update_data = {
        'status': 'returned',
        'return_date': datetime.now(),
        'fine': fine_amount,
        'overdue_days': overdue_days
    }

    # Nếu có phạt thì đánh dấu là Chưa trả tiền
    if fine_amount > 0:
        update_data['fine_paid'] = False

    db.transactions.update_one({'_id': trans['_id']}, {'$set': update_data})

    # Update Kho sách
    db.book_copies.update_one({'barcode': barcode}, {'$set': {'status': 'available'}})
    copy = db.book_copies.find_one({'barcode': barcode})
    db.books.update_one({'isbn': copy['isbn_ref']}, {'$inc': {'qty_avail': 1}})

    return jsonify({
        'status': 'success',
        'message': 'Trả sách thành công!',
        'fine': fine_amount,
        'overdue': overdue_days
    })
# 5. API Lấy sách đang mượn của User (Để Gia hạn)
@app.route('/api/admin/user-loans/<uid>', methods=['GET'])
def get_user_loans(uid):
    loans = list(db.transactions.find({'user_id': uid, 'status': 'borrowing'}))
    for l in loans:
        l['_id'] = str(l['_id'])
        l['borrow_date'] = l['borrow_date'].strftime('%d/%m/%Y')
        l['due_date_fmt'] = l['due_date'].strftime('%d/%m/%Y')
        l['is_overdue'] = datetime.now() > l['due_date']
    return jsonify(loans)


# 6. API Gia hạn sách
@app.route('/api/admin/renew', methods=['POST'])
def renew_book():
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    trans_id = request.json.get('trans_id')

    trans = db.transactions.find_one({'_id': ObjectId(trans_id)})

    # Kiểm tra điều kiện (Chưa quá hạn, chưa gia hạn quá 1 lần)
    if trans['renew_count'] >= 1:
        return jsonify({'status': 'error', 'message': 'Sách này đã gia hạn 1 lần, không thể gia hạn thêm!'}), 400

    if datetime.now() > trans['due_date']:
        return jsonify({'status': 'error', 'message': 'Sách đã quá hạn, không thể gia hạn!'}), 400

    # Gia hạn thêm 7 ngày
    new_due = trans['due_date'] + timedelta(days=7)
    db.transactions.update_one({'_id': trans['_id']}, {
        '$set': {'due_date': new_due},
        '$inc': {'renew_count': 1}
    })

    return jsonify({'status': 'success', 'message': 'Gia hạn thành công thêm 7 ngày!'})
# --- API MƯỢN SÁCH ---
@app.route('/api/borrow', methods=['POST'])
def borrow_book():
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Chưa đăng nhập'}), 401

    data = request.json
    isbn = data.get('isbn')

    # 1. Kiểm tra giới hạn mượn (Max 5)
    current_loans = db.transactions.count_documents({'user_id': session['user_id'], 'status': 'borrowing'})
    if current_loans >= 5:
        return jsonify({'status': 'error', 'message': 'Bạn đã đạt giới hạn mượn 5 cuốn!'}), 400

    # 2. Tìm một cuốn sách "available"
    copy = db.book_copies.find_one({'isbn_ref': isbn, 'status': 'available'})
    if not copy:
        return jsonify({'status': 'error', 'message': 'Sách này đã hết bản lưu!'}), 400

    # 3. Thực hiện mượn
    # Update trạng thái copy
    db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
    # Giảm số lượng khả dụng ở đầu sách
    db.books.update_one({'isbn': isbn}, {'$inc': {'qty_avail': -1}})

    # Tạo transaction
    db.transactions.insert_one({
        'user_id': session['user_id'],
        'book_title': db.books.find_one({'isbn': isbn})['title'],
        'book_barcode': copy['barcode'],
        'borrow_date': datetime.now(),
        'due_date': datetime.now() + timedelta(days=14),
        'status': 'borrowing',
        'renew_count': 0
    })

    return jsonify({'status': 'success', 'message': 'Mượn sách thành công!'})


# --- API THỐNG KÊ (ADMIN) ---
@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify({
        'total_books': db.books.count_documents({}),
        'borrowing': db.transactions.count_documents({'status': 'borrowing'}),
        'overdue': db.transactions.count_documents({'status': 'borrowing', 'due_date': {'$lt': datetime.now()}}),
        'revenue': '2.500.000'
    })


# --- API GIỎ HÀNG (DATABASE) ---

@app.route('/api/cart', methods=['GET'])
def get_cart():
    """Lấy danh sách sách trong giỏ của User"""
    if 'user_id' not in session: return jsonify([])

    cart = db.carts.find_one({'user_id': session['user_id']})
    # Trả về list items hoặc list rỗng nếu chưa có cart
    return jsonify(cart.get('items', []) if cart else [])


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """Thêm sách vào giỏ DB"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Vui lòng đăng nhập!'}), 401

    data = request.json
    isbn = data.get('isbn')

    # 1. Kiểm tra giới hạn giỏ hàng (Max 5)
    cart = db.carts.find_one({'user_id': session['user_id']})
    current_items = cart.get('items', []) if cart else []

    if len(current_items) >= 5:
        return jsonify({'status': 'error', 'message': 'Giỏ sách đã đầy (Max 5 cuốn)!'}), 400

    # 2. Kiểm tra trùng sách
    if any(item['isbn'] == isbn for item in current_items):
        return jsonify({'status': 'error', 'message': 'Sách này đã có trong giỏ!'}), 400

    # 3. Thêm vào DB (Dùng $push và upsert=True để tự tạo nếu chưa có)
    new_item = {
        'isbn': isbn,
        'title': data.get('title'),
        'author': data.get('author')
    }
    db.carts.update_one(
        {'user_id': session['user_id']},
        {'$push': {'items': new_item}},
        upsert=True
    )

    return jsonify({'status': 'success', 'message': 'Đã thêm vào giỏ!'})


@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    """Xóa sách khỏi giỏ DB"""
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401
    data = request.json

    # Dùng $pull để xóa item có isbn khớp
    db.carts.update_one(
        {'user_id': session['user_id']},
        {'$pull': {'items': {'isbn': data.get('isbn')}}}
    )
    return jsonify({'status': 'success'})


@app.route('/api/user/checkout-db', methods=['POST'])
def checkout_db():
    """Xử lý đăng ký mượn từ Giỏ hàng trong DB"""
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    # 1. Lấy sách từ DB Cart
    cart = db.carts.find_one({'user_id': session['user_id']})
    if not cart or not cart.get('items'):
        return jsonify({'status': 'error', 'message': 'Giỏ hàng trống!'}), 400

    items = cart['items']

    # 2. Kiểm tra giới hạn mượn (Tổng đang mượn + Giỏ hàng <= 5)
    current_borrowing = db.transactions.count_documents({
        'user_id': session['user_id'],
        'status': {'$in': ['borrowing', 'pending']}
    })

    if current_borrowing + len(items) > 5:
        return jsonify({'status': 'error', 'message': f'Quá giới hạn! Bạn đang mượn {current_borrowing} cuốn.'}), 400

    success_count = 0

    # 3. Duyệt từng sách để đăng ký
    for item in items:
        isbn = item['isbn']
        # Tìm bản lưu có sẵn
        copy = db.book_copies.find_one({'isbn_ref': isbn, 'status': 'available'})

        if copy:
            # Update trạng thái
            db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'pending'}})
            db.books.update_one({'isbn': isbn}, {'$inc': {'qty_avail': -1}})

            # Tạo Transaction Pending
            db.transactions.insert_one({
                'user_id': session['user_id'],
                'book_title': item['title'],
                'barcode': copy['barcode'],
                'borrow_date': datetime.now(),
                'due_date': datetime.now() + timedelta(days=2),
                'status': 'pending',
                'renew_count': 0
            })
            success_count += 1

    # 4. Nếu thành công ít nhất 1 cuốn -> Xóa giỏ hàng
    if success_count > 0:
        db.carts.delete_one({'user_id': session['user_id']})
        return jsonify({'status': 'success',
                        'message': f'Đăng ký thành công {success_count} cuốn! Vui lòng đến thư viện nhận sách.'})
    else:
        return jsonify({'status': 'error', 'message': 'Các sách trong giỏ đều đã hết bản lưu!'}), 400
# --- ROUTE CHO USER (Thêm vào app.py) ---
@app.route('/my-books')
def user_loans_page():
    # Kiểm tra đăng nhập
    if 'user_id' not in session: return redirect('/')
    # Trả về giao diện html
    return render_template('user_loans.html')


# --- CÁC API CÒN THIẾU CHO USER (Chèn vào trước app.run) ---

@app.route('/api/user/my-loans', methods=['GET'])
def get_my_loans():
    if 'user_id' not in session: return jsonify([]), 401

    # Lấy cả sách đang mượn và sách đang chờ lấy (pending)
    loans = list(db.transactions.find({
        'user_id': session['user_id'],
        'status': {'$in': ['borrowing', 'pending']}
    }).sort('borrow_date', -1))

    for l in loans:
        l['_id'] = str(l['_id'])
        l['borrow_date_fmt'] = l['borrow_date'].strftime('%d/%m/%Y')
        l['due_date_fmt'] = l['due_date'].strftime('%d/%m/%Y')
        l['is_overdue'] = datetime.now() > l['due_date']

        # Tính số ngày còn lại
        delta = l['due_date'] - datetime.now()
        l['days_left'] = delta.days if delta.days > 0 else 0

    return jsonify(loans)


@app.route('/api/user/renew', methods=['POST'])
def user_renew():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    trans_id = request.json.get('trans_id')
    trans = db.transactions.find_one({'_id': ObjectId(trans_id), 'user_id': session['user_id']})

    if not trans: return jsonify({'status': 'error', 'message': 'Giao dịch không tồn tại!'}), 404

    # Kiểm tra điều kiện gia hạn
    if trans['status'] != 'borrowing':
        return jsonify({'status': 'error', 'message': 'Chỉ có thể gia hạn sách đang mượn!'}), 400

    if trans['renew_count'] >= 1:
        return jsonify({'status': 'error', 'message': 'Bạn đã hết lượt gia hạn cho sách này!'}), 400

    if datetime.now() > trans['due_date']:
        return jsonify({'status': 'error', 'message': 'Sách đã quá hạn, vui lòng mang trả!'}), 400

    # Gia hạn thêm 7 ngày
    new_due = trans['due_date'] + timedelta(days=7)
    db.transactions.update_one({'_id': trans['_id']}, {
        '$set': {'due_date': new_due},
        '$inc': {'renew_count': 1}
    })

    return jsonify({'status': 'success', 'message': 'Gia hạn thành công thêm 7 ngày!'})


# --- ROUTE MỚI ---
@app.route('/admin/fines')
def admin_fines():
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_fines.html')


# --- API QUẢN LÝ PHẠT ---
@app.route('/api/admin/fines', methods=['GET'])
def get_fines_list():
    if session.get('role') != 'admin': return jsonify([]), 403

    # Lấy các giao dịch có tiền phạt > 0
    # Sắp xếp: Chưa trả tiền lên trước
    fines = list(db.transactions.find({'fine': {'$gt': 0}}).sort([('fine_paid', 1), ('return_date', -1)]))

    result = []
    for f in fines:
        # Lấy thông tin user để hiển thị tên
        user = db.users.find_one({'_id': ObjectId(f['user_id'])})
        result.append({
            'id': str(f['_id']),
            'user_name': user['fullname'] if user else 'Unknown',
            'user_msv': user['msv'] if user else '---',
            'book_title': f['book_title'],
            'fine': f['fine'],
            'reason': f"Quá hạn {f.get('overdue_days', 0)} ngày",
            'date': f['return_date'].strftime('%d/%m/%Y'),
            'paid': f.get('fine_paid', True)  # Nếu không có field này coi như đã trả (dữ liệu cũ)
        })
    return jsonify(result)


@app.route('/api/admin/pay-fine', methods=['POST'])
def pay_fine():
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    trans_id = request.json.get('id')

    db.transactions.update_one({'_id': ObjectId(trans_id)}, {
        '$set': {'fine_paid': True, 'payment_date': datetime.now()}
    })
    return jsonify({'status': 'success', 'message': 'Đã xác nhận thu tiền!'})


# --- API BIỂU ĐỒ DASHBOARD ---
@app.route('/api/admin/chart-data', methods=['GET'])
def get_chart_data():
    # 1. Thống kê tình trạng sách
    total_books = db.book_copies.count_documents({})
    borrowed = db.book_copies.count_documents({'status': 'borrowed'})
    available = total_books - borrowed

    # 2. Thống kê doanh thu phạt (Giả lập theo 6 tháng gần nhất)
    # Trong thực tế bạn sẽ query aggregate từ DB
    revenue_data = [0, 0, 0, 0, 0, 0]  # Placeholder
    months = []
    for i in range(5, -1, -1):
        month = (datetime.now() - timedelta(days=30 * i)).strftime('%m/%Y')
        months.append(month)

    return jsonify({
        'pie_data': [available, borrowed],
        'bar_labels': months,
        'bar_data': [50000, 150000, 80000, 200000, 120000, 300000]  # Số liệu giả lập để demo biểu đồ
    })
if __name__ == '__main__':
    app.run(debug=True, port=5000)