from xml.parsers.expat import model
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO
import re
#from google import genai
from sklearn.ensemble import RandomForestRegressor,RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score


# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="AI Data Analysis Tool",
    page_icon="📊",
    layout="wide"
)

st.title("🤖 AI-Powered Data Analysis Tool")
st.markdown("---")

# ================= SESSION STATE =================
if "cleaned_data" not in st.session_state:
    st.session_state.cleaned_data = None
if "original_data" not in st.session_state:
    st.session_state.original_data = None
if "cleaning_report" not in st.session_state:
    st.session_state.cleaning_report = {}
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ================= DATA QUALITY =================
def calculate_data_quality(df):
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = df.isnull().sum().sum()
    duplicate_rows = df.duplicated().sum()

    completeness = 100 - (missing_cells / total_cells * 100)
    uniqueness = 100 - (duplicate_rows / len(df) * 100)

    score = (completeness * 0.6) + (uniqueness * 0.4)
    return round(score, 2), missing_cells, duplicate_rows

# ================= OUTLIER DETECTION =================
def detect_outliers(df):
    outliers = {}
    for col in df.select_dtypes(include=["int64", "float64"]).columns:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        count = ((df[col] < Q1 - 1.5 * IQR) | (df[col] > Q3 + 1.5 * IQR)).sum()
        if count > 0:
            outliers[col] = int(count)
    return outliers

# ================= AUTO CLEAN (YOUR LOGIC KEPT) =================
def auto_clean_data(df):
    cleaned_df = df.copy()
    
    report = {
        "rows_before": len(cleaned_df),
        "missing": {},
        "duplicates_removed": 0
    }

    # 🔥 1. Fill numeric missing values (use median - more robust than mean)
    num_cols = cleaned_df.select_dtypes(include="number").columns

    for col in num_cols:
        if cleaned_df[col].isnull().sum() > 0:

        # Check skewness
            skew_value = cleaned_df[col].skew()

            if abs(skew_value) > 1:
            # Highly skewed → use median
                cleaned_df[col].fillna(cleaned_df[col].median(), inplace=True)
                report["missing"][col] = "Filled with median"
            else:
            # Normal distribution → use mean
                cleaned_df[col].fillna(cleaned_df[col].mean(), inplace=True)
                report["missing"][col] = "Filled with mean"

    # 🔥 2. Fill categorical missing values
    cat_cols = cleaned_df.select_dtypes(include="object").columns
    if len(cat_cols) > 0:
        cleaned_df[cat_cols] = cleaned_df[cat_cols].fillna("Unknown")
        for col in cat_cols:
            if df[col].isnull().sum() > 0:
                report["missing"][col] = "Filled with 'Unknown'"

    # 🔥 3. Remove duplicates (ONLY ONCE, not inside loop)
    rows_before_drop = len(cleaned_df)
    cleaned_df = cleaned_df.drop_duplicates()
    report["duplicates_removed"] = rows_before_drop - len(cleaned_df)

    report["rows_after"] = len(cleaned_df)

    return cleaned_df, report

# ================= AI PANDAS AGENT =================
def ask_ai_for_code(question, df):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    prompt = f"""
    You are a Python data analyst.
    Dataframe name: df
    Columns: {', '.join(df.columns)}

    User question:
    {question}

    Return ONLY valid pandas code.
    Store final answer in variable named result.
    Do not add explanation.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",  # Latest stable free model
        contents=prompt,
    )

    return response.text
def execute_code(code, df):
    local_vars = {"df": df.copy()}
    exec(code, {}, local_vars)
    return local_vars.get("result", "No result")

# ================= SIDEBAR =================
with st.sidebar:
    st.header("📁 Upload Data")
    file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    


# ================= MAIN =================
if file:
    df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
    st.session_state.original_data = df

    tab1, tab2, tab3, tab5= st.tabs([
        "📊 Overview", "🧹 Cleaning", "📈 Visualization",  "🤖 ML"
    ])

    # ---------- TAB 1 ----------
    with tab1:
        score, miss, dup = calculate_data_quality(df)
        st.metric("📊 Data Quality Score", f"{score}/100")
        st.write(f"Missing Cells: {miss}")
        st.write(f"Duplicate Rows: {dup}")
        st.dataframe(df.head())

        st.header("Outlier info")
        outliers = detect_outliers(df)
        if outliers:
            st.warning("⚠️ Outliers detected")
            st.write(
                pd.DataFrame({
                    "Column":list(outliers.keys()),
                    "outlier count":list(outliers.values())
                })
            )
        else:
            st.write("There is no outliers detected")    
        st.subheader("📉 Column-wise Data Report")
        column_report = pd.DataFrame({
        "Column Name": df.columns,
        "Data Type": df.dtypes.values,
        "Total Values": df.count().values,
        "Missing Values": df.isnull().sum().values,
        "Missing %":((df.isnull().sum().values / len(df)) * 100).round(2)
        })

        column_report = column_report.sort_values(by="Missing Values", ascending=False)

        st.dataframe(column_report)    

    # ---------- TAB 2 ----------
    with tab2:
        if st.button("🚀 Clean Data"):
            cleaned, report = auto_clean_data(df)
            st.session_state.cleaned_data = cleaned
            st.session_state.cleaning_report = report
            st.success("Cleaned Successfully")

        if st.session_state.cleaned_data is not None:
            st.dataframe(st.session_state.cleaning_report)

    # Function to convert dataframe to Excel
            def convert_to_excel(data):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    data.to_excel(writer, index=False, sheet_name='Cleaned Data')
                processed_data = output.getvalue()
                return processed_data

            excel_file = convert_to_excel(st.session_state.cleaned_data)

    # Download button
            st.download_button(
                label="📥 Download Cleaned Data (Excel)",
                data=excel_file,
                file_name="cleaned_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ---------- TAB 3 ----------
    

    with tab3:
        if st.session_state.cleaned_data is not None:
            cdf = st.session_state.cleaned_data
            numeric_cols = cdf.select_dtypes(include="number").columns.tolist()
            categorical_cols = cdf.select_dtypes(include="object").columns.tolist()

            x_col = st.selectbox("X", cdf.columns)
            y_col = st.selectbox("Y", [c for c in cdf.columns if c != x_col])

            # Auto suggestion logic
            if x_col in categorical_cols and y_col in numeric_cols:
                suggested_chart = "Bar Chart"
            elif "date" in x_col.lower():
                suggested_chart = "Line Chart"
            elif x_col in numeric_cols and y_col in numeric_cols:
                suggested_chart = "Scatter Plot"
            else:
                suggested_chart = "Histogram"

# Initialize session state only once
            if "chart_type" not in st.session_state:
                 st.session_state.chart_type = suggested_chart

            chart_type = st.selectbox(
                "Chart Type (Auto-suggested)",
                ["Bar Chart", "Line Chart", "Histogram", "Scatter Plot"],
                key="chart_type"  # This prevents reset
                )

            st.info(f"💡 Suggested chart: *{suggested_chart}*")
            fig = None
            if chart_type == "Bar Chart":
                fig = px.bar(cdf, x=x_col, y=y_col)

            elif chart_type == "Line Chart":
                fig = px.line(cdf, x=x_col, y=y_col)

            elif chart_type == "Histogram":
                fig = px.histogram(cdf, x=y_col, nbins=30)

            elif chart_type == "Scatter Plot":
                fig = px.scatter(cdf, x=x_col, y=y_col)

            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

        
            if fig is not None:
        # Unique key to avoid StreamlitDuplicateElementId error
                chart_key = f"chart_{x_col}_{y_col}_{chart_type}"

    # Display chart
            #st.plotly_chart(fig, use_container_width=True, key=chart_key)

                st.subheader("📥 Download Chart")    
                try:
                    html_bytes = fig.to_html().encode("utf-8")

                    st.download_button(
                    label="Download Chart as Interactive HTML",
                    data=html_bytes,
                    file_name=f"{chart_key}.html",
                    mime="text/html",
                    key=f"download_html_{chart_key}"
                    )
                except Exception as e:
                    st.warning("⚠️ Install kaleido to enable PNG download: pip install kaleido")
            else:
                st.write("The dataset is uncleaned")


        

    # ---------- TAB 4 ----------
   
    # ---------- TAB 5 ----------
    with tab5:
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=["number"]).columns.tolist()
        all_cols = df.columns.tolist()


        st.write("🧮 Numeric Columns:", numeric_cols)
        st.write("🔤 Categorical Columns:", categorical_cols)

# Let user select only numeric columns as target
        target = st.selectbox("🎯 Select Target Column ",all_cols)

# -----------------------
# Train Button
# -----------------------
        if st.button("Train Model"):
            X = df.drop(columns=[target])
            y = df[target]

    # Remove rows where target is NaN
            valid_idx = y.notna()
            X = X[valid_idx]
            y = y[valid_idx]

     # 🔥 Encode categorical columns (instead of dropping them)
            X = pd.get_dummies(X, drop_first=True)


    # Split the data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

    # Train model
            if y.dtype == "object":
                st.info("The detected problem is a classification problem")
                model = RandomForestClassifier(
                n_estimators=100,
                random_state=42
                )
            else:
                st.info("The detected problem is a Regression problem")
                model = RandomForestRegressor(
                n_estimators=100,
                random_state=42
                )    
            model.fit(X_train, y_train)

    # R² Score
            r2 = model.score(X_test, y_test)
            st.success(f"✅ Model Trained Successfully! R² Score: {r2:.4f}")

    # 🔥 IMPORTANT FIX: Use same filtered rows for prediction
            df_clean = df[valid_idx].copy()
            df_clean["Predicted_Value"] = model.predict(X)

            st.subheader("📊 Dataset with Predictions")
            st.dataframe(df_clean)
            st.subheader("Actual vs Predicted")
            chart_df = pd.DataFrame({
                "Actual": y,
                "Predicted": model.predict(X)
            })
            st.line_chart(chart_df)
else:
    st.info("👈 Upload a file to begin")