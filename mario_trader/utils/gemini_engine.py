"""
Gemini AI Integration Module for Trade Verification and Monitoring

This module uses Google's Gemini API to:
1. Verify trade setups before execution
2. Monitor ongoing trades for potential issues
3. Provide AI-assisted analysis of market conditions
"""
import os
import json
import requests
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
from mario_trader.utils.logger import logger
from mario_trader.config import GEMINI_SETTINGS

class GeminiEngine:
    """
    Handles integration with Google's Gemini API for trade verification and monitoring
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini Engine
        
        Args:
            api_key: Gemini API key (optional, will use config if not provided)
        """
        self.api_key = api_key or GEMINI_SETTINGS.get("api_key")
        if not self.api_key:
            logger.warning("Gemini API key not found. Gemini verification will be disabled.")
        
        self.api_endpoint = GEMINI_SETTINGS.get("api_endpoint", "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent")
        self.enabled = GEMINI_SETTINGS.get("enabled", False)
        self.min_confidence = GEMINI_SETTINGS.get("min_confidence", 0.7)  # Minimum confidence score to approve a trade
    
    def verify_trade_setup(self, 
                           forex_pair: str, 
                           signal_type: str, 
                           data: pd.DataFrame,
                           indicators: Dict[str, float]) -> Tuple[bool, str, float]:
        """
        Verify a potential trade setup using Gemini AI
        
        Args:
            forex_pair: Currency pair symbol
            signal_type: "BUY" or "SELL"
            data: DataFrame with recent price data
            indicators: Dictionary with current indicator values
        
        Returns:
            Tuple of (approved, reason, confidence_score)
        """
        if not self.enabled or not self.api_key:
            # If Gemini is disabled, automatically approve the trade
            return True, "Gemini verification disabled", 1.0
        
        try:
            # Prepare market data summary for Gemini
            market_context = self._prepare_market_context(forex_pair, signal_type, data, indicators)
            
            # Create the prompt for Gemini
            prompt = self._create_trade_verification_prompt(forex_pair, signal_type, market_context)
            
            # Call Gemini API
            response = self._call_gemini_api(prompt)
            
            # Parse Gemini's response
            approved, reason, confidence = self._parse_verification_response(response)
            
            # Log the verification result
            logger.info(f"Gemini verification for {signal_type} {forex_pair}: {'APPROVED' if approved else 'REJECTED'} (Confidence: {confidence:.2f})")
            logger.info(f"Gemini reason: {reason}")
            
            return approved, reason, confidence
            
        except Exception as e:
            logger.error(f"Error during Gemini trade verification: {e}")
            # If there's an error, we'll still allow the trade but log the issue
            return True, f"Gemini verification error: {str(e)}", 0.0
    
    def monitor_trade(self, 
                     forex_pair: str, 
                     position_type: str, 
                     entry_price: float,
                     current_price: float,
                     trade_duration: int,
                     data: pd.DataFrame,
                     indicators: Dict[str, float]) -> Tuple[bool, str, float]:
        """
        Monitor an ongoing trade using Gemini AI to determine if it should be exited
        
        Args:
            forex_pair: Currency pair symbol
            position_type: "BUY" or "SELL"
            entry_price: Entry price of the trade
            current_price: Current market price
            trade_duration: Duration of the trade in minutes
            data: DataFrame with recent price data
            indicators: Dictionary with current indicator values
        
        Returns:
            Tuple of (should_exit, reason, confidence_score)
        """
        if not self.enabled or not self.api_key:
            # If Gemini is disabled, don't recommend exit
            return False, "Gemini monitoring disabled", 0.0
        
        try:
            # Calculate current profit/loss
            if position_type == "BUY":
                profit_pips = (current_price - entry_price) * 10000
            else:  # SELL
                profit_pips = (entry_price - current_price) * 10000
                
            # Prepare market data summary for Gemini
            market_context = self._prepare_market_context(forex_pair, position_type, data, indicators)
            market_context["profit_pips"] = profit_pips
            market_context["trade_duration_minutes"] = trade_duration
            
            # Create the prompt for Gemini
            prompt = self._create_trade_monitoring_prompt(forex_pair, position_type, entry_price, current_price, market_context)
            
            # Call Gemini API
            response = self._call_gemini_api(prompt)
            
            # Parse Gemini's response
            should_exit, reason, confidence = self._parse_monitoring_response(response)
            
            # Only log if Gemini recommends exit or every hour
            if should_exit or trade_duration % 60 == 0:
                logger.info(f"Gemini trade monitor for {position_type} {forex_pair}: {'EXIT' if should_exit else 'HOLD'} (Confidence: {confidence:.2f})")
                logger.info(f"Gemini reason: {reason}")
            
            return should_exit, reason, confidence
            
        except Exception as e:
            logger.error(f"Error during Gemini trade monitoring: {e}")
            # If there's an error, we'll not recommend exit but log the issue
            return False, f"Gemini monitoring error: {str(e)}", 0.0
    
    def _prepare_market_context(self, 
                               forex_pair: str, 
                               signal_type: str, 
                               data: pd.DataFrame,
                               indicators: Dict[str, float]) -> Dict:
        """
        Prepare market context data for Gemini analysis
        
        Args:
            forex_pair: Currency pair symbol
            signal_type: "BUY" or "SELL"
            data: DataFrame with recent price data
            indicators: Dictionary with current indicator values
            
        Returns:
            Dictionary with market context
        """
        # Get the most recent candles (last 10)
        recent_candles = data.iloc[-10:].copy()
        
        # Calculate candle patterns
        candle_pattern = ""
        for i in range(len(recent_candles)):
            candle = recent_candles.iloc[i]
            if candle['close'] > candle['open']:
                candle_pattern += "+"  # Bullish candle
            else:
                candle_pattern += "-"  # Bearish candle
        
        # Prepare market context
        context = {
            "forex_pair": forex_pair,
            "signal_type": signal_type,
            "current_price": data.iloc[-1]['close'],
            "sma_200": indicators.get("200_SMA", data.iloc[-1].get('200_SMA', 0)),
            "sma_50": indicators.get("50_SMA", data.iloc[-1].get('50_SMA', 0)),
            "sma_21": indicators.get("21_SMA", data.iloc[-1].get('21_SMA', 0)),
            "rsi": indicators.get("RSI", data.iloc[-1].get('RSI', 0)),
            "candle_pattern": candle_pattern,
            "market_volatility": data['high'].iloc[-10:].max() - data['low'].iloc[-10:].min(),
            "daily_range_pips": (data['high'].iloc[-1] - data['low'].iloc[-1]) * 10000,
            "market_session": self._determine_market_session(),
        }
        
        return context
    
    def _determine_market_session(self) -> str:
        """
        Determine the current forex market session
        
        Returns:
            String indicating the current market session
        """
        # This is a simplified version - in production you would use actual time checks
        import datetime
        current_hour = datetime.datetime.utcnow().hour
        
        if 7 <= current_hour < 16:
            return "London/European"
        elif 12 <= current_hour < 21:
            return "New York/US"
        elif 0 <= current_hour < 9:
            return "Tokyo/Asian"
        else:
            return "Quiet/Transition"
    
    def _create_trade_verification_prompt(self, 
                                         forex_pair: str, 
                                         signal_type: str, 
                                         market_context: Dict) -> str:
        """
        Create a prompt for trade verification
        
        Args:
            forex_pair: Currency pair symbol
            signal_type: "BUY" or "SELL"
            market_context: Dictionary with market data
            
        Returns:
            Prompt string for Gemini
        """
        prompt = f"""
You are an expert Forex trading advisor specialized in SMA Crossover strategies with RSI confirmation.

I need you to verify if the following {signal_type} signal for {forex_pair} is valid:

## Market Context
- Current price: {market_context['current_price']:.5f}
- 200 SMA: {market_context['sma_200']:.5f}
- 50 SMA: {market_context['sma_50']:.5f}
- 21 SMA: {market_context['sma_21']:.5f}
- RSI: {market_context['rsi']:.2f}
- Recent candle pattern (+ = bullish, - = bearish): {market_context['candle_pattern']}
- Current market session: {market_context['market_session']}
- Current market volatility: {market_context['market_volatility']:.5f}
- Daily range in pips: {market_context['daily_range_pips']:.1f}

## Strategy Rules
- For a BUY signal: Price above 200 SMA, RSI above 50, pattern of 3+ consecutive sell candles followed by a buy candle
- For a SELL signal: Price below 200 SMA, RSI below 50, pattern of 3+ consecutive buy candles followed by a sell candle
- We want at least 0.0005 separation between 21 SMA and 50 SMA
- We avoid trading during high volatility or major news events

Please respond in the following JSON format:
{{
    "approved": true/false,
    "confidence": 0.0-1.0 (decimal indicating your confidence in this decision),
    "reason": "Brief explanation for your decision",
    "additional_observations": "Any other insights about the market conditions"
}}
"""
        return prompt
    
    def _create_trade_monitoring_prompt(self, 
                                       forex_pair: str, 
                                       position_type: str, 
                                       entry_price: float,
                                       current_price: float,
                                       market_context: Dict) -> str:
        """
        Create a prompt for trade monitoring
        
        Args:
            forex_pair: Currency pair symbol
            position_type: "BUY" or "SELL"
            entry_price: Entry price of the trade
            current_price: Current market price
            market_context: Dictionary with market data
            
        Returns:
            Prompt string for Gemini
        """
        prompt = f"""
You are an expert Forex trading advisor specialized in SMA Crossover strategies with RSI confirmation.

I need you to evaluate if I should exit my current {position_type} position in {forex_pair}:

## Trade Details
- Entry price: {entry_price:.5f}
- Current price: {current_price:.5f}
- Current profit/loss: {market_context['profit_pips']:.1f} pips
- Trade duration: {market_context['trade_duration_minutes']} minutes

## Market Context
- 200 SMA: {market_context['sma_200']:.5f}
- 50 SMA: {market_context['sma_50']:.5f}
- 21 SMA: {market_context['sma_21']:.5f}
- RSI: {market_context['rsi']:.2f}
- Recent candle pattern (+ = bullish, - = bearish): {market_context['candle_pattern']}
- Current market session: {market_context['market_session']}
- Current market volatility: {market_context['market_volatility']:.5f}
- Daily range in pips: {market_context['daily_range_pips']:.1f}

## Exit Considerations
- For BUY positions: Consider exit on bearish RSI divergence or return to support level
- For SELL positions: Consider exit on bullish RSI divergence or return to resistance level
- Also consider exit on trend reversal signs or when profit target is reached
- We want to let profitable trades run but protect profits when the trend weakens

Please respond in the following JSON format:
{{
    "should_exit": true/false,
    "confidence": 0.0-1.0 (decimal indicating your confidence in this decision),
    "reason": "Brief explanation for your decision",
    "additional_observations": "Any other insights about the current trade"
}}
"""
        return prompt
    
    def _call_gemini_api(self, prompt: str) -> Dict:
        """
        Call the Gemini API with the given prompt
        
        Args:
            prompt: The prompt to send to Gemini
            
        Returns:
            Gemini API response as a dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        data = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 32,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        response = requests.post(
            self.api_endpoint,
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"Error calling Gemini API: {response.status_code} {response.text}")
            raise Exception(f"Gemini API error: {response.status_code}")
        
        return response.json()
    
    def _parse_verification_response(self, response: Dict) -> Tuple[bool, str, float]:
        """
        Parse Gemini's verification response
        
        Args:
            response: Gemini API response
            
        Returns:
            Tuple of (approved, reason, confidence_score)
        """
        try:
            # Extract the text from Gemini's response
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            
            # Parse the JSON response
            import re
            json_match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_text = text
                
            # Clean up the JSON text
            json_text = re.sub(r'```(json)?', '', json_text).strip()
            
            result = json.loads(json_text)
            
            approved = result.get("approved", False)
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "No reason provided")
            
            # Only approve if confidence is above the minimum threshold
            if approved and confidence < self.min_confidence:
                approved = False
                reason = f"Insufficient confidence ({confidence:.2f} < {self.min_confidence}): {reason}"
            
            return approved, reason, confidence
            
        except Exception as e:
            logger.error(f"Error parsing Gemini verification response: {e}")
            # If there's an error parsing, we don't approve the trade
            return False, f"Error parsing Gemini response: {str(e)}", 0.0
    
    def _parse_monitoring_response(self, response: Dict) -> Tuple[bool, str, float]:
        """
        Parse Gemini's monitoring response
        
        Args:
            response: Gemini API response
            
        Returns:
            Tuple of (should_exit, reason, confidence_score)
        """
        try:
            # Extract the text from Gemini's response
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            
            # Parse the JSON response
            import re
            json_match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_text = text
                
            # Clean up the JSON text
            json_text = re.sub(r'```(json)?', '', json_text).strip()
            
            result = json.loads(json_text)
            
            should_exit = result.get("should_exit", False)
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "No reason provided")
            
            # Only recommend exit if confidence is above the minimum threshold
            if should_exit and confidence < self.min_confidence:
                should_exit = False
                reason = f"Insufficient confidence ({confidence:.2f} < {self.min_confidence}) for exit: {reason}"
            
            return should_exit, reason, confidence
            
        except Exception as e:
            logger.error(f"Error parsing Gemini monitoring response: {e}")
            # If there's an error parsing, we don't recommend exit
            return False, f"Error parsing Gemini response: {str(e)}", 0.0 