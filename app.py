import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import requests

st.set_page_config(page_title="Overdue Owl", page_icon="🦉", layout="wide")
st.title("🦉 Overdue Owl")

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to:", ["📧 Send Reminders", "❓ How to Use / About"])

# --- PAGE 1: THE MAIN APP ---
if page == "📧 Send Reminders":
    st.write("Upload a CSV or Excel file to send overdue book reminders.")

    with st.container():
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

        col5, col6 = st.columns(2)
        with col5:
            fine_rate = st.number_input("Fine per day", value=0.50, step=1.0, min_value=0.0)
        with col6:
            currency = st.text_input("Currency Symbol", value="PKR")

    def send_email(sender_email, sender_password, to_email, subject, body, attachment_data=None, attachment_name=None):
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        
        if attachment_data and attachment_name:
            msg.add_attachment(attachment_data, maintype="text", subtype="plain", filename=attachment_name)
            
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
                                sender_email,
                                sender_password,
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
                        report = "Overdue Summary:\n\n" + "\n".join(summary_lines)
                        report += f"\n\n==============================\nTOTAL FINE TO BE COLLECTED: {currency} {total_fine:.2f}\n=============================="
                        
                        st.success(f"Sent {success_count} reminder(s) successfully!")
                        
                        if owner_email:
                            try:
                                owner_email_body = f"Hello,\n\nHere is the summary of overdue books.\n\nTotal Fine to be Collected: {currency} {total_fine:.2f}\n\nAttached is the full list.\n\n" + report
                                file_bytes = report.encode('utf-8')
                                send_email(sender_email, sender_password, owner_email, "Library Overdue Summary", owner_email_body, file_bytes, "overdue_summary.txt")
                                st.info("Summary emailed to owner successfully.")
                            except Exception as e:
                                st.warning(f"Owner email failed: {e}")

                        if discord_webhook:
                            try:
                                requests.post(discord_webhook, json={"content": report[:1900]}, timeout=10)
                                st.info("Summary sent to Discord.")
                            except Exception as e:
                                st.warning(f"Discord failed: {e}")
                                
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

# --- PAGE 2: THE HELP / ABOUT PAGE ---
elif page == "❓ How to Use / About":
    st.header("About Overdue Owl")
    st.write("This tool automates sending library overdue reminders to borrowers and a summary to the owner.")
    st.divider()
    
    st.subheader("1. Get Your Gmail App Password")
    st.write("Because normal passwords don't work for security reasons, you must generate an App Password:")
    st.markdown("""
    1. Go to your **Google Account Security** settings.
    2. Make sure **2-Step Verification** is turned ON.
    3. Search for **App Passwords** in the settings search bar (or go to `myaccount.google.com/apppasswords`).
    4. Type a name (like "Overdue Owl") and click **Create**.
    5. Copy the **16-letter code** that pops up (you will paste this into the app).
    """)
    
    st.divider()
    st.subheader("2. Prepare Your Excel or CSV File")
    st.write("Your file must have exactly these 4 column headers in the first row:")
    st.code("name, email, book_title, due_date", language="text")
    st.write("*Note: The `due_date` must be in the format `YYYY-MM-DD` (e.g., 2026-10-14).*")
    
    st.divider()
    st.subheader("3. What Each Option Does")
    st.markdown("""
    * **Upload File:** Choose your `.xlsx` or `.csv` file from your computer.
    * **Your Gmail Address:** The email account that will send the reminders.
    * **Gmail App Password:** The 16-letter code you generated in Step 1.
    * **Summary Recipient Email:** (Optional) Where you want a master list of all overdue books and total fines sent to. If left blank, it won't send an email.
    * **Discord Webhook URL:** (Optional) If you want the summary posted in a Discord channel. (Go to Discord Server Settings -> Integrations -> Webhooks to create one).
    * **Fine per day:** How much money is charged for each day the book is late.
    * **Currency Symbol:** Changes the text in the email (e.g., "PKR", "$", "Rs").
    """)
