from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Lead:
    id: Optional[int]
    linkedin_url: str
    brand: str
    first_name: str
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    title: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    headline: Optional[str] = None
    about_snippet: Optional[str] = None
    recent_post_1: Optional[str] = None
    recent_post_2: Optional[str] = None
    recent_post_3: Optional[str] = None
    connection_degree: Optional[str] = None
    status: str = "not_contacted"
    source_list: Optional[str] = None
    imported_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    notes: Optional[str] = None
    calendly_booked: int = 0

    @property
    def recent_posts(self) -> list[str]:
        return [p for p in [self.recent_post_1, self.recent_post_2, self.recent_post_3] if p]

    @classmethod
    def from_row(cls, row: tuple) -> "Lead":
        cols = [
            "id", "linkedin_url", "brand", "first_name", "last_name", "full_name",
            "title", "company_name", "industry", "location", "headline",
            "about_snippet", "recent_post_1", "recent_post_2", "recent_post_3",
            "connection_degree", "status", "source_list", "imported_at",
            "last_activity_at", "notes", "calendly_booked",
        ]
        return cls(**dict(zip(cols, row)))


@dataclass
class OutreachLog:
    id: Optional[int]
    lead_id: int
    brand: str
    stage: str
    message_text: str
    sent_at: Optional[datetime] = None
    status: str = "sent"
    error_message: Optional[str] = None

    @classmethod
    def from_row(cls, row: tuple) -> "OutreachLog":
        cols = ["id", "lead_id", "brand", "stage", "message_text", "sent_at", "status", "error_message"]
        return cls(**dict(zip(cols, row)))


@dataclass
class DailyStats:
    id: Optional[int]
    date: str
    brand: str
    connections_sent: int = 0
    messages_sent: int = 0
    replies_received: int = 0
    bookings_detected: int = 0
    session_duration_mins: int = 0
    errors_encountered: int = 0

    @property
    def total_sent(self) -> int:
        return self.connections_sent + self.messages_sent

    @classmethod
    def from_row(cls, row: tuple) -> "DailyStats":
        cols = [
            "id", "date", "brand", "connections_sent", "messages_sent", "replies_received",
            "bookings_detected", "session_duration_mins", "errors_encountered",
        ]
        return cls(**dict(zip(cols, row)))
