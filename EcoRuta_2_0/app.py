import os, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambia-esta-clave-antes-de-publicar")
DATABASE = os.environ.get("DATABASE_PATH", "ecoruta.db")

MATERIALS = ["Plástico", "Cartón", "Papel", "Vidrio", "Metales", "Electrónicos", "Textiles", "Aceite usado"]

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'reciclador', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS listings (
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
      material TEXT NOT NULL, quantity TEXT NOT NULL, neighborhood TEXT NOT NULL,
      address TEXT NOT NULL, description TEXT, contact TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Disponible', created_by INTEGER,
      created_at TEXT NOT NULL,
      FOREIGN KEY(created_by) REFERENCES users(id)
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    if count == 0:
        samples = [
          ("Cartón limpio para recoger", "Cartón", "Aprox. 35 kg", "La Castellana", "Cerca al parque del barrio", "Cajas desarmadas y secas. Recoger en horario de mañana.", "300 000 0001"),
          ("Botellas PET transparentes", "Plástico", "2 sacos", "Centro", "Sector del mercado, punto de encuentro por confirmar", "Botellas vacías, separadas y compactadas.", "300 000 0002"),
          ("Frascos de vidrio", "Vidrio", "20 unidades", "La Granja", "Calle principal del sector", "Frascos limpios. Manipular con cuidado.", "300 000 0003"),
          ("Papel archivo", "Papel", "12 kg", "Monteverde", "Zona comercial", "Papel seco, sin plastificar.", "300 000 0004"),
          ("Chatarra metálica", "Metales", "Aprox. 18 kg", "Cantaclaro", "Punto acordado con el anunciante", "Piezas pequeñas de metal, sin elementos peligrosos.", "300 000 0005"),
        ]
        conn.executemany("""INSERT INTO listings(title,material,quantity,neighborhood,address,description,contact,created_at)
        VALUES(?,?,?,?,?,?,?,?)""", [(*s, datetime.now().isoformat(timespec="minutes")) for s in samples])
    conn.commit()
    conn.close()

@app.context_processor
def inject_globals():
    user = None
    if session.get("user_id"):
        user = db().execute("SELECT id,name,email,role FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return {"current_user": user, "materials": MATERIALS}

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Inicia sesión para continuar.", "info")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    conn = db()
    total = conn.execute("SELECT COUNT(*) FROM listings WHERE status='Disponible'").fetchone()[0]
    neighborhoods = conn.execute("SELECT COUNT(DISTINCT neighborhood) FROM listings WHERE status='Disponible'").fetchone()[0]
    counts = conn.execute("SELECT material, COUNT(*) total FROM listings WHERE status='Disponible' GROUP BY material ORDER BY total DESC").fetchall()
    latest = conn.execute("SELECT * FROM listings WHERE status='Disponible' ORDER BY id DESC LIMIT 3").fetchall()
    return render_template("index.html", total=total, neighborhoods=neighborhoods, counts=counts, latest=latest)

@app.route("/materiales")
def materials_page():
    material = request.args.get("material", "").strip()
    neighborhood = request.args.get("barrio", "").strip()
    sql = "SELECT * FROM listings WHERE status='Disponible'"
    params = []
    if material:
        sql += " AND material=?"; params.append(material)
    if neighborhood:
        sql += " AND neighborhood LIKE ?"; params.append(f"%{neighborhood}%")
    sql += " ORDER BY id DESC"
    listings = db().execute(sql, params).fetchall()
    return render_template("materials.html", listings=listings, selected_material=material, barrio=neighborhood)

@app.route("/publicar", methods=["GET", "POST"])
@login_required
def publish():
    if request.method == "POST":
        fields = {k: request.form.get(k, "").strip() for k in ["title","material","quantity","neighborhood","address","description","contact"]}
        if not all(fields[k] for k in ["title","material","quantity","neighborhood","address","contact"]):
            flash("Completa los campos obligatorios para publicar.", "error")
        elif fields["material"] not in MATERIALS:
            flash("Selecciona un material válido.", "error")
        else:
            db().execute("""INSERT INTO listings(title,material,quantity,neighborhood,address,description,contact,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", (fields["title"],fields["material"],fields["quantity"],fields["neighborhood"],fields["address"],fields["description"],fields["contact"],session["user_id"],datetime.now().isoformat(timespec="minutes")))
            db().commit()
            flash("¡Publicación creada! Ya aparece en el listado de materiales.", "success")
            return redirect(url_for("materials_page"))
    return render_template("publish.html")

@app.route("/registro", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        role=request.form.get("role","reciclador")
        if not name or not email or len(password)<8 or role not in ["reciclador","generador"]:
            flash("Revisa los datos. La contraseña debe tener al menos 8 caracteres.", "error")
        else:
            try:
                cur=db().execute("INSERT INTO users(name,email,password,role,created_at) VALUES(?,?,?,?,?)",
                    (name,email,generate_password_hash(password),role,datetime.now().isoformat(timespec="minutes")))
                db().commit()
                session["user_id"]=cur.lastrowid
                flash("Tu cuenta está lista. ¡Bienvenido a EcoRuta!", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("Ese correo ya está registrado.", "error")
    return render_template("auth.html", mode="register")

@app.route("/ingresar", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        user=db().execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password"],password):
            session.clear(); session["user_id"]=user["id"]
            flash("Sesión iniciada correctamente.", "success")
            return redirect(url_for("dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("auth.html", mode="login")

@app.route("/salir")
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("index"))

@app.route("/panel")
@login_required
def dashboard():
    mine=db().execute("SELECT * FROM listings WHERE created_by=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    return render_template("dashboard.html", mine=mine)

@app.route("/tomar/<int:item_id>", methods=["POST"])
@login_required
def take_listing(item_id):
    db().execute("UPDATE listings SET status='En gestión' WHERE id=? AND status='Disponible'",(item_id,))
    db().commit()
    flash("Solicitud registrada. Contacta al anunciante para coordinar la recogida.", "success")
    return redirect(url_for("materials_page"))

@app.route("/mapa")
def map_page():
    points=db().execute("SELECT * FROM listings WHERE status='Disponible' ORDER BY id DESC").fetchall()
    return render_template("map.html", points=points)

@app.route("/salud")
def health():
    return {"status":"ok","app":"EcoRuta"}

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
