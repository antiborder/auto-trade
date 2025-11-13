"""
LSTMモデルを使用するエージェント
"""
import json
import os
from datetime import datetime
from typing import Optional
import numpy as np
from shared.agents.base_agent import BaseAgent
from shared.models.trading import Action, PriceData, TradingDecision


class LSTMAgent(BaseAgent):
    """LSTMモデルベースのエージェント"""
    
    def __init__(self, agent_id: str, trader_id: str = None, model_path: Optional[str] = None):
        super().__init__(agent_id, trader_id)
        self.model_path = model_path
        self.model = None
        self.sequence_length = 60  # LSTMの入力シーケンス長
        self._load_model()
    
    def _load_model(self):
        """モデルをロード（Lambda環境ではS3から読み込む）"""
        # 実際の実装では、S3からモデルをダウンロードしてロード
        # ここではプレースホルダー
        if self.model_path and os.path.exists(self.model_path):
            try:
                # TensorFlow/Kerasモデルのロード
                # from tensorflow import keras
                # self.model = keras.models.load_model(self.model_path)
                pass
            except Exception as e:
                print(f"Failed to load model: {e}")
    
    def _prepare_features(self, historical_data: list[PriceData]) -> Optional[np.ndarray]:
        """特徴量を準備"""
        if len(historical_data) < self.sequence_length:
            return None
        
        # 価格データを正規化
        prices = [d.price for d in historical_data[-self.sequence_length:]]
        prices_array = np.array(prices)
        
        # 正規化（簡易版）
        mean = prices_array.mean()
        std = prices_array.std()
        if std == 0:
            return None
        
        normalized = (prices_array - mean) / std
        return normalized.reshape(1, self.sequence_length, 1)
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """LSTMモデルを使用した判断"""
        if self.model is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Model not loaded"
            )
        
        features = self._prepare_features(historical_data)
        if features is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Insufficient data for LSTM"
            )
        
        try:
            # モデル予測
            prediction = self.model.predict(features, verbose=0)[0][0]
            
            # 予測値に基づいて判断
            # 予測値は将来の価格変化率と仮定
            if prediction > 0.02:  # 2%以上の上昇予測
                action = Action.BUY
                confidence = min(0.95, 0.5 + abs(prediction) * 10)
                reason = f"LSTM predicts {prediction*100:.2f}% price increase"
            elif prediction < -0.02:  # 2%以上の下落予測
                action = Action.SELL
                confidence = min(0.95, 0.5 + abs(prediction) * 10)
                reason = f"LSTM predicts {prediction*100:.2f}% price decrease"
            else:
                action = Action.HOLD
                confidence = 0.5
                reason = f"LSTM predicts minimal change ({prediction*100:.2f}%)"
            
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=action,
                confidence=confidence,
                price=price_data.price,
                reason=reason,
                model_prediction=prediction
            )
        except Exception as e:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason=f"Model prediction error: {str(e)}"
            )
    
    def get_agent_type(self) -> str:
        return "LSTM"


