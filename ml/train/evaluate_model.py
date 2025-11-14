"""
学習済みLSTMモデルの評価スクリプト
学習結果を可視化し、モデルの性能を評価
"""
import numpy as np
import pandas as pd
import json
import os
import sys
from tensorflow import keras
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt


def load_model_and_scaler(model_path: str):
    """モデルとスケーラーを読み込み"""
    # Keras 3.x互換性のため、compile=Falseで読み込み
    try:
        model = keras.models.load_model(model_path, compile=False)
        # モデルを再コンパイル（評価用）
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    except Exception as e:
        print(f"Warning: Could not load with compile=False, trying default: {e}")
        model = keras.models.load_model(model_path)
    
    scaler_path = model_path.replace('.h5', '_scaler.json')
    with open(scaler_path, 'r') as f:
        scaler_info = json.load(f)
    
    scaler = MinMaxScaler()
    scaler.data_min_ = np.array([scaler_info['min']])
    scaler.data_max_ = np.array([scaler_info['max']])
    
    return model, scaler


def prepare_sequences(data: np.ndarray, sequence_length: int = 60) -> tuple:
    """時系列データをシーケンスに変換"""
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data.reshape(-1, 1))
    
    X, y = [], []
    for i in range(len(data_scaled) - sequence_length):
        X.append(data_scaled[i:i+sequence_length])
        # ゼロ除算を避ける
        prev_value = data_scaled[i+sequence_length-1][0]
        if abs(prev_value) < 1e-10:
            price_change = 0.0
        else:
            price_change = (data_scaled[i+sequence_length][0] - prev_value) / prev_value
        y.append(price_change)
    
    return np.array(X), np.array(y), scaler


def evaluate_model(model_path: str, csv_path: str, output_dir: str = None):
    """
    モデルを評価
    
    Args:
        model_path: モデルファイルのパス
        csv_path: テストデータのCSVパス
        output_dir: 結果を保存するディレクトリ
    """
    print("=" * 60)
    print("LSTM Model Evaluation")
    print("=" * 60)
    
    # モデルとスケーラーを読み込み
    print("\n1. Loading model and scaler...")
    model, scaler = load_model_and_scaler(model_path)
    print(f"   ✓ Model loaded: {model_path}")
    print(f"   ✓ Model summary:")
    model.summary()
    
    # データを読み込み
    print("\n2. Loading test data...")
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    prices = df['price'].values
    print(f"   ✓ Data loaded: {len(prices)} records")
    print(f"   ✓ Price range: ${prices.min():,.2f} - ${prices.max():,.2f}")
    
    # シーケンスを準備
    print("\n3. Preparing sequences...")
    X, y, data_scaler = prepare_sequences(prices, sequence_length=60)
    print(f"   ✓ Sequences prepared: {len(X)} samples")
    
    # データ分割（学習時と同じ分割）
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    print(f"   ✓ Training samples: {len(X_train)}")
    print(f"   ✓ Test samples: {len(X_test)}")
    
    # 予測
    print("\n4. Making predictions...")
    y_train_pred = model.predict(X_train, verbose=0)
    y_test_pred = model.predict(X_test, verbose=0)
    
    # NaNチェック
    if np.any(np.isnan(y_train_pred)) or np.any(np.isnan(y_test_pred)):
        print("   ⚠ Warning: NaN values detected in predictions!")
        print(f"   Train NaN count: {np.sum(np.isnan(y_train_pred))}")
        print(f"   Test NaN count: {np.sum(np.isnan(y_test_pred))}")
        # NaNを0で置換（暫定対応）
        y_train_pred = np.nan_to_num(y_train_pred, nan=0.0)
        y_test_pred = np.nan_to_num(y_test_pred, nan=0.0)
    
    # 評価指標を計算
    print("\n5. Calculating metrics...")
    
    def calculate_metrics(y_true, y_pred, name):
        mse = np.mean((y_true - y_pred.flatten()) ** 2)
        mae = np.mean(np.abs(y_true - y_pred.flatten()))
        rmse = np.sqrt(mse)
        
        # 方向性の精度（上昇/下降を正しく予測できたか）
        direction_true = np.sign(y_true)
        direction_pred = np.sign(y_pred.flatten())
        direction_accuracy = np.mean(direction_true == direction_pred) * 100
        
        print(f"\n   {name} Metrics:")
        print(f"   - MSE:  {mse:.6f}")
        print(f"   - MAE:  {mae:.6f}")
        print(f"   - RMSE: {rmse:.6f}")
        print(f"   - Direction Accuracy: {direction_accuracy:.2f}%")
        
        return {
            'mse': mse,
            'mae': mae,
            'rmse': rmse,
            'direction_accuracy': direction_accuracy
        }
    
    train_metrics = calculate_metrics(y_train, y_train_pred, "Training")
    test_metrics = calculate_metrics(y_test, y_test_pred, "Test")
    
    # 過学習チェック
    print("\n6. Overfitting check...")
    train_mae = train_metrics['mae']
    test_mae = test_metrics['mae']
    overfitting_ratio = test_mae / train_mae if train_mae > 0 else float('inf')
    
    print(f"   - Train MAE: {train_mae:.6f}")
    print(f"   - Test MAE:  {test_mae:.6f}")
    print(f"   - Ratio (Test/Train): {overfitting_ratio:.2f}")
    
    if overfitting_ratio > 1.5:
        print("   ⚠ Warning: Possible overfitting detected!")
    elif overfitting_ratio < 1.2:
        print("   ✓ Good generalization!")
    else:
        print("   ✓ Acceptable generalization")
    
    # 可視化
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        print(f"\n7. Generating visualizations...")
        
        # 予測値と実際の値の比較（テストデータの最初の500サンプル）
        plot_samples = min(500, len(y_test))
        indices = np.arange(plot_samples)
        
        plt.figure(figsize=(15, 10))
        
        # サブプロット1: 予測値 vs 実際の値（テストデータ）
        plt.subplot(2, 2, 1)
        plt.plot(indices, y_test[:plot_samples], label='Actual', alpha=0.7)
        plt.plot(indices, y_test_pred[:plot_samples].flatten(), label='Predicted', alpha=0.7)
        plt.xlabel('Sample Index')
        plt.ylabel('Price Change Rate')
        plt.title('Test Set: Actual vs Predicted (First 500 samples)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # サブプロット2: 散布図（予測値 vs 実際の値）
        plt.subplot(2, 2, 2)
        plt.scatter(y_test, y_test_pred.flatten(), alpha=0.5, s=10)
        plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
        plt.xlabel('Actual Price Change Rate')
        plt.ylabel('Predicted Price Change Rate')
        plt.title('Test Set: Scatter Plot')
        plt.grid(True, alpha=0.3)
        
        # サブプロット3: 残差プロット
        plt.subplot(2, 2, 3)
        residuals = y_test - y_test_pred.flatten()
        plt.scatter(y_test_pred.flatten(), residuals, alpha=0.5, s=10)
        plt.axhline(y=0, color='r', linestyle='--')
        plt.xlabel('Predicted Price Change Rate')
        plt.ylabel('Residuals')
        plt.title('Residual Plot')
        plt.grid(True, alpha=0.3)
        
        # サブプロット4: 誤差の分布
        plt.subplot(2, 2, 4)
        # NaNや無限大を除外
        residuals_clean = residuals[np.isfinite(residuals)]
        if len(residuals_clean) > 0:
            plt.hist(residuals_clean, bins=50, alpha=0.7, edgecolor='black')
            plt.xlabel('Residuals')
            plt.ylabel('Frequency')
            plt.title('Residual Distribution')
            plt.grid(True, alpha=0.3)
        else:
            plt.text(0.5, 0.5, 'No valid residuals', ha='center', va='center', transform=plt.gca().transAxes)
            plt.title('Residual Distribution (No Data)')
        
        plt.tight_layout()
        plot_path = os.path.join(output_dir, 'model_evaluation.png')
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"   ✓ Visualization saved: {plot_path}")
        
        # メトリクスをJSONで保存
        metrics_path = os.path.join(output_dir, 'metrics.json')
        metrics = {
            'train': train_metrics,
            'test': test_metrics,
            'overfitting_ratio': float(overfitting_ratio)
        }
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"   ✓ Metrics saved: {metrics_path}")
    
    print("\n" + "=" * 60)
    print("Evaluation completed!")
    print("=" * 60)
    
    return {
        'train_metrics': train_metrics,
        'test_metrics': test_metrics,
        'overfitting_ratio': overfitting_ratio
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate trained LSTM model')
    parser.add_argument('--model', type=str, required=True, help='Path to trained model (.h5)')
    parser.add_argument('--data', type=str, required=True, help='Path to test data CSV')
    parser.add_argument('--output', type=str, default='../models/evaluation', help='Output directory for results')
    
    args = parser.parse_args()
    
    evaluate_model(
        model_path=args.model,
        csv_path=args.data,
        output_dir=args.output
    )

