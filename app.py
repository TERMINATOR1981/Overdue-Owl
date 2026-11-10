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

# --- TOP CONTROL PANEL ---
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
                
                # Clean up dates and format for Supabase
                df['due_date'] = pd.to_datetime(df['due_date']).dt.strftime('%Y-%m-%d')
                df['returned'] = False # Default all new uploads to unreturned
                
                # Convert to list of dictionaries
                records = df.to_dict(orient='records')
                
                # Push to Supabase
                supabase.table('library_loans').insert(records).execute()
                st.success(f"Successfully uploaded {len(records)} records to Supabase!")
            except Exception as e:
                st.error(f"Error uploading: {e}")
        else:
            st.warning("Please upload a file first.")

with col2:
    st.write("**2. Trigger Automation**")
    st.write("Click below to tell GitHub to send the emails right now.")
    if st.button("🚀 Force Run Agent Now", type="primary"):
        gh_pat = st.secrets.get("GH_PAT", "")
        if not gh_pat:
            st.error("Missing GH_PAT in Streamlit Secrets.")
        else:
            # Replace with your actual GitHub Username and Repo Name
            GH_USERNAME = "TERMINATOR1981" 
            GH_REPO = "Overdue-Owl"
            
            url = f"https://api.github.com/repos/{GH_USERNAME}/{GH_REPO}/actions/workflows/daily_agent.yml/dispatches"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {gh_pat}"
            }
            data = {"ref": "main"}
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 204:
                st.success("Agent triggered! Emails are being sent in the background.")
            else:
                st.error(f"Failed to trigger: {response.text}")

st.divider()

# --- DASHBOARD VIEW ---
st.subheader("📊 Current Overdue Books (Live from Supabase)")
try:
    response = supabase.table('library_loans').select("*").eq('returned', False).execute()
    data = response.data
    
    if data:
        df = pd.DataFrame(data)
        # Drop the ID and created_at columns for a cleaner look
        if 'id' in df.columns: df = df.drop(columns=['id'])
        if 'created_at' in df.columns: df = df.drop(columns=['created_at'])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No unreturned books in the database right now.")
except Exception as e:
    st.error(f"Could not fetch database: {e}")
