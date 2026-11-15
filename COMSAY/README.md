# COMSAY — 3D Model Marketplace

A Flask + SQLite starter e-commerce website with a customer storefront, 3D GLB/GLTF viewer, cart, checkout order creation, customer accounts, and an admin dashboard.

## Run on Windows

1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. Open Terminal and run:

```powershell
py -m venv venv
venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

4. Open http://127.0.0.1:5000

## Demo administrator

- Email: `admin@comsay.com`
- Password: `Admin123!`

Change this password and `SECRET_KEY` before deployment. The database and demo products are created automatically.

## Main features

- Customer registration/login and account settings
- Product search and category filtering
- Product details with interactive 3D model viewer
- Session-based shopping cart
- Checkout creates a real order record in SQLite
- Customer order history
- Admin dashboard: sales, orders, products, customers, pending orders
- Admin product CRUD and GLB/GLTF uploads
- Admin order status management and customer list

## Important notes

- Checkout records an order but does **not** charge a card or collect online payment. A payment provider and its server-side verification must be integrated before accepting real payments.
- The sample 3D models are hosted by modelviewer.dev and need an internet connection. Upload your own `.glb` or `.gltf` models from Admin → Products → Add product.
- This is a learning/MVP starter. Before public production use, add CSRF protection, rate limiting, email verification, secure production secrets, HTTPS, backups, and a production WSGI server. Do not use Flask's debug server in production.
- SQLite is suitable for local development; consider PostgreSQL for a public store with multiple concurrent users.
