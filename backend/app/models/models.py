from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, UniqueConstraint, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.database import Base

# Association table for many-to-many relationship between leads and groups
lead_groups = Table(
    'lead_groups',
    Base.metadata,
    Column('lead_id', Integer, ForeignKey('leads.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)

class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=True, index=True)  # Made nullable for auto-generation
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    industry = Column(String(100))  # New field
    mobile = Column(String(20))  # New field
    country_code = Column(String(10))  # New field
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Lead(Base):
    """Lead model for storing lead information"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)  # Removed global unique constraint
    email = Column(String(255))
    company = Column(String(255))
    title = Column(String(255))
    address = Column(Text)
    notes = Column(Text)
    priority = Column(Integer, default=3)  # 1-5 scale
    status = Column(String(50), default="pending")  # pending, scheduled, calling, called, not_interested
    user_id = Column(Integer, ForeignKey("users.id"))  # Associate leads with users
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="leads")
    calls = relationship("Call", back_populates="lead")
    groups = relationship("Group", secondary=lead_groups, back_populates="leads")
    
    # Composite unique constraint on phone and user_id
    __table_args__ = (
        UniqueConstraint('phone', 'user_id', name='uq_lead_phone_user'),
    )

class Group(Base):
    """Group model for organizing leads"""
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="groups")
    leads = relationship("Lead", secondary=lead_groups, back_populates="groups")
    group_calls = relationship("GroupCall", back_populates="group")

class Call(Base):
    """Call model for storing call records"""
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(255), unique=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    user_id = Column(Integer, ForeignKey("users.id"))  # Associate calls with users
    phone_number = Column(String(20), nullable=False)
    status = Column(String(50), default="initiated")  # initiated, answered, completed, failed
    outcome = Column(String(50))  # meeting_scheduled, answered, no_answer, busy, rejected
    duration = Column(Integer, default=0)  # in seconds
    recording_url = Column(String(500))
    meeting_url = Column(String(500))
    purpose = Column(String(50), default="general")  # feedback, upsell, custom_purpose
    custom_prompt = Column(Text)  # For custom purpose calls
    additional_notes = Column(Text)  # Additional notes for the call
    group_call_id = Column(Integer, ForeignKey("group_calls.id"), nullable=True)  # Link to group call if applicable
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    lead = relationship("Lead", back_populates="calls")
    user = relationship("User", back_populates="calls")
    conversation_messages = relationship("ConversationMessage", back_populates="call")
    group_call = relationship("GroupCall", back_populates="calls")

class GroupCall(Base):
    """Group call model for managing group call queues"""
    __tablename__ = "group_calls"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50), default="queued")  # queued, in_progress, completed, paused
    purpose = Column(String(50), default="general")  # feedback, upsell, custom_purpose
    custom_prompt = Column(Text)  # For custom purpose calls
    additional_notes = Column(Text)  # Additional notes for the group call
    current_lead_index = Column(Integer, default=0)  # Track current position in queue
    total_leads = Column(Integer, default=0)  # Total number of leads in group
    completed_calls = Column(Integer, default=0)  # Number of completed calls
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    group = relationship("Group", back_populates="group_calls")
    user = relationship("User", back_populates="group_calls")
    calls = relationship("Call", back_populates="group_call")

class ConversationMessage(Base):
    """Conversation message model for storing AI conversation history"""
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"))
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    call = relationship("Call", back_populates="conversation_messages")

class SystemStatus(Base):
    """System status model for storing scheduler and queue information"""
    __tablename__ = "system_status"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # Associate status with users
    scheduler_running = Column(Boolean, default=False)
    active_calls = Column(Integer, default=0)
    queue_health = Column(String(50), default="unknown")  # healthy, warning, critical
    overdue_calls = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="system_status")

# Add relationships to User model
User.leads = relationship("Lead", back_populates="user")
User.calls = relationship("Call", back_populates="user")
User.groups = relationship("Group", back_populates="user")
User.group_calls = relationship("GroupCall", back_populates="user")
User.system_status = relationship("SystemStatus", back_populates="user")

# Business Agent Platform Models
class BusinessProfile(Base):
    """Business profile model for comprehensive business understanding"""
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=False)
    business_size = Column(String(50))  # small, medium, large, enterprise
    location = Column(String(255))
    website = Column(String(500))
    phone = Column(String(20))
    business_email = Column(String(255))
    services_offered = Column(Text)  # JSON array of services
    target_audience = Column(Text)  # Description of target customers
    unique_value_proposition = Column(Text)
    business_hours = Column(String(255))
    competitive_advantages = Column(Text)  # JSON array of advantages
    business_goals = Column(Text)  # JSON array of goals
    pain_points_solved = Column(Text)  # JSON array of pain points addressed
    customer_base_size = Column(Integer)
    annual_revenue = Column(String(100))  # Range or actual
    years_in_business = Column(Integer)
    number_of_employees = Column(Integer)
    business_model = Column(String(100))  # B2B, B2C, B2B2C, etc.
    primary_markets = Column(Text)  # JSON array of markets/regions
    technology_stack = Column(Text)  # Current technology used
    social_media_presence = Column(Text)  # JSON array of platforms
    marketing_channels = Column(Text)  # JSON array of channels
    customer_service_approach = Column(Text)
    sales_process = Column(Text)
    compliance_requirements = Column(Text)  # Industry-specific compliance
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="business_profile")
    agents = relationship("AgentConfiguration", back_populates="business_profile")
    question_sessions = relationship("QuestionSession", back_populates="business_profile")

class AgentConfiguration(Base):
    """Agent configuration model for AI assistants"""
    __tablename__ = "agent_configurations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    agent_name = Column(String(255), nullable=False)
    agent_type = Column(String(100), nullable=False)  # secretary, sales, support, general
    personality_traits = Column(Text)  # JSON array of personality traits
    voice_style = Column(String(100))  # professional, friendly, energetic, calm
    communication_style = Column(String(100))  # formal, casual, mixed
    industry_knowledge = Column(Text)  # JSON array of industry-specific knowledge
    capabilities = Column(Text)  # JSON array of agent capabilities
    languages = Column(Text)  # JSON array of supported languages
    working_hours = Column(String(255))
    escalation_rules = Column(Text)  # JSON array of escalation conditions
    integration_settings = Column(Text)  # JSON object for third-party integrations
    custom_responses = Column(Text)  # JSON object for custom response templates
    learning_enabled = Column(Boolean, default=True)
    emotional_intelligence = Column(Boolean, default=True)
    voice_profile_id = Column(Integer, ForeignKey("voice_profiles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    deployment_status = Column(String(50), default="draft")  # draft, testing, deployed, paused
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="agents")
    business_profile = relationship("BusinessProfile", back_populates="agents")
    voice_profile = relationship("VoiceProfile", back_populates="agents")
    conversations = relationship("AgentConversation", back_populates="agent")

class QuestionSession(Base):
    """Question session model for business profiling conversations"""
    __tablename__ = "question_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    session_status = Column(String(50), default="in_progress")  # in_progress, completed, abandoned
    current_question_category = Column(String(100))
    questions_asked = Column(Text)  # JSON array of asked questions
    answers_received = Column(Text)  # JSON object of answers
    confidence_score = Column(Float, default=0.0)  # AI confidence in business understanding
    next_questions = Column(Text)  # JSON array of recommended next questions
    session_metadata = Column(Text)  # JSON object for session metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
    business_profile = relationship("BusinessProfile", back_populates="question_sessions")

class VoiceProfile(Base):
    """Voice profile model for agent voice configurations"""
    __tablename__ = "voice_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    profile_name = Column(String(255), nullable=False)
    voice_type = Column(String(100), nullable=False)  # cloned, celebrity, custom, standard
    gender = Column(String(20))  # male, female, neutral
    age_range = Column(String(50))  # young, adult, mature, senior
    accent = Column(String(100))
    pitch = Column(Float, default=1.0)  # Voice pitch multiplier
    speed = Column(Float, default=1.0)  # Speech speed multiplier
    volume = Column(Float, default=1.0)  # Volume multiplier
    emotion_range = Column(Text)  # JSON array of supported emotions
    language = Column(String(10), default="en-US")
    sample_audio_url = Column(String(500))
    voice_model_path = Column(String(500))
    is_celebrity = Column(Boolean, default=False)
    celebrity_name = Column(String(255))
    license_info = Column(Text)  # JSON object for licensing details
    usage_count = Column(Integer, default=0)
    quality_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="voice_profiles")
    agents = relationship("AgentConfiguration", back_populates="voice_profile")

class AgentConversation(Base):
    """Agent conversation model for tracking AI agent interactions"""
    __tablename__ = "agent_conversations"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agent_configurations.id"), nullable=False)
    customer_id = Column(String(255))  # Customer identifier (phone, email, etc.)
    conversation_type = Column(String(100))  # phone, chat, email, in-person
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    sentiment_analysis = Column(Text)  # JSON object of sentiment data
    customer_satisfaction_score = Column(Integer)  # 1-5 rating
    resolution_status = Column(String(50))  # resolved, escalated, follow_up_needed
    topics_discussed = Column(Text)  # JSON array of topics
    emotional_journey = Column(Text)  # JSON array of emotional states
    learning_insights = Column(Text)  # JSON object of AI learning data
    conversation_summary = Column(Text)
    action_items = Column(Text)  # JSON array of action items
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    agent = relationship("AgentConfiguration", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="agent_conversation")

class CompetitiveAnalysis(Base):
    """Competitive analysis model for market intelligence"""
    __tablename__ = "competitive_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    competitor_name = Column(String(255), nullable=False)
    competitor_website = Column(String(500))
    competitor_size = Column(String(100))
    competitor_revenue = Column(String(100))
    market_position = Column(String(100))
    strengths = Column(Text)  # JSON array of identified strengths
    weaknesses = Column(Text)  # JSON array of identified weaknesses
    opportunities = Column(Text)  # JSON array of opportunities
    threats = Column(Text)  # JSON array of threats
    feature_comparison = Column(Text)  # JSON object comparing features
    pricing_analysis = Column(Text)  # JSON object of pricing comparison
    customer_reviews_analysis = Column(Text)  # JSON object of review analysis
    market_share_estimate = Column(Float)
    growth_trend = Column(String(50))  # growing, stable, declining
    technological_advantages = Column(Text)  # JSON array of tech advantages
    gap_analysis = Column(Text)  # JSON array of feature gaps
    recommended_actions = Column(Text)  # JSON array of recommendations
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    business_profile = relationship("BusinessProfile")

# Add new relationships to User model
User.business_profile = relationship("BusinessProfile", back_populates="user", uselist=False)
User.agents = relationship("AgentConfiguration", back_populates="user")
User.voice_profiles = relationship("VoiceProfile", back_populates="user")

# Update ConversationMessage to support agent conversations
ConversationMessage.agent_conversation_id = Column(Integer, ForeignKey("agent_conversations.id"), nullable=True)
ConversationMessage.agent_conversation = relationship("AgentConversation", back_populates="messages") 