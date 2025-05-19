import os
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_4goh9zuOGjQR@ep-steep-haze-a4idiy36-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require")

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    date = Column(String, default=datetime.now().strftime("%d/%m/%Y %H:%M"))
    name = Column(String)
    qty_1l = Column(Integer, default=0)
    qty_500ml = Column(Integer, default=0)
    qty_2l = Column(Integer, default=0)
    qty_pouch = Column(Integer, default=0)
    rate_1l = Column(Float, default=0)
    rate_500ml = Column(Float, default=0)
    rate_2l = Column(Float, default=0)
    rate_pouch = Column(Float, default=0)
    cash = Column(Integer, default=0)
    due = Column(Integer, default=0)
    prev_deposit = Column(Integer, default=0)  # 🆕 Renamed from 'short'
    sign = Column(Text, default="Nandkishore")


Base.metadata.create_all(engine)


def calculate_total(qty_1l, qty_500ml, qty_2l, qty_pouch, rate_1l, rate_500ml, rate_2l, rate_pouch):
    return (
        int(qty_1l or 0) * float(rate_1l or 0) +
        int(qty_500ml or 0) * float(rate_500ml or 0) +
        int(qty_2l or 0) * float(rate_2l or 0) +
        int(qty_pouch or 0) * float(rate_pouch or 0)
    )


@app.route('/')
def index():
    session = Session()
    today_str = datetime.today().strftime('%d/%m/%Y')
    rows = session.query(Sale).filter(Sale.date.startswith(today_str)).order_by(Sale.id.desc()).all()

    records = [{"record": r, "total": calculate_total(
        r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
        r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch)} for r in rows]

    summary = {
        "qty_1l": sum(r.qty_1l for r in rows),
        "qty_500ml": sum(r.qty_500ml for r in rows),
        "qty_2l": sum(r.qty_2l for r in rows),
        "qty_pouch": sum(r.qty_pouch for r in rows),
        "total_cash": sum(r.cash for r in rows),
        "total_due": sum(r.due for r in rows),
        "total_revenue": sum(
            calculate_total(r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
                            r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch) for r in rows
        )
    }

    return render_template('index.html', records=records, date=today_str, summary=summary)


@app.route('/add', methods=['POST'])
def add():
    data = request.form
    qtys = {k: int(data.get(k) or 0) for k in ['qty_1l', 'qty_500ml', 'qty_2l', 'qty_pouch']}
    rates = {k: float(data.get(k) or 0) for k in ['rate_1l', 'rate_500ml', 'rate_2l', 'rate_pouch']}
    cash = int(data.get('cash') or 0)
    prev_deposit = int(data.get('prev_deposit') or 0)

    total = calculate_total(**qtys, **rates)
    due = int(total - cash)
    sale = Sale(
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        name=data['name'],
        qty_1l=qtys['qty_1l'],
        qty_500ml=qtys['qty_500ml'],
        qty_2l=qtys['qty_2l'],
        qty_pouch=qtys['qty_pouch'],
        rate_1l=rates['rate_1l'],
        rate_500ml=rates['rate_500ml'],
        rate_2l=rates['rate_2l'],
        rate_pouch=rates['rate_pouch'],
        cash=cash,
        due=due,
        prev_deposit=prev_deposit,
        sign=data.get('sign', 'Nandkishore')
    )
    session = Session()
    session.add(sale)
    session.commit()
    return redirect(url_for('index'))


@app.route('/all')
def all():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    session = Session()
    query = session.query(Sale).order_by(Sale.date.desc())
    if start_date and end_date:
        query = query.filter(Sale.date >= start_date, Sale.date <= end_date)
    elif start_date:
        query = query.filter(Sale.date.startswith(start_date))
    rows = query.all()

    records = [(r, calculate_total(r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
                                   r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch)) for r in rows]

    summary = {
        "qty_1l": sum(r.qty_1l for r in rows),
        "qty_500ml": sum(r.qty_500ml for r in rows),
        "qty_2l": sum(r.qty_2l for r in rows),
        "qty_pouch": sum(r.qty_pouch for r in rows),
        "total_cash": sum(r.cash for r in rows),
        "total_due": sum(r.due for r in rows),
        "total_revenue": sum(
            calculate_total(r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
                            r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch) for r in rows
        )
    }

    return render_template('all.html', records=records, start_date=start_date, end_date=end_date, summary=summary)


@app.route('/delete/<int:id>')
def delete(id):
    session = Session()
    record = session.query(Sale).get(id)
    if record:
        session.delete(record)
        session.commit()
    return redirect(url_for('index'))


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    session = Session()
    sale = session.query(Sale).get(id)
    if not sale:
        return "Record not found", 404

    if request.method == 'POST':
        qtys = {k: int(request.form.get(k, 0)) for k in ['qty_1l', 'qty_500ml', 'qty_2l', 'qty_pouch']}
        rates = {k: float(request.form.get(k, 0)) for k in ['rate_1l', 'rate_500ml', 'rate_2l', 'rate_pouch']}
        total = calculate_total(**qtys, **rates)
        cash = int(request.form.get('cash', 0))
        due = int(total - cash)

        sale.name = request.form['name']
        sale.qty_1l = qtys['qty_1l']
        sale.qty_500ml = qtys['qty_500ml']
        sale.qty_2l = qtys['qty_2l']
        sale.qty_pouch = qtys['qty_pouch']
        sale.rate_1l = rates['rate_1l']
        sale.rate_500ml = rates['rate_500ml']
        sale.rate_2l = rates['rate_2l']
        sale.rate_pouch = rates['rate_pouch']
        sale.cash = cash
        sale.due = due
        sale.prev_deposit = int(request.form.get('prev_deposit', 0))
        sale.sign = request.form.get('sign', 'Nandkishore')
        session.commit()
        return redirect(url_for('index'))

    return render_template('edit.html', sale=sale)


@app.route('/export')
def export():
    filename = 'sales_export.csv'
    session = Session()
    records = session.query(Sale).all()
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Date', 'Name', '1L Qty', '500ml Qty', '2L Qty', 'Pouch Qty',
            'Rate 1L', 'Rate 500ml', 'Rate 2L', 'Rate Pouch',
            'Cash', 'Due', 'Prev Deposit', 'Sign'
        ])
        for r in records:
            writer.writerow([
                r.date, r.name, r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
                r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch,
                r.cash, r.due, r.prev_deposit, r.sign
            ])
    return send_file(filename, as_attachment=True)


@app.route('/export/pdf')
def export_pdf():
    today = datetime.today().strftime('%Y-%m-%d')
    filename = f"romokon_sales_{today}.pdf"
    session = Session()
    records = session.query(Sale).filter(Sale.date.startswith(datetime.today().strftime('%d/%m/%Y'))).order_by(Sale.id.desc()).all()

    # Create PDF
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph(f"<b>Romokon - Sales Report for {today}</b>", styles['Title']))
    elements.append(Spacer(1, 12))

    # Table header
    data = [["Time", "Name", "1L", "500ml", "2L", "Pouch", "Cash", "Due", "Deposit", "Total"]]

    # Table rows
    for r in records:
        total = calculate_total(
            r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
            r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch
        )
        row = [
            r.date[-5:],  # time
            Paragraph(r.name, styles['Normal']),  # allow wrapping
            str(r.qty_1l),
            str(r.qty_500ml),
            str(r.qty_2l),
            str(r.qty_pouch),
            f"{r.cash}",
            f"{r.due}",
            f"{r.prev_deposit}",
            f"{total:.2f}"
        ]
        data.append(row)

    # Define table with styling
    table = Table(data, repeatRows=1, colWidths=[
        50, 120, 40, 50, 40, 50, 60, 50, 60, 60
    ])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file(filename, as_attachment=True)


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    app.run(debug=True)
