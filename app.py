import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import requests

FINE_PER_DAY = 0.5  # Change this to your fine rate

st.set_page_config(page_title="Overdue Owl", page_icon="🦉")
st.title("🦉 Overdue Owl")
st.write("Upload a CSV or Excel file to send overdue book reminders.")

# UI Layout
with st.container():
    # Added .xlsx support here
    uploaded_file = st.file_uploader("Upload File (CSV or Excel)", type=["csv", "xlsx"])
    
    col1, col2 = st.columns(2)
    with col1:
        sender_email = st.text_input("Your Gmail Address")
    with col2:
        sender_password = st.text_input("Gmail App Password", type="password")
        
    col3, col4 = st.columns(2)
    with col3:
        owner_email = st.text_input("Summary Recipient Email (Optional)")
    with col4:
        discord_webhook = st.text_input("Discord Webhook URL (Optional)")

def send_email(sender_email, sender_password, to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)

if st.button("Send Reminders", type="primary"):
    if not uploaded_file:
        st.error("Please upload a CSV or Excel file.")
    elif not sender_email or not sender_password:
        st.error("Please enter your Gmail and App Password.")
    else:
        try:
            # Check if it's an Excel file or CSV and read it
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)

            required_cols = {"name", "email", "book_title", "due_date"}
            missing = required_cols - set(df.columns)
            
            if missing:
                st.error(f"File is missing columns: {', '.join(missing)}. Please check your header row.")
            else:
                today = datetime.now().date()
                summary_lines = []
                success_count = 0
                error_lines = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for index, row in df.iterrows():
                    status_text.text(f"Processing {row.get('name', 'record')}...")
                    
                    try:
                        due = datetime.strptime(str(row["due_date"]).strip(), "%Y-%m-%d").date()
                    except Exception:
                        error_lines.append(f"Skipped {row.get('name', '?')}: bad due_date format '{row.get('due_date')}' (Use YYYY-MM-DD)")
                        continue

                    days_overdue = (today - due).days
                    if days_overdue <= 0:
                        continue

                    fine = days_overdue * FINE_PER_DAY
                    body = (
                        f"Hello {row['name']},\n\n"
                        f'You have not yet returned "{row["book_title"]}".\n\n'
                        f"Days overdue: {days_overdue}\n"
                        f"Fine so far: {fine:.2f}\n\n"
                        f"Please return it as soon as possible.\n"
                    )
                    
                    try:
                        send_email(
                            sender_email,
                            sender_password,
                            str(row["email"]).strip(),
                            f"Overdue Reminder: {row['book_title']}",
                            body,
                        )
                        success_count += 1
                        summary_lines.append(f"{row['name']} | {row['book_title']} | {days_overdue} days overdue | fine {fine:.2f}")
                    except Exception as e:
                        error_lines.append(f"Email failed for {row['name']}: {e}")
                        
                    progress_bar.progress((index + 1) / len(df))
                
                status_text.empty()
                
                if not summary_lines:
                    st.warning("No overdue records found.")
                    if error_lines:
                        st.write("Errors:", error_lines)
                else:
                    report = "Overdue Summary:\n\n" + "\n".join(summary_lines)
                    st.success(f"Sent {success_count} reminder(s) successfully!")
                    
                    if owner_email:
                        try:
                            send_email(sender_email, sender_password, owner_email, "Library Overdue Summary", report)
                            st.info("Summary emailed to owner.")
                        except Exception as e:
                            st.warning(f"Owner email failed: {e}")

                    if discord_webhook:
                        try:
                            requests.post(discord_webhook, json={"content": report[:1900]}, timeout=10)
                            st.info("Summary sent to Discord.")
                        except Exception as e:
                            st.warning(f"Discord failed: {e}")
                            
                    with st.expander("View Summary Details"):
                        st.text(report)
                        
                    if error_lines:
                        with st.expander("View Errors"):
                            for err in error_lines:
                                st.text(err)

        except Exception as e:
            st.error(f"An error occurred: {e}")
