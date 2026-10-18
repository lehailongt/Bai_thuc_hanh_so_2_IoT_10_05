import pandas as pd 
import numpy as np
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.domain.write_precision import WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from sklearn.preprocessing import StandardScaler

from config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG,
    INFLUX_BUCKET_RAW, INFLUX_BUCKET_PROCESSED
)

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)


def load_raw_data(minutes=30) -> pd.DataFrame:
    query = f'''
    from(bucket: "{INFLUX_BUCKET_RAW}")
      |> range(start: -{minutes}m)
      |> filter(fn: (r) => r["_measurement"] == "sensor_data")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    try:
        df = query_api.query_data_frame(query)
    except Exception as e:
        print(f"Lỗi kết nối InfluxDB: {e}")
        return pd.DataFrame()

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return pd.DataFrame()

    if isinstance(df, list):
        df = pd.concat(df)

    # Chỉ giữ lại các cột số liệu và cột thời gian, BỎ các cột string (tag, result, table...)
    numeric_cols = ['temperature', 'humidity', 'distance_cm', 'rssi', 'sequence']
    keep_cols = ['_time'] + [c for c in numeric_cols if c in df.columns]
    
    df = df[keep_cols]
    df['_time'] = pd.to_datetime(df['_time'])
    df = df.set_index('_time')
    
    return df.sort_index()


def remove_outliers_iqr(df, col):
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lo, hi = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    df.loc[(df[col] < lo) | (df[col] > hi), col] = np.nan
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Missing values
    df = df.interpolate(method='linear').ffill().bfill()

    # 2. Outliers
    for col in ['temperature', 'humidity', 'distance_cm']:
        if col in df.columns:
            df = remove_outliers_iqr(df, col)
    df = df.interpolate(method='linear').ffill().bfill()

    # 3. Resampling 10s (Sửa lỗi '10S' thành '10s')
    if not df.empty:
        df = df.resample('10s').mean()

    # 4. Feature engineering
    if 'temperature' in df.columns and not df.empty:
        df['temp_rolling_mean'] = df['temperature'].rolling(window=3, min_periods=1).mean()
        df['temp_delta']        = df['temperature'].diff().fillna(0)

    # 5. Normalize
    cols = [c for c in ['temperature', 'humidity', 'distance_cm'] if c in df.columns]
    if cols and not df.empty:
        scaler = StandardScaler()
        scaled = scaler.fit_transform(df[cols])
        for i, c in enumerate(cols):
            df[f'{c}_scaled'] = scaled[:, i]

    return df


def write_processed(df: pd.DataFrame):
    if df.empty:
        print("[!] Không có dữ liệu sau khi xử lý để ghi.")
        return

    count = 0
    for ts, row in df.iterrows():
        p = Point("sensor_data_processed").tag("device", "esp32-lab2")
        
        # Ghi các trường cơ bản (chỉ ghi nếu dữ liệu không bị NaN)
        if 'temperature' in row and pd.notna(row['temperature']): 
            p.field("temperature", float(row['temperature']))
        if 'humidity' in row and pd.notna(row['humidity']): 
            p.field("humidity", float(row['humidity']))
        if 'distance_cm' in row and pd.notna(row['distance_cm']): 
            p.field("distance_cm", float(row['distance_cm']))
        
        # Ghi các trường đặc trưng
        if 'temp_rolling_mean' in row and pd.notna(row['temp_rolling_mean']): 
            p.field("temp_rolling_mean", float(row['temp_rolling_mean']))
        if 'temp_delta' in row and pd.notna(row['temp_delta']): 
            p.field("temp_delta", float(row['temp_delta']))
        
        # Ghi các trường đã chuẩn hóa
        if 'temperature_scaled' in row and pd.notna(row['temperature_scaled']): 
            p.field("temperature_scaled", float(row['temperature_scaled']))
        if 'humidity_scaled' in row and pd.notna(row['humidity_scaled']): 
            p.field("humidity_scaled", float(row['humidity_scaled']))
        if 'distance_cm_scaled' in row and pd.notna(row['distance_cm_scaled']): 
            p.field("distance_cm_scaled", float(row['distance_cm_scaled']))
        
        # Nếu point có chứa ít nhất 1 field thì mới ghi
        if p._fields:
            p.time(ts, WritePrecision.NS)
            write_api.write(bucket=INFLUX_BUCKET_PROCESSED, org=INFLUX_ORG, record=p)
            count += 1
            
    print(f"[OK] Wrote {count} processed points")


if __name__ == "__main__":
    print("[1] Loading raw data...")
    df = load_raw_data(minutes=30)
    if df.empty:
        print("[!] No data found. Hãy chạy collector + ESP32 trước.")
        raise SystemExit

    print(f"[2] Loaded {len(df)} raw points")
    df_clean = preprocess(df)
    print(f"[3] After preprocess: {len(df_clean)} points")

    write_processed(df_clean)
    print("[DONE]")