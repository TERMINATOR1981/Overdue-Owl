import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import datetime
from supabase import create_client, Client

# --- SECRETS & INPUTS ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL")

# Pull Fine Rate and Currency dynamically from the workflow (or default to 50 / PKR)
FINE_RATE = float(os.environ.get("FINE_RATE", 50.0))
CURRENCY = os.environ.get("CURRENCY", "PKR")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)

def run_agent():
    print(f"Agent starting with Fine Rate: {FINE_RATE} {CURRENCY}...")
    
    response = supabase.table('library_loans').select("*").eq('returned', False).execute()
    loans = response.data
    
    today = datetime.now().date()
    summary_lines = []
    total_fine = 0.0
    
    for loan in loans:
        try:
            due = datetime.strptime(str(loan['due_date']).split('T')[0], "%Y-%m-%d").date()
        except Exception as e:
            print(f"Error parsing date for {loan['name']}: {e}")
            continue
            
        days_overdue = (today - due).days
        if days_overdue <= 0:
            continue
            
        fine = days_overdue * FINE_RATE
        total_fine += fine
        
        body = (
            f"Hello {loan['name']},\n\n"
            f'Our records show you have not returned "{loan["book_title"]}".\n\n'
            f"Days overdue: {days_overdue}\n"
            f"Fine so far: {CURRENCY} {fine:.2f}\n\n"
            f"Please return it as soon as possible to avoid further fines."
        )
        
        try:
            send_email(loan['email'], f"Overdue Reminder: {loan['book_title']}", body)
            print(f"Reminder sent to {loan['name']}")
            summary_lines.append(f"{loan['name']} | {loan['book_title']} | {days_overdue} days | {CURRENCY} {fine:.2f}")
        except Exception as e:
            print(f"Failed to email {loan['name']}: {e}")

    if not summary_lines:
        print("No overdue books today.")
        return

    report = "Daily Overdue Summary:\n\n" + "\n".join(summary_lines)
    report += f"\n\n==============================\nTOTAL FINE TO BE COLLECTED: {CURRENCY} {total_fine:.2f}\n=============================="

    if OWNER_EMAIL:
        try:
            send_email(OWNER_EMAIL, "Daily Library Overdue Summary", report)
            print("Summary emailed to owner.")
        except Exception as e:
            print(f"Owner email failed: {e}")

if __name__ == "__main__":
    run_agent()
