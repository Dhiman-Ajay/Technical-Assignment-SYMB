import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, send_file, request, jsonify
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF
import io
import os
import sys


API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
DATABASE_NAME = 'weather.db'

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_data (
            timestamp TEXT PRIMARY KEY,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            latitude REAL,
            longitude REAL
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Table 'weather_data' created or already exists in {DATABASE_NAME}")

def insert_weather_data(data, latitude, longitude):
    conn = get_db_connection()
    cursor = conn.cursor()
    for i in range(len(data['time'])):
        timestamp, temperature, humidity = data['time'][i], data['temperature_2m'][i], data['relative_humidity_2m'][i]
        try:
            cursor.execute('INSERT OR REPLACE INTO weather_data VALUES (?, ?, ?, ?, ?)', (timestamp, temperature, humidity, latitude, longitude))
        except sqlite3.Error as e:
            print(f"Error inserting data for {timestamp}: {e}", file=sys.stderr)
    conn.commit()
    conn.close()

def get_weather_data_for_export(latitude, longitude, days_ago=2):
    conn = get_db_connection()
    cursor = conn.cursor()
    end_time_utc = datetime.utcnow()
    start_time_utc = end_time_utc - timedelta(days=days_ago)
    cursor.execute('''
        SELECT timestamp, temperature_2m, relative_humidity_2m FROM weather_data
        WHERE timestamp >= ? AND timestamp <= ? AND latitude = ? AND longitude = ?
        ORDER BY timestamp ASC
    ''', (start_time_utc.isoformat(timespec='minutes'), end_time_utc.isoformat(timespec='minutes'), latitude, longitude))
    data = cursor.fetchall()
    conn.close()
    return data

def fetch_open_meteo_data(latitude, longitude, days_ago=2):
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days_ago)
    params = {"latitude": latitude, "longitude": longitude, "hourly": "temperature_2m,relative_humidity_2m", "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "timezone": "UTC"}
    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status()
        return response.json().get('hourly', {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Open-Meteo API: {e}", file=sys.stderr)
        return None

# --- Flask Endpoints ---
@app.route('/')
def home():
    return "Welcome to the Weather Report Service! <br> Use /weather-report, /export/excel, or /export/pdf endpoints."

@app.route('/weather-report')
def weather_report():
    latitude = request.args.get('lat', type=float)
    longitude = request.args.get('lon', type=float)
    if latitude is None or longitude is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
    create_table()
    hourly_data = fetch_open_meteo_data(latitude, longitude, days_ago=2)
    if hourly_data:
        insert_weather_data(hourly_data, latitude, longitude)
        return jsonify({"message": f"Data for lat={latitude}, lon={longitude} stored.", "points": len(hourly_data.get('time', []))})
    return jsonify({"error": "Failed to fetch or store data."}), 500

@app.route('/export/excel')
def export_excel():
    latitude = request.args.get('lat', type=float)
    longitude = request.args.get('lon', type=float)
    if latitude is None or longitude is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400
    data = get_weather_data_for_export(latitude, longitude)
    if not data:
        return jsonify({"message": "No data available to generate Excel."}), 404
    df = pd.DataFrame(data, columns=['timestamp', 'temperature_2m', 'relative_humidity_2m'])
    excel_filename = f'weather_data_lat{latitude}_lon{longitude}.xlsx'
    excel_filepath = os.path.join(os.getcwd(), excel_filename)
    df.to_excel(excel_filepath, index=False, sheet_name='Weather Data', engine='openpyxl')
    print(f"Excel file saved to: {excel_filepath}")
    return send_file(excel_filepath, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', download_name=excel_filename, as_attachment=True)

@app.route('/export/pdf')
def export_pdf():
    latitude = request.args.get('lat', type=float)
    longitude = request.args.get('lon', type=float)

    if latitude is None or longitude is None:
        return jsonify({"error": "Please provide latitude and longitude parameters"}), 400

    data = get_weather_data_for_export(latitude, longitude)
    if not data:
        return jsonify({"message": "No data available to generate PDF."}), 404

    df = pd.DataFrame(data, columns=['timestamp', 'temperature_2m', 'relative_humidity_2m'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    fig, ax1 = plt.subplots(figsize=(10, 5))
    color = 'tab:red'
    ax1.set_xlabel('Time (UTC)')
    ax1.set_ylabel('Temperature (°C)', color=color)
    ax1.plot(df['timestamp'], df['temperature_2m'], color=color, label='Temperature')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.tick_params(axis='x', rotation=45)
    ax1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y-%m-%d %H:%M'))
    ax2 = ax1.twinx()
    color = 'tab:blue'
    ax2.set_ylabel('Humidity (%)', color=color)
    ax2.plot(df['timestamp'], df['relative_humidity_2m'], color=color, linestyle='--', label='Humidity')
    ax2.tick_params(axis='y', labelcolor=color)
    fig.tight_layout()
    plt.title(f'Weather Data for Lat: {latitude}, Lon: {longitude}')
    fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
    
    chart_img_buffer = io.BytesIO()
    plt.savefig(chart_img_buffer, format='png', bbox_inches='tight')
    chart_img_buffer.seek(0)
    plt.close(fig)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Weather Report', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Location: Latitude: {latitude}, Longitude: {longitude}", 0, 1, 'C')
    date_range = f"{df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')} UTC"
    pdf.cell(0, 8, f"Date Range: {date_range}", 0, 1, 'C')
    pdf.cell(0, 8, f"Report Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", 0, 1, 'C')
    pdf.ln(10)
    pdf.image(chart_img_buffer, x=10, y=None, w=190)

    pdf_filename = f'weather_report_lat{latitude}_lon{longitude}.pdf'
    pdf_filepath = os.path.join(os.getcwd(), pdf_filename)
    pdf.output(pdf_filepath)

    print(f"PDF report saved to: {pdf_filepath}")
    return send_file(
        pdf_filepath,
        mimetype='application/pdf',
        download_name=pdf_filename,
        as_attachment=True
    )

if __name__ == '__main__':
    create_table()
    print(f"Database '{DATABASE_NAME}' initialized.")
    app.run(debug=True, port=5000)