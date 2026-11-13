from flask import Flask, request, jsonify, render_template, current_app
import sqlite3
import os

DATABASE = 'instance/tasks.sqlite3'

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, 'tasks.sqlite3')
    )
    if test_config is not None:
        app.config.update(test_config)

    database_directory = os.path.dirname(
        os.path.abspath(app.config['DATABASE'])
    )
    os.makedirs(database_directory, exist_ok=True)

    with app.app_context():
        conn = get_db_connection()
        conn.execute('''CREATE TABLE IF NOT EXISTS tasks
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       title TEXT NOT NULL,
                       description TEXT,
                       completed BOOLEAN DEFAULT 0)''')
        conn.commit()
        conn.close()

    @app.route('/', methods=['GET'])
    def index():
        return render_template('index.html')

    @app.route('/api/tasks', methods=['GET'])
    def get_tasks():
        conn = get_db_connection()
        tasks = conn.execute('SELECT * FROM tasks ORDER BY id').fetchall()
        conn.close()
        return jsonify({'tasks': [
            dict(task, completed=bool(task['completed']))
            for task in tasks
        ]})

    @app.route('/api/tasks', methods=['POST'])
    def create_task():
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid input'}), 400
        if 'title' not in data or not isinstance(data['title'], str) or not data['title'].strip():
            return jsonify({'error': 'Title is required and must be a non-empty string'}), 400
        if set(data) - {'title', 'description'}:
            return jsonify({'error': 'Unexpected fields'}), 400
        title = data['title'].strip()
        if len(title) > 200:
            return jsonify({'error': 'Title exceeds 200 characters'}), 400
        description = data.get('description', '')
        if not isinstance(description, str) or len(description) > 5000:
            return jsonify({'error': 'Description must be a string of at most 5000 characters'}), 400
        conn = get_db_connection()
        cursor = conn.execute('INSERT INTO tasks (title, description) VALUES (?, ?)', (title, description))
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()
        return jsonify({'task': {'id': task_id, 'title': title, 'description': description, 'completed': False}}), 201

    @app.route('/api/tasks/<int:task_id>', methods=['PATCH'])
    def update_task(task_id):
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid input'}), 400
        if set(data) != {'completed'}:
            return jsonify({'error': 'Only completed is accepted'}), 400
        if not isinstance(data['completed'], bool):
            return jsonify({'error': 'Completed must be a boolean'}), 400
        conn = get_db_connection()
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if task is None:
            conn.close()
            return jsonify({'error': 'Task not found'}), 404
        conn.execute('UPDATE tasks SET completed = ? WHERE id = ?', (data['completed'], task_id))
        conn.commit()
        conn.close()
        return jsonify({'task': {'id': task_id, 'title': task['title'], 'description': task['description'], 'completed': data['completed']}}), 200

    @app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
    def delete_task(task_id):
        conn = get_db_connection()
        task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if task is None:
            conn.close()
            return jsonify({'error': 'Task not found'}), 404
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        return '', 204

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)