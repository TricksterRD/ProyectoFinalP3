import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from threading import Thread
import time

# Configuración de la aplicación
app = Flask(__name__, template_folder='pagina', static_folder='css')
app.config['SECRET_KEY'] = os.urandom(24)
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(base_dir, "instance", "database.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# Modelo de usuario
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)


# Modelo de producto
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)


# Cargar usuario
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/index')
@login_required
def index():
    order_by = request.args.get('order_by', 'id')
    if order_by == 'name':
        products = Product.query.order_by(Product.name.asc()).all()
    elif order_by == 'price':
        products = Product.query.order_by(Product.price.asc()).all()
    else:
        products = Product.query.order_by(Product.id.asc()).all()
    return render_template('index.html', products=products)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']
        new_product = Product(name=name, price=price, description=description)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_product.html')


@app.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_product(id):
    product = Product.query.get(id)
    if product:
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    product = Product.query.get(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = request.form['price']
        product.description = request.form['description']
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_product.html', product=product)


@app.route('/view/<int:id>', methods=['GET'])
@login_required
def view_product(id):
    product = Product.query.get(id)
    return render_template('view_product.html', product=product)


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search_product():
    results = []
    if request.method == 'POST':
        name_query = request.form.get('query', '').strip()
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')

        query = Product.query
        if name_query:
            query = query.filter(Product.name.contains(name_query))
        if min_price:
            query = query.filter(Product.price >= float(min_price))
        if max_price:
            query = query.filter(Product.price <= float(max_price))

        results = query.all()
        if not results:
            flash('No products found matching your criteria.', 'warning')
    return render_template('search_product.html', results=results)


@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.username != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully.', 'success')
        return redirect(url_for('index'))
    return render_template('add_user.html')


@app.route('/stats', methods=['GET'])
@login_required
def stats():
    total_products = Product.query.count()
    most_expensive = Product.query.order_by(Product.price.desc()).first()
    cheapest = Product.query.order_by(Product.price.asc()).first()
    avg_price = db.session.query(db.func.avg(Product.price)).scalar()
    return render_template('stats.html', total_products=total_products,
                           most_expensive=most_expensive, cheapest=cheapest, avg_price=avg_price)


def create_default_user():
    with app.app_context():
        print("Verifying user 'admin'...")
        user = User.query.filter_by(username='admin').first()
        if not user:
            hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
            new_user = User(username='admin', password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            print("User 'admin' created successfully.")


# Función para iniciar las pruebas de Selenium
def run_selenium_tests():
    # Crear carpeta de screenshots si no existe
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')

    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    edge_options = EdgeOptions()
    edge_options.binary_location = edge_path
    edge_driver_path = r"C:\Users\User\Downloads\edgedriver_win64\msedgedriver.exe"
    driver = webdriver.Edge(service=EdgeService(edge_driver_path), options=edge_options)

    # 1. Inicio de sesión (Como admin)
    driver.get('http://localhost:5000/login')
    time.sleep(4)
    driver.find_element(By.NAME, 'username').send_keys('admin')
    time.sleep(4)
    driver.find_element(By.NAME, 'password').send_keys('admin123')
    time.sleep(4)
    driver.find_element(By.NAME, 'password').send_keys(Keys.RETURN)
    driver.save_screenshot('screenshots/login.png')
    time.sleep(6)

    # 2. Ordenar productos (ID, nombre, precio)
    driver.get('http://localhost:5000/index?order_by=id')
    time.sleep(2)
    driver.save_screenshot('screenshots/sorted_by_id.png')
    time.sleep(2)
    driver.get('http://localhost:5000/index?order_by=name')
    time.sleep(3)
    driver.save_screenshot('screenshots/sorted_by_name.png')
    time.sleep(2)
    driver.get('http://localhost:5000/index?order_by=price')
    driver.save_screenshot('screenshots/sorted_by_price.png')
    time.sleep(4)

    # 3. Agregar un producto
    driver.get('http://localhost:5000/add')
    time.sleep(6)
    driver.find_element(By.NAME, 'name').send_keys('Producto de Prueba 3')
    time.sleep(6)
    driver.find_element(By.NAME, 'price').send_keys('700.0')
    time.sleep(6)
    driver.find_element(By.NAME, 'description').send_keys('Descripción del producto')
    time.sleep(6)
    driver.find_element(By.XPATH, '//button[text()="Agregar"]').click()
    time.sleep(6)
    driver.save_screenshot('screenshots/product_added.png')


    # 4. Ver un producto
    time.sleep(4)
    driver.get('http://localhost:5000/view/7')
    driver.save_screenshot('screenshots/view_product.png')
    time.sleep(6)

    # 5. Editar un producto
    driver.get('http://localhost:5000/edit/7')
    time.sleep(6)
    driver.find_element(By.NAME, 'name').clear()
    driver.find_element(By.NAME, 'name').send_keys('Producto Editado')
    time.sleep(4)
    driver.find_element(By.NAME, 'price').clear()
    driver.find_element(By.NAME, 'price').send_keys('150.0')
    time.sleep(4)
    driver.find_element(By.NAME, 'description').clear()
    driver.find_element(By.NAME, 'description').send_keys('Descripción editada')
    time.sleep(4)
    driver.find_element(By.XPATH, '//button[text()="Guardar Cambios"]').click()
    time.sleep(4)
    driver.save_screenshot('screenshots/product_edited.png')
    time.sleep(6)

    # 6. Borrar un producto
    time.sleep(6)
    driver.get('http://localhost:5000/delete/7')
    driver.save_screenshot('screenshots/product_deleted.png')
    time.sleep(6)

    # 7. Buscar un producto
    driver.get('http://localhost:5000/search')
    time.sleep(4)
    driver.find_element(By.NAME, 'query').send_keys('Motocicleta')
    time.sleep(4)
    driver.find_element(By.NAME, 'query').send_keys(Keys.RETURN)
    driver.save_screenshot('screenshots/product_searched.png')
    time.sleep(6)

    # 8. Ir a las estadísticas
    driver.get('http://localhost:5000/stats')
    time.sleep(4)
    driver.save_screenshot('screenshots/stats.png')
    time.sleep(6)

    # 9. Crear un Usuario
    driver.get('http://localhost:5000/admin/add_user')
    time.sleep(4)
    driver.find_element(By.NAME, 'username').send_keys('francis')
    driver.find_element(By.NAME, 'password').send_keys('francis123')
    time.sleep(4)
    driver.find_element(By.NAME, 'password').send_keys(Keys.RETURN)
    driver.save_screenshot('screenshots/user_created.png')
    time.sleep(6)

    driver.get('http://localhost:5000/logout')
    driver.save_screenshot('screenshots/logout.png')
    time.sleep(6)

    driver.get('http://localhost:5000/login')
    time.sleep(6)
    driver.find_element(By.NAME, 'username').send_keys('francis')
    driver.find_element(By.NAME, 'password').send_keys('francis123')
    time.sleep(6)
    driver.find_element(By.NAME, 'password').send_keys(Keys.RETURN)
    driver.save_screenshot('screenshots/login_new_user.png')
    time.sleep(6)


    driver.quit()



if len(sys.argv) > 1 and sys.argv[1] == "selenium":
    thread = Thread(target=run_selenium_tests)
    thread.start()
else:
    create_default_user()
    app.run(debug=True)
