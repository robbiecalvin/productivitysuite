from flask import Flask, request, jsonify, render_template
import sqlite3
def create_app(test_config=None):
    app = Flask(__name__)
    if test_config is None:
        app.config.from_mapping(
            DATABASE='instance/expenses.sqlite3'
        )
    else:
        app.config.from_mapping(test_config)
    def init_db():
        conn = sqlite3.connect(app.config['DATABASE'])
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS expenses
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       date TEXT NOT NULL,
                       category TEXT NOT NULL,
                       description TEXT,
                       amount_cents INTEGER NOT NULL)''')
        conn.commit()
        conn.close()
    @app.before_first_request
    def before_first_request_func():
        init_db()
    @app.route('/', methods=['GET'])
    def index():
        return render_template('index.html')
    @app.route('/api/expenses', methods=['POST'])
    def add_expense():
        data = request.get_json()
        if not data or 'date' not in data or 'category' not in data or 'amount_cents' not in data:
            return jsonify({'error': 'Invalid input'}), 400
        date = data['date']
        category = data['category'].strip()
        description = data.get('description', '').strip()[:1000]
        amount_cents = int(data['amount_cents'])
        if not (isinstance(date, str) and isinstance(category, str) and isinstance(amount_cents, int)) or len(category) > 60 or amount_cents <= 0:
            return jsonify({'error': 'Invalid input'}), 400
        conn = sqlite3.connect(app.config['DATABASE'])
        cur = conn.cursor()
        cur.execute('''INSERT INTO expenses (date, category, description, amount_cents)
                      VALUES (?, ?, ?, ?)''', (date, category, description, amount_cents))
        conn.commit()
        expense_id = cur.lastrowid
        conn.close()
        return jsonify({'expense': {'id': expense_id, 'date': date, 'category': category, 'description': description, 'amount_cents': amount_cents}}), 201
    @app.route('/api/expenses', methods=['GET'])
    def get_expenses():
        category = request.args.get('category')
        conn = sqlite3.connect(app.config['DATABASE'])
        cur = conn.cursor()
        if category:
            cur.execute('''SELECT * FROM expenses WHERE category=? ORDER BY id ASC''', (category.strip(),))
        else:
            cur.execute('''SELECT * FROM expenses ORDER BY id ASC''')
        expenses = cur.fetchall()
        total_cents = sum(row[4] for row in expenses)
        conn.close()
        return jsonify({'expenses': [{'id': row[0], 'date': row[1], 'category': row[2], 'description': row[3], 'amount_cents': row[4]} for row in expenses], 'total_cents': total_cents})
    return app
