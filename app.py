import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(180), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False, default='')


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    limit_amount = db.Column(db.Numeric(12, 2), nullable=False)
    __table_args__ = (UniqueConstraint('user_id', 'category', 'month'),)


class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Numeric(12, 2), nullable=False)


class SavingsContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('savings_goal.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    date = db.Column(db.Date, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def money(raw):
    try:
        number = Decimal(str(raw)).quantize(Decimal('0.01'))
        if not number.is_finite() or number <= 0 or number > Decimal('9999999999.99'):
            raise ValueError
        return number
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Enter a valid positive amount.')


def create_app(config=None):
    app = Flask(__name__)
    database_url = os.getenv('DATABASE_URL', 'sqlite:///smartbudget.db')
    if database_url.startswith('postgres://'):
        database_url = 'postgresql://' + database_url[len('postgres://'):]
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-only-change-this-before-deploying'),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    csrf.init_app(app)

    @app.route('/')
    def home():
        return redirect(url_for('dashboard' if current_user.is_authenticated else 'login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            if not username or '@' not in email or len(password) < 8:
                flash('Enter a username, valid email, and password of at least 8 characters.', 'error')
            elif db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
                flash('That email is already registered.', 'error')
            else:
                db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password)))
                db.session.commit()
                flash('Account created. Please log in.', 'success')
                return redirect(url_for('login'))
        return render_template('auth.html', mode='register')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
            if user and check_password_hash(user.password_hash, request.form.get('password', '')):
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('Invalid email or password.', 'error')
        return render_template('auth.html', mode='login')

    @app.post('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        month = request.args.get('month', date.today().strftime('%Y-%m'))
        try:
            date.fromisoformat(month + '-01')
        except ValueError:
            month = date.today().strftime('%Y-%m')
        transactions = db.session.execute(db.select(Transaction).where(
            Transaction.user_id == current_user.id,
            func.strftime('%Y-%m', Transaction.date) == month
        ).order_by(Transaction.date.desc(), Transaction.id.desc())).scalars().all() if db.engine.dialect.name == 'sqlite' else db.session.execute(db.select(Transaction).where(
            Transaction.user_id == current_user.id,
            func.to_char(Transaction.date, 'YYYY-MM') == month
        ).order_by(Transaction.date.desc(), Transaction.id.desc())).scalars().all()
        income = sum((t.amount for t in transactions if t.kind == 'income'), Decimal('0'))
        expenses = sum((t.amount for t in transactions if t.kind == 'expense'), Decimal('0'))
        budgets = db.session.execute(db.select(Budget).filter_by(user_id=current_user.id, month=month)).scalars().all()
        spending = {}
        for t in transactions:
            if t.kind == 'expense':
                spending[t.category] = spending.get(t.category, Decimal('0')) + t.amount
        goals = db.session.execute(db.select(SavingsGoal).filter_by(user_id=current_user.id)).scalars().all()
        contributions = db.session.execute(db.select(SavingsContribution).join(SavingsGoal).where(SavingsGoal.user_id == current_user.id)).scalars().all()
        totals = {}
        for c in contributions:
            totals[c.goal_id] = totals.get(c.goal_id, Decimal('0')) + c.amount
        return render_template('dashboard.html', month=month, transactions=transactions, income=income, expenses=expenses,
                               budgets=budgets, spending=spending, goals=goals, totals=totals)

    @app.post('/transactions')
    @login_required
    def add_transaction():
        kind = request.form.get('kind')
        category = request.form.get('category', '').strip()[:40]
        if kind not in ('income', 'expense') or not category:
            flash('Choose an income/expense type and category.', 'error')
            return redirect(url_for('dashboard'))
        try:
            amount = money(request.form.get('amount'))
            transaction_date = date.fromisoformat(request.form.get('date', ''))
        except (ValueError, TypeError):
            flash('Enter a valid positive amount and date.', 'error')
            return redirect(url_for('dashboard'))
        db.session.add(Transaction(user_id=current_user.id, kind=kind, category=category,
                                   amount=amount, date=transaction_date,
                                   description=request.form.get('description', '').strip()[:255]))
        db.session.commit()
        flash('Transaction saved.', 'success')
        return redirect(url_for('dashboard', month=transaction_date.strftime('%Y-%m')))

    @app.post('/transactions/<int:transaction_id>/delete')
    @login_required
    def delete_transaction(transaction_id):
        transaction = db.session.get(Transaction, transaction_id)
        if not transaction or transaction.user_id != current_user.id:
            return ('Not found', 404)
        month = transaction.date.strftime('%Y-%m')
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction deleted.', 'success')
        return redirect(url_for('dashboard', month=month))

    @app.post('/budgets')
    @login_required
    def save_budget():
        category = request.form.get('category', '').strip()[:40]
        month = request.form.get('month', '')
        try:
            date.fromisoformat(month + '-01')
            amount = money(request.form.get('limit_amount'))
            if not category:
                raise ValueError
        except (ValueError, TypeError):
            flash('Enter a category, month, and positive limit.', 'error')
            return redirect(url_for('dashboard'))
        budget = db.session.execute(db.select(Budget).filter_by(user_id=current_user.id, category=category, month=month)).scalar_one_or_none()
        if budget:
            budget.limit_amount = amount
        else:
            db.session.add(Budget(user_id=current_user.id, category=category, month=month, limit_amount=amount))
        db.session.commit()
        flash('Budget saved.', 'success')
        return redirect(url_for('dashboard', month=month))

    @app.post('/goals')
    @login_required
    def add_goal():
        name = request.form.get('name', '').strip()[:100]
        try:
            target = money(request.form.get('target_amount'))
            if not name:
                raise ValueError
        except (ValueError, TypeError):
            flash('Enter a goal name and valid target.', 'error')
            return redirect(url_for('dashboard'))
        db.session.add(SavingsGoal(user_id=current_user.id, name=name, target_amount=target))
        db.session.commit()
        flash('Savings goal created.', 'success')
        return redirect(url_for('dashboard'))

    @app.post('/goals/<int:goal_id>/contributions')
    @login_required
    def contribute(goal_id):
        goal = db.session.get(SavingsGoal, goal_id)
        if not goal or goal.user_id != current_user.id:
            return ('Not found', 404)
        try:
            amount = money(request.form.get('amount'))
        except ValueError:
            flash('Enter a valid contribution.', 'error')
            return redirect(url_for('dashboard'))
        db.session.add(SavingsContribution(goal_id=goal.id, amount=amount, date=date.today()))

        expense_transaction = Transaction(
            kind='expense',
            category='Savings',
            amount=amount,
            date=date.today(),
            description=f'Contribution to savings goal: {goal.name}',
            user_id=current_user.id
        )

        db.session.add(expense_transaction)
        
        db.session.commit()
        flash('Contribution recorded.', 'success')
        return redirect(url_for('dashboard'))

    with app.app_context():
        db.create_all()  # classroom MVP; use migrations for production schema changes
    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
