from flask import Flask, render_template, redirect, request, session, url_for, send_file
import json
import random
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from mail import send_email

app = Flask(__name__)
app.secret_key = 'atm@26'

def generate_otp():
    return str(random.randint(100000, 999999))

def get_data():
    with open('data.json', 'r') as file:  
        return json.load(file)

def save_data(data):
    with open('data.json', 'w') as file:
        return json.dump(data, file, indent=4)

def get_user_by_id(user_id):
    data = get_data()
    for user in data.get("users", []):
        if user.get("id") == user_id:
            return user
    return None

def parse_transaction(item_str):
    item_str = str(item_str).strip()
    is_deposit = True
    amount = 0.0
    tx_type = "Transaction"
    if " - " in item_str:
        parts = item_str.split(" - ", 1)
        amt_str = parts[0].strip()
        type_str = parts[1].strip()
        try:
            amount = float(amt_str.replace(",", ""))
        except ValueError:
            amount = 0.0
        if "dep" in type_str.lower():
            tx_type = "Deposit"
            is_deposit = True
        elif "with" in type_str.lower():
            tx_type = "Withdrawal"
            is_deposit = False
        else:
            tx_type = type_str.capitalize()
    else:
        tx_type = item_str.capitalize()
        is_deposit = "dep" in item_str.lower()
        
    return {
        "raw": item_str,
        "type": tx_type,
        "amount": amount,
        "is_deposit": is_deposit,
        "formatted_amount": f"{amount:,.2f}" if amount else item_str
    }

def generate_pdf_statement(user):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        alignment=1
    )
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B')
    )
    bold_style = ParagraphStyle(
        'BoldStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0F172A')
    )

    elements = []
    
    # Header
    elements.append(Paragraph('SMART ATM BANKING SERVICES', title_style))
    elements.append(Paragraph('Official Account Transaction Statement', subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#2563EB'), spaceAfter=15))

    now_str = datetime.now().strftime('%d %b %Y, %I:%M %p')
    balance = user.get("balance", 0)
    raw_history = user.get("history", [])
    parsed = [parse_transaction(t) for t in raw_history]
    
    total_deposited = sum(t["amount"] for t in parsed if t["is_deposit"])
    total_withdrawn = sum(t["amount"] for t in parsed if not t["is_deposit"])

    # User Information Box
    account_info = [
        [
            Paragraph(f'<b>Account Holder:</b> {user.get("username", "N/A")}', meta_style),
            Paragraph(f'<b>Statement Date:</b> {now_str}', meta_style)
        ],
        [
            Paragraph(f'<b>Account Number:</b> {user.get("accnum", "N/A")}', meta_style),
            Paragraph(f'<b>Current Balance:</b> Rs. {balance:,.2f}', bold_style)
        ],
        [
            Paragraph(f'<b>Registered Email:</b> {user.get("email", "N/A")}', meta_style),
            Paragraph(f'<b>Total Transactions:</b> {len(parsed)}', meta_style)
        ]
    ]
    t_user = Table(account_info, colWidths=[270, 270])
    t_user.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_user)
    elements.append(Spacer(1, 12))

    # Financial Summary Box
    summary_data = [
        [
            Paragraph(f'<b>Total Deposited:</b> <font color="#059669">+ Rs. {total_deposited:,.2f}</font>', meta_style),
            Paragraph(f'<b>Total Withdrawn:</b> <font color="#DC2626">- Rs. {total_withdrawn:,.2f}</font>', meta_style),
            Paragraph(f'<b>Net Balance:</b> <b>Rs. {balance:,.2f}</b>', meta_style),
        ]
    ]
    t_summary = Table(summary_data, colWidths=[180, 180, 180])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#93C5FD')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 15))

    # Transactions Section Heading
    tx_title_style = ParagraphStyle(
        'TxTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    elements.append(Paragraph('Transaction Records', tx_title_style))

    # Transactions Table
    table_headers = ['#', 'Type', 'Description', 'Amount (INR)']
    table_rows = [table_headers]

    if parsed:
        for idx, item in enumerate(parsed, 1):
            sign = '+' if item['is_deposit'] else '-'
            type_label = item['type']
            amt_display = f"{sign} Rs. {item['formatted_amount']}"
            table_rows.append([
                str(idx),
                type_label,
                item['raw'],
                amt_display
            ])
    else:
        table_rows.append(['-', 'No Records', 'No transaction history found for this account', '-'])

    t_tx = Table(table_rows, colWidths=[35, 115, 240, 150])
    
    table_style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
    ]

    if parsed:
        for i, item in enumerate(parsed, 1):
            c = colors.HexColor('#059669') if item['is_deposit'] else colors.HexColor('#DC2626')
            table_style_commands.append(('TEXTCOLOR', (3, i), (3, i), c))
            table_style_commands.append(('FONTNAME', (3, i), (3, i), 'Helvetica-Bold'))

    t_tx.setStyle(TableStyle(table_style_commands))
    elements.append(t_tx)
    elements.append(Spacer(1, 20))

    # Disclaimer / Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )
    elements.append(Paragraph('This is a computer-generated bank statement and does not require a physical signature.', footer_style))
    elements.append(Paragraph(f'Smart ATM System • Generated on {now_str} • Confirmed & Validated', footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer

@app.route('/')
def base():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    info = request.args.get('info')
    if request.method == 'POST':
        acc_num = request.form.get('accnum', '').strip()
        pin = request.form.get('pin', '').strip()
        data = get_data()
        users = data.get("users", [])
        for i in users:
            if i.get("accnum") == acc_num and i.get("pin") == pin:
                session["username"] = i["username"]
                session["id"] = i["id"]
                return redirect(url_for('dashboard'))
        return redirect(url_for('login', info="Invalid Account Number or PIN"))
    return render_template('login.html', info=info)

@app.route('/verify', methods=['POST', 'GET'])
def verify():
    info = request.args.get('info')
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        if 'otp' in session and otp == session['otp']:
            session.pop('otp', None)
            return redirect(url_for('setuppin'))
        return redirect(url_for('verify', info="Invalid OTP. Please check and re-enter."))
    return render_template('verify.html', info=info)

@app.route('/dashboard')
def dashboard():
    if 'id' not in session:
        return redirect(url_for('login', info="Please log in to continue"))
    return render_template('dashboard.html', username=session.get("username", ""))

@app.route('/setuppin', methods=['GET', 'POST'])
def setuppin():
    info = request.args.get('info')
    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        cpin = request.form.get('cpin', '').strip()
        if pin and pin == cpin:
            data = get_data()
            users = data.get("users", [])
            for i in users:
                if i.get("email") == session.get("email"):
                    session.pop('email', None)
                    i["pin"] = pin
                    save_data(data)
                    return redirect(url_for('login', info='PIN has been updated successfully. Please login.'))
            return redirect(url_for('setuppin', info='User email not found.'))
        return redirect(url_for('setuppin', info='PINs do not match. Please try again.'))      
    return render_template('setuppin.html', info=info)

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'id' not in session:
        return redirect(url_for('login', info="Please log in to continue"))

    info = request.args.get('info')
    if request.method == 'POST':
        try:
            amount = int(request.form.get('amount', 0))
        except ValueError:
            return redirect(url_for('deposit', info='Please enter a valid numeric amount'))

        if amount <= 0:
            return redirect(url_for('deposit', info='Amount must be greater than zero'))

        data = get_data()
        users = data.get("users", [])
        for i in users:
            if i["id"] == session["id"]:
                i["balance"] += amount
                i["history"].append(f'{amount} - Deposited')
                save_data(data)
                return redirect(url_for('checkbalance'))
    return render_template('deposit.html', info=info)

@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if 'id' not in session:
        return redirect(url_for('login', info="Please log in to continue"))

    info = request.args.get('info')
    if request.method == 'POST':
        try:
            amount = int(request.form.get('amount', 0))
        except ValueError:
            return redirect(url_for('withdraw', info='Please enter a valid numeric amount'))

        data = get_data()
        users = data.get("users", [])
        for i in users:
            if i["id"] == session["id"]:
                if 0 < amount <= i["balance"]:
                    i["balance"] -= amount
                    i["history"].append(f'{amount} - withdraw')
                    save_data(data)
                    return redirect(url_for('checkbalance'))
                else:
                    return redirect(url_for('withdraw', info="Amount must be > 0 and within your available balance"))
    return render_template('withdraw.html', info=info)

@app.route('/transaction')
def transaction():
    if 'id' not in session:
        return redirect(url_for('login', info='Please log in to continue'))
    user = get_user_by_id(session["id"])
    if not user:
        session.clear()
        return redirect(url_for('login', info='Session expired. Please log in again.'))

    history = user.get("history", [])
    parsed_history = [parse_transaction(item) for item in history]
    # Reverse so latest transactions appear on top
    parsed_history.reverse()
    
    return render_template(
        'transaction.html',
        history=history,
        parsed_history=parsed_history,
        balance=user.get("balance", 0),
        username=user.get("username", "")
    )

@app.route('/download-transactions')
@app.route('/download_statement')
def download_statement():
    if 'id' not in session:
        return redirect(url_for('login', info='Please log in to download statements'))
    user = get_user_by_id(session["id"])
    if not user:
        return redirect(url_for('login', info='User not found'))

    pdf_buffer = generate_pdf_statement(user)
    accnum = user.get("accnum", "account")
    filename = f"SmartATM_Statement_{accnum}.pdf"
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/checkbalance')
def checkbalance():
    if "id" not in session:
        return redirect(url_for('login', info="Please log in to continue"))

    user = get_user_by_id(session["id"])
    if not user:
        return redirect(url_for('login', info="Please log in to continue"))
    return render_template('checkbalance.html', balance=user.get("balance", 0))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/confirmemail', methods=['POST', 'GET'])
def confirmemail():
    info = request.args.get('info')
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        session['email'] = email
        data = get_data()
        users = data.get("users", [])
        for i in users:
            if i.get("email") == email:
                otp = generate_otp()
                session['otp'] = otp
                print(f"[DEBUG] OTP generated for {email}: {otp}")
                sent = send_email(email, "Smart ATM OTP Verification", f"Hello {i['username']},\n\nYour Smart ATM OTP code is: {otp}\n\nPlease enter this OTP to reset your PIN.")
                if sent:
                    return redirect(url_for('verify'))
                else:
                    return redirect(url_for('confirmemail', info="Failed to send email. Please check your network or try again."))
        return redirect(url_for('confirmemail', info="Email is not registered with any bank account."))
    return render_template('confirmemail.html', info=info)

if __name__ == '__main__':
    app.run(debug=True)