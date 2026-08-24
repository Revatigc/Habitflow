from datetime import date, datetime
from sqlalchemy import String, ForeignKey, Date, DateTime, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base
class User(Base):
    __tablename__="users"; id:Mapped[str]=mapped_column(String,primary_key=True); email:Mapped[str]=mapped_column(String,index=True); name:Mapped[str]=mapped_column(String); timezone:Mapped[str]=mapped_column(String,default="UTC")
class Habit(Base):
    __tablename__="habits"; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); title:Mapped[str]=mapped_column(String(120)); category:Mapped[str]=mapped_column(String(40),default="General"); frequency:Mapped[str]=mapped_column(String(20),default="daily"); target:Mapped[int]=mapped_column(Integer,default=1); archived:Mapped[bool]=mapped_column(Boolean,default=False)
class HabitLog(Base):
    __tablename__="habit_logs"; __table_args__=(UniqueConstraint("habit_id","completed_on"),); id:Mapped[int]=mapped_column(primary_key=True); habit_id:Mapped[int]=mapped_column(ForeignKey("habits.id"),index=True); completed_on:Mapped[date]=mapped_column(Date,default=date.today)
class Task(Base):
    __tablename__="tasks"; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); title:Mapped[str]=mapped_column(String(180)); description:Mapped[str|None]=mapped_column(String,nullable=True); priority:Mapped[str]=mapped_column(String(12),default="medium"); status:Mapped[str]=mapped_column(String(16),default="todo"); due_date:Mapped[date|None]=mapped_column(Date,nullable=True)
class FocusSession(Base):
    __tablename__="focus_sessions"; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); minutes:Mapped[int]=mapped_column(Integer); completed_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
