import os
import json
import asyncio
import decisionrules
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ChatMessageHistory

# Load env vars
load_dotenv()

# API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DECISIONRULES_API_KEY = os.getenv("DECISIONRULES_API_KEY")
DECISIONRULES_MODEL_ID = "d0ec0e76-8ccb-9b87-4e9c-7672cee0d427"  # Your model ID

# Setup Groq LLM with supported model
llm = ChatGroq(
    model_name="llama3-70b-8192",
    groq_api_key=GROQ_API_KEY
)

class LegalChatbot:
    def __init__(self):
        self.payload_data = {
            "isTenant?": None,
            "isSecurity": None,
            "inStateDefendant?": None,
            "ClaimAmount": None
        }
        self.required_fields = ["isTenant?", "isSecurity", "inStateDefendant?", "ClaimAmount"]
        self.current_question = 0
        self.is_tenant_security_case = False
        self.case_identified = False
        self.retry_count = {}  # Track retry attempts for each field
        self.started = False  # Track if conversation has started
        
        # Questions to ask for each field with better context
        self.questions = {
            "isTenant?": "First, I need to confirm: Are you a tenant (renter) in this situation? Please answer 'Yes' or 'No'.",
            "isSecurity": "Did you pay a security deposit when you moved into this rental property? Please answer 'Yes' or 'No'.",
            "inStateDefendant?": "Is the landlord or property owner located in the same state as you? Please answer 'Yes' or 'No'.",
            "ClaimAmount": "What is the total dollar amount you want to claim? Please provide a specific number (for example: 1500 or $2,000)."
        }
        
        # Setup Prompt with specific instructions
        self.case_detection_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a legal assistant for small claims court. Your job is to identify if the user's query is related to tenant security deposit issues.

Look for these specific keywords and phrases that indicate tenant security deposit cases:
- "security deposit", "deposit", "rental deposit"
- "landlord won't return", "landlord keeping", "get my deposit back"
- "tenant", "renter", "lease", "rental", "apartment"
- "move out", "end of lease", "withheld deposit"
- "damage charges", "cleaning fees", "deposit deduction"
- Combined mentions of rental/tenant AND money/deposit issues

ONLY respond with "TENANT_SECURITY_CASE" if the query clearly mentions:
- Being a tenant/renter AND having deposit issues, OR
- Specific mention of security deposit problems, OR
- Landlord not returning money/deposits

For all other legal questions (divorce, business, contracts, criminal law, etc.), provide helpful general legal advice.

Be very specific - only identify tenant security deposit cases, not general landlord-tenant issues."""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

        self.data_collection_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a legal assistant collecting specific information for a small claims case.

Current payload data: {payload_data}
Current question field: {current_field}

Your job is to analyze the user's response and determine their intent/sentiment to extract the correct Yes/No answer.

For each field, analyze what the user REALLY means:

isTenant?: Determine if they are actually a tenant/renter
- Look for: "I rent", "I'm a tenant", "my landlord", "lease agreement"
- Respond "YES_INTENT" if they indicate they rent/lease property
- Respond "NO_INTENT" if they indicate they own the property
- Respond "UNCLEAR_INTENT" if you cannot determine their status

isSecurity: Determine if they actually paid a security deposit
- Look for: "I paid deposit", "gave security deposit", "deposit was required"
- Respond "YES_INTENT" if they clearly paid a deposit
- Respond "NO_INTENT" if they clearly didn't pay a deposit  
- Respond "UNCLEAR_INTENT" if you cannot determine

inStateDefendant?: Determine if landlord is in same state
- Look for: "same state", "different state", state names, "local landlord"
- Respond "YES_INTENT" if clearly same state
- Respond "NO_INTENT" if clearly different states
- Respond "UNCLEAR_INTENT" if you cannot determine

Only respond with one of: YES_INTENT, NO_INTENT, or UNCLEAR_INTENT
Do not provide explanations, just the intent classification."""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "Question field: {current_field}\nUser response: {input}")
        ])

        self.general_legal_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful legal assistant for general legal questions. Provide helpful, informative responses about legal matters, but remind users that this is not legal advice and they should consult with a qualified attorney for specific legal guidance.

Be professional, knowledgeable, and helpful."""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Chain = Prompt -> LLM
        self.case_detection_chain = self.case_detection_prompt | llm
        self.data_collection_chain = self.data_collection_prompt | llm
        self.general_legal_chain = self.general_legal_prompt | llm
        
        # Setup RunnableWithMessageHistory
        self.case_detection_history = RunnableWithMessageHistory(
            self.case_detection_chain,
            lambda session_id: ChatMessageHistory(),
            input_messages_key="input",
            history_messages_key="history"
        )
        
        self.data_collection_history = RunnableWithMessageHistory(
            self.data_collection_chain,
            lambda session_id: ChatMessageHistory(),
            input_messages_key="input",
            history_messages_key="history"
        )
        
        self.general_legal_history = RunnableWithMessageHistory(
            self.general_legal_chain,
            lambda session_id: ChatMessageHistory(),
            input_messages_key="input",
            history_messages_key="history"
        )
    
    def detect_tenant_security_case(self, user_input, session_id):
        """Detect if user query is about tenant security issues"""
        # First check for obvious keywords
        input_lower = user_input.lower()
        tenant_keywords = ['tenant', 'renter', 'lease', 'rental', 'apartment', 'landlord']
        deposit_keywords = ['deposit', 'security deposit', 'money back', 'return', 'refund', 'withheld', 'keeping']
        
        has_tenant_context = any(keyword in input_lower for keyword in tenant_keywords)
        has_deposit_context = any(keyword in input_lower for keyword in deposit_keywords)
        
        # If clear keywords match, it's likely a tenant case
        if has_tenant_context and has_deposit_context:
            return True, "TENANT_SECURITY_CASE detected based on keywords"
        
        # Otherwise use LLM for more nuanced detection
        response = self.case_detection_history.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": f"{session_id}_detection"}}
        )
        return "TENANT_SECURITY_CASE" in response.content, response.content
    
    def reset_payload_data(self):
        """Reset payload data for new case"""
        self.payload_data = {
            "isTenant?": None,
            "isSecurity": None,
            "inStateDefendant?": None,
            "ClaimAmount": None
        }
        self.is_tenant_security_case = False
        self.case_identified = False
        self.retry_count = {}
        self.started = False
    
    def analyze_response_intent(self, user_input, current_field, session_id):
        """Use LLM to analyze user response intent for Yes/No questions"""
        if current_field not in ["isTenant?", "isSecurity", "inStateDefendant?"]:
            return None
            
        response = self.data_collection_history.invoke(
            {
                "input": user_input,
                "current_field": current_field,
                "payload_data": str(self.payload_data)
            },
            config={"configurable": {"session_id": f"{session_id}_analysis"}}
        )
        
        content = response.content.strip().upper()
        if "YES_INTENT" in content:
            return "Yes"
        elif "NO_INTENT" in content:
            return "No"
        else:
            return None  # UNCLEAR_INTENT
    
    def extract_yes_no(self, response_text):
        """Extract Yes/No from response - only return value if clearly stated"""
        response_lower = response_text.lower().strip()
        
        # Only look for very explicit yes/no words
        explicit_yes = ['yes', 'y']
        explicit_no = ['no', 'n']
        
        # Check for explicit yes (exact word match)
        words = response_lower.split()
        if any(word in explicit_yes for word in words):
            return "Yes"
        
        # Check for explicit no (exact word match)
        if any(word in explicit_no for word in words):
            return "No"
        
        # If not explicitly clear, return None
        return None
    
    def extract_amount(self, response_text):
        """Extract numerical amount from response"""
        import re
        
        # Remove common currency symbols and clean the text
        cleaned_text = response_text.replace('$', '').replace(',', '').replace('USD', '').replace('dollars', '')
        
        # Look for numbers (including decimals)
        numbers = re.findall(r'\b\d+\.?\d*\b', cleaned_text)
        
        if numbers:
            try:
                # Take the first number found
                amount = float(numbers[0])
                return int(amount) if amount.is_integer() else amount
            except (ValueError, TypeError):
                return None
        return None
    
    def is_payload_complete(self):
        """Check if all required fields are filled"""
        return all(self.payload_data[field] is not None for field in self.required_fields)
    
    def get_next_question(self):
        """Get the next question to ask"""
        for field in self.required_fields:
            if self.payload_data[field] is None:
                return field, self.questions[field]
        return None, None
    
    def process_response(self, user_input, current_field, session_id):
        """Process user response and extract relevant information"""
        if current_field in ["isTenant?", "isSecurity", "inStateDefendant?"]:
            # First try explicit Yes/No extraction
            explicit_value = self.extract_yes_no(user_input)
            if explicit_value:
                self.payload_data[current_field] = explicit_value
                return True, f"Perfect! I've recorded '{explicit_value}' for {current_field}."
            
            # If not explicit, use LLM to analyze intent
            intent_value = self.analyze_response_intent(user_input, current_field, session_id)
            if intent_value:
                self.payload_data[current_field] = intent_value
                return True, f"Based on your response, I've recorded '{intent_value}' for {current_field}."
            
            # If still unclear, return False for clarification
            return False, None
        
        elif current_field == "ClaimAmount":
            extracted_value = self.extract_amount(user_input)
            if extracted_value is not None and extracted_value > 0:
                self.payload_data[current_field] = extracted_value
                return True, f"Perfect! I've recorded ${extracted_value} as the claim amount."
            else:
                # Return False so we can ask for clarification
                return False, None
        
        return False, None
    
    def get_clarification_message(self, current_field, _user_input=None):
        """Generate appropriate clarification message based on field and user input"""
        # Track retry attempts
        if current_field not in self.retry_count:
            self.retry_count[current_field] = 0
        self.retry_count[current_field] += 1
        
        if current_field == "isTenant?":
            if self.retry_count[current_field] == 1:
                return "I need a clear and proper answer. Are you currently a tenant (renter) in this situation? Please respond with either 'Yes' or 'No' only. If you explain your situation, I can understand it, but I need a definitive yes or no answer."
            else:
                return "Let me rephrase: Do you rent this property from a landlord? Please answer only 'Yes' if you rent/lease the property, or 'No' if you own the property. I need this exact format to proceed."
        
        elif current_field == "isSecurity":
            if self.retry_count[current_field] == 1:
                return "I need a clear and proper answer. Did you pay a security deposit when you moved in? Please respond with either 'Yes' or 'No' only. You can explain the details, but I need a definitive yes or no answer."
            else:
                return "To clarify: When you first moved into this rental, did you pay any money upfront as a 'security deposit' or 'damage deposit'? Please answer only 'Yes' if you paid a deposit, or 'No' if you didn't. I need this exact format."
        
        elif current_field == "inStateDefendant?":
            if self.retry_count[current_field] == 1:
                return "I need a clear and proper answer. Is the defendant (landlord/property owner) located in the same state as you? Please respond with either 'Yes' or 'No' only. You can provide details, but I need a definitive yes or no answer."
            else:
                return "To clarify: Do you and your landlord both live in the same U.S. state? Please answer only 'Yes' if same state, or 'No' if different states. I need this exact format to proceed."
        
        elif current_field == "ClaimAmount":
            if self.retry_count[current_field] == 1:
                return "I need a specific dollar amount for your claim. Please provide the amount as a number (for example: 1500 or $1,500). Give me a proper numerical value."
            else:
                return "Please provide only the dollar amount you want to claim as a number. For example, if you want $2,000 back, just type '2000' or '$2000'. I need a proper numerical value."
        
        return "I didn't understand your response. Please provide a proper answer in the format I requested."
    
    def get_final_payload(self):
        """Generate final payload in required format"""
        return {
            "input": self.payload_data
        }
    
    async def call_decision_api(self, payload):
        """Call DecisionRules API with the completed payload"""
        try:
            # Initialize solver with API key
            solver = decisionrules.SolverApi(DECISIONRULES_API_KEY)
            
            # FIXED: Properly await the API call
            response = await solver.solve(
                decisionrules.SolverType.RULE,
                DECISIONRULES_MODEL_ID,
                payload,
                "STANDARD",
                1
            )
            print("+++++++++++++", response)
            
            return True, response
            
        except Exception as e:
            error_msg = f"API Error: {str(e)}"
            print(f"DecisionRules API Error: {error_msg}")
            return False, error_msg
    
    def format_api_response(self, api_response):
        """Format the API response for user display"""
        try:
            # Parse string if necessary
            if isinstance(api_response, str):
                try:
                    response_data = json.loads(api_response)
                except json.JSONDecodeError:
                    response_data = api_response
            else:
                response_data = api_response

            formatted_response = ""

            if isinstance(response_data, list) and len(response_data) > 0:
                output = response_data[0].get("output", {})

                # Beautify routeTo field
                route = output.get("routeTo", "")
                if route == "Superior Court":
                    route_line = "📍 **Routed to: Superior Court**"
                elif route == "Small Claims Court":
                    route_line = "📍 **Routed to: Small Claims Court**"
                elif route == "Not Applicable":
                    route_line = "❌ **Not applicable for filing in court**"
                else:
                    route_line = f"📍 **Route:** {route}"

                # Beautify document list
                docs = output.get("documentList", "NA")
                if docs == "NA":
                    docs_line = "📂 No documents required."
                elif isinstance(docs, list):
                    docs_line = "📄 **Documents Needed:**\n" + "\n".join([f"- {doc}" for doc in docs])
                else:
                    docs_line = f"📄 Documents: {docs}"

                formatted_response += f"{route_line}\n\n{docs_line}"
            else:
                # Fallback to raw JSON
                formatted_response += f"```json\n{json.dumps(response_data, indent=2)}\n```"

            formatted_response += "\n\n💡 *This is an automated legal analysis. Always consult a qualified attorney for advice.*"
            return formatted_response

        except Exception as e:
            return f"⚠️ Error formatting response: {str(e)}\n\nRaw response: {api_response}"

    
    async def chat(self, user_input, session_id="default"):
        """Main chat function - NOW ASYNC"""
        # If this is the first interaction or user wants to start over
        if user_input.lower() in ["start", "new case", "reset"]:
            self.reset_payload_data()
            return "Hello! I'm your legal assistant. How can I help you today? I can assist with general legal questions or help you gather information for tenant security deposit cases."

        # If we're currently in a tenant security case, continue with data collection
        if self.is_tenant_security_case and not self.is_payload_complete():
            return await self.handle_tenant_security_case(user_input, session_id)

        # If we haven't identified the case type yet OR if we're done with current case
        if not self.case_identified or (self.is_tenant_security_case and self.is_payload_complete()):
            is_tenant_case, detection_response = self.detect_tenant_security_case(user_input, session_id)

            if is_tenant_case:
                # Reset and start new tenant case
                if self.is_payload_complete():
                    self.reset_payload_data()

                self.is_tenant_security_case = True
                self.case_identified = True

                # ✨ NEW LOGIC HERE: if user message contains personal pronouns, assume isTenant? = Yes
                lower_input = user_input.lower()
                if any(p in lower_input for p in [" i ", " me ", " my ", "i'", "i'm", "i am", "i'm", "i've", "i pay", "i rent", "i live"]):
                    self.payload_data["isTenant?"] = "Yes"
                    next_field, next_question = self.get_next_question()
                    return f"I understand you have a tenant security deposit issue. I've marked you as a tenant based on your message.\n\n{next_question}"
                else:
                    # Start regular data collection
                    first_field, first_question = self.get_next_question()
                    return f"I understand you have a tenant security deposit issue. I'll help you gather the necessary information for your case.\n\n{first_question}"
            else:
                # Set as general legal case but don't reset if we just completed a tenant case
                if not self.is_payload_complete():
                    self.case_identified = True
                return detection_response

        # If it's a tenant security case, proceed with data collection
        if self.is_tenant_security_case:
            return await self.handle_tenant_security_case(user_input, session_id)

        # Otherwise, handle as general legal chatbot
        else:
            response = self.general_legal_history.invoke(
                {"input": user_input},
                config={"configurable": {"session_id": f"{session_id}_general"}}
            )
            return response.content

    
    async def handle_tenant_security_case(self, user_input, session_id):
        """Handle tenant security case data collection - NOW ASYNC"""
        # Check if we have a pending question
        current_field, current_question = self.get_next_question()
        
        if current_field:
            # Try to process the user's response for the current field
            success, confirmation = self.process_response(user_input, current_field, session_id)
            
            if success:
                response_text = confirmation
                
                # Check if payload is complete
                if self.is_payload_complete():
                    payload = self.get_final_payload()
                    # response_text += f"\n\n✅ Excellent! I have all the information needed for your tenant security deposit case.\n\nFinal Payload:\n```json\n{json.dumps(payload, indent=2)}\n```"
                    
                    # Call the Decision API
                    # response_text += "\n\n🔄 Analyzing your case with our legal decision engine...\n"
                    
                    try:
                        # FIXED: Now properly await the async API call
                        api_success, api_response = await self.call_decision_api(payload)
                        
                        if api_success:
                            formatted_response = self.format_api_response(api_response)
                            response_text += f"\n{formatted_response}"
                        else:
                            response_text += f"\n❌ **API Error:** {api_response}"
                            response_text += "\n\nI've collected all your information, but there was an issue connecting to the legal analysis service. Please try again later."
                            
                    except Exception as e:
                        response_text += f"\n❌ **Error:** Unable to analyze your case: {str(e)}"
                        response_text += "\n\nI've collected all your information, but the analysis service is currently unavailable."
                    
                    # response_text += "\n\nYou can now type 'new case' to start over or ask me other legal questions."
                else:
                    # Ask next question
                    next_field, next_question = self.get_next_question()
                    if next_question:
                        response_text += f"\n\n{next_question}"
                
                return response_text
            else:
                # Response wasn't clear, ask for clarification directly
                clarification = self.get_clarification_message(current_field, user_input)
                return clarification
        
        else:
            # All data collected, handle general questions about the case
            response = self.general_legal_history.invoke(
                {"input": user_input},
                config={"configurable": {"session_id": f"{session_id}_general"}}
            )
            return response.content

# FIXED: Updated main function to handle async
async def main():
    chatbot = LegalChatbot()
    
    print("👩‍⚖️ Improved Legal Assistant Chatbot (LangChain + Groq)")
    print("I can help with general legal questions and gather information for tenant security deposit cases.")
    print("For tenant issues, I'll ask specific questions to build a structured case file.")
    print("Type 'exit' or 'quit' to end the conversation.")
    print("Type 'new case' to start a new tenant security case.")
    print("Type 'test' to see example interactions.\n")
    
    session_id = "legal_session"
    
    while True:
        if not chatbot.started:
            response = await chatbot.chat('start', session_id)
            print(f"Bot: {response}")
            chatbot.started = True
        
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        elif user_input.lower() == "test":
            print("\n=== Example Test Cases ===")
            print("Try these inputs to see how the bot works:")
            print("• 'My landlord won't return my security deposit'")
            print("• 'How do I start a small business?'")
            print("• 'I need help with a rental deposit issue'")
            continue
        
        response = await chatbot.chat(user_input, session_id)
        print(f"Bot: {response}")
        
        # Check if payload is complete for tenant cases
        if chatbot.is_tenant_security_case and chatbot.is_payload_complete():
            print("\n🎉 Tenant security case information gathering complete!")
            print("You can ask other questions or type 'new case' to start another case.")

if __name__ == "__main__":
    # FIXED: Run the async main function
    asyncio.run(main())