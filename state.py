# Shared state across different cogs
_setup_wizard_state: dict = {}
_verify_wizard_state: dict = {}
_ticket_wizard_state: dict = {}
_selfrole_wizard_state: dict = {}
_status_wizard_state: dict = {}
_joinroles_wizard_state: dict = {}
_embed_gen_state: dict = {}
_wizard_interactions: dict = {}
_wizard_messages: dict = {}
_edit_state: dict = {}
_ticket_edit_state: dict = {}

# Application related
pending_applications: dict = {}
_application_edit_state: dict = {}
_verify_edit_state: dict = {}
_selfrole_edit_state: dict = {}

# Questions per step for applications
QUESTIONS_PER_STEP = 4

QUESTION_SECTIONS = {
    0:  "👤  Personal Information",
    6:  "🏆  Experience",
    8:  "💬  Motivation",
    12: "📅  Activity",
    15: "⚡  Situation Questions",
    20: "📖  Rule Knowledge",
    24: "🔧  Technical",
    27: "✅  Agreement",
}

DEFAULT_APPLICATION_QUESTIONS = []
