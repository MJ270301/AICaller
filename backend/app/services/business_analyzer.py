import json
import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.models import BusinessProfile, QuestionSession, User
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

class BusinessAnalyzer:
    """Service for deep business understanding through adaptive questioning"""

    def __init__(self, db: Session):
        self.db = db
        self.ai_service = AIService()
        self.question_categories = {
            "basic_info": [
                "What is your business name and what industry are you in?",
                "How long have you been in business?",
                "What size is your business (small, medium, large, enterprise)?",
                "How many employees do you have?",
                "What's your primary business model (B2B, B2C, B2B2C)?"
            ],
            "services_products": [
                "What specific products or services do you offer?",
                "What makes your products/services unique?",
                "Who are your target customers?",
                "What problems do you solve for your customers?",
                "What are your main revenue streams?"
            ],
            "operations": [
                "What are your business hours?",
                "How do customers typically contact you?",
                "What's your current customer service approach?",
                "How do you handle sales and leads?",
                "What technology stack do you currently use?"
            ],
            "marketing": [
                "How do you currently market your business?",
                "What marketing channels work best for you?",
                "Do you have social media presence? Which platforms?",
                "What's your customer acquisition cost?",
                "How do you measure marketing success?"
            ],
            "competition": [
                "Who are your main competitors?",
                "What makes you different from competitors?",
                "What are your competitive advantages?",
                "How do you position yourself in the market?",
                "What market share do you estimate you have?"
            ],
            "goals": [
                "What are your business goals for the next year?",
                "Where do you see the business in 5 years?",
                "What's preventing you from reaching those goals?",
                "What are your biggest challenges right now?",
                "How do you measure business success?"
            ],
            "compliance": [
                "Are there any industry regulations you need to comply with?",
                "Do you handle sensitive customer data?",
                "What privacy and security measures do you have?",
                "Are there any licensing requirements?",
                "Do you need to meet specific industry standards?"
            ]
        }

        self.industry_specific_questions = {
            "healthcare": [
                "What type of healthcare services do you provide?",
                "Do you handle patient records (HIPAA compliance)?",
                "What medical specializations do you cover?",
                "How do you handle patient appointments?",
                "What medical software systems do you use?"
            ],
            "legal": [
                "What areas of law do you practice?",
                "How do you manage client cases?",
                "Do you handle confidential legal documents?",
                "What legal software do you use?",
                "How do you track billable hours?"
            ],
            "retail": [
                "What types of products do you sell?",
                "Do you have physical stores, online, or both?",
                "How do you manage inventory?",
                "What payment systems do you use?",
                "How do you handle customer returns?"
            ],
            "finance": [
                "What financial services do you offer?",
                "Are you regulated by financial authorities?",
                "How do you handle customer accounts?",
                "What banking systems do you integrate with?",
                "How do you ensure financial compliance?"
            ],
            "technology": [
                "What technology solutions do you provide?",
                "Do you offer SaaS products?",
                "How do you handle customer support?",
                "What development methodologies do you use?",
                "How do you manage software deployments?"
            ]
        }

    async def start_questionnaire_session(self, user_id: int, business_profile_id: int) -> Dict[str, Any]:
        """Start a new questionnaire session for business profiling"""
        try:
            # Create new question session
            session = QuestionSession(
                user_id=user_id,
                business_profile_id=business_profile_id,
                session_status="in_progress",
                current_question_category="basic_info",
                questions_asked=json.dumps([]),
                answers_received=json.dumps({}),
                next_questions=json.dumps(self.question_categories["basic_info"][:3])
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            # Get first questions
            next_questions = json.loads(session.next_questions)

            return {
                "session_id": session.id,
                "status": "started",
                "current_category": "basic_info",
                "next_questions": next_questions,
                "welcome_message": "I'll help you create the perfect AI assistant for your business. Let me ask some questions to understand your business better."
            }

        except Exception as e:
            logger.error(f"Error starting questionnaire session: {str(e)}")
            raise

    async def process_answer(self, session_id: int, answer: str, question_index: int = None) -> Dict[str, Any]:
        """Process user answer and generate next questions"""
        try:
            session = self.db.query(QuestionSession).filter(QuestionSession.id == session_id).first()
            if not session:
                return {"error": "Session not found"}

            # Parse current state
            questions_asked = json.loads(session.questions_asked or "[]")
            answers = json.loads(session.answers_received or "{}")
            next_questions = json.loads(session.next_questions or "[]")

            # Store answer
            if question_index is not None and question_index < len(next_questions):
                question = next_questions[question_index]
                answers[question] = answer
                questions_asked.append(question)

                # Remove answered question from next_questions
                next_questions.pop(question_index)

            # Analyze answer and determine next category
            category, new_questions = await self._analyze_answer_and_get_next_questions(
                session.current_question_category, answers, session.business_profile
            )

            # Update session
            session.questions_asked = json.dumps(questions_asked)
            session.answers_received = json.dumps(answers)
            session.next_questions = json.dumps(new_questions)
            session.current_question_category = category
            session.confidence_score = await self._calculate_confidence_score(answers)

            self.db.commit()

            # Determine if session should continue or end
            if session.confidence_score >= 0.8 or len(questions_asked) >= 25:
                await self._complete_session(session)
                return {
                    "session_id": session_id,
                    "status": "completed",
                    "confidence_score": session.confidence_score,
                    "summary": await self._generate_business_summary(answers),
                    "completion_message": "Great! I now have a good understanding of your business. Let's create your AI assistant."
                }

            return {
                "session_id": session_id,
                "status": "in_progress",
                "current_category": category,
                "next_questions": new_questions[:3],  # Limit to 3 questions at a time
                "confidence_score": session.confidence_score,
                "progress": min(session.confidence_score * 100, 95)
            }

        except Exception as e:
            logger.error(f"Error processing answer: {str(e)}")
            raise

    async def _analyze_answer_and_get_next_questions(self, current_category: str, answers: Dict[str, str], business_profile: BusinessProfile) -> tuple[str, List[str]]:
        """Analyze current answers and determine next questions"""
        try:
            # Use AI to analyze answers and suggest next category
            analysis_prompt = f"""
            Based on these answers about a business, determine what category of questions should be asked next:

            Current category: {current_category}
            Answers so far: {json.dumps(answers, indent=2)}

            Available categories: {list(self.question_categories.keys())}

            Choose the most appropriate next category based on:
            1. What information is still missing for complete business understanding
            2. What would be most valuable for creating an AI assistant
            3. The logical flow of business discovery

            Return only the category name.
            """

            # For now, implement simple category progression
            category_order = ["basic_info", "services_products", "operations", "marketing", "competition", "goals", "compliance"]

            try:
                current_index = category_order.index(current_category) if current_category in category_order else -1
                next_category = category_order[current_index + 1] if current_index + 1 < len(category_order) else "goals"
            except (ValueError, IndexError):
                next_category = "services_products"

            # Get industry-specific questions if industry is known
            industry = answers.get("What industry are you in?", "").lower()
            base_questions = self.question_categories.get(next_category, [])

            if industry in self.industry_specific_questions and next_category == "operations":
                base_questions.extend(self.industry_specific_questions[industry][:3])

            return next_category, base_questions

        except Exception as e:
            logger.error(f"Error analyzing answer: {str(e)}")
            return "services_products", self.question_categories.get("services_products", [])

    async def _calculate_confidence_score(self, answers: Dict[str, str]) -> float:
        """Calculate confidence score based on completeness of answers"""
        try:
            # Define key information categories
            key_categories = {
                "basic": ["business name", "industry", "size", "employees"],
                "services": ["products", "services", "customers", "problems"],
                "operations": ["hours", "contact", "service", "sales"],
                "marketing": ["market", "channels", "social", "acquisition"],
                "competition": ["competitors", "different", "advantages", "position"],
                "goals": ["goals", "challenges", "success", "future"]
            }

            # Calculate coverage for each category
            category_scores = {}
            for category, keywords in key_categories.items():
                score = 0
                for keyword in keywords:
                    for answer in answers.values():
                        if keyword.lower() in answer.lower():
                            score += 1
                            break
                category_scores[category] = min(score / len(keywords), 1.0)

            # Calculate overall confidence score
            total_score = sum(category_scores.values()) / len(category_scores)

            # Bonus for detailed answers
            avg_answer_length = sum(len(answer) for answer in answers.values()) / len(answers) if answers else 0
            length_bonus = min(avg_answer_length / 100, 0.3)

            return min(total_score + length_bonus, 1.0)

        except Exception as e:
            logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.5

    async def _complete_session(self, session: QuestionSession):
        """Complete the questionnaire session"""
        try:
            session.session_status = "completed"
            session.session_metadata = json.dumps({
                "completion_time": "now",
                "total_questions_asked": len(json.loads(session.questions_asked or "[]")),
                "completion_confidence": session.confidence_score
            })
            self.db.commit()

        except Exception as e:
            logger.error(f"Error completing session: {str(e)}")
            raise

    async def _generate_business_summary(self, answers: Dict[str, str]) -> str:
        """Generate a comprehensive business summary"""
        try:
            summary_prompt = f"""
            Create a comprehensive business summary based on these answers:

            {json.dumps(answers, indent=2)}

            The summary should include:
            1. Business overview
            2. Key services/products
            3. Target market
            4. Competitive advantages
            5. Business goals

            Format as a professional business profile.
            """

            # For now, create a simple summary
            business_name = answers.get("What is your business name", "Business")
            industry = answers.get("What industry are you in", "Industry")

            return f"""
            Business Profile: {business_name}
            Industry: {industry}

            Key Information:
            - Business Type: Based on provided answers
            - Target Market: Identified through questioning
            - Services: Detailed in responses
            - Goals: Outlined in conversation

            This profile will be used to create a customized AI assistant that understands your business context and can interact with customers professionally.
            """

        except Exception as e:
            logger.error(f"Error generating business summary: {str(e)}")
            return "Business profile completed successfully."

    async def get_session_status(self, session_id: int) -> Dict[str, Any]:
        """Get current status of questionnaire session"""
        try:
            session = self.db.query(QuestionSession).filter(QuestionSession.id == session_id).first()
            if not session:
                return {"error": "Session not found"}

            return {
                "session_id": session.id,
                "status": session.session_status,
                "current_category": session.current_question_category,
                "confidence_score": session.confidence_score,
                "next_questions": json.loads(session.next_questions or "[]"),
                "progress": min(session.confidence_score * 100, 95)
            }

        except Exception as e:
            logger.error(f"Error getting session status: {str(e)}")
            raise

    async def get_business_insights(self, business_profile_id: int) -> Dict[str, Any]:
        """Get AI-generated insights about the business"""
        try:
            business_profile = self.db.query(BusinessProfile).filter(BusinessProfile.id == business_profile_id).first()
            if not business_profile:
                return {"error": "Business profile not found"}

            insights_prompt = f"""
            Analyze this business profile and provide actionable insights for AI assistant creation:

            Business: {business_profile.business_name}
            Industry: {business_profile.industry}
            Size: {business_profile.business_size}
            Services: {business_profile.services_offered}
            Target: {business_profile.target_audience}

            Provide insights on:
            1. Recommended agent type and personality
            2. Key capabilities needed
            3. Communication style suggestions
            4. Industry-specific knowledge requirements
            5. Integration opportunities

            Format as JSON.
            """

            # For now, return basic insights
            return {
                "recommended_agent_type": self._recommend_agent_type(business_profile),
                "suggested_capabilities": self._suggest_capabilities(business_profile),
                "communication_style": self._suggest_communication_style(business_profile),
                "industry_knowledge": self._suggest_industry_knowledge(business_profile)
            }

        except Exception as e:
            logger.error(f"Error generating business insights: {str(e)}")
            raise

    def _recommend_agent_type(self, profile: BusinessProfile) -> str:
        """Recommend agent type based on business profile"""
        if "support" in profile.industry.lower() or "service" in profile.industry.lower():
            return "support"
        elif "sales" in profile.services_offered.lower() or "revenue" in profile.business_goals.lower():
            return "sales"
        else:
            return "secretary"

    def _suggest_capabilities(self, profile: BusinessProfile) -> List[str]:
        """Suggest agent capabilities based on business profile"""
        capabilities = ["conversation", "information_provision"]

        if "appointment" in profile.services_offered.lower():
            capabilities.append("scheduling")
        if "support" in profile.industry.lower():
            capabilities.append("troubleshooting")
        if "sales" in profile.services_offered.lower():
            capabilities.append("lead_qualification")

        return capabilities

    def _suggest_communication_style(self, profile: BusinessProfile) -> str:
        """Suggest communication style based on business profile"""
        if profile.industry.lower() in ["legal", "finance", "healthcare"]:
            return "formal"
        elif profile.industry.lower() in ["retail", "entertainment", "hospitality"]:
            return "casual"
        else:
            return "mixed"

    def _suggest_industry_knowledge(self, profile: BusinessProfile) -> List[str]:
        """Suggest industry-specific knowledge areas"""
        industry = profile.industry.lower()

        knowledge_map = {
            "healthcare": ["HIPAA compliance", "medical terminology", "patient privacy"],
            "legal": ["legal terminology", "client confidentiality", "legal procedures"],
            "finance": ["financial regulations", "investment products", "risk management"],
            "retail": ["product knowledge", "inventory systems", "customer service"],
            "technology": ["technical support", "software solutions", "industry trends"]
        }

        return knowledge_map.get(industry, ["general business knowledge", "customer service"])