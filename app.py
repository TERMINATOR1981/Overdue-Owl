import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests
from datetime import datetime

st.set_page_config(page_title="Overdue Owl Command Center", page_icon="🦉", layout="wide")
st.title("🦉 Overdue Owl Command Center")

# --- CONNECT TO SUPABASE ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Missing Supabase Secrets. Please add SUPABASE_URL and SUPABASE_KEY to Streamlit Secrets.")
    st.stop()

# --- GLOBAL SETTINGS ---
st.sidebar.header("Settings")
fine_rate = st.sidebar.number_input("Fine per day", value=50.0, step=10.0)
currency = st.sidebar.text_input("Currency Symbol", value="PKR")
today = datetime.now().date()

# --- UPLOAD & TRIGGER SECTION ---
st.subheader("⚙️ Control Panel")
col1, col2 = st.columns(2)

with col1:
    st.write("**1. Upload Data to Database**")
    uploaded_file = st.file_uploader("Upload Excel/CSV to save in Supabase", type=["csv", "xlsx"])
    if st.button("Upload to Supabase"):
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file)
                else:
                    df = pd.read_csv(uploaded_file)
                
                # Clean up dates
                df['due_date'] = pd.to_datetime(df['due_date']).dt.strftime('%Y-%m-%d')
                df['returned'] = False
                
                records = df.to_dict(orient='records')
                supabase.table('library_loans').insert(records).execute()
                st.success(f"Successfully uploaded {len(records)} records to Supabase!")
                st.rerun() # Refresh the table below
            except Exception as e:
                st.error(f"Error uploading: {e}")
        else:
            st.warning("Please upload a file first.")

with col2:
    st.write("**2. Trigger Automation**")
    st.write("Click below to tell GitHub to send the emails right now.")
    if st.button("🚀 Force Run Agent Now", type="primary"):
        gh_pat = st.secrets.get("GH_PAT", "")
        GH_USERNAME = "TERMINATOR1981" 
        GH_REPO = "Overdue-Owl"
        
        if not gh_pat:
            st.error("Missing GH_PAT in Streamlit Secrets.")
        else:
            url = f"https://api.github.com/repos/{GH_USERNAME}/{GH_REPO}/actions/workflows/daily_agent.yml/dispatches"
            headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {gh_pat}"}
            response = requests.post(url, headers=headers, json={"ref": "main"})
            if response.status_code == 204:
                st.success("Agent triggered! Emails are being sent in the background.")
            else:
                st.error(f"Failed to trigger: {response.text}")

st.divider()

# --- LIVE PREVIEW DASHBOARD ---
st.subheader("📊 Live Overdue Preview (From Supabase)")
try:
    response = supabase.table('library_loans').select("*").eq('returned', False).execute()
    data = response.data
    
    if data:
        df = pd.DataFrame(data)
        
        # Calculate fines for the preview
        calculated_data = []
        total_fine = 0.0
        
        for index, row in df.iterrows():
            try:
                due = datetime.strptime(str(row['due_date']).split('T')[0], "%Y-%m-%d").date()
                days_overdue = (today - due).days
                if days_overdue > 0:
                    fine = days_overdue * fine_rate
                    total_fine += fine
                    calculated_data.append({
                        "Name": row['name'],
                        "Book": row['book_title'],
                        "Due Date": row['due_date'],
                        "Days Overdue": days_overdue,
                        "Fine": f"{currency} {fine:.2f}"
                    })
            except Exception:
                continue
        
        if calculated_data:
            preview_df = pd.DataFrame(calculated_data)
            st.dataframe(preview_df, use_container_width=True)
            st.markdown(f"### **Total Fine to be Collected: {currency} {total_fine:.2f}**")
        else:
            st.info("No overdue books right now (or all books are returned!).")
            
        # Show raw database in an expander
        with st.expander("View Raw Database (All Unreturned Books)"):
            st.dataframe(df, use_container_width=True)
            
    else:
        st.info("The database is currently empty.")
except Exception as e:
    st.error(f"Could not fetch database: {e}")
