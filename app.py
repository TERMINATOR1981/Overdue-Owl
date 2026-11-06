import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import requests

st.set_page_config(page_title="Overdue Owl", page_icon="🦉")
st.title("🦉 Overdue Owl")
st.write("Upload a CSV or Excel file to send overdue book reminders.")

# SECURE: Pull credentials from Streamlit Secrets
try:
    SENDER_EMAIL = st.secrets["GMAIL_USER"]
    SENDER_PASSWORD = st.secrets["GMAIL_PASSWORD"]
except Exception:
    st.error("Missing Secrets! Please add GMAIL_USER and GMAIL_PASSWORD in the Streamlit Settings > Secrets.")
    st.stop()

with st.container():
    uploaded_file = st.file_uploader("Upload File (CSV or Excel)", type=["csv", "xlsx"])
    
    col3, col4 = st.columns(2)
    with col3:
        owner_email = st.text_input("Summary Recipient Email (Optional)")
    with col4:
        discord_webhook = st.text_input("Discord Webhook URL (Optional)")

    col5, col6 = st.columns(2)
    with col5:
        fine_rate = st.number_input("Fine per day", value=0.50, step=1.0, min_value=0.0)
    with col6:
        currency = st.text_input("Currency Symbol", value="PKR")

def send_email(to_email, subject, body, attachment_data=None, attachment_name=None):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    
    if attachment_data and attachment_name:
        msg.add_attachment(attachment_data, maintype="text", subtype="plain", filename=attachment_name)
        
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
        smtp.send_message(msg)

if st.button("Send Reminders", type="primary"):
    if not uploaded_file:
        st.error("Please upload a CSV or Excel file.")
    else:
        try:
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
                total_fine = 0.0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for index, row in df.iterrows():
                    status_text.text(f"Processing {row.get('name', 'record')}...")
                    
                    try:
                        raw_date = str(row["due_date"]).strip().split(' ')[0]
                        due = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    except Exception:
                        error_lines.append(f"Skipped {row.get('name', '?')}: bad due_date format '{row.get('due_date')}'")
                        continue

                    days_overdue = (today - due).days
                    if days_overdue <= 0:
                        continue

                    fine = days_overdue * fine_rate
                    total_fine += fine
                    
                    body = (
                        f"Hello {row['name']},\n\n"
                        f'You have not yet returned "{row["book_title"]}".\n\n'
                        f"Days overdue: {days_overdue}\n"
                        f"Fine so far: {currency} {fine:.2f}\n\n"
                        f"Please return it as soon as possible.\n"
                    )
                    
                    try:
                        send_email(
                            str(row["email"]).strip(),
                            f"Overdue Reminder: {row['book_title']}",
                            body,
                        )
                        success_count += 1
                        summary_lines.append(f"{row['name']} | {row['book_title']} | {days_overdue} days overdue | Fine: {currency} {fine:.2f}")
                    except Exception as e:
                        error_lines.append(f"Email failed for {row['name']}: {e}")
                        
                    progress_bar.progress((index + 1) / len(df))
                
                status_text.empty()
                
                if not summary_lines:
                    st.warning("No overdue records found.")
                    if error_lines:
                        st.write("Errors:", error_lines)
                else:
                    # Create the full report text
                    report = "Overdue Summary:\n\n" + "\n".join(summary_lines)
                    # Changed to "TOTAL FINE TO BE COLLECTED"
                    report += f"\n\n==============================\nTOTAL FINE TO BE COLLECTED: {currency} {total_fine:.2f}\n=============================="
                    
                    st.success(f"Sent {success_count} reminder(s) successfully!")
                    
                    # Owner Email - Sends if owner_email is filled
                    if owner_email:
                        try:
                            # Include the total at the top of the email body as well
                            owner_email_body = f"Hello,\n\nHere is the summary of overdue books.\n\nTotal Fine to be Collected: {currency} {total_fine:.2f}\n\nAttached is the full list.\n\n" + report
                            
                            file_bytes = report.encode('utf-8')
                            send_email(owner_email, "Library Overdue Summary", owner_email_body, file_bytes, "overdue_summary.txt")
                            st.info("Summary emailed to owner successfully.")
                        except Exception as e:
                            st.warning(f"Owner email failed: {e}")

                    # Discord Webhook
                    if discord_webhook:
                        try:
                            requests.post(discord_webhook, json={"content": report[:1900]}, timeout=10)
                            st.info("Summary sent to Discord.")
                        except Exception as e:
                            st.warning(f"Discord failed: {e}")
                            
                    # Download Button on the App
                    st.download_button(
                        label="📥 Download Summary Report",
                        data=report,
                        file_name="overdue_summary.txt",
                        mime="text/plain"
                    )
                            
                    with st.expander("View Summary Details"):
                        st.text(report)
                        
                    if error_lines:
                        with st.expander("View Errors"):
                            for err in error_lines:
                                st.text(err)

        except Exception as e:
            st.error(f"An error occurred: {e}")
