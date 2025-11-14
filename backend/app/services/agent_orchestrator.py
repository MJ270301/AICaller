import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
import aiohttp
import websockets
from datetime import datetime

from app.models.models import (
    AgentConfiguration, AgentConversation, ConversationMessage,
    BusinessProfile, VoiceProfile, User
)
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    """Orchestrates agent deployment and communication across microservices"""

    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.microservice_urls = {
            "voice_ai_suite": os.getenv("VOICE_AI_SUITE_URL", "http://localhost:8001"),
            "competitive_intel": os.getenv("COMPETITIVE_INTEL_URL", "http://localhost:8002"),
            "ai_inference_engine": os.getenv("AI_INFERENCE_ENGINE_URL", "http://localhost:8003")
        }
        self.active_conversations = {}  # In-memory store for active conversations
        self.websocket_connections = {}  # WebSocket connections for real-time updates

    async def deploy_agent(self, agent_id: int, user_id: int) -> Dict[str, Any]:
        """Deploy an agent by coordinating all microservices"""
        try:
            # Get agent configuration
            agent_config = self.db.query(AgentConfiguration).filter(
                and_(AgentConfiguration.id == agent_id, AgentConfiguration.user_id == user_id)
            ).first()

            if not agent_config:
                return {"success": False, "error": "Agent not found"}

            # Step 1: Initialize voice AI suite
            voice_config = await self._configure_voice_ai_suite(agent_config)
            if not voice_config["success"]:
                return {"success": False, "error": "Voice AI configuration failed"}

            # Step 2: Set up competitive intelligence
            intel_config = await self._configure_competitive_intelligence(agent_config)

            # Step 3: Initialize AI inference engine
            inference_config = await self._configure_inference_engine(agent_config)
            if not inference_config["success"]:
                return {"success": False, "error": "Inference engine configuration failed"}

            # Step 4: Update agent deployment status
            agent_config.deployment_status = "deployed"
            agent_config.is_active = True
            self.db.commit()

            # Step 5: Register agent with orchestrator
            await self._register_active_agent(agent_config)

            return {
                "success": True,
                "agent_id": agent_id,
                "deployment_time": datetime.utcnow().isoformat(),
                "voice_config": voice_config,
                "inference_config": inference_config,
                "intel_config": intel_config,
                "endpoints": {
                    "conversation": f"/api/conversations/start/{agent_id}",
                    "monitoring": f"/api/agents/{agent_id}/monitor",
                    "analytics": f"/api/agents/{agent_id}/analytics"
                }
            }

        except Exception as e:
            logger.error(f"Error deploying agent {agent_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_conversation(self, agent_id: int, customer_id: str,
                               conversation_type: str = "phone",
                               initial_message: str = None) -> Dict[str, Any]:
        """Handle real-time conversation with AI agent"""
        try:
            # Get agent configuration
            agent_config = self.db.query(AgentConfiguration).filter(
                AgentConfiguration.id == agent_id
            ).first()

            if not agent_config or not agent_config.is_active:
                return {"success": False, "error": "Agent not found or inactive"}

            # Create conversation record
            conversation = AgentConversation(
                agent_id=agent_id,
                customer_id=customer_id,
                conversation_type=conversation_type,
                start_time=datetime.utcnow()
            )

            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

            # Initialize conversation state
            conversation_state = {
                "conversation_id": conversation.id,
                "agent_id": agent_id,
                "customer_id": customer_id,
                "agent_config": agent_config,
                "business_context": agent_config.business_profile,
                "voice_profile": agent_config.voice_profile,
                "conversation_history": [],
                "emotional_state": "neutral",
                "context_variables": {}
            }

            self.active_conversations[conversation.id] = conversation_state

            # Start conversation processing
            if initial_message:
                await self._process_message(conversation.id, initial_message, "customer")

            return {
                "success": True,
                "conversation_id": conversation.id,
                "status": "active",
                "message": "Conversation started successfully"
            }

        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _process_message(self, conversation_id: int, message: str, sender: str) -> Dict[str, Any]:
        """Process incoming message and generate response"""
        try:
            if conversation_id not in self.active_conversations:
                return {"success": False, "error": "Conversation not found"}

            state = self.active_conversations[conversation_id]
            agent_config = state["agent_config"]
            business_context = state["business_context"]

            # Store message in conversation history
            self.active_conversations[conversation_id]["conversation_history"].append({
                "sender": sender,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Save message to database
            await self._save_conversation_message(conversation_id, sender, message)

            if sender == "customer":
                # Process customer message
                # Step 1: Sentiment analysis (from voice AI suite)
                sentiment_result = await self._analyze_sentiment(message, conversation_id)

                # Step 2: Generate AI response (from inference engine)
                ai_response = await self._generate_ai_response(
                    message, state, sentiment_result, business_context
                )

                # Step 3: Apply voice synthesis if needed
                if state["voice_profile"]:
                    audio_response = await self._synthesize_speech(
                        ai_response["text"], state["voice_profile"]
                    )
                    ai_response["audio_url"] = audio_response.get("audio_url")

                # Step 4: Save AI response
                await self._save_conversation_message(conversation_id, "assistant", ai_response["text"])

                # Step 5: Update emotional state
                self.active_conversations[conversation_id]["emotional_state"] = sentiment_result.get("emotion", "neutral")

                # Step 6: Update learning insights
                await self._update_learning_insights(conversation_id, sentiment_result, ai_response)

                return {
                    "success": True,
                    "response": ai_response,
                    "sentiment": sentiment_result,
                    "emotional_state": self.active_conversations[conversation_id]["emotional_state"]
                }

            else:
                return {"success": True, "message": "Message processed"}

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _configure_voice_ai_suite(self, agent_config: AgentConfiguration) -> Dict[str, Any]:
        """Configure voice AI suite for agent"""
        try:
            voice_profile = agent_config.voice_profile
            if not voice_profile:
                return {"success": True, "message": "No voice profile configured"}

            voice_config = {
                "voice_id": voice_profile.id,
                "voice_type": voice_profile.voice_type,
                "pitch": voice_profile.pitch,
                "speed": voice_profile.speed,
                "volume": voice_profile.volume,
                "emotion_range": json.loads(voice_profile.emotion_range or "[]"),
                "language": voice_profile.language,
                "agent_id": agent_config.id
            }

            # Send configuration to voice AI suite
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['voice_ai_suite']}/api/voice/configure",
                    json=voice_config
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"success": False, "error": f"Voice AI suite error: {response.status}"}

        except Exception as e:
            logger.error(f"Error configuring voice AI suite: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _configure_competitive_intelligence(self, agent_config: AgentConfiguration) -> Dict[str, Any]:
        """Configure competitive intelligence for agent"""
        try:
            business_context = agent_config.business_profile

            intel_config = {
                "agent_id": agent_config.id,
                "industry": business_context.industry,
                "business_size": business_context.business_size,
                "services": json.loads(business_context.services_offered or "[]"),
                "target_market": business_context.target_audience
            }

            # Start competitive analysis in background
            asyncio.create_task(self._start_competitive_analysis(intel_config))

            return {"success": True, "message": "Competitive intelligence configured"}

        except Exception as e:
            logger.error(f"Error configuring competitive intelligence: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _configure_inference_engine(self, agent_config: AgentConfiguration) -> Dict[str, Any]:
        """Configure AI inference engine for agent"""
        try:
            business_context = agent_config.business_profile

            inference_config = {
                "agent_id": agent_config.id,
                "agent_name": agent_config.agent_name,
                "agent_type": agent_config.agent_type,
                "personality_traits": json.loads(agent_config.personality_traits or "[]"),
                "communication_style": agent_config.communication_style,
                "industry_knowledge": json.loads(agent_config.industry_knowledge or "[]"),
                "capabilities": json.loads(agent_config.capabilities or "[]"),
                "custom_responses": json.loads(agent_config.custom_responses or "{}"),
                "learning_enabled": agent_config.learning_enabled,
                "emotional_intelligence": agent_config.emotional_intelligence,
                "business_context": {
                    "business_name": business_context.business_name,
                    "industry": business_context.industry,
                    "services": json.loads(business_context.services_offered or "[]"),
                    "unique_value": business_context.unique_value_proposition,
                    "target_audience": business_context.target_audience
                }
            }

            # Send configuration to inference engine
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['ai_inference_engine']}/api/inference/configure",
                    json=inference_config
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"success": False, "error": f"Inference engine error: {response.status}"}

        except Exception as e:
            logger.error(f"Error configuring inference engine: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _analyze_sentiment(self, message: str, conversation_id: int) -> Dict[str, Any]:
        """Analyze sentiment using voice AI suite"""
        try:
            sentiment_request = {
                "text": message,
                "conversation_id": conversation_id
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['voice_ai_suite']}/api/sentiment/analyze",
                    json=sentiment_request
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        # Fallback sentiment analysis
                        return self._fallback_sentiment_analysis(message)

        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return self._fallback_sentiment_analysis(message)

    async def _generate_ai_response(self, message: str, state: Dict[str, Any],
                                 sentiment_result: Dict[str, Any],
                                 business_context: BusinessProfile) -> Dict[str, Any]:
        """Generate AI response using inference engine"""
        try:
            response_request = {
                "message": message,
                "conversation_history": state["conversation_history"],
                "agent_config": {
                    "agent_type": state["agent_config"].agent_type,
                    "personality": json.loads(state["agent_config"].personality_traits or "[]"),
                    "communication_style": state["agent_config"].communication_style
                },
                "business_context": {
                    "industry": business_context.industry,
                    "services": json.loads(business_context.services_offered or "[]"),
                    "unique_value": business_context.unique_value_proposition
                },
                "emotional_state": state["emotional_state"],
                "sentiment": sentiment_result,
                "learning_enabled": state["agent_config"].learning_enabled
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['ai_inference_engine']}/api/inference/converse",
                    json=response_request
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        # Fallback response generation
                        return self._fallback_response_generation(message, state, business_context)

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return self._fallback_response_generation(message, state, business_context)

    async def _synthesize_speech(self, text: str, voice_profile: VoiceProfile) -> Dict[str, Any]:
        """Synthesize speech using voice AI suite"""
        try:
            synthesis_request = {
                "text": text,
                "voice_config": {
                    "voice_id": voice_profile.id,
                    "voice_type": voice_profile.voice_type,
                    "pitch": voice_profile.pitch,
                    "speed": voice_profile.speed,
                    "volume": voice_profile.volume,
                    "emotion": "neutral"  # Can be adjusted based on context
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['voice_ai_suite']}/api/voice/synthesize",
                    json=synthesis_request
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"success": False, "error": "Speech synthesis failed"}

        except Exception as e:
            logger.error(f"Error synthesizing speech: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _start_competitive_analysis(self, intel_config: Dict[str, Any]):
        """Start competitive analysis in background"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['competitive_intel']}/api/intelligence/analyze",
                    json=intel_config
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Competitive analysis started: {result}")
                    else:
                        logger.warning(f"Competitive analysis failed: {response.status}")

        except Exception as e:
            logger.error(f"Error starting competitive analysis: {str(e)}")

    async def _save_conversation_message(self, conversation_id: int, role: str, content: str):
        """Save conversation message to database"""
        try:
            message = ConversationMessage(
                agent_conversation_id=conversation_id,
                role=role,
                content=content,
                timestamp=datetime.utcnow()
            )

            self.db.add(message)
            self.db.commit()

        except Exception as e:
            logger.error(f"Error saving conversation message: {str(e)}")

    async def _update_learning_insights(self, conversation_id: int,
                                      sentiment_result: Dict[str, Any],
                                      ai_response: Dict[str, Any]):
        """Update learning insights for agent improvement"""
        try:
            if conversation_id not in self.active_conversations:
                return

            learning_data = {
                "conversation_id": conversation_id,
                "sentiment": sentiment_result,
                "response_effectiveness": ai_response.get("confidence", 0.5),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Send learning data to inference engine
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.microservice_urls['ai_inference_engine']}/api/inference/learn",
                    json=learning_data
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Learning data submission failed: {response.status}")

        except Exception as e:
            logger.error(f"Error updating learning insights: {str(e)}")

    def _fallback_sentiment_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback sentiment analysis when microservice is unavailable"""
        # Simple keyword-based sentiment analysis
        positive_words = ["good", "great", "excellent", "happy", "satisfied", "love", "perfect"]
        negative_words = ["bad", "terrible", "awful", "angry", "frustrated", "hate", "worst"]

        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)

        if positive_count > negative_count:
            emotion = "positive"
        elif negative_count > positive_count:
            emotion = "negative"
        else:
            emotion = "neutral"

        return {
            "emotion": emotion,
            "confidence": 0.6,
            "sentiment_score": (positive_count - negative_count) / max(positive_count + negative_count, 1)
        }

    def _fallback_response_generation(self, message: str, state: Dict[str, Any],
                                   business_context: BusinessProfile) -> Dict[str, Any]:
        """Fallback response generation when inference engine is unavailable"""
        agent_type = state["agent_config"].agent_type
        business_name = business_context.business_name

        # Simple rule-based responses
        if "hello" in message.lower() or "hi" in message.lower():
            response_text = f"Hello! I'm the AI assistant for {business_name}. How can I help you today?"
        elif "help" in message.lower():
            response_text = f"I'm here to assist you with {business_name}. What specifically do you need help with?"
        elif "thank" in message.lower():
            response_text = "You're welcome! Is there anything else I can help you with?"
        else:
            response_text = f"Thank you for contacting {business_name}. I understand your message and I'm here to help. Could you please provide more details so I can assist you better?"

        return {
            "text": response_text,
            "confidence": 0.7,
            "response_type": "fallback"
        }

    async def _register_active_agent(self, agent_config: AgentConfiguration):
        """Register agent as active in orchestrator"""
        try:
            agent_state = {
                "agent_id": agent_config.id,
                "status": "active",
                "deployment_time": datetime.utcnow().isoformat(),
                "configuration": {
                    "name": agent_config.agent_name,
                    "type": agent_config.agent_type,
                    "capabilities": json.loads(agent_config.capabilities or "[]")
                }
            }

            # Store in active agents registry
            # This could be stored in Redis for distributed systems
            logger.info(f"Agent {agent_config.id} registered as active")

        except Exception as e:
            logger.error(f"Error registering active agent: {str(e)}")

    async def get_agent_status(self, agent_id: int) -> Dict[str, Any]:
        """Get current status of deployed agent"""
        try:
            agent_config = self.db.query(AgentConfiguration).filter(
                AgentConfiguration.id == agent_id
            ).first()

            if not agent_config:
                return {"error": "Agent not found"}

            active_conversations_count = len([
                conv_id for conv_id, state in self.active_conversations.items()
                if state["agent_id"] == agent_id
            ])

            return {
                "agent_id": agent_id,
                "is_active": agent_config.is_active,
                "deployment_status": agent_config.deployment_status,
                "active_conversations": active_conversations_count,
                "last_updated": agent_config.updated_at.isoformat(),
                "microservice_status": await self._check_microservice_health()
            }

        except Exception as e:
            logger.error(f"Error getting agent status: {str(e)}")
            return {"error": str(e)}

    async def _check_microservice_health(self) -> Dict[str, str]:
        """Check health of all microservices"""
        health_status = {}

        for service_name, base_url in self.microservice_urls.items():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{base_url}/health") as response:
                        health_status[service_name] = "healthy" if response.status == 200 else "unhealthy"
            except:
                health_status[service_name] = "unreachable"

        return health_status