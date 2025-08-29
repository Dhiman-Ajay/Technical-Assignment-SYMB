# Weather Report Service

This project provides a simple web service to fetch, store, and export weather data for a given location using the Open-Meteo API.

## How to Run Locally

### Option 1: Using Python

1. Make sure you have Python 3 installed.
2. Install required packages:
   ```bash
   pip install flask requests pandas matplotlib fpdf openpyxl
   ```
3. Start the server:
   ```bash
   python app.py
   ```
4. The service will run at `http://localhost:5000`.

## Endpoints

- `/weather-report?lat=<latitude>&lon=<longitude>`: Fetches and stores weather data for the given location.
- `/export/excel?lat=<latitude>&lon=<longitude>`: Downloads weather data as an Excel file.
- `/export/pdf?lat=<latitude>&lon=<longitude>`: Downloads a PDF weather report with a chart.

## Example Output Files

- `weather_data_lat47.37_lon8.55.xlsx`: Excel file containing weather data.
- `weather_report_lat47.37_lon8.55.pdf`: PDF report with weather chart and summary.

---
