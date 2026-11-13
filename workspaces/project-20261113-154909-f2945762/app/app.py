"""Local CAD expense ledger; all arithmetic uses integer cents."""
from contextlib import closing
from datetime import date
from pathlib import Path
import re
import sqlite3

from flask import Flask, jsonify, render_template, request


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(DATABASE=str(Path(app.instance_path) / 'expenses.sqlite3'))
    app.config.update(test_config or {})
    database = Path(app.config['DATABASE'])
    database.parent.mkdir(parents=True, exist_ok=True)

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    with closing(connect()) as connection, connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            category TEXT NOT NULL, description TEXT NOT NULL,
            amount_cents INTEGER NOT NULL)''')

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.post('/api/expenses')
    def add_expense():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - {'date', 'category', 'description', 'amount_cents'}:
            return jsonify(error='Expected an expense object with supported fields.'), 400
        day = data.get('date')
        category = data.get('category')
        description = data.get('description', '')
        amount = data.get('amount_cents')
        if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            return jsonify(error='Date must be YYYY-MM-DD.'), 400
        try:
            date.fromisoformat(day)
        except ValueError:
            return jsonify(error='Date must be a valid calendar date.'), 400
        if not isinstance(category, str) or not 1 <= len(category.strip()) <= 60:
            return jsonify(error='Category must contain 1 to 60 characters.'), 400
        if not isinstance(description, str) or len(description) > 1000:
            return jsonify(error='Description must be at most 1000 characters.'), 400
        if type(amount) is not int or not 1 <= amount <= 100000000:
            return jsonify(error='Amount must be 1 to 100000000 integer cents.'), 400
        with closing(connect()) as connection, connection:
            cursor = connection.execute(
                'INSERT INTO expenses (date, category, description, amount_cents) VALUES (?, ?, ?, ?)',
                (day, category.strip(), description, amount))
            record = connection.execute('SELECT * FROM expenses WHERE id=?', (cursor.lastrowid,)).fetchone()
        return jsonify(expense=dict(record)), 201

    @app.get('/api/expenses')
    def list_expenses():
        category = request.args.get('category', '').strip()
        with closing(connect()) as connection:
            if category:
                rows = connection.execute('SELECT * FROM expenses WHERE category=? ORDER BY id', (category,)).fetchall()
            else:
                rows = connection.execute('SELECT * FROM expenses ORDER BY id').fetchall()
        records = [dict(row) for row in rows]
        return jsonify(expenses=records, total_cents=sum(row['amount_cents'] for row in records))

    return app
