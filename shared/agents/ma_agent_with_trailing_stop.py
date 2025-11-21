"""
損失確定機能とトレーリングストップロス（利益確定）機能付き移動平均エージェント
"""
from datetime import datetime
from typing import Optional
from shared.agents.ma_agent_with_stoploss import MaAgentWithStopLoss
from shared.models.trading import Action, PriceData, TradingDecision


class MaAgentWithTrailingStop(MaAgentWithStopLoss):
    """
    損失確定機能（パーセンテージベース）とトレーリングストップロス（利益確定）機能付きエージェント
    
    - 損失確定: エントリー価格から一定パーセンテージ下がったら損失確定
    - トレーリングストップロス: 最高値から一定パーセンテージ下がったら利益確定
    """
    
    def __init__(
        self,
        agent_id: str,
        trader_id: str = None,
        short_window: int = 5,
        long_window: int = 20,
        stop_loss_percentage: float = 0.07,  # デフォルト -7%
        trailing_stop_percentage: float = 0.05  # デフォルト -5%（最高値から）
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            short_window: 短期移動平均のウィンドウサイズ
            long_window: 長期移動平均のウィンドウサイズ
            stop_loss_percentage: 損失確定パーセンテージ（0.07 = 7%）
            trailing_stop_percentage: トレーリングストップロスパーセンテージ（0.05 = 5%）
        """
        super().__init__(agent_id, trader_id, short_window, long_window, stop_loss_percentage)
        self.trailing_stop_percentage = trailing_stop_percentage
        
        # トレーリングストップロス用の最高価格追跡
        self.highest_price: Optional[float] = None
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（損失確定とトレーリングストップロス機能付き）
        
        Args:
            price_data: 現在の価格データ
            historical_data: 過去の価格データ
        
        Returns:
            TradingDecision: 取引判断
        """
        current_price = price_data.price
        
        # ポジションを持っている場合のチェック
        if self.entry_price is not None and self.position_btc > 0:
            # 最高価格を更新
            if self.highest_price is None:
                self.highest_price = current_price
            else:
                self.highest_price = max(self.highest_price, current_price)
            
            # 1. 損失確定チェック（最優先）
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            
            if loss_percentage <= -self.stop_loss_percentage:
                # 損失確定トリガー
                entry = self.entry_price
                self.entry_price = None
                self.highest_price = None  # リセット
                return TradingDecision(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    action=Action.SELL,
                    confidence=1.0,
                    price=current_price,
                    reason=f"Stop Loss triggered: {loss_percentage*100:.2f}% loss (entry: ${entry:.2f}, current: ${current_price:.2f})"
                )
            
            # 2. トレーリングストップロスチェック（利益確定）
            if self.highest_price is not None:
                decline_from_high = (current_price - self.highest_price) / self.highest_price
                
                if decline_from_high <= -self.trailing_stop_percentage:
                    # トレーリングストップロストリガー（利益確定）
                    entry = self.entry_price
                    highest = self.highest_price
                    profit_percentage = (current_price - entry) / entry
                    self.entry_price = None
                    self.highest_price = None  # リセット
                    return TradingDecision(
                        agent_id=self.agent_id,
                        timestamp=datetime.utcnow(),
                        action=Action.SELL,
                        confidence=1.0,
                        price=current_price,
                        reason=f"Trailing Stop triggered: {decline_from_high*100:.2f}% decline from high ${highest:.2f} (entry: ${entry:.2f}, current: ${current_price:.2f}, profit: {profit_percentage*100:.2f}%)"
                    )
        
        # 通常の移動平均クロスオーバー戦略
        decision = super().decide(price_data, historical_data)
        
        # 買い注文の場合は最高価格を初期化
        if decision.action == Action.BUY:
            self.highest_price = current_price  # 買い時に最高価格を初期化
        # 売り注文の場合は最高価格をリセット
        elif decision.action == Action.SELL:
            self.highest_price = None
        
        return decision
    
    def update_position(self, entry_price: Optional[float], btc_holdings: float, current_price: Optional[float] = None):
        """
        ポジション情報を更新
        
        Args:
            entry_price: エントリー価格（Noneの場合はポジションなし）
            btc_holdings: 現在のBTC保有量
            current_price: 現在の価格（トレーリングストップロス用、オプション）
        """
        super().update_position(entry_price, btc_holdings)
        
        # ポジションがない場合は最高価格をリセット
        if entry_price is None or btc_holdings <= 0:
            self.highest_price = None
        elif current_price is not None:
            # 現在価格で最高価格を更新
            if self.highest_price is None:
                self.highest_price = current_price
            else:
                self.highest_price = max(self.highest_price, current_price)
    
    def check_trailing_stop(self, current_price: float) -> Optional[TradingDecision]:
        """
        トレーリングストップロス条件をチェック（外部から呼び出す用）
        
        Args:
            current_price: 現在の価格
        
        Returns:
            トレーリングストップロスがトリガーされた場合はTradingDecision、そうでなければNone
        """
        if self.entry_price is not None and self.position_btc > 0 and self.highest_price is not None:
            # 最高価格を更新
            self.highest_price = max(self.highest_price, current_price)
            
            decline_from_high = (current_price - self.highest_price) / self.highest_price
            
            if decline_from_high <= -self.trailing_stop_percentage:
                entry = self.entry_price
                highest = self.highest_price
                profit_percentage = (current_price - entry) / entry
                self.entry_price = None
                self.highest_price = None
                return TradingDecision(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    action=Action.SELL,
                    confidence=1.0,
                    price=current_price,
                    reason=f"Trailing Stop triggered: {decline_from_high*100:.2f}% decline from high ${highest:.2f} (entry: ${entry:.2f}, current: ${current_price:.2f}, profit: {profit_percentage*100:.2f}%)"
                )
        return None
    
    def get_agent_type(self) -> str:
        return "MA_TrailingStop"

