""" Session service for managing agent session and state """

from typing import Any, Dict, Optional
from google.adk.sessions import InMemorySessionService
from google.adk.sessions import Session
import logging

logger = logging.getLogger(__name__)

class SessionService:

    def __init__(self):
        """ Initialize the session service with in-memory store"""
        self._session_service = InMemorySessionService()
        logger.info("SessionService initialized with InMemorySessionService")

    def _find_session(self, session_id: str) -> Optional[Session]:
        """Find a session object by id from the underlying in-memory store."""
        for app_sessions in self._session_service.sessions.values():
            for user_sessions in app_sessions.values():
                if session_id in user_sessions:
                    return user_sessions[session_id]
        return None

    async def create_session(
            self,
            app_name:str,
            user_id:str,
            state:Dict[str,Any]
    ) -> Session:
        logger.info(f"Creating new session with app- {app_name}, user- {user_id}")
        session = await self._session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
        )
        logger.info(f"Session created with sessionId : {session.id}")
        return session
    
    async def get_session(
            self,
            session_id:str,
            app_name: Optional[str] = None,
            user_id: Optional[str] = None,
    ) -> Optional[Session]:
        """Retrieve an existing session by ID."""
        logger.info(f"Retrieving session with session-id: {session_id}")
        try:
            if app_name and user_id:
                session = await self._session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
            else:
                session = self._find_session(session_id)

            if session:
                logger.info("Session found")
                return session
            logger.error("Session not found")
            return None
        except Exception as e:
            logger.error(f"Error retrieving session with sessionId: {session_id}: {str(e)}")
            return None

    async def persist_session_state(
            self,
            session: Session,
            metadata: Dict[str, Any],
    ) -> Optional[Session]:
        """Persist session state into the underlying in-memory session store."""
        try:
            storage_session = self._find_session(session.id)
            if storage_session is None:
                logger.info(f"Session {session.id} not found in the in-memory store; creating a fresh session object")
                storage_session = await self._session_service.create_session(
                    app_name=session.app_name,
                    user_id=session.user_id,
                    state=metadata,
                    session_id=session.id,
                )
            else:
                storage_session.state.update(metadata)

            session.state.update(metadata)
            logger.info(f"Persisted session state for session-id {session.id}", )
            return storage_session
        except Exception as e:
            logger.error(f"Error persisting session state for sessionId- {session.id}: {str(e)}")
            return None

    async def update_session(
            self,
            session_id:str,
            metadata:Dict[str, Any],
    ) -> Optional[Session]:
        """Update session with latest metadata in the real in-memory store."""
        logger.info(f"Updating session with session-id: {session_id}")
        try:
            session = self._find_session(session_id)
            if session:
                return await self.persist_session_state(session, metadata)
            logger.error("Session not found")
            return None
        except Exception as e:
            logger.error(f"Error updating session with sessionId- {session_id}: {str(e)}")
            return None
        
# Singleton instance
_session_service_instance: Optional[SessionService] = None


def get_session_service() -> SessionService:
    global _session_service_instance
    if _session_service_instance is None:
        _session_service_instance = SessionService()
    return _session_service_instance