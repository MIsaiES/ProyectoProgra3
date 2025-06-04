import json
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import os

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


@dataclass
class AgentMessage:
    """Standard message format for agent-to-agent communication"""
    agent_id: str
    message_type: str
    timestamp: str
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

@dataclass
class EmailRequest:
    """Email request payload structure"""
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[str]] = None
    html_body: Optional[str] = None

@dataclass
class EmailResponse:
    """Email response payload structure"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class GmailAgent:
    """Gmail Agent implementing Google's Agent2Agent protocol"""
    
    def __init__(self, agent_id: str, credentials_file: str = 'credentials.json'):
        self.agent_id = agent_id
        self.credentials_file = credentials_file
        self.token_file = 'token.json'
        self.scopes = ['https://www.googleapis.com/auth/gmail.send']
        self.service = None
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the agent"""
        logger = logging.getLogger(f'GmailAgent-{self.agent_id}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def authenticate(self) -> bool:
        """Authenticate with Gmail API using OAuth2"""
        try:
            creds = None
            
            
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes
                    )
                    creds = flow.run_local_server(port=0)
                
                
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            
            self.service = build('gmail', 'v1', credentials=creds)
            self.logger.info(f"Agent {self.agent_id} authenticated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def create_message(self, email_req: EmailRequest) -> Optional[Dict[str, Any]]:
        """Create email message in Gmail API format"""
        try:
            
            if email_req.html_body:
                message = MIMEMultipart('alternative')
                text_part = MIMEText(email_req.body, 'plain')
                html_part = MIMEText(email_req.html_body, 'html')
                message.attach(text_part)
                message.attach(html_part)
            else:
                message = MIMEText(email_req.body)
            
           
            message['to'] = ', '.join(email_req.to)
            message['subject'] = email_req.subject
            
            if email_req.cc:
                message['cc'] = ', '.join(email_req.cc)
            
            if email_req.bcc:
                message['bcc'] = ', '.join(email_req.bcc)
            
            
            if email_req.attachments:
                if not isinstance(message, MIMEMultipart):                  
                    old_message = message
                    message = MIMEMultipart()
                    message.attach(old_message)
                
                for attachment_path in email_req.attachments:
                    if os.path.exists(attachment_path):
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {os.path.basename(attachment_path)}'
                        )
                        message.attach(part)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            return {'raw': raw_message}
            
        except Exception as e:
            self.logger.error(f"Failed to create message: {str(e)}")
            return None
    
    def send_email(self, email_req: EmailRequest) -> EmailResponse:
        """Send email using Gmail API"""
        try:
            if not self.service:
                if not self.authenticate():
                    return EmailResponse(
                        success=False,
                        error="Authentication failed"
                    )
            
            message = self.create_message(email_req)
            if not message:
                return EmailResponse(
                    success=False,
                    error="Failed to create email message"
                )
            

            result = self.service.users().messages().send(
                userId='me',
                body=message
            ).execute()
            
            self.logger.info(f"Email sent successfully. Message ID: {result['id']}")
            
            return EmailResponse(
                success=True,
                message_id=result['id'],
                details={'thread_id': result.get('threadId')}
            )
            
        except HttpError as e:
            error_msg = f"Gmail API error: {str(e)}"
            self.logger.error(error_msg)
            return EmailResponse(success=False, error=error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            return EmailResponse(success=False, error=error_msg)
    
    def process_agent_message(self, message: AgentMessage) -> AgentMessage:
        """Process incoming agent message according to Agent2Agent protocol"""
        self.logger.info(f"Processing message from {message.agent_id}: {message.message_type}")
        
        response_payload = {}
        
        try:
            if message.message_type == "email_send_request":
                # Parse email request
                email_req = EmailRequest(**message.payload)
                
                # Send email
                email_response = self.send_email(email_req)
                response_payload = asdict(email_response)
                
                response_type = "email_send_response"
                
            elif message.message_type == "health_check":
                response_payload = {
                    "status": "healthy",
                    "agent_id": self.agent_id,
                    "authenticated": self.service is not None
                }
                response_type = "health_check_response"
                
            elif message.message_type == "capability_inquiry":
                response_payload = {
                    "capabilities": [
                        "email_send",
                        "html_email",
                        "attachments",
                        "cc_bcc_support"
                    ],
                    "agent_type": "gmail_agent",
                    "version": "1.0"
                }
                response_type = "capability_response"
                
            else:
                response_payload = {
                    "error": f"Unknown message type: {message.message_type}"
                }
                response_type = "error_response"
                
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            response_payload = {
                "error": f"Processing error: {str(e)}"
            }
            response_type = "error_response"
        
        # Create response message
        response = AgentMessage(
            agent_id=self.agent_id,
            message_type=response_type,
            timestamp=datetime.utcnow().isoformat(),
            payload=response_payload,
            correlation_id=message.correlation_id,
            reply_to=message.agent_id
        )
        
        return response
    
    def handle_message_json(self, message_json: str) -> str:
        """Handle JSON message string and return JSON response"""
        try:
            # Parse incoming message
            message_data = json.loads(message_json)
            message = AgentMessage(**message_data)
            
            # Process message
            response = self.process_agent_message(message)
            
            # Return JSON response
            return json.dumps(asdict(response), indent=2)
            
        except json.JSONDecodeError as e:
            error_response = AgentMessage(
                agent_id=self.agent_id,
                message_type="error_response",
                timestamp=datetime.utcnow().isoformat(),
                payload={"error": f"Invalid JSON: {str(e)}"}
            )
            return json.dumps(asdict(error_response), indent=2)
        
        except Exception as e:
            error_response = AgentMessage(
                agent_id=self.agent_id,
                message_type="error_response",
                timestamp=datetime.utcnow().isoformat(),
                payload={"error": f"Message handling error: {str(e)}"}
            )
            return json.dumps(asdict(error_response), indent=2)

def main():
    """Example usage of the Gmail Agent"""
    
    # Initialize agent
    agent = GmailAgent("gmail-agent-001")
    
    
    if not agent.authenticate():
        print("Failed to authenticate. Please check your credentials.")
        return
    

    email_request = EmailRequest(
        to=["*******"],
        subject="Test Email from Gmail Agent",
        body="This is a test email sent using the Gmail Agent with Agent2Agent protocol.",
        cc=["*******"]
    )
    
    
    agent_message = AgentMessage(
        agent_id="client-agent-001",
        message_type="email_send_request",
        timestamp=datetime.utcnow().isoformat(),
        payload=asdict(email_request),
        correlation_id="test-001"
    )
    
    # Process message
    response = agent.process_agent_message(agent_message)
    print("Agent Response:")
    print(json.dumps(asdict(response), indent=2))
    
    # Test health check
    health_check = AgentMessage(
        agent_id="client-agent-001",
        message_type="health_check",
        timestamp=datetime.utcnow().isoformat(),
        payload={}
    )
    
    health_response = agent.process_agent_message(health_check)
    print("\nHealth Check Response:")
    print(json.dumps(asdict(health_response), indent=2))

if __name__ == "__main__":
    main()