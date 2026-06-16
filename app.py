from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
import pymysql.cursors
from datetime import datetime
import os
import ssl
from functools import wraps # <--- Ditambahkan untuk mendukung decorator hak akses

app = Flask(__name__)
app.secret_key = 'SistemInformasiLaundrySuperRahasiaCloudTiDB'

# Konfigurasi Koneksi TiDB Cloud
DB_HOST = "gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com"
DB_PORT = 4000
DB_USER = "3VgU2wA5SMVPQ4y.root"
DB_PASSWORD = "2Yjs7g7h2tubb4Sq"
DB_NAME = "LAUNDRY"

def get_db_connection():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            ssl=ssl_context 
        )
        return connection
    except Exception as e:
        print(f"Koneksi Database Gagal: {e}")
        return None

def is_logged_in():
    return 'logged_in' in session

# --- DECORATOR HAK AKSES ADMIN ---
def admin_required(f):
    """Decorator untuk membatasi akses rute khusus untuk Admin saja."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'Admin':
            flash('Akses ditolak! Anda tidak memiliki wewenang untuk melakukan aksi ini.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def filter_auth():
    allowed_routes = ['login', 'static']
    if request.endpoint and request.endpoint not in allowed_routes:
        if not is_logged_in():
            flash('Silakan login terlebih dahulu untuk mengakses sistem.', 'warning')
            return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if conn is None:
            flash('Gagal terhubung ke database cloud.', 'danger')
            return render_template('login.html')
            
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM users WHERE username = %s AND password = %s"
                cursor.execute(sql, (username, password))
                user = cursor.fetchone()
                
                if user:
                    session['logged_in'] = True
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['nama'] = user['nama']
                    session['role'] = user['role']
                    flash(f'Selamat datang kembali, {user["nama"]}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Username atau password salah.', 'danger')
        except Exception as e:
            flash(f'Terjadi kesalahan sistem: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar dari sistem.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    if conn is None:
        flash('Gagal mengambil data dashboard.', 'danger')
        return render_template('dashboard.html', stats={}, datetime_now="")
        
    stats = {
        'total_pelanggan': 0,
        'total_transaksi': 0,
        'diproses': 0,
        'selesai': 0
    }
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM pelanggan")
            stats['total_pelanggan'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM transaksi")
            stats['total_transaksi'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM transaksi WHERE status = 'Diproses'")
            stats['diproses'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM transaksi WHERE status = 'Selesai'")
            stats['selesai'] = cursor.fetchone()['count']
            
    except Exception as e:
        flash(f'Gagal memuat statistik: {e}', 'danger')
    finally:
        conn.close()
        
    current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
    return render_template('dashboard.html', stats=stats, datetime_now=current_time)

# --- CRUD PELANGGAN ---
@app.route('/pelanggan')
def pelanggan_index():
    search = request.args.get('search', '')
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('dashboard'))
        
    pelanggan_list = []
    try:
        with conn.cursor() as cursor:
            if search:
                sql = "SELECT * FROM pelanggan WHERE nama LIKE %s ORDER BY id DESC"
                cursor.execute(sql, (f"%{search}%",))
            else:
                sql = "SELECT * FROM pelanggan ORDER BY id DESC"
                cursor.execute(sql)
            pelanggan_list = cursor.fetchall()
    except Exception as e:
        flash(f'Gagal memuat data pelanggan: {e}', 'danger')
    finally:
        conn.close()
        
    return render_template('pelanggan/list.html', pelanggan=pelanggan_list, search=search)

@app.route('/pelanggan/tambah', methods=['GET', 'POST'])
def pelanggan_tambah():
    if request.method == 'POST':
        nama = request.form.get('nama')
        no_hp = request.form.get('no_hp')
        alamat = request.form.get('alamat')
        
        if not nama or not no_hp or not alamat:
            flash('Semua field wajib diisi.', 'warning')
            return render_template('pelanggan/tambah.html')
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "INSERT INTO pelanggan (nama, no_hp, alamat) VALUES (%s, %s, %s)"
                cursor.execute(sql, (nama, no_hp, alamat))
                conn.commit()
                flash('Pelanggan berhasil disimpan.', 'success')
                return redirect(url_for('pelanggan_index'))
        except Exception as e:
            flash(f'Gagal menyimpan pelanggan: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('pelanggan/tambah.html')

@app.route('/pelanggan/edit/<int:id>', methods=['GET', 'POST'])
def pelanggan_edit(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('pelanggan_index'))
        
    pelanggan = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM pelanggan WHERE id = %s", (id,))
            pelanggan = cursor.fetchone()
    except Exception as e:
        flash(f'Gagal mengambil data pelanggan: {e}', 'danger')
        conn.close()
        return redirect(url_for('pelanggan_index'))
        
    if not pelanggan:
        flash('Pelanggan tidak ditemukan.', 'warning')
        conn.close()
        return redirect(url_for('pelanggan_index'))
        
    if request.method == 'POST':
        nama = request.form.get('nama')
        no_hp = request.form.get('no_hp')
        alamat = request.form.get('alamat')
        
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE pelanggan SET nama = %s, no_hp = %s, alamat = %s WHERE id = %s"
                cursor.execute(sql, (nama, no_hp, alamat, id))
                conn.commit()
                flash('Pelanggan berhasil diperbarui.', 'success')
                return redirect(url_for('pelanggan_index'))
        except Exception as e:
            flash(f'Gagal memperbarui data: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('pelanggan/edit.html', pelanggan=pelanggan)

@app.route('/pelanggan/hapus/<int:id>', methods=['POST'])
@admin_required  # <--- Hanya Admin yang boleh menghapus
def pelanggan_hapus(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('pelanggan_index'))
        
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM pelanggan WHERE id = %s"
            cursor.execute(sql, (id,))
            conn.commit()
            flash('Pelanggan berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus data: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('pelanggan_index'))


# --- CRUD TRANSAKSI ---
@app.route('/transaksi')
def transaksi_index():
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('dashboard'))
        
    transaksi_list = []
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT t.*, p.nama AS pelanggan_nama 
                FROM transaksi t
                JOIN pelanggan p ON t.pelanggan_id = p.id
                ORDER BY t.tanggal_masuk DESC
            """
            cursor.execute(sql)
            transaksi_list = cursor.fetchall()
    except Exception as e:
        flash(f'Gagal memuat daftar transaksi: {e}', 'danger')
    finally:
        conn.close()
        
    return render_template('transaksi/list.html', transaksi=transaksi_list)

@app.route('/transaksi/tambah', methods=['GET', 'POST'])
def transaksi_tambah():
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('transaksi_index'))
        
    pelanggan_list = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nama FROM pelanggan ORDER BY nama ASC")
            pelanggan_list = cursor.fetchall()
    except Exception as e:
        flash(f'Gagal memuat relasi pelanggan: {e}', 'danger')
        conn.close()
        return redirect(url_for('transaksi_index'))
        
    if request.method == 'POST':
        pelanggan_id = request.form.get('pelanggan_id')
        berat = request.form.get('berat')
        harga_per_kg = request.form.get('harga_per_kg')
        status = request.form.get('status', 'Diproses')
        tanggal_masuk = request.form.get('tanggal_masuk')
        
        try:
            f_berat = float(berat)
            f_harga = float(harga_per_kg)
            total = f_berat * f_harga
            
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO transaksi (pelanggan_id, berat, harga_per_kg, total, status, tanggal_masuk)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (pelanggan_id, f_berat, f_harga, total, status, tanggal_masuk))
                conn.commit()
                flash('Transaksi berhasil ditambahkan.', 'success')
                return redirect(url_for('transaksi_index'))
        except ValueError:
            flash('Format angka pada berat atau harga tidak valid.', 'warning')
        except Exception as e:
            flash(f'Gagal menambahkan transaksi: {e}', 'danger')
        finally:
            conn.close()
            
    default_date = datetime.now().strftime('%Y-%m-%dT%H:%M')
    return render_template('transaksi/tambah.html', pelanggan_list=pelanggan_list, default_date=default_date)

@app.route('/transaksi/edit/<int:id>', methods=['GET', 'POST'])
def transaksi_edit(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('transaksi_index'))
        
    transaksi = None
    pelanggan_list = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM transaksi WHERE id = %s", (id,))
            transaksi = cursor.fetchone()
            
            cursor.execute("SELECT id, nama FROM pelanggan ORDER BY nama ASC")
            pelanggan_list = cursor.fetchall()
    except Exception as e:
        flash(f'Gagal memuat transaksi: {e}', 'danger')
        conn.close()
        return redirect(url_for('transaksi_index'))
        
    if not transaksi:
        flash('Transaksi tidak ditemukan.', 'warning')
        conn.close()
        return redirect(url_for('transaksi_index'))
        
    if transaksi['tanggal_masuk']:
        if isinstance(transaksi['tanggal_masuk'], str):
            try:
                dt = datetime.strptime(transaksi['tanggal_masuk'], '%Y-%m-%d %H:%M:%S')
                formatted_date = dt.strftime('%Y-%m-%dT%H:%M')
            except ValueError:
                formatted_date = transaksi['tanggal_masuk']
        else:
            formatted_date = transaksi['tanggal_masuk'].strftime('%Y-%m-%dT%H:%M')
    else:
        formatted_date = datetime.now().strftime('%Y-%m-%dT%H:%M')
        
    if request.method == 'POST':
        pelanggan_id = request.form.get('pelanggan_id')
        berat = request.form.get('berat')
        harga_per_kg = request.form.get('harga_per_kg')
        status = request.form.get('status')
        tanggal_masuk = request.form.get('tanggal_masuk')
        
        try:
            f_berat = float(berat)
            f_harga = float(harga_per_kg)
            total = f_berat * f_harga
            
            with conn.cursor() as cursor:
                sql = """
                    UPDATE transaksi 
                    SET pelanggan_id = %s, berat = %s, harga_per_kg = %s, total = %s, status = %s, tanggal_masuk = %s 
                    WHERE id = %s
                """
                cursor.execute(sql, (pelanggan_id, f_berat, f_harga, total, status, tanggal_masuk, id))
                conn.commit()
                flash('Transaksi berhasil diperbarui.', 'success')
                return redirect(url_for('transaksi_index'))
        except ValueError:
            flash('Format angka tidak valid.', 'warning')
        except Exception as e:
            flash(f'Gagal memperbarui transaksi: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('transaksi/edit.html', transaksi=transaksi, pelanggan_list=pelanggan_list, formatted_date=formatted_date)

@app.route('/transaksi/hapus/<int:id>', methods=['POST'])
@admin_required  # <--- Hanya Admin yang boleh menghapus
def transaksi_hapus(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('transaksi_index'))
        
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM transaksi WHERE id = %s"
            cursor.execute(sql, (id,))
            conn.commit()
            flash('Transaksi berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus transaksi: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('transaksi_index'))


# --- MENU BARU KHUSUS ADMIN: MANAJEMEN PENGGUNA (USERS) ---
@app.route('/users')
@admin_required
def users_index():
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('dashboard'))
    
    users_list = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, nama, role FROM users ORDER BY id DESC")
            users_list = cursor.fetchall()
    except Exception as e:
        flash(f'Gagal mengambil data user: {e}', 'danger')
    finally:
        conn.close()
        
    return render_template('users/list.html', users=users_list)

@app.route('/users/tambah', methods=['GET', 'POST'])
@admin_required
def users_tambah():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nama = request.form.get('nama')
        role = request.form.get('role')
        
        if not username or not password or not nama or not role:
            flash('Semua field wajib diisi.', 'warning')
            return render_template('users/tambah.html')
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                sql = "INSERT INTO users (username, password, nama, role) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (username, password, nama, role))
                conn.commit()
                flash(f'Pengguna {nama} berhasil didaftarkan.', 'success')
                return redirect(url_for('users_index'))
        except Exception as e:
            flash(f'Gagal menyimpan pengguna baru: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('users/tambah.html')

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def users_edit(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('users_index'))
        
    user = None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (id,))
            user = cursor.fetchone()
    except Exception as e:
        flash(f'Gagal mengambil data pengguna: {e}', 'danger')
        conn.close()
        return redirect(url_for('users_index'))
        
    if not user:
        flash('Pengguna tidak ditemukan.', 'warning')
        conn.close()
        return redirect(url_for('users_index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nama = request.form.get('nama')
        role = request.form.get('role')
        
        try:
            with conn.cursor() as cursor:
                sql = "UPDATE users SET username = %s, password = %s, nama = %s, role = %s WHERE id = %s"
                cursor.execute(sql, (username, password, nama, role, id))
                conn.commit()
                flash('Akun pengguna berhasil diperbarui.', 'success')
                return redirect(url_for('users_index'))
        except Exception as e:
            flash(f'Gagal memperbarui data pengguna: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('users/edit.html', user=user)

@app.route('/users/hapus/<int:id>', methods=['POST'])
@admin_required
def users_hapus(id):
    # Proteksi agar admin tidak tidak sengaja menghapus akunnya sendiri saat sedang login
    if id == session.get('user_id'):
        flash('Anda tidak diizinkan menghapus akun Anda sendiri yang sedang aktif.', 'warning')
        return redirect(url_for('users_index'))
        
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('users_index'))
        
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM users WHERE id = %s"
            cursor.execute(sql, (id,))
            conn.commit()
            flash('Pengguna berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus pengguna: {e}', 'danger')
    finally:
        conn.close()
        
    return redirect(url_for('users_index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)