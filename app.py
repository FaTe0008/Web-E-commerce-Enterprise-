from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import hashlib
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'fajlfitemvbsihfgw'

template_directory = os.path.abspath('templates')
app.template_folder = template_directory

# Initialising the database
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('customer', 'admin'))
        )
    ''')
    
    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')
    
    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            total_amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Order items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Check if admin exists, if not create one
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if cursor.fetchone()[0] == 0:
        hashed_password = hash_password('admin123')
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ('admin', hashed_password, 'admin')
        )
        print("Default admin created: username='admin', password='admin123'")
    
    # Add some sample products if none exist
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        sample_products = [
            ('Bluetooth Speaker', 799.99, 'Electronics', 10),
            ('Digital Camera', 1499.99, 'Electronics', 5),
            ('Leather Jacket', 79.99, 'Clothing', 20),
            ('Water Bottle', 19.99, 'Kitchenware', 30),
            ('Travelling bagpack', 9.99, 'Travel', 25)
        ]
        cursor.executemany(
            "INSERT INTO products (name, price, category, stock) VALUES (?, ?, ?, ?)",
            sample_products
        )
        print("Sample products added")
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    
    return render_template('index.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        hashed_password = hash_password(password)
        
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed_password, 'customer')
            )
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose another.', 'error')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hashed_password = hash_password(password)
        
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, hashed_password)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/products')
def products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    
    return render_template('products.html', products=products)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    quantity = int(request.form['quantity'])
    
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))
    
    if quantity > product['stock']:
        flash(f'Not enough stock. Only {product["stock"]} available.', 'error')
        return redirect(url_for('products'))
    
    # Initialize cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    
    # Add product to cart or update quantity
    if str(product_id) in cart:
        cart[str(product_id)] += quantity
    else:
        cart[str(product_id)] = quantity
    
    session['cart'] = cart
    session.modified = True
    
    flash(f'Added {quantity} x {product["name"]} to cart.', 'success')
    return redirect(url_for('products'))

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    cart_items = []
    total = 0
    
    conn = get_db_connection()
    
    for product_id, quantity in cart.items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if product:
            subtotal = product['price'] * quantity
            total += subtotal
            cart_items.append({
                'id': product['id'],
                'name': product['name'],
                'price': product['price'],
                'quantity': quantity,
                'subtotal': subtotal
            })
    
    conn.close()
    
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    
    if str(product_id) in cart:
        del cart[str(product_id)]
        session['cart'] = cart
        session.modified = True
        flash('Item removed from cart.', 'success')
    
    return redirect(url_for('view_cart'))

@app.route('/checkout')
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('view_cart'))
    
    conn = get_db_connection()
    total = 0
    cart_items = []
    
    # Calculate total and check stock
    for product_id, quantity in cart.items():
        product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
        if product:
            if quantity > product['stock']:
                flash(f'Not enough stock for {product["name"]}. Only {product["stock"]} available.', 'error')
                conn.close()
                return redirect(url_for('view_cart'))
            
            subtotal = product['price'] * quantity
            total += subtotal
            cart_items.append({
                'product_id': product_id,
                'quantity': quantity,
                'price': product['price']
            })
    
    # Create order
    order_date = datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, order_date, total_amount) VALUES (?, ?, ?)",
        (session['user_id'], order_date, total)
    )
    order_id = cursor.lastrowid
    
    # Add order items and update stock
    for item in cart_items:
        cursor.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            (order_id, item['product_id'], item['quantity'], item['price'])
        )
        
        # Update product stock
        cursor.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (item['quantity'], item['product_id'])
        )
    
    conn.commit()
    conn.close()
    
    # Clear cart
    session['cart'] = {}
    session.modified = True
    
    flash(f'Order placed successfully! Order ID: {order_id}', 'success')
    return redirect(url_for('index'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        
        # Get only basic order information
        orders = conn.execute(
            "SELECT id, order_date, total_amount FROM orders WHERE user_id = ? ORDER BY order_date DESC",
            (session['user_id'],)
        ).fetchall()
        
        conn.close()
        
        return render_template('simple_orders.html', orders=orders)
        
    except Exception as e:
        print(f"Error in orders route: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading orders. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/debug_schema')
def debug_schema():
    conn = get_db_connection()
    cursor = conn.execute("PRAGMA table_info(orders)")
    columns = cursor.fetchall()
    conn.close()
    return str(columns)
# Admin routes
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # Total items sold
    total_items = conn.execute("SELECT SUM(quantity) FROM order_items").fetchone()[0] or 0
    
    # Total revenue
    total_revenue = conn.execute("SELECT SUM(total_amount) FROM orders").fetchone()[0] or 0
    
    # Total orders
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] or 0
    
    # Top selling products
    top_products = conn.execute('''
        SELECT p.name, SUM(oi.quantity) as total_sold 
        FROM order_items oi 
        JOIN products p ON oi.product_id = p.id 
        GROUP BY p.id 
        ORDER BY total_sold DESC 
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return render_template(
        'admin_dashboard.html',
        total_items=total_items,
        total_revenue=total_revenue,
        total_orders=total_orders,
        top_products=top_products
    )

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/add_product', methods=['GET', 'POST'])
def admin_add_product():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        category = request.form['category']
        stock = int(request.form['stock'])
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO products (name, price, category, stock) VALUES (?, ?, ?, ?)",
            (name, price, category, stock)
        )
        conn.commit()
        conn.close()
        
        flash('Product added successfully.', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin_add_product.html')

@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        category = request.form['category']
        stock = int(request.form['stock'])
        
        conn.execute(
            "UPDATE products SET name=?, price=?, category=?, stock=? WHERE id=?",
            (name, price, category, stock, product_id)
        )
        conn.commit()
        conn.close()
        
        flash('Product updated successfully.', 'success')
        return redirect(url_for('admin_products'))
    
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin_products'))
    
    return render_template('admin_edit_product.html', product=product)

@app.route('/admin/delete_product/<int:product_id>')
def admin_delete_product(product_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
    
    flash('Product deleted successfully.', 'success')
    return redirect(url_for('admin_products'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)