import os
import csv
from flask import Flask, render_template, request, redirect, url_for, send_file
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sales.db")

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
Session = sessionmaker(bind=engine)

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True)
    date = Column(String, default=datetime.today().strftime("%Y-%m-%d"))
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
    sign = Column(Text)

Base.metadata.create_all(engine)

def calculate_total(qty1, qty05, qty2, qtyp, rate1, rate05, rate2, ratep):
    return (
        int(qty1 or 0) * float(rate1 or 0) +
        int(qty05 or 0) * float(rate05 or 0) +
        int(qty2 or 0) * float(rate2 or 0) +
        int(qtyp or 0) * float(ratep or 0)
    )

@app.route('/')
def index():
    today = datetime.today().strftime('%Y-%m-%d')
    session = Session()
    rows = session.query(Sale).filter(Sale.date == today).order_by(Sale.id.desc()).all()
    records = [{"record": r, "total": calculate_total(
    r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
    r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch)} for r in rows]

    return render_template('index.html', records=records, date=today)

@app.route('/add', methods=['POST'])
def add():
    data = request.form
    sale = Sale(
        date=datetime.today().strftime('%Y-%m-%d'),
        name=data['name'],
        qty_1l=int(data.get('qty_1l', 0)),
        qty_500ml=int(data.get('qty_500ml', 0)),
        qty_2l=int(data.get('qty_2l', 0)),
        qty_pouch=int(data.get('qty_pouch', 0)),
        rate_1l=float(data.get('rate_1l', 0)),
        rate_500ml=float(data.get('rate_500ml', 0)),
        rate_2l=float(data.get('rate_2l', 0)),
        rate_pouch=float(data.get('rate_pouch', 0)),
        cash=int(data.get('cash', 0)),
        due=int(data.get('due', 0)),
        sign=data['sign']
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
        query = query.filter(Sale.date.between(start_date, end_date))
    elif start_date:
        query = query.filter(Sale.date == start_date)
    rows = query.all()
    records = [(r, calculate_total(r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch, r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch)) for r in rows]
    return render_template('all.html', records=records, start_date=start_date, end_date=end_date)

@app.route('/delete/<int:id>')
def delete(id):
    session = Session()
    record = session.query(Sale).get(id)
    if record:
        session.delete(record)
        session.commit()
    return redirect(url_for('index'))

@app.route('/export')
def export():
    filename = 'sales_export.csv'
    session = Session()
    records = session.query(Sale).all()
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ID', 'Date', 'Name', '1L Qty', '500ml Qty', '2L Qty', 'Pouch Qty',
            'Rate 1L', 'Rate 500ml', 'Rate 2L', 'Rate Pouch',
            'Cash', 'Due', 'Sign'
        ])
        for r in records:
            writer.writerow([
                r.id, r.date, r.name, r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch,
                r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch,
                r.cash, r.due, r.sign
            ])
    return send_file(filename, as_attachment=True)

@app.route('/export/pdf')
def export_pdf():
    today = datetime.today().strftime('%Y-%m-%d')
    filename = f"romokon_sales_{today}.pdf"
    session = Session()
    records = session.query(Sale).filter(Sale.date == today).order_by(Sale.id.desc()).all()
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Romokon - Sales Report for {today}")
    c.setFont("Helvetica", 10)
    headers = ["ID", "Name", "1L", "500ml", "2L", "Pouch", "Cash", "Due", "Total"]
    y = height - 80
    row_height = 18
    for i, header in enumerate(headers):
        c.drawString(50 + i*60, y, header)
    y -= row_height
    for r in records:
        total = calculate_total(r.qty_1l, r.qty_500ml, r.qty_2l, r.qty_pouch, r.rate_1l, r.rate_500ml, r.rate_2l, r.rate_pouch)
        row_data = [
            str(r.id), r.name, str(r.qty_1l), str(r.qty_500ml), str(r.qty_2l), str(r.qty_pouch),
            str(r.cash), str(r.due), f"{total:.2f}"
        ]
        for i, item in enumerate(row_data):
            c.drawString(50 + i*60, y, item)
        y -= row_height
        if y < 100:
            c.showPage()
            y = height - 80
    c.save()
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    app.run(debug=True)