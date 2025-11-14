from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import json
import logging

from app.database.database import get_db
from app.models.models import User, BusinessProfile, AgentConfiguration, QuestionSession, VoiceProfile
from app.services.business_analyzer import BusinessAnalyzer
from app.api.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class BusinessProfileCreate(BaseModel):
    business_name: str
    industry: str
    business_size: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    business_email: Optional[str] = None

class BusinessProfileUpdate(BaseModel):
    services_offered: Optional[List[str]] = None
    target_audience: Optional[str] = None
    unique_value_proposition: Optional[str] = None
    business_hours: Optional[str] = None
    competitive_advantages: Optional[List[str]] = None
    business_goals: Optional[List[str]] = None
    pain_points_solved: Optional[List[str]] = None
    customer_base_size: Optional[int] = None
    annual_revenue: Optional[str] = None
    years_in_business: Optional[int] = None
    number_of_employees: Optional[int] = None
    business_model: Optional[str] = None
    primary_markets: Optional[List[str]] = None
    technology_stack: Optional[str] = None
    social_media_presence: Optional[List[str]] = None
    marketing_channels: Optional[List[str]] = None
    customer_service_approach: Optional[str] = None
    sales_process: Optional[str] = None
    compliance_requirements: Optional[str] = None

class QuestionAnswer(BaseModel):
    answer: str
    question_index: Optional[int] = None

class AgentConfigurationCreate(BaseModel):
    agent_name: str
    agent_type: str
    personality_traits: Optional[List[str]] = None
    voice_style: Optional[str] = "professional"
    communication_style: Optional[str] = "mixed"
    industry_knowledge: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    languages: Optional[List[str]] = ["en-US"]
    working_hours: Optional[str] = None
    escalation_rules: Optional[List[Dict[str, Any]]] = None
    integration_settings: Optional[Dict[str, Any]] = None
    custom_responses: Optional[Dict[str, str]] = None
    learning_enabled: Optional[bool] = True
    emotional_intelligence: Optional[bool] = True
    voice_profile_id: Optional[int] = None

class AgentConfigurationUpdate(BaseModel):
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    voice_style: Optional[str] = None
    communication_style: Optional[str] = None
    industry_knowledge: Optional[List[str]] = None
    capabilities: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    working_hours: Optional[str] = None
    escalation_rules: Optional[List[Dict[str, Any]]] = None
    integration_settings: Optional[Dict[str, Any]] = None
    custom_responses: Optional[Dict[str, str]] = None
    learning_enabled: Optional[bool] = None
    emotional_intelligence: Optional[bool] = None
    voice_profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    deployment_status: Optional[str] = None

@router.post("/api/agents/business-profile/create", response_model=Dict[str, Any])
async def create_business_profile(
    profile_data: BusinessProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new business profile"""
    try:
        # Check if user already has a business profile
        existing_profile = db.query(BusinessProfile).filter(
            BusinessProfile.user_id == current_user.id
        ).first()

        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has a business profile. Use update endpoint instead."
            )

        # Create business profile
        business_profile = BusinessProfile(
            user_id=current_user.id,
            business_name=profile_data.business_name,
            industry=profile_data.industry,
            business_size=profile_data.business_size,
            location=profile_data.location,
            website=profile_data.website,
            phone=profile_data.phone,
            business_email=profile_data.business_email
        )

        db.add(business_profile)
        db.commit()
        db.refresh(business_profile)

        return {
            "success": True,
            "business_profile_id": business_profile.id,
            "message": "Business profile created successfully",
            "next_step": "Start questionnaire to complete business understanding"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating business profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/api/agents/questionnaire/start", response_model=Dict[str, Any])
async def start_questionnaire(
    business_profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start business questionnaire session"""
    try:
        # Verify business profile ownership
        business_profile = db.query(BusinessProfile).filter(
            and_(BusinessProfile.id == business_profile_id, BusinessProfile.user_id == current_user.id)
        ).first()

        if not business_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found"
            )

        # Start questionnaire session
        analyzer = BusinessAnalyzer(db)
        result = await analyzer.start_questionnaire_session(current_user.id, business_profile_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting questionnaire: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/api/agents/questionnaire/answer", response_model=Dict[str, Any])
async def submit_questionnaire_answer(
    session_id: int,
    answer_data: QuestionAnswer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit answer to questionnaire"""
    try:
        # Verify session ownership
        session = db.query(QuestionSession).filter(
            and_(QuestionSession.id == session_id, QuestionSession.user_id == current_user.id)
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire session not found"
            )

        # Process answer
        analyzer = BusinessAnalyzer(db)
        result = await analyzer.process_answer(session_id, answer_data.answer, answer_data.question_index)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api/agents/questionnaire/status/{session_id}", response_model=Dict[str, Any])
async def get_questionnaire_status(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get questionnaire session status"""
    try:
        # Verify session ownership
        session = db.query(QuestionSession).filter(
            and_(QuestionSession.id == session_id, QuestionSession.user_id == current_user.id)
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questionnaire session not found"
            )

        analyzer = BusinessAnalyzer(db)
        result = await analyzer.get_session_status(session_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting questionnaire status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/api/agents/business-profile/{profile_id}", response_model=Dict[str, Any])
async def update_business_profile(
    profile_id: int,
    profile_data: BusinessProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update business profile"""
    try:
        # Verify business profile ownership
        business_profile = db.query(BusinessProfile).filter(
            and_(BusinessProfile.id == profile_id, BusinessProfile.user_id == current_user.id)
        ).first()

        if not business_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found"
            )

        # Update fields
        update_data = profile_data.dict(exclude_unset=True)

        # Convert lists to JSON strings
        for field, value in update_data.items():
            if isinstance(value, list) and field in [
                "services_offered", "competitive_advantages", "business_goals",
                "pain_points_solved", "primary_markets", "social_media_presence",
                "marketing_channels"
            ]:
                setattr(business_profile, field, json.dumps(value))
            else:
                setattr(business_profile, field, value)

        db.commit()
        db.refresh(business_profile)

        return {
            "success": True,
            "business_profile_id": business_profile.id,
            "message": "Business profile updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating business profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/api/agents/configure", response_model=Dict[str, Any])
async def create_agent_configuration(
    agent_data: AgentConfigurationCreate,
    business_profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create agent configuration"""
    try:
        # Verify business profile ownership
        business_profile = db.query(BusinessProfile).filter(
            and_(BusinessProfile.id == business_profile_id, BusinessProfile.user_id == current_user.id)
        ).first()

        if not business_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found"
            )

        # Verify voice profile ownership if provided
        if agent_data.voice_profile_id:
            voice_profile = db.query(VoiceProfile).filter(
                and_(VoiceProfile.id == agent_data.voice_profile_id, VoiceProfile.user_id == current_user.id)
            ).first()

            if not voice_profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Voice profile not found"
                )

        # Create agent configuration
        agent_config = AgentConfiguration(
            user_id=current_user.id,
            business_profile_id=business_profile_id,
            agent_name=agent_data.agent_name,
            agent_type=agent_data.agent_type,
            personality_traits=json.dumps(agent_data.personality_traits or []),
            voice_style=agent_data.voice_style,
            communication_style=agent_data.communication_style,
            industry_knowledge=json.dumps(agent_data.industry_knowledge or []),
            capabilities=json.dumps(agent_data.capabilities or ["conversation"]),
            languages=json.dumps(agent_data.languages or ["en-US"]),
            working_hours=agent_data.working_hours,
            escalation_rules=json.dumps(agent_data.escalation_rules or []),
            integration_settings=json.dumps(agent_data.integration_settings or {}),
            custom_responses=json.dumps(agent_data.custom_responses or {}),
            learning_enabled=agent_data.learning_enabled,
            emotional_intelligence=agent_data.emotional_intelligence,
            voice_profile_id=agent_data.voice_profile_id
        )

        db.add(agent_config)
        db.commit()
        db.refresh(agent_config)

        return {
            "success": True,
            "agent_id": agent_config.id,
            "deployment_status": agent_config.deployment_status,
            "message": "Agent configuration created successfully",
            "next_steps": [
                "Test agent functionality",
                "Configure voice settings",
                "Set up integrations",
                "Deploy agent"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api/agents/{agent_id}/preview", response_model=Dict[str, Any])
async def get_agent_preview(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent configuration preview"""
    try:
        # Verify agent ownership
        agent_config = db.query(AgentConfiguration).filter(
            and_(AgentConfiguration.id == agent_id, AgentConfiguration.user_id == current_user.id)
        ).first()

        if not agent_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent configuration not found"
            )

        # Get related data
        business_profile = agent_config.business_profile
        voice_profile = agent_config.voice_profile

        preview_data = {
            "agent": {
                "id": agent_config.id,
                "name": agent_config.agent_name,
                "type": agent_config.agent_type,
                "deployment_status": agent_config.deployment_status,
                "created_at": agent_config.created_at,
                "updated_at": agent_config.updated_at
            },
            "configuration": {
                "personality_traits": json.loads(agent_config.personality_traits or "[]"),
                "voice_style": agent_config.voice_style,
                "communication_style": agent_config.communication_style,
                "industry_knowledge": json.loads(agent_config.industry_knowledge or "[]"),
                "capabilities": json.loads(agent_config.capabilities or "[]"),
                "languages": json.loads(agent_config.languages or "[]"),
                "working_hours": agent_config.working_hours,
                "learning_enabled": agent_config.learning_enabled,
                "emotional_intelligence": agent_config.emotional_intelligence
            },
            "business_context": {
                "business_name": business_profile.business_name,
                "industry": business_profile.industry,
                "services_offered": json.loads(business_profile.services_offered or "[]"),
                "target_audience": business_profile.target_audience
            },
            "voice_profile": {
                "id": voice_profile.id if voice_profile else None,
                "profile_name": voice_profile.profile_name if voice_profile else None,
                "voice_type": voice_profile.voice_type if voice_profile else None,
                "gender": voice_profile.gender if voice_profile else None
            },
            "deployment_info": {
                "is_active": agent_config.is_active,
                "deployment_status": agent_config.deployment_status,
                "next_actions": self._get_deployment_actions(agent_config.deployment_status)
            }
        }

        return preview_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent preview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/api/agents/{agent_id}/configure", response_model=Dict[str, Any])
async def update_agent_configuration(
    agent_id: int,
    agent_data: AgentConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update agent configuration"""
    try:
        # Verify agent ownership
        agent_config = db.query(AgentConfiguration).filter(
            and_(AgentConfiguration.id == agent_id, AgentConfiguration.user_id == current_user.id)
        ).first()

        if not agent_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent configuration not found"
            )

        # Update fields
        update_data = agent_data.dict(exclude_unset=True)

        for field, value in update_data.items():
            if isinstance(value, (list, dict)) and field in [
                "personality_traits", "industry_knowledge", "capabilities",
                "languages", "escalation_rules", "integration_settings", "custom_responses"
            ]:
                setattr(agent_config, field, json.dumps(value))
            else:
                setattr(agent_config, field, value)

        db.commit()
        db.refresh(agent_config)

        return {
            "success": True,
            "agent_id": agent_config.id,
            "deployment_status": agent_config.deployment_status,
            "message": "Agent configuration updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api/agents/list", response_model=List[Dict[str, Any]])
async def list_user_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all agents for current user"""
    try:
        agents = db.query(AgentConfiguration).filter(
            AgentConfiguration.user_id == current_user.id
        ).all()

        agent_list = []
        for agent in agents:
            agent_list.append({
                "id": agent.id,
                "name": agent.agent_name,
                "type": agent.agent_type,
                "deployment_status": agent.deployment_status,
                "is_active": agent.is_active,
                "created_at": agent.created_at,
                "business_name": agent.business_profile.business_name,
                "industry": agent.business_profile.industry
            })

        return agent_list

    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api/agents/business-insights/{profile_id}", response_model=Dict[str, Any])
async def get_business_insights(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get AI-generated business insights"""
    try:
        # Verify business profile ownership
        business_profile = db.query(BusinessProfile).filter(
            and_(BusinessProfile.id == profile_id, BusinessProfile.user_id == current_user.id)
        ).first()

        if not business_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business profile not found"
            )

        analyzer = BusinessAnalyzer(db)
        insights = await analyzer.get_business_insights(profile_id)

        return insights

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting business insights: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

def _get_deployment_actions(status: str) -> List[str]:
    """Get recommended actions based on deployment status"""
    actions_map = {
        "draft": ["Complete configuration", "Test agent", "Deploy to production"],
        "testing": ["Run integration tests", "Test conversations", "Monitor performance"],
        "deployed": ["Monitor performance", "Update training data", "Scale if needed"],
        "paused": ["Investigate issues", "Update configuration", "Resume deployment"]
    }
    return actions_map.get(status, ["Complete configuration", "Test and deploy"])