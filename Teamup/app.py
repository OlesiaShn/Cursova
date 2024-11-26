from flask import Flask, render_template, url_for, request, redirect, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure MySQL database
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')

mysql = MySQL(app)


@app.route('/')
def landing_page():
    return render_template('teamup-landing-page.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()

        if account and check_password_hash(account['password'], password):
            session['user_id'] = account['id']  # Зберігаємо ID користувача в сесії
            return redirect(url_for('my_account'))
        else:
            flash('Incorrect username or password!')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('signup'))

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (username, email))
        account = cursor.fetchone()

        if account:
            flash("Username or email already exists!")
        else:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (username, password, first_name, last_name, email) VALUES (%s, %s, %s, %s, %s)',
                (username, hashed_password, first_name, last_name, email)
            )
            mysql.connection.commit()

            # Авторизуємо нового користувача після реєстрації
            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
            new_user = cursor.fetchone()
            session['user_id'] = new_user['id']  # Зберігаємо ID у сесії

            flash('You have successfully signed up!')
            return redirect(url_for('roleselector'))
    return render_template('teamup-signup.html')


@app.route('/roleselector', methods=['GET', 'POST'])
def roleselector():
    if request.method == 'POST':
        role = request.form.get('role')
        user_id = session.get('user_id')  # Беремо ID з сесії

        if user_id:  # Перевіряємо, чи авторизований користувач
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                cursor.execute('UPDATE users SET role = %s WHERE id = %s', (role, user_id))
                mysql.connection.commit()
            except MySQLdb.Error as e:
                flash(f'Database error: {e}')
                return redirect(url_for('roleselector'))

            if role == 'leader':
                return redirect(url_for('addaproject'))
            elif role == 'member':
                return redirect(url_for('profilecompletion'))
        else:
            flash('Please log in first!')
            return redirect(url_for('login'))
    return render_template('roleselector.html')


@app.route('/my-account')
def my_account():
    if 'user_id' not in session:  # Перевірка авторизації
        flash('Please log in first!')
        return redirect(url_for('login'))
    return render_template('my-account-detailed.html')


@app.route('/projects')
def projects():
    if 'user_id' not in session:
        flash('Please log in first!')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT p.id, p.name AS title, p.description, u.username AS author
        FROM projects p
        JOIN users u ON p.leader_id = u.id
    ''')
    projects_data = cursor.fetchall()

    for project in projects_data:
        cursor.execute('''
            SELECT s.name
            FROM project_skills ps
            JOIN skills s ON ps.skill_id = s.id
            WHERE ps.project_id = %s
        ''', (project['id'],))
        tags = cursor.fetchall()
        project['tags'] = [tag['name'] for tag in tags]

    return render_template('projects.html',
                         projects=projects_data,
                         user_name=session.get('user_name', 'User'))

@app.route('/projectsforall')
def projectsforall():
    if 'user_id' not in session:  # Перевірка авторизації користувача
        flash('Please log in first!')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Вибір усіх проєктів із бази даних
    cursor.execute('''
        SELECT p.id, p.name AS title, p.description, u.username AS author
        FROM projects p
        JOIN users u ON p.leader_id = u.id
    ''')
    projects_data = cursor.fetchall()

    # Додаємо теги до кожного проєкту
    for project in projects_data:
        cursor.execute('''
            SELECT s.name
            FROM project_skills ps
            JOIN skills s ON ps.skill_id = s.id
            WHERE ps.project_id = %s
        ''', (project['id'],))
        tags = cursor.fetchall()
        project['tags'] = [tag['name'] for tag in tags]

    return render_template('projectsforall.html',  # Завантажуємо шаблон для сторінки "projectsforall"
                           projects=projects_data,
                           user_name=session.get('user_name', 'User'))

@app.route('/project/<int:project_id>')
def project_details(project_id):
    if 'user_id' not in session:  # Перевірка авторизації
        flash('Please log in first!')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Отримання основної інформації про проєкт
    cursor.execute('''
        SELECT p.id, p.name, p.description, p.timeframes, p.phone_number, u.username AS author, p.created_at
        FROM projects p
        JOIN users u ON p.leader_id = u.id
        WHERE p.id = %s
    ''', (project_id,))
    project = cursor.fetchone()

    if not project:  # Якщо проєкт не знайдено
        flash('Project not found!')
        return redirect(url_for('projects_for_all'))

    # Отримання тегів (навичок), пов'язаних із проєктом
    cursor.execute('''
        SELECT s.name
        FROM project_skills ps
        JOIN skills s ON ps.skill_id = s.id
        WHERE ps.project_id = %s
    ''', (project_id,))
    skills = cursor.fetchall()
    project['skills'] = [skill['name'] for skill in skills]

    return render_template('projectdetail.html', project=project, username=session.get('user_name', 'User'))


@app.route('/read-more')
def read_more():
    return render_template('teamup-info.html')


@app.route('/addaproject', methods=['GET', 'POST'])
def addaproject():
    if 'user_id' not in session:
        flash('Please log in first!')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        timeframes = request.form['timeframes']
        phone = request.form['phone']
        skills = request.form.getlist('skills[]')  # Отримуємо список навичок

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            # Додаємо проект
            cursor.execute(
                'INSERT INTO projects (name, description, timeframes, phone_number, leader_id) VALUES (%s, %s, %s, %s, %s)',
                (name, description, timeframes, phone, session['user_id'])
            )
            mysql.connection.commit()
            project_id = cursor.lastrowid

            # Додаємо навички до таблиці skills і зв'язуємо з проектом
            for skill_name in skills:
                # Перевіряємо, чи навичка вже існує в таблиці skills
                cursor.execute('SELECT id FROM skills WHERE name = %s', (skill_name,))
                skill = cursor.fetchone()

                # Якщо навичка не знайдена, додаємо її
                if not skill:
                    cursor.execute('INSERT INTO skills (name) VALUES (%s)', (skill_name,))
                    mysql.connection.commit()
                    skill_id = cursor.lastrowid
                else:
                    skill_id = skill['id']

                # Додаємо зв'язок навички з проектом
                cursor.execute(
                    'INSERT INTO project_skills (project_id, skill_id) VALUES (%s, %s)',
                    (project_id, skill_id)
                )

            mysql.connection.commit()
            flash('Project successfully created!')
            return redirect(url_for('projects'))

        except MySQLdb.Error as e:
            flash(f'Error creating project: {e}')
            return redirect(url_for('addaproject'))

    return render_template('addaproject.html')

@app.route('/profilecompletion', methods=['GET', 'POST'])
def profilecompletion():
    if 'user_id' not in session:  # Перевірка, чи користувач авторизований
        flash('Please log in first!')
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_id = session.get('user_id')  # Отримуємо ID користувача з сесії
        biography = request.form['biography']
        work_experience = request.form['work_experience']
        linkedin = request.form.get('linkedin')  # Це поле не обов'язкове
        portfolio = request.form.get('portfolio')  # Це поле не обов'язкове

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        try:
            # Вставляємо дані в таблицю user_profiles
            cursor.execute('''
                INSERT INTO user_profiles (user_id, biography, work_experience, linkedin, portfolio)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, biography, work_experience, linkedin, portfolio))

            mysql.connection.commit()

            flash('Your profile has been successfully completed!')
            return redirect(url_for('projectsforall'))  # Перенаправлення на сторінку профілю

        except MySQLdb.Error as e:
            flash(f'Error saving profile data: {e}')
            return redirect(url_for('profilecompletion'))  # Якщо сталася помилка, залишаємо на сторінці

    return render_template('profilecompletion.html')  # Завантажуємо оновлений шаблон



@app.route('/logout')
def logout():
    session.clear()  # Видаляємо всі дані з сесії
    flash('You have been logged out!')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
