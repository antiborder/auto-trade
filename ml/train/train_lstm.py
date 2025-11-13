"""
LSTMモデルの学習スクリプト
ローカルPCで実行し、学習済みモデルを保存
"""
import numpy as np
import pandas as pd
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
import os
import json
from datetime import datetime


def load_price_data(csv_path: str) -> pd.DataFrame:
    """価格データをCSVから読み込み"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    return df


def prepare_sequences(data: np.ndarray, sequence_length: int = 60) -> tuple:
    """
    時系列データをシーケンスに変換
    
    Args:
        data: 価格データの配列
        sequence_length: シーケンス長
        
    Returns:
        X: 入力シーケンス
        y: ターゲット（次の価格変化率）
    """
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data.reshape(-1, 1))
    
    X, y = [], []
    for i in range(len(data_scaled) - sequence_length):
        X.append(data_scaled[i:i+sequence_length])
        # 次の価格変化率を予測
        price_change = (data_scaled[i+sequence_length] - data_scaled[i+sequence_length-1]) / data_scaled[i+sequence_length-1]
        y.append(price_change[0])
    
    return np.array(X), np.array(y), scaler


def build_lstm_model(sequence_length: int, features: int = 1) -> Sequential:
    """LSTMモデルを構築"""
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(sequence_length, features)),
        Dropout(0.2),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50),
        Dropout(0.2),
        Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model


def train_model(csv_path: str, model_output_path: str, epochs: int = 50, batch_size: int = 32):
    """
    モデルを学習
    
    Args:
        csv_path: 価格データのCSVパス
        model_output_path: モデル保存先
        epochs: エポック数
        batch_size: バッチサイズ
    """
    print("Loading price data...")
    df = load_price_data(csv_path)
    
    # 価格データを取得
    prices = df['price'].values
    
    print("Preparing sequences...")
    X, y, scaler = prepare_sequences(prices, sequence_length=60)
    
    # 訓練/検証データ分割
    split = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    
    print(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")
    
    # モデル構築
    print("Building model...")
    model = build_lstm_model(sequence_length=60)
    
    # 学習
    print("Training model...")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        verbose=1
    )
    
    # モデル保存
    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    model.save(model_output_path)
    
    # スケーラー情報も保存
    scaler_path = model_output_path.replace('.h5', '_scaler.json')
    scaler_info = {
        'min': float(scaler.data_min_[0]),
        'max': float(scaler.data_max_[0])
    }
    with open(scaler_path, 'w') as f:
        json.dump(scaler_info, f)
    
    print(f"Model saved to {model_output_path}")
    print(f"Scaler info saved to {scaler_path}")
    
    return model, history


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Train LSTM model for Bitcoin price prediction')
    parser.add_argument('--data', type=str, required=True, help='Path to price data CSV')
    parser.add_argument('--output', type=str, default='../models/lstm_model.h5', help='Output model path')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    
    args = parser.parse_args()
    
    train_model(
        csv_path=args.data,
        model_output_path=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size
    )


