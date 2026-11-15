import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///comsay.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
db = SQLAlchemy(app)

ALLOWED_MODELS = {"glb", "gltf"}
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "webp"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), default="3D Model")
    description = db.Column(db.Text, default="")
    price = db.Column(db.Float, nullable=False, default=0)
    image = db.Column(db.String(300), default="")
    model_url = db.Column(db.String(500), default="")
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="orders")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    order = db.relationship("Order", backref="items")

def logged_in():
    return User.query.get(session.get("user_id")) if session.get("user_id") else None

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = logged_in()
        if not user or user.role != "admin":
            flash("Please sign in with an administrator account.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def customer_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not logged_in():
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename, extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in extensions

def cart_data():
    cart = session.get("cart", {})
    items, total, count = [], 0, 0
    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            qty = max(1, int(qty))
            subtotal = product.price * qty
            items.append({"product": product, "quantity": qty, "subtotal": subtotal})
            total += subtotal
            count += qty
    return items, total, count

@app.context_processor
def inject_globals():
    _, _, cart_count = cart_data()
    return {"current_user": logged_in(), "cart_count": cart_count}

@app.route("/")
def home():
    featured = Product.query.order_by(Product.created_at.desc()).limit(6).all()
    return render_template("home.html", featured=featured)

@app.route("/products")
def products():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if category:
        query = query.filter_by(category=category)
    items = query.order_by(Product.created_at.desc()).all()
    categories = [r[0] for r in db.session.query(Product.category).distinct().all()]
    return render_template("products.html", products=items, categories=categories, search=search, selected_category=category)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("product_detail.html", product=product)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password with at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "error")
        else:
            user = User(name=name, email=email, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("Your COMSAY account is ready!", "success")
            return redirect(url_for("home"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard") if user.role == "admin" else url_for("home"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))

@app.route("/cart")
def cart():
    items, total, _ = cart_data()
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    Product.query.get_or_404(product_id)
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = int(cart.get(key, 0)) + 1
    session["cart"] = cart
    flash("Product added to your cart.", "success")
    return redirect(request.referrer or url_for("products"))

@app.route("/cart/update", methods=["POST"])
def update_cart():
    cart = session.get("cart", {})
    for pid in list(cart):
        try:
            qty = int(request.form.get(f"qty_{pid}", 0))
            if qty <= 0:
                cart.pop(pid, None)
            else:
                cart[pid] = min(qty, 99)
        except ValueError:
            pass
    session["cart"] = cart
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    items, total, _ = cart_data()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("products"))
    user = logged_in()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        if not name or not email:
            flash("Please complete your contact details.", "error")
        else:
            order = Order(user_id=user.id, customer_name=name, email=email, total=total)
            db.session.add(order)
            db.session.flush()
            for item in items:
                db.session.add(OrderItem(order_id=order.id, product_id=item["product"].id,
                    product_name=item["product"].name, quantity=item["quantity"], price=item["product"].price))
            db.session.commit()
            session["cart"] = {}
            flash(f"Order #{order.id} was placed successfully. Payment is not collected by this demo.", "success")
            return redirect(url_for("my_orders"))
    return render_template("checkout.html", items=items, total=total, user=user)

@app.route("/account")
@customer_required
def account():
    return render_template("account.html", user=logged_in())

@app.route("/account/update", methods=["POST"])
@customer_required
def update_account():
    user = logged_in()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not name or not email:
        flash("Name and email are required.", "error")
    elif User.query.filter(User.email == email, User.id != user.id).first():
        flash("That email is already in use.", "error")
    else:
        user.name, user.email = name, email
        db.session.commit()
        flash("Account details updated.", "success")
    return redirect(url_for("account"))

@app.route("/account/password", methods=["POST"])
@customer_required
def change_password():
    user = logged_in()
    old, new = request.form.get("old_password", ""), request.form.get("new_password", "")
    if not check_password_hash(user.password, old):
        flash("Your current password is incorrect.", "error")
    elif len(new) < 8:
        flash("New password must contain at least 8 characters.", "error")
    else:
        user.password = generate_password_hash(new)
        db.session.commit()
        flash("Password changed successfully.", "success")
    return redirect(url_for("account"))

@app.route("/orders")
@customer_required
def my_orders():
    orders = Order.query.filter_by(user_id=logged_in().id).order_by(Order.created_at.desc()).all()
    return render_template("my_orders.html", orders=orders)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    stats = {
        "sales": db.session.query(db.func.sum(Order.total)).scalar() or 0,
        "orders": Order.query.count(),
        "products": Product.query.count(),
        "users": User.query.filter_by(role="customer").count(),
        "pending": Order.query.filter_by(status="Pending").count()
    }
    return render_template("admin_dashboard.html", stats=stats, orders=orders)

@app.route("/admin/products")
@admin_required
def admin_products():
    return render_template("admin_products.html", products=Product.query.order_by(Product.created_at.desc()).all())

@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        try:
            price = float(request.form.get("price", "0"))
        except ValueError:
            price = -1
        if not name or price < 0:
            flash("Enter a product name and a valid price.", "error")
            return render_template("product_form.html", product=None)
        image_file = request.files.get("image")
        model_file = request.files.get("model")
        image_path = ""
        model_path = ""
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        if image_file and image_file.filename and allowed_file(image_file.filename, ALLOWED_IMAGES):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{image_file.filename}")
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            image_path = url_for("static", filename=f"uploads/{filename}")
        if model_file and model_file.filename and allowed_file(model_file.filename, ALLOWED_MODELS):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{model_file.filename}")
            model_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            model_path = url_for("static", filename=f"uploads/{filename}")
        product = Product(name=name, category=request.form.get("category", "3D Model"),
            description=request.form.get("description", ""), price=price, image=image_path,
            model_url=model_path or request.form.get("model_url", "").strip(),
            featured=bool(request.form.get("featured")))
        db.session.add(product)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("admin_products"))
    return render_template("product_form.html", product=None)

@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        product.name = request.form.get("name", "").strip()
        product.category = request.form.get("category", "3D Model")
        product.description = request.form.get("description", "")
        product.price = float(request.form.get("price", product.price))
        product.featured = bool(request.form.get("featured"))
        product.model_url = request.form.get("model_url", "").strip() or product.model_url
        image_file, model_file = request.files.get("image"), request.files.get("model")
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        if image_file and image_file.filename and allowed_file(image_file.filename, ALLOWED_IMAGES):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{image_file.filename}")
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            product.image = url_for("static", filename=f"uploads/{filename}")
        if model_file and model_file.filename and allowed_file(model_file.filename, ALLOWED_MODELS):
            filename = secure_filename(f"{datetime.utcnow().timestamp()}_{model_file.filename}")
            model_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            product.model_url = url_for("static", filename=f"uploads/{filename}")
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("admin_products"))
    return render_template("product_form.html", product=product)

@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    if OrderItem.query.filter_by(product_id=product.id).first():
        flash("This product is in an order history and cannot be deleted.", "error")
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted.", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin_orders.html", orders=orders)

@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")
    if status in {"Pending", "Processing", "Completed", "Cancelled"}:
        order.status = status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        user = logged_in()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        if name and email and not User.query.filter(User.email == email, User.id != user.id).first():
            user.name, user.email = name, email
            db.session.commit()
            flash("Admin profile updated.", "success")
        else:
            flash("Please enter valid details and an unused email.", "error")
        return redirect(url_for("admin_settings"))
    return render_template("admin_settings.html", user=logged_in())

@app.errorhandler(413)
def too_large(_):
    flash("Upload is too large. Maximum upload size is 80 MB.", "error")
    return redirect(request.referrer or url_for("admin_products"))

def initialize():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email="admin@comsay.com").first():
            db.session.add(User(name="COMSAY Admin", email="admin@comsay.com",
                password=generate_password_hash("Admin123!"), role="admin"))
        if Product.query.count() == 0:
            db.session.add_all([
                Product(name="Astronaut Explorer", category="Characters", description="A detailed astronaut character model, ready for your creative scenes.", price=499, model_url="https://modelviewer.dev/shared-assets/models/Astronaut.glb", featured=True),
                Product(name="Robot Companion", category="Characters", description="A friendly animated robot model for games and 3D projects.", price=699, model_url="https://modelviewer.dev/shared-assets/models/RobotExpressive.glb", featured=True),
                Product(name="Vintage Camera", category="Props", description="A stylized camera prop for product scenes and environments.", price=299, model_url="https://modelviewer.dev/shared-assets/models/Astronaut.glb", featured=True)
            ])
        db.session.commit()

initialize()

if __name__ == "__main__":
    app.run(debug=True)
