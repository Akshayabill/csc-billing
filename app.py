import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, session, abort
from datetime import datetime

app = Flask(__name__)
app.secret_key = "csc_secret"

DATABASE_URL = "postgresql://postgres.srtqnjzrgmrqvorhshaq:Kondazhy106@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
db_pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL)

def get_db_connection():
    global global_conn
    if global_conn.closed:
        global_conn = psycopg2.connect(DATABASE_URL)
    return global_conn
def release_db_connection(conn):
    pass
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_slabs (
        id SERIAL PRIMARY KEY,
        service_id INTEGER,
        from_amount REAL,
        to_amount REAL,
        service_charge REAL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id SERIAL PRIMARY KEY,
        bill_no TEXT,
        bill_date TEXT,
        bill_time TEXT,
        customer_name TEXT,
        mobile TEXT,
        staff_name TEXT,
        payment_method TEXT,
        total_amount REAL,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bill_items (
        id SERIAL PRIMARY KEY,
        bill_id INTEGER,
        service_name TEXT,
        bill_amount REAL,
        service_charge REAL,
        total_amount REAL,
        quantity INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id SERIAL PRIMARY KEY,
        service_name TEXT UNIQUE,
        charge REAL,
        service_type TEXT
    )
    """)

    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'STAFF',
            perm_new_bill BOOLEAN DEFAULT FALSE,
            perm_all_bills BOOLEAN DEFAULT FALSE,
            perm_collection_rep BOOLEAN DEFAULT FALSE,
            perm_date_rep BOOLEAN DEFAULT FALSE,
            perm_staff_rep BOOLEAN DEFAULT FALSE,
            perm_service_rep BOOLEAN DEFAULT FALSE,
            perm_expense BOOLEAN DEFAULT FALSE,
            perm_profit_loss BOOLEAN DEFAULT FALSE,
            perm_services_mgmt BOOLEAN DEFAULT FALSE,
            is_full_access BOOLEAN DEFAULT FALSE
        )
    ''')

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id SERIAL PRIMARY KEY,
        expense_date TEXT,
        expense_name TEXT,
        amount REAL,
        staff_name TEXT DEFAULT 'admin'
    )
    """)

    cursor.execute("SELECT * FROM users WHERE role = 'ADMIN'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (username, password, role, perm_new_bill, perm_all_bills, perm_collection_rep, perm_date_rep, perm_staff_rep, perm_service_rep, perm_expense, perm_profit_loss, perm_services_mgmt, is_full_access) 
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, ("admin", "admin123", "ADMIN", True, True, True, True, True, True, True, True, True, True))

    conn.commit()
    cursor.close()
    release_db_connection(conn)

init_db()

def has_permission(permission_name):
    if "username" not in session:
        return False
    if session.get("role") == "ADMIN":
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT is_full_access, {permission_name} FROM users WHERE username=%s", (session.get("username"),))
    res = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    
    if res:
        return res[0] or res[1]
    return False

def is_manager_or_admin():
    if "username" not in session:
        return False
    if session.get("role") == "ADMIN":
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_full_access FROM users WHERE username=%s", (session.get("username"),))
    res = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    return res[0] if res else False

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        release_db_connection(conn)

        if user:
            session["username"] = username
            session["role"] = user[0].upper()
            return redirect("/dashboard")

    return render_template("login.html")

@app.route("/users")
def users():
    if session.get("role") != "ADMIN":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password, role, perm_new_bill, perm_all_bills, perm_collection_rep, perm_date_rep, perm_staff_rep, perm_service_rep, perm_expense, perm_profit_loss, perm_services_mgmt, is_full_access FROM users ORDER BY username")
    users_list = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("users.html", users=users_list)

@app.route("/add_user", methods=["GET","POST"])
def add_user():
    if session.get("role") != "ADMIN":
        return redirect("/dashboard")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role").upper()
        
        selected_features = request.form.getlist("features[]")
        is_full = "FULL_ACCESS" in selected_features or role == "ADMIN"
        
        p_new_bill = "NEW_BILL" in selected_features or is_full
        p_all_bills = "ALL_BILLS" in selected_features or is_full
        p_coll_rep = "COLLECTION_REP" in selected_features or is_full
        p_date_rep = "DATE_REP" in selected_features or is_full
        p_staff_rep = "STAFF_REP" in selected_features or is_full
        p_serv_rep = "SERVICE_REP" in selected_features or is_full
        p_expense = "EXPENSE" in selected_features or is_full
        p_prof_loss = "PROFIT_LOSS" in selected_features or is_full
        p_serv_mgmt = "SERVICES_MGMT" in selected_features or is_full

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password, role, perm_new_bill, perm_all_bills, perm_collection_rep, perm_date_rep, perm_staff_rep, perm_service_rep, perm_expense, perm_profit_loss, perm_services_mgmt, is_full_access) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (username, password, role, p_new_bill, p_all_bills, p_coll_rep, p_date_rep, p_staff_rep, p_serv_rep, p_expense, p_prof_loss, p_serv_mgmt, is_full))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect("/users")

    return render_template("add_user.html")

@app.route("/edit_user/<int:id>", methods=["GET","POST"])
def edit_user(id):
    if session.get("role") != "ADMIN":
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role").upper()
        
        selected_features = request.form.getlist("features[]")
        is_full = "FULL_ACCESS" in selected_features or role == "ADMIN"
        
        p_new_bill = "NEW_BILL" in selected_features or is_full
        p_all_bills = "ALL_BILLS" in selected_features or is_full
        p_coll_rep = "COLLECTION_REP" in selected_features or is_full
        p_date_rep = "DATE_REP" in selected_features or is_full
        p_staff_rep = "STAFF_REP" in selected_features or is_full
        p_serv_rep = "SERVICE_REP" in selected_features or is_full
        p_expense = "EXPENSE" in selected_features or is_full
        p_prof_loss = "PROFIT_LOSS" in selected_features or is_full
        p_serv_mgmt = "SERVICES_MGMT" in selected_features or is_full

        cursor.execute("""
            UPDATE users SET username=%s, password=%s, role=%s, perm_new_bill=%s, perm_all_bills=%s, perm_collection_rep=%s, perm_date_rep=%s, perm_staff_rep=%s, perm_service_rep=%s, perm_expense=%s, perm_profit_loss=%s, perm_services_mgmt=%s, is_full_access=%s 
            WHERE id=%s
        """, (username, password, role, p_new_bill, p_all_bills, p_coll_rep, p_date_rep, p_staff_rep, p_serv_rep, p_expense, p_prof_loss, p_serv_mgmt, is_full, id))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect("/users")

    cursor.execute("SELECT id, username, password, role, perm_new_bill, perm_all_bills, perm_collection_rep, perm_date_rep, perm_staff_rep, perm_service_rep, perm_expense, perm_profit_loss, perm_services_mgmt, is_full_access FROM users WHERE id=%s", (id,))
    user = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    return render_template("edit_user.html", user=user)

@app.route("/new_bill", methods=["GET", "POST"])
def new_bill():
    if not has_permission("perm_new_bill"):
        return redirect("/dashboard")
        
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        customer_name = request.form.get("customer_name")
        mobile = request.form.get("mobile")
        staff_name = session.get("username")
        payment_method = request.form.get("payment_method")
        notes = request.form.get("notes")

        selected_services = request.form.getlist("services[]")
        bill_amounts = request.form.getlist("bill_amounts[]")
        quantities = request.form.getlist("quantities[]")

        total_amount = 0
        items_to_insert = []

        for i in range(len(selected_services)):
            service = selected_services[i]
            cursor.execute("SELECT id, charge, service_type FROM services WHERE service_name=%s", (service,))
            row = cursor.fetchone()
            if not row: continue

            service_id, service_charge, service_type = row[0], row[1], row[2]

            if service_type == "QUANTITY":
                qty = int(quantities[i]) if (i < len(quantities) and quantities[i]) else 1
                per_page_charge = float(service_charge or 0)
                item_total = per_page_charge * qty
                total_amount += item_total
                items_to_insert.append((service, 0, per_page_charge, item_total, qty))

            elif service_type == "VARIABLE":
                bill_amount = float(bill_amounts[i]) if (i < len(bill_amounts) and bill_amounts[i]) else 0.0
                cursor.execute("""
                    SELECT service_charge FROM service_slabs 
                    WHERE service_id=%s AND %s BETWEEN from_amount AND to_amount
                """, (service_id, bill_amount))
                slab = cursor.fetchone()
                charge = float(slab[0]) if slab else 0

                item_total = bill_amount + charge
                total_amount += item_total
                items_to_insert.append((service, bill_amount, charge, item_total, 1))

            else:
                charge = float(service_charge or 0)
                total_amount += charge
                items_to_insert.append((service, 0, charge, charge, 1))

        cursor.execute("SELECT COUNT(*) FROM bills")
        bill_count = cursor.fetchone()[0] + 1
        bill_no = f"BILL{bill_count:04d}"
        bill_date = datetime.now().strftime("%Y-%m-%d")
        bill_time = datetime.now().strftime("%H:%M:%S")

        cursor.execute("""
            INSERT INTO bills (bill_no, bill_date, bill_time, customer_name, mobile, staff_name, payment_method, total_amount, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (bill_no, bill_date, bill_time, customer_name, mobile, staff_name, payment_method, total_amount, notes))

        cursor.execute("SELECT id FROM bills WHERE bill_no=%s ORDER BY id DESC LIMIT 1", (bill_no,))
        bill_id = cursor.fetchone()[0]

        for item in items_to_insert:
            cursor.execute("""
                INSERT INTO bill_items (bill_id, service_name, bill_amount, service_charge, total_amount, quantity)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (bill_id, item[0], item[1], item[2], item[3], item[4]))

        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect(f"/bill/{bill_id}")

    cursor.execute("SELECT service_name, service_type, charge FROM services ORDER BY service_name")
    services = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    
    services_list = [{'name': r[0], 'type': r[1], 'charge': r[2]} for r in services]
    return render_template("new_bill.html", services=services_list)

@app.route("/reports")
def reports():
    if not has_permission("perm_all_bills"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    search = request.args.get("search")
    
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
        
    limit = 20
    offset = (page - 1) * limit
    username = session.get("username")

    if is_manager_or_admin():
        if search:
            cursor.execute("SELECT COUNT(*) FROM bills WHERE bill_no LIKE %s OR customer_name LIKE %s OR mobile LIKE %s", (f"%{search}%", f"%{search}%", f"%{search}%"))
            total_records = cursor.fetchone()[0]
            cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills WHERE bill_no LIKE %s OR customer_name LIKE %s OR mobile LIKE %s ORDER BY id DESC LIMIT %s OFFSET %s", (f"%{search}%", f"%{search}%", f"%{search}%", limit, offset))
        else:
            cursor.execute("SELECT COUNT(*) FROM bills")
            total_records = cursor.fetchone()[0]
            cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset))
    else:
        if search:
            cursor.execute("SELECT COUNT(*) FROM bills WHERE staff_name=%s AND (bill_no LIKE %s OR customer_name LIKE %s OR mobile LIKE %s)", (username, f"%{search}%", f"%{search}%", f"%{search}%"))
            total_records = cursor.fetchone()[0]
            cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills WHERE staff_name=%s AND (bill_no LIKE %s OR customer_name LIKE %s OR mobile LIKE %s) ORDER BY id DESC LIMIT %s OFFSET %s", (username, f"%{search}%", f"%{search}%", f"%{search}%", limit, offset))
        else:
            cursor.execute("SELECT COUNT(*) FROM bills WHERE staff_name=%s", (username,))
            total_records = cursor.fetchone()[0]
            cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills WHERE staff_name=%s ORDER BY id DESC LIMIT %s OFFSET %s", (username, limit, offset))

    data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    total_pages = (total_records + limit - 1) // limit

    return render_template("reports.html", data=data, current_page=page, total_pages=total_pages, search=search)

@app.route("/bill/<int:bill_id>")
def bill_view(bill_id):
    if "username" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    cursor.execute("SELECT * FROM bills WHERE id=%s", (bill_id,))
    bill = cursor.fetchone()

    if bill and bill['staff_name'] != session.get("username") and not is_manager_or_admin():
        cursor.close()
        release_db_connection(conn)
        return redirect("/dashboard")

    cursor.execute("SELECT service_name, bill_amount, service_charge, total_amount, quantity FROM bill_items WHERE bill_id=%s", (bill_id,))
    items = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    
    bill_list = [bill['id'], bill['bill_no'], bill['bill_date'], bill['customer_name'], bill['mobile'], bill['staff_name'], bill['total_amount'], bill['bill_time'], bill['payment_method'], bill['notes']]
    items_list = [[i['service_name'], i['bill_amount'], i['service_charge'], i['total_amount'], i['quantity']] for i in items]
    
    return render_template("bill_view.html", bill=bill_list, items=items_list)

@app.route("/balance_sheet")
def balance_sheet():
    if not has_permission("perm_all_bills"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    username = session.get("username")

    if is_manager_or_admin():
        cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills")
        data = cursor.fetchall()
        cursor.execute("SELECT SUM(total_amount) FROM bills")
        total = cursor.fetchone()[0] or 0
    else:
        cursor.execute("SELECT id, bill_no, bill_date, customer_name, mobile, staff_name, total_amount FROM bills WHERE staff_name=%s", (username,))
        data = cursor.fetchall()
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE staff_name=%s", (username,))
        total = cursor.fetchone()[0] or 0

    cursor.close()
    release_db_connection(conn)
    return render_template("balance_sheet.html", data=data, total=total)

@app.route("/staff_report", methods=["GET"])
def staff_report():
    if not has_permission("perm_staff_rep"):
        return redirect("/dashboard")

    from_date = request.args.get("from_date") or datetime.now().strftime("%Y-%m-01")
    to_date = request.args.get("to_date") or datetime.now().strftime("%Y-%m-%d")
    username = session.get("username")

    conn = get_db_connection()
    cursor = conn.cursor()

    if is_manager_or_admin():
        cursor.execute("""
            SELECT 
                staff_name, 
                COUNT(id) as total_bills, 
                COALESCE(SUM(total_amount), 0) as total_collection
            FROM bills
            WHERE bill_date BETWEEN %s AND %s
            GROUP BY staff_name
            ORDER BY total_collection DESC
        """, (from_date, to_date))
    else:
        cursor.execute("""
            SELECT 
                staff_name, 
                COUNT(id) as total_bills, 
                COALESCE(SUM(total_amount), 0) as total_collection
            FROM bills
            WHERE staff_name=%s AND bill_date BETWEEN %s AND %s
            GROUP BY staff_name
        """, (username, from_date, to_date))
    
    report_data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("staff_report.html", report_data=report_data, from_date=from_date, to_date=to_date)

@app.route("/service_report", methods=["GET"])
def service_report():
    if not has_permission("perm_service_rep"):
        return redirect("/dashboard")

    from_date = request.args.get("from_date") or datetime.now().strftime("%Y-%m-01")
    to_date = request.args.get("to_date") or datetime.now().strftime("%Y-%m-%d")
    username = session.get("username")

    conn = get_db_connection()
    cursor = conn.cursor()

    if is_manager_or_admin():
        cursor.execute("SELECT service_name, COUNT(*), SUM(total_amount) FROM bill_items WHERE bill_id IN (SELECT id FROM bills WHERE bill_date BETWEEN %s AND %s) GROUP BY service_name ORDER BY SUM(total_amount) DESC", (from_date, to_date))
    else:
        cursor.execute("SELECT service_name, COUNT(*), SUM(total_amount) FROM bill_items WHERE bill_id IN (SELECT id FROM bills WHERE staff_name=%s AND bill_date BETWEEN %s AND %s) GROUP BY service_name ORDER BY SUM(total_amount) DESC", (username, from_date, to_date))

    data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("service_report.html", data=data, from_date=from_date, to_date=to_date)

@app.route("/date_report", methods=["GET", "POST"])
def date_report():
    if not has_permission("perm_date_rep"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    data = []
    total = 0
    username = session.get("username")

    if request.method == "POST":
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        if is_manager_or_admin():
            cursor.execute("SELECT bill_no, bill_date, customer_name, total_amount FROM bills WHERE bill_date BETWEEN %s AND %s ORDER BY bill_date", (from_date, to_date))
        else:
            cursor.execute("SELECT bill_no, bill_date, customer_name, total_amount FROM bills WHERE staff_name=%s AND bill_date BETWEEN %s AND %s ORDER BY bill_date", (username, from_date, to_date))
        
        data = cursor.fetchall()
        for row in data:
            total += row[3]

    cursor.close()
    release_db_connection(conn)
    return render_template("date_report.html", data=data, total=total)

@app.route("/expense", methods=["GET","POST"])
def expense():
    if not has_permission("perm_expense"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    username = session.get("username")

    if request.method == "POST":
        expense_name = request.form.get("expense_name")
        amount = float(request.form.get("amount") or 0)
        expense_date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("INSERT INTO expenses (expense_date, expense_name, amount, staff_name) VALUES (%s,%s,%s,%s)", (expense_date, expense_name, amount, username))
        conn.commit()
        return redirect("/expense")

    if is_manager_or_admin():
        cursor.execute("SELECT id, expense_date, expense_name, amount FROM expenses ORDER BY id DESC")
    else:
        cursor.execute("SELECT id, expense_date, expense_name, amount FROM expenses WHERE staff_name=%s ORDER BY id DESC", (username,))
        
    data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("expense.html", data=data)

@app.route("/edit_expense/<int:id>", methods=["GET","POST"])
def edit_expense(id):
    if not has_permission("perm_expense"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    username = session.get("username")

    cursor.execute("SELECT staff_name FROM expenses WHERE id=%s", (id,))
    exp_owner = cursor.fetchone()
    if exp_owner and exp_owner[0] != username and not is_manager_or_admin():
        cursor.close()
        release_db_connection(conn)
        return redirect("/expense")

    if request.method == "POST":
        expense_name = request.form.get("expense_name")
        amount = float(request.form.get("amount") or 0)
        cursor.execute("UPDATE expenses SET expense_name=%s, amount=%s WHERE id=%s", (expense_name, amount, id))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect("/expense")

    cursor.execute("SELECT id, expense_date, expense_name, amount FROM expenses WHERE id=%s", (id,))
    expense_data = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    return render_template("edit_expense.html", expense=expense_data)

@app.route("/delete_expense/<int:id>")
def delete_expense(id):
    if not has_permission("perm_expense"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    username = session.get("username")

    cursor.execute("SELECT staff_name FROM expenses WHERE id=%s", (id,))
    exp_owner = cursor.fetchone()
    if exp_owner and exp_owner[0] != username and not is_manager_or_admin():
        cursor.close()
        release_db_connection(conn)
        return redirect("/expense")

    cursor.execute("DELETE FROM expenses WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    release_db_connection(conn)
    return redirect("/expense")

@app.route("/profit_loss", methods=["GET"])
def profit_loss():
    if not has_permission("perm_profit_loss"):
        return redirect("/dashboard")

    selected_date = request.args.get("selected_date") or datetime.now().strftime("%Y-%m-%d")
    username = session.get("username")

    conn = get_db_connection()
    cursor = conn.cursor()

    if is_manager_or_admin():
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE bill_date = %s", (selected_date,))
        collection = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE expense_date = %s", (selected_date,))
        expenses = cursor.fetchone()[0] or 0
    else:
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE staff_name=%s AND bill_date = %s", (username, selected_date))
        collection = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE staff_name=%s AND expense_date = %s", (username, selected_date))
        expenses = cursor.fetchone()[0] or 0

    profit = collection - expenses
    cursor.close()
    release_db_connection(conn)
    return render_template("profit_loss.html", collection=collection, expenses=expenses, profit=profit, selected_date=selected_date)

@app.route("/delete_bill/<int:bill_id>")
def delete_bill(bill_id):
    if session.get("role") != "ADMIN":
        return redirect("/dashboard")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bill_items WHERE bill_id=%s", (bill_id,))
    cursor.execute("DELETE FROM bills WHERE id=%s", (bill_id,))
    conn.commit()
    cursor.close()
    release_db_connection(conn)
    return redirect("/reports")

@app.route("/check")
def check():
    if session.get("role") != "ADMIN":
        return redirect("/dashboard")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, bill_no, customer_name FROM bills")
    data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return str(data)

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")
        
    c_new_bill = has_permission("perm_new_bill")
    c_all_bills = has_permission("perm_all_bills")
    c_coll_rep = has_permission("perm_collection_rep")
    c_date_rep = has_permission("perm_date_rep")
    c_staff_rep = has_permission("perm_staff_rep")
    c_serv_rep = has_permission("perm_service_rep")
    c_expense = has_permission("perm_expense")
    c_prof_loss = has_permission("perm_profit_loss")
    c_serv_mgmt = has_permission("perm_services_mgmt")
    
    return render_template("dashboard.html", 
                           role=session.get("role"), 
                           can_new_bill=c_new_bill,
                           can_all_bills=c_all_bills,
                           can_collection_rep=c_coll_rep,
                           can_date_rep=c_date_rep,
                           can_staff_rep=c_staff_rep,
                           can_service_rep=c_serv_rep,
                           can_expense=c_expense,
                           can_profit_loss=c_prof_loss,
                           can_services_mgmt=c_serv_mgmt)

@app.route("/collection_report")
def collection_report():
    if "username" not in session:
        return redirect("/")

    role = session.get("role")
    username = session.get("username")
    selected_date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    staff_balances = []

    if role == "STAFF" and not is_manager_or_admin():
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE staff_name=%s AND bill_date=%s", (username, selected_date))
        total_collection = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bills WHERE staff_name=%s AND bill_date=%s", (username, selected_date))
        bill_count = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE staff_name=%s AND payment_method='Cash' AND bill_date=%s", (username, selected_date))
        cash_total = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE staff_name=%s AND payment_method='UPI' AND bill_date=%s", (username, selected_date))
        upi_total = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE staff_name=%s AND expense_date=%s", (username, selected_date))
        day_expenses = cursor.fetchone()[0]
        cash_in_hand = cash_total - day_expenses
    else:
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE bill_date=%s", (selected_date,))
        total_collection = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bills WHERE bill_date=%s", (selected_date,))
        bill_count = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE payment_method='Cash' AND bill_date=%s", (selected_date,))
        cash_total = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE payment_method='UPI' AND bill_date=%s", (selected_date,))
        upi_total = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date=%s", (selected_date,))
        day_expenses = cursor.fetchone()[0]
        cash_in_hand = cash_total - day_expenses

        # Dynamic breakdown extraction for Admin/Manager
        cursor.execute("SELECT DISTINCT username FROM users WHERE role='STAFF'")
        all_staffs = cursor.fetchall()
        for s in all_staffs:
            s_name = s[0]
            cursor.execute("SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE staff_name=%s AND payment_method='Cash' AND bill_date=%s", (s_name, selected_date))
            s_cash = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE staff_name=%s AND expense_date=%s", (s_name, selected_date))
            s_exp = cursor.fetchone()[0]
            s_balance = s_cash - s_exp
            
            if s_cash > 0 or s_exp > 0:
                staff_balances.append({'name': s_name, 'cash_in': s_cash, 'expense': s_exp, 'balance': s_balance})

    cursor.close()
    release_db_connection(conn)
    return render_template("collection_report.html", role=role, selected_date=selected_date, total_collection=total_collection, bill_count=bill_count, cash_total=cash_total, upi_total=upi_total, day_expenses=day_expenses, cash_in_hand=cash_in_hand, staff_balances=staff_balances)

@app.route("/service_management")
def service_management():
    if not has_permission("perm_services_mgmt"):
        return redirect("/dashboard")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, service_name, charge, service_type FROM services ORDER BY id ASC")
    data = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("service_management.html", data=data)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/add_service", methods=["GET","POST"])
def add_service():
    if not has_permission("perm_services_mgmt"):
        return redirect("/dashboard")

    if request.method == "POST":
        service_name = request.form.get("service_name")
        charge_val = request.form.get("charge")
        charge = float(charge_val) if charge_val and charge_val.strip() != "" else 0.0
        service_type = request.form.get("service_type")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO services (service_name, charge, service_type) VALUES (%s,%s,%s)", (service_name, charge, service_type))
        cursor.execute("SELECT id FROM services WHERE service_name=%s ORDER BY id DESC LIMIT 1", (service_name,))
        service_id = cursor.fetchone()[0]

        if service_type == "VARIABLE":
            from_amounts = request.form.getlist("from_amount[]")
            to_amounts = request.form.getlist("to_amount[]")
            charges = request.form.getlist("service_charge[]")
            for i in range(len(from_amounts)):
                if from_amounts[i] != "":
                    cursor.execute("INSERT INTO service_slabs (service_id, from_amount, to_amount, service_charge) VALUES (%s,%s,%s,%s)", (service_id, float(from_amounts[i]), float(to_amounts[i]), float(charges[i])))

        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect("/service_management")

    return render_template("add_service.html")

@app.route("/edit_service/<int:id>", methods=["GET","POST"])
def edit_service(id):
    if not has_permission("perm_services_mgmt"):
        return redirect("/dashboard")
        
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        service_name = request.form.get("service_name")
        charge = float(request.form.get("charge") or 0)
        service_type = request.form.get("service_type")
        cursor.execute("UPDATE services SET service_name=%s, charge=%s, service_type=%s WHERE id=%s", (service_name, charge, service_type, id))

        if service_type == "VARIABLE":
            from_amounts = request.form.getlist("from_amount[]")
            to_amounts = request.form.getlist("to_amount[]")
            charges = request.form.getlist("service_charge[]")
            cursor.execute("DELETE FROM service_slabs WHERE service_id=%s", (id,))
            for i in range(len(from_amounts)):
                if from_amounts[i] != "":
                    cursor.execute("INSERT INTO service_slabs (service_id, from_amount, to_amount, service_charge) VALUES (%s,%s,%s,%s)", (id, float(from_amounts[i]), float(to_amounts[i]), float(charges[i])))

        conn.commit()
        cursor.close()
        release_db_connection(conn)
        return redirect("/service_management")

    cursor.execute("SELECT id, service_name, charge, service_type FROM services WHERE id=%s", (id,))
    service = cursor.fetchone()
    cursor.execute("SELECT from_amount, to_amount, service_charge FROM service_slabs WHERE service_id=%s", (id,))
    slabs = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    return render_template("edit_service.html", service=service, slabs=slabs)

@app.route("/delete_service/<int:id>")
def delete_service(id):
    if not has_permission("perm_services_mgmt"):
        return redirect("/dashboard")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    release_db_connection(conn)
    return redirect("/service_management")

if __name__ == "__main__":
    app.run(debug=True)
